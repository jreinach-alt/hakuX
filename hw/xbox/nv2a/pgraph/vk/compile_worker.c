/*
 * Geforce NV2A PGRAPH Vulkan Renderer - Async Compile Worker
 *
 * Copyright (c) 2024-2025 Matt Borgerson
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#include "renderer.h"
#include "qemu/fast-hash.h"
#include "qemu/mstring.h"
#include "system/runstate.h"
#include "ui/xemu-settings.h"

/*
 * #569 P1: every graphics pipeline create goes through here. It times the
 * call and, on a Vulkan 1.3 device, chains VkPipelineCreationFeedback so the
 * driver says how long the whole pipeline and each stage took, and whether
 * it found them in the pipeline cache. For draw pipelines it also asks
 * whether a stage's VkShaderModule was used by an earlier pipeline: a stage
 * that was, and still misses, is one the driver compiled again for a new
 * partner or state (what VK_EXT_graphics_pipeline_library would save).
 *
 * Module handles are remembered by value and never forgotten, so a module
 * freed and a new one given the same handle reads as reused. Shader modules
 * are evicted rarely enough that this is noise, not a bias to design around.
 */
VkResult pgraph_vk_create_graphics_pipeline_fb(
    PGRAPHVkState *r, const VkGraphicsPipelineCreateInfo *info, bool draw,
    VkPipeline *pipeline);

static GMutex pcfb_lock;
static GHashTable *pcfb_modules;
/* #569 P3: set around a pre-build create, which is not a draw-path stall;
 * the calling thread's last draw-path create time, for the [pb569] rec line */
static __thread bool pcfb_quiet;
static __thread int64_t pcfb_last_us;

static int pcfb_stage_index(VkShaderStageFlagBits stage)
{
    switch (stage) {
    case VK_SHADER_STAGE_VERTEX_BIT:
        return 0;
    case VK_SHADER_STAGE_GEOMETRY_BIT:
        return 1;
    case VK_SHADER_STAGE_FRAGMENT_BIT:
        return 2;
    default:
        return -1;
    }
}

VkResult pgraph_vk_create_graphics_pipeline_fb(
    PGRAPHVkState *r, const VkGraphicsPipelineCreateInfo *info, bool draw,
    VkPipeline *pipeline)
{
    if (pcfb_quiet) {
        return vkCreateGraphicsPipelines(r->device, r->vk_pipeline_cache, 1,
                                         info, NULL, pipeline);
    }

    VkPipelineCreationFeedback pipeline_fb = { 0 };
    VkPipelineCreationFeedback stage_fb[3] = { { 0 } };
    VkPipelineCreationFeedbackCreateInfo fb_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_CREATION_FEEDBACK_CREATE_INFO,
        .pNext = info->pNext,
        .pPipelineCreationFeedback = &pipeline_fb,
        .pipelineStageCreationFeedbackCount = info->stageCount,
        .pPipelineStageCreationFeedbacks = stage_fb,
    };
    VkGraphicsPipelineCreateInfo chained = *info;
    bool want_fb = r->device_props.apiVersion >= VK_API_VERSION_1_3 &&
                   info->stageCount <= ARRAY_SIZE(stage_fb);
    if (want_fb) {
        chained.pNext = &fb_info;
    }

    int64_t t0 = nv2a_clock_ns();
    VkResult result = vkCreateGraphicsPipelines(r->device, r->vk_pipeline_cache,
                                                1, &chained, NULL, pipeline);
    int64_t t1 = nv2a_clock_ns();

    pcfb_last_us = (t1 - t0) / 1000;
    g_mutex_lock(&pcfb_lock);
    ShaderPipelineStats *s = &g_nv2a_stats.shader_stats;
    s->pipeline_create_us += (t1 - t0) / 1000;
    s->pipeline_creates++;
    if (want_fb &&
        (pipeline_fb.flags & VK_PIPELINE_CREATION_FEEDBACK_VALID_BIT)) {
        s->pipeline_fb_valid++;
        s->pipeline_fb_us += pipeline_fb.duration / 1000;
        if (pipeline_fb.flags &
            VK_PIPELINE_CREATION_FEEDBACK_APPLICATION_PIPELINE_CACHE_HIT_BIT) {
            s->pipeline_fb_hit++;
        }
        if (!pcfb_modules) {
            pcfb_modules = g_hash_table_new_full(g_int64_hash, g_int64_equal,
                                                 g_free, NULL);
        }
        for (uint32_t i = 0; i < info->stageCount; i++) {
            int idx = pcfb_stage_index(info->pStages[i].stage);
            if (idx < 0 ||
                !(stage_fb[i].flags & VK_PIPELINE_CREATION_FEEDBACK_VALID_BIT)) {
                continue;
            }
            s->stage_fb_us[idx] += stage_fb[i].duration / 1000;
            if (!draw) {
                continue;
            }
            bool miss = !(stage_fb[i].flags &
                          VK_PIPELINE_CREATION_FEEDBACK_APPLICATION_PIPELINE_CACHE_HIT_BIT);
            gint64 handle = (gint64)(uint64_t)info->pStages[i].module;
            if (g_hash_table_contains(pcfb_modules, &handle)) {
                s->stage_reused++;
                s->stage_reused_miss += miss;
                s->stage_reused_us += stage_fb[i].duration / 1000;
            } else {
                s->stage_new++;
                s->stage_new_miss += miss;
                s->stage_new_us += stage_fb[i].duration / 1000;
                g_hash_table_add(pcfb_modules, g_memdup2(&handle, sizeof(handle)));
            }
        }
    }
    s->instr_ns += nv2a_clock_ns() - t1;
    g_mutex_unlock(&pcfb_lock);

    return result;
}

#if OPT_ASYNC_COMPILE

extern bool xemu_get_async_compile(void);
extern void shader_module_key_persist(const ShaderModuleCacheKey *key);

static void process_shader_module_job(PGRAPHVkState *r, CompileJob *job)
{
    ShaderModuleCacheEntry *target = job->shader_module.target;
    ShaderModuleCacheKey *key = &job->shader_module.key;
    MString *code;

    switch (key->kind) {
    case VK_SHADER_STAGE_VERTEX_BIT:
        code = pgraph_glsl_gen_vsh(&key->vsh.state, key->vsh.glsl_opts);
        break;
    case VK_SHADER_STAGE_GEOMETRY_BIT:
        code = pgraph_glsl_gen_geom(&key->geom.state, key->geom.glsl_opts);
        break;
    case VK_SHADER_STAGE_FRAGMENT_BIT:
        code = pgraph_glsl_gen_psh(&key->psh.state, key->psh.glsl_opts);
        break;
    default:
        assert(!"Invalid shader module kind");
        code = NULL;
    }

    ShaderModuleInfo *info = pgraph_vk_create_shader_module_from_glsl(
        r, key->kind, mstring_get_str(code));
    mstring_unref(code);

    if (info) {
        pgraph_vk_ref_shader_module(info);
        shader_module_key_persist(key);
    }

    qatomic_set(&target->module_info, info);
    qatomic_set(&target->ready, true);
}

static VkResult create_monolithic_pipeline(PGRAPHVkState *r,
                                           const PipelineCreateParams *p,
                                           VkPipeline *pipeline)
{
    VkPipelineVertexInputStateCreateInfo vertex_input = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
        .vertexBindingDescriptionCount = p->num_binding_descs,
        .pVertexBindingDescriptions = p->binding_descs,
        .vertexAttributeDescriptionCount = p->num_attr_descs,
        .pVertexAttributeDescriptions = p->attr_descs,
    };

    VkPipelineInputAssemblyStateCreateInfo input_assembly = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
        .topology = p->topology,
        .primitiveRestartEnable = VK_FALSE,
    };

    VkPipelineViewportStateCreateInfo viewport_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
        .viewportCount = 1,
        .scissorCount = 1,
    };

    VkPipelineMultisampleStateCreateInfo multisampling = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
        .sampleShadingEnable = VK_FALSE,
        .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT,
    };

    VkPipelineColorBlendStateCreateInfo color_blending = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
        .logicOpEnable = VK_FALSE,
        .logicOp = VK_LOGIC_OP_COPY,
        .attachmentCount = p->has_color ? 1 : 0,
        .pAttachments = p->has_color ? &p->color_blend_attachment : NULL,
        .blendConstants[0] = p->blend_constants[0],
        .blendConstants[1] = p->blend_constants[1],
        .blendConstants[2] = p->blend_constants[2],
        .blendConstants[3] = p->blend_constants[3],
    };

    VkPipelineDynamicStateCreateInfo dynamic_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,
        .dynamicStateCount = p->num_dynamic_states,
        .pDynamicStates = p->dynamic_states,
    };

    VkGraphicsPipelineCreateInfo pipeline_create_info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .stageCount = p->num_shader_stages,
        .pStages = p->shader_stages,
        .pVertexInputState = &vertex_input,
        .pInputAssemblyState = &input_assembly,
        .pViewportState = &viewport_state,
        .pRasterizationState = &p->rasterizer,
        .pMultisampleState = &multisampling,
        .pDepthStencilState = p->has_zeta ? &p->depth_stencil : NULL,
        .pColorBlendState = &color_blending,
        .pDynamicState = &dynamic_state,
        .layout = p->layout,
        .renderPass = p->render_pass,
        .subpass = 0,
        .basePipelineHandle = VK_NULL_HANDLE,
    };

    return pgraph_vk_create_graphics_pipeline_fb(r, &pipeline_create_info,
                                                 true, pipeline);
}

static void process_pipeline_job(PGRAPHVkState *r, CompileJob *job)
{
    PipelineBinding *target = job->pipeline.target;
    PipelineCreateParams *p = &job->pipeline.params;

    VkPipeline pipeline;
    VkResult result =
        p->gpl ? pgraph_vk_gpl_create_pipeline(r, target, p, &pipeline) :
                 create_monolithic_pipeline(r, p, &pipeline);

    if (result == VK_SUCCESS) {
        target->pipeline = pipeline;
        target->layout = p->layout;
        target->render_pass = p->render_pass;
        target->has_dynamic_line_width = p->has_dynamic_line_width;
        pgraph_vk_compile_worker_note_dirty(r);
    }
    qatomic_set(&target->pending, false);
}

/*
 * #569 P5: VK_EXT_graphics_pipeline_library.
 *
 * WHY. P1 (lane.shaderfb569, #574) measured a cold DOA Ultimate soak on the
 * Nova with creation feedback on all 164 creates: Turnip compiled again, at
 * full price, all 246 stages whose VkShaderModule an earlier pipeline had
 * already used -- 77% of stage time. A monolithic create hashes the whole
 * pipeline, so a vs met with a new fragment shader, blend state or vertex
 * layout is compiled from scratch every time.
 *
 * WHAT. A draw pipeline is linked from four libraries, each cached here by
 * the state its own subset reads:
 *   VI  vertex input interface: vertex bindings, attributes, topology;
 *   PR  pre-rasterization: vs + gs module ids, rasterizer, render pass;
 *   FS  fragment shader: fs module id, depth/stencil, render pass;
 *   FO  fragment output: blend attachment, render pass.
 * A miss creates only the libraries it has not seen and links them without
 * link-time optimisation (graphicsPipelineLibraryFastLinking). With
 * HAKUX_GPL=2 the same libraries are linked again with LTO on the worker and
 * the result swapped in by create_pipeline().
 *
 * THE FS SLOT IS ITS OWN LIBRARY so a prebuilt fragment library -- an
 * ubershader (lane.uberspike569) -- can be linked against any PR library:
 * it needs only to be created with this file's fixed layout and render pass
 * per format pair, and put in the FS table under its own key.
 *
 * ONE LAYOUT. Every draw pipeline in this mode uses r->gpl.layout, which
 * carries the full vertex push-constant range (all 16 inline attributes),
 * because libraries linked together need identically defined layouts and a
 * per-miss layout sized by the vs's attribute count would make PR and FS
 * disagree. INDEPENDENT_SETS is not used: every library gets the same whole
 * layout, which is the case the flag exists to relax.
 *
 * MODULE IDENTITY is a hash of the SPIR-V (ShaderModuleInfo::gpl_id), not
 * the VkShaderModule handle, which the driver may hand out again after a
 * module is freed.
 *
 * LIFETIME. A GplLib is reference counted: the table holds one, a build
 * holds one per library while it links, an LTO job one until it has run.
 * The tables are flushed whole when one reaches GPL_MAX_LIBS; a linked
 * pipeline does not need its libraries afterwards.
 */
struct GplLib {
    VkPipeline pipeline;
    int refcnt;
};

enum { GPL_VI, GPL_PR, GPL_FS, GPL_FO, GPL_NUM_LIBS };

#define GPL_MAX_LIBS 4096

static const VkGraphicsPipelineLibraryFlagsEXT gpl_lib_flags[GPL_NUM_LIBS] = {
    VK_GRAPHICS_PIPELINE_LIBRARY_VERTEX_INPUT_INTERFACE_BIT_EXT,
    VK_GRAPHICS_PIPELINE_LIBRARY_PRE_RASTERIZATION_SHADERS_BIT_EXT,
    VK_GRAPHICS_PIPELINE_LIBRARY_FRAGMENT_SHADER_BIT_EXT,
    VK_GRAPHICS_PIPELINE_LIBRARY_FRAGMENT_OUTPUT_INTERFACE_BIT_EXT,
};

/* Keys are built on a zeroed struct from 4-byte fields only, so memcmp and
 * hashing never see padding. */
typedef struct GplDynKey {
    uint32_t num;
    VkDynamicState states[20];
} GplDynKey;

typedef struct GplViKey {
    GplDynKey dyn;
    uint32_t num_bindings, num_attrs;
    VkVertexInputBindingDescription bindings[NV2A_VERTEXSHADER_ATTRIBUTES];
    VkVertexInputAttributeDescription attrs[NV2A_VERTEXSHADER_ATTRIBUTES];
    VkPrimitiveTopology topology;
} GplViKey;

typedef struct GplPrKey {
    uint64_t vs, gs;
    GplDynKey dyn;
    VkFormat color, zeta;
    VkBool32 depth_clamp, discard;
    VkPolygonMode polygon_mode;
    VkCullModeFlags cull_mode;
    VkFrontFace front_face;
    VkBool32 depth_bias;
    float line_width;
} GplPrKey;

typedef struct GplFsKey {
    uint64_t fs;
    GplDynKey dyn;
    VkFormat color, zeta;
    uint32_t has_zeta;
    /* VkPipelineDepthStencilStateCreateInfo from flags on: all 4 bytes */
    uint32_t ds[(sizeof(VkPipelineDepthStencilStateCreateInfo) -
                 offsetof(VkPipelineDepthStencilStateCreateInfo, flags)) /
                sizeof(uint32_t)];
} GplFsKey;

typedef struct GplFoKey {
    GplDynKey dyn;
    VkFormat color, zeta;
    uint32_t has_color;
    VkPipelineColorBlendAttachmentState attachment;
    float blend_constants[4];
} GplFoKey;

static void gpl_lib_unref(PGRAPHVkState *r, GplLib *lib)
{
    if (lib && qatomic_fetch_dec(&lib->refcnt) == 1) {
        vkDestroyPipeline(r->device, lib->pipeline, NULL);
        g_free(lib);
    }
}

static void gpl_lib_ref(GplLib *lib)
{
    qatomic_inc(&lib->refcnt);
}

/* Drop the tables' references. Caller holds r->gpl.lock. */
static void gpl_flush_locked(PGRAPHVkState *r)
{
    for (int i = 0; i < GPL_NUM_LIBS; i++) {
        GHashTableIter it;
        gpointer value;
        g_hash_table_iter_init(&it, r->gpl.libs[i]);
        while (g_hash_table_iter_next(&it, NULL, &value)) {
            gpl_lib_unref(r, value);
        }
        g_hash_table_remove_all(r->gpl.libs[i]);
    }
    r->gpl.stats.flushes++;
}

/*
 * The library for kind/key, created from info if the table has none. Returns
 * it with a reference for the caller, or NULL if the driver refused.
 * Caller holds r->gpl.lock.
 */
static GplLib *gpl_get_lib(PGRAPHVkState *r, int kind, const void *key,
                           size_t key_size,
                           const VkGraphicsPipelineCreateInfo *info)
{
    GBytes *k = g_bytes_new(key, key_size);
    GplLib *lib = g_hash_table_lookup(r->gpl.libs[kind], k);
    if (lib) {
        g_bytes_unref(k);
        r->gpl.stats.lib_hit[kind]++;
        gpl_lib_ref(lib);
        return lib;
    }

    VkGraphicsPipelineLibraryCreateInfoEXT lib_info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_LIBRARY_CREATE_INFO_EXT,
        .pNext = info->pNext,
        .flags = gpl_lib_flags[kind],
    };
    VkGraphicsPipelineCreateInfo ci = *info;
    ci.pNext = &lib_info;
    ci.flags |= VK_PIPELINE_CREATE_LIBRARY_BIT_KHR;
    if (r->gpl.mode == 2) {
        ci.flags |= VK_PIPELINE_CREATE_RETAIN_LINK_TIME_OPTIMIZATION_INFO_BIT_EXT;
    }

    VkPipeline pipeline;
    int64_t t0 = nv2a_clock_ns();
    VkResult result =
        pgraph_vk_create_graphics_pipeline_fb(r, &ci, true, &pipeline);
    r->gpl.stats.lib_us[kind] += (nv2a_clock_ns() - t0) / 1000;
    if (result != VK_SUCCESS) {
        g_bytes_unref(k);
        r->gpl.stats.lib_fail[kind]++;
        return NULL;
    }
    r->gpl.stats.lib_new[kind]++;

    if (g_hash_table_size(r->gpl.libs[kind]) >= GPL_MAX_LIBS) {
        gpl_flush_locked(r);
    }
    lib = g_new0(GplLib, 1);
    lib->pipeline = pipeline;
    lib->refcnt = 2; /* the table's and the caller's */
    g_hash_table_insert(r->gpl.libs[kind], k, lib);
    return lib;
}

static uint64_t gpl_heap_usage(PGRAPHVkState *r)
{
    if (!r->memory_budget_extension_enabled) {
        return 0;
    }
    VkPhysicalDeviceMemoryBudgetPropertiesEXT budget = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MEMORY_BUDGET_PROPERTIES_EXT,
    };
    VkPhysicalDeviceMemoryProperties2 props = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MEMORY_PROPERTIES_2,
        .pNext = &budget,
    };
    vkGetPhysicalDeviceMemoryProperties2(r->physical_device, &props);
    uint64_t used = 0;
    for (uint32_t i = 0; i < props.memoryProperties.memoryHeapCount; i++) {
        if (props.memoryProperties.memoryHeaps[i].flags &
            VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) {
            used += budget.heapUsage[i];
        }
    }
    return used;
}

/*
 * One line per link that created a library, and every 32nd link, all
 * counters running totals since start: links/link_ms the fast links and
 * their wall time; new/hit/fail per library kind vi/pr/fs/fo with lib_ms
 * their create wall time; libs the table sizes now; fb= monolithic
 * fallbacks; lto= done/failed/swapped in, with lto_ms its worker time (not
 * a stall); heap_mb the device-local heap usage, the memory leg's reading.
 * The creates here also go through pgraph_vk_create_graphics_pipeline_fb(),
 * so [shd413]'s dpc_ms is still the render thread's whole create time.
 * Caller holds r->gpl.lock.
 */
static void gpl_log_locked(PGRAPHVkState *r)
{
    typeof(r->gpl.stats) *s = &r->gpl.stats;
    char line[512];
    snprintf(line, sizeof(line),
             "[gpl569] mode=%d links=%u link_ms=%.1f link_fail=%u fb=%u "
             "new=%u/%u/%u/%u hit=%u/%u/%u/%u fail=%u/%u/%u/%u "
             "lib_ms=%.1f/%.1f/%.1f/%.1f libs=%u/%u/%u/%u flush=%u "
             "lto=%u/%u/%u lto_ms=%.1f heap_mb=%.1f",
             r->gpl.mode, s->links, s->link_us / 1000.0, s->link_fail,
             s->fallbacks, s->lib_new[0], s->lib_new[1], s->lib_new[2],
             s->lib_new[3], s->lib_hit[0], s->lib_hit[1], s->lib_hit[2],
             s->lib_hit[3], s->lib_fail[0], s->lib_fail[1], s->lib_fail[2],
             s->lib_fail[3], s->lib_us[0] / 1000.0, s->lib_us[1] / 1000.0,
             s->lib_us[2] / 1000.0, s->lib_us[3] / 1000.0,
             g_hash_table_size(r->gpl.libs[0]),
             g_hash_table_size(r->gpl.libs[1]),
             g_hash_table_size(r->gpl.libs[2]),
             g_hash_table_size(r->gpl.libs[3]), s->flushes,
             qatomic_read(&s->lto_done), qatomic_read(&s->lto_fail),
             qatomic_read(&s->lto_swapped), s->lto_us / 1000.0,
             gpl_heap_usage(r) / (1024.0 * 1024.0));
#ifdef __ANDROID__
    __android_log_print(ANDROID_LOG_INFO, "hakuX-perf", "%s", line);
#else
    fprintf(stderr, "%s\n", line);
#endif
}

VkPipelineLayout pgraph_vk_gpl_layout(PGRAPHVkState *r)
{
    if (r->gpl.layout != VK_NULL_HANDLE) {
        return r->gpl.layout;
    }

    /* create_pipeline()'s layout at the full inline-attribute count; the
     * push descriptor template for that count (vk/shaders.c) was built from
     * an identically defined layout, which push_template_index() picks */
    VkPushConstantRange ranges[2] = {
        {
            .stageFlags = VK_SHADER_STAGE_GEOMETRY_BIT,
            .offset = 0,
            .size = 4 * sizeof(float), /* GEOM_PUSH_CONSTANT_SIZE */
        },
        {
            .stageFlags = VK_SHADER_STAGE_VERTEX_BIT,
            .offset = 4 * sizeof(float),
            .size = NV2A_VERTEXSHADER_ATTRIBUTES * 4 * sizeof(float),
        },
    };
    VkDescriptorSetLayout set_layouts[2] = {
        r->push_descriptors_supported ? r->push_tex_set_layout :
                                        r->descriptor_set_layout,
        r->push_ubo_set_layout,
    };
    VkPipelineLayoutCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 2,
        .pSetLayouts = set_layouts,
        .pushConstantRangeCount = r->use_push_constants_for_uniform_attrs ? 2 : 1,
        .pPushConstantRanges = ranges,
    };
    VkPipelineLayout layout;
    VK_CHECK(vkCreatePipelineLayout(r->device, &info, NULL, &layout));
    r->gpl.layout = layout;
    return layout;
}

static void gpl_dyn_key(GplDynKey *k, const PipelineCreateParams *p)
{
    k->num = p->num_dynamic_states;
    memcpy(k->states, p->dynamic_states,
           p->num_dynamic_states * sizeof(VkDynamicState));
}

static bool gpl_dynamic(const PipelineCreateParams *p, VkDynamicState s)
{
    for (int i = 0; i < p->num_dynamic_states; i++) {
        if (p->dynamic_states[i] == s) {
            return true;
        }
    }
    return false;
}

VkResult pgraph_vk_gpl_create_pipeline(PGRAPHVkState *r,
                                       PipelineBinding *target,
                                       const PipelineCreateParams *p,
                                       VkPipeline *pipeline)
{
    VkPipelineDynamicStateCreateInfo dynamic_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,
        .dynamicStateCount = p->num_dynamic_states,
        .pDynamicStates = p->dynamic_states,
    };
    VkPipelineMultisampleStateCreateInfo multisampling = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
        .sampleShadingEnable = VK_FALSE,
        .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT,
    };

    /* VI */
    VkPipelineVertexInputStateCreateInfo vertex_input = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
        .vertexBindingDescriptionCount = p->num_binding_descs,
        .pVertexBindingDescriptions = p->binding_descs,
        .vertexAttributeDescriptionCount = p->num_attr_descs,
        .pVertexAttributeDescriptions = p->attr_descs,
    };
    VkPipelineInputAssemblyStateCreateInfo input_assembly = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
        .topology = p->topology,
        .primitiveRestartEnable = VK_FALSE,
    };
    VkGraphicsPipelineCreateInfo vi_info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .pVertexInputState = &vertex_input,
        .pInputAssemblyState = &input_assembly,
        .pDynamicState = &dynamic_state,
    };
    GplViKey vi_key;
    memset(&vi_key, 0, sizeof(vi_key));
    gpl_dyn_key(&vi_key.dyn, p);
    vi_key.num_bindings = p->num_binding_descs;
    vi_key.num_attrs = p->num_attr_descs;
    memcpy(vi_key.bindings, p->binding_descs,
           p->num_binding_descs * sizeof(p->binding_descs[0]));
    memcpy(vi_key.attrs, p->attr_descs,
           p->num_attr_descs * sizeof(p->attr_descs[0]));
    vi_key.topology = p->topology;

    /* PR */
    VkPipelineShaderStageCreateInfo pr_stages[2];
    uint32_t num_pr_stages = 0;
    const VkPipelineShaderStageCreateInfo *fs_stage = NULL;
    for (int i = 0; i < p->num_shader_stages; i++) {
        if (p->shader_stages[i].stage == VK_SHADER_STAGE_FRAGMENT_BIT) {
            fs_stage = &p->shader_stages[i];
        } else {
            assert(num_pr_stages < ARRAY_SIZE(pr_stages));
            pr_stages[num_pr_stages++] = p->shader_stages[i];
        }
    }
    assert(fs_stage);
    VkPipelineViewportStateCreateInfo viewport_state = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
        .viewportCount = 1,
        .scissorCount = 1,
    };
    VkGraphicsPipelineCreateInfo pr_info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .stageCount = num_pr_stages,
        .pStages = pr_stages,
        .pViewportState = &viewport_state,
        .pRasterizationState = &p->rasterizer,
        .pDynamicState = &dynamic_state,
        .layout = p->layout,
        .renderPass = p->gpl_lib_render_pass,
        .subpass = 0,
    };
    GplPrKey pr_key;
    memset(&pr_key, 0, sizeof(pr_key));
    gpl_dyn_key(&pr_key.dyn, p);
    pr_key.vs = p->gpl_vs_id;
    pr_key.gs = p->gpl_gs_id;
    pr_key.color = p->gpl_color_format;
    pr_key.zeta = p->gpl_zeta_format;
    pr_key.depth_clamp = p->rasterizer.depthClampEnable;
    pr_key.discard = p->rasterizer.rasterizerDiscardEnable;
    pr_key.polygon_mode = p->rasterizer.polygonMode;
    pr_key.cull_mode = p->rasterizer.cullMode;
    pr_key.front_face = p->rasterizer.frontFace;
    pr_key.depth_bias = p->rasterizer.depthBiasEnable;
    pr_key.line_width = p->rasterizer.lineWidth;
    assert(p->rasterizer.pNext == NULL);

    /* FS */
    VkGraphicsPipelineCreateInfo fs_info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .stageCount = 1,
        .pStages = fs_stage,
        .pMultisampleState = &multisampling,
        .pDepthStencilState = p->has_zeta ? &p->depth_stencil : NULL,
        .pDynamicState = &dynamic_state,
        .layout = p->layout,
        .renderPass = p->gpl_lib_render_pass,
        .subpass = 0,
    };
    GplFsKey fs_key;
    memset(&fs_key, 0, sizeof(fs_key));
    gpl_dyn_key(&fs_key.dyn, p);
    fs_key.fs = p->gpl_fs_id;
    fs_key.color = p->gpl_color_format;
    fs_key.zeta = p->gpl_zeta_format;
    fs_key.has_zeta = p->has_zeta;
    if (p->has_zeta) {
        memcpy(fs_key.ds, &p->depth_stencil.flags, sizeof(fs_key.ds));
    }

    /* FO */
    VkPipelineColorBlendStateCreateInfo color_blending = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
        .logicOpEnable = VK_FALSE,
        .logicOp = VK_LOGIC_OP_COPY,
        .attachmentCount = p->has_color ? 1 : 0,
        .pAttachments = p->has_color ? &p->color_blend_attachment : NULL,
        .blendConstants[0] = p->blend_constants[0],
        .blendConstants[1] = p->blend_constants[1],
        .blendConstants[2] = p->blend_constants[2],
        .blendConstants[3] = p->blend_constants[3],
    };
    VkGraphicsPipelineCreateInfo fo_info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .pMultisampleState = &multisampling,
        .pColorBlendState = &color_blending,
        .pDynamicState = &dynamic_state,
        .layout = p->layout,
        .renderPass = p->gpl_lib_render_pass,
        .subpass = 0,
    };
    GplFoKey fo_key;
    memset(&fo_key, 0, sizeof(fo_key));
    gpl_dyn_key(&fo_key.dyn, p);
    fo_key.color = p->gpl_color_format;
    fo_key.zeta = p->gpl_zeta_format;
    fo_key.has_color = p->has_color;
    if (p->has_color) {
        fo_key.attachment = p->color_blend_attachment;
    }
    if (!gpl_dynamic(p, VK_DYNAMIC_STATE_BLEND_CONSTANTS)) {
        memcpy(fo_key.blend_constants, p->blend_constants,
               sizeof(fo_key.blend_constants));
    }

    GplLib *libs[GPL_NUM_LIBS] = { NULL };
    const void *keys[GPL_NUM_LIBS] = { &vi_key, &pr_key, &fs_key, &fo_key };
    const size_t key_sizes[GPL_NUM_LIBS] = { sizeof(vi_key), sizeof(pr_key),
                                             sizeof(fs_key), sizeof(fo_key) };
    const VkGraphicsPipelineCreateInfo *infos[GPL_NUM_LIBS] = {
        &vi_info, &pr_info, &fs_info, &fo_info
    };

    qemu_mutex_lock(&r->gpl.lock);
    unsigned int created_before = r->gpl.stats.lib_new[0] +
                                  r->gpl.stats.lib_new[1] +
                                  r->gpl.stats.lib_new[2] +
                                  r->gpl.stats.lib_new[3];
    bool have_libs = true;
    for (int i = 0; i < GPL_NUM_LIBS && have_libs; i++) {
        libs[i] = gpl_get_lib(r, i, keys[i], key_sizes[i], infos[i]);
        have_libs = libs[i] != NULL;
    }
    qemu_mutex_unlock(&r->gpl.lock);

    VkResult result = VK_ERROR_UNKNOWN;
    if (have_libs) {
        VkPipeline handles[GPL_NUM_LIBS];
        for (int i = 0; i < GPL_NUM_LIBS; i++) {
            handles[i] = libs[i]->pipeline;
        }
        VkPipelineLibraryCreateInfoKHR link_info = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_LIBRARY_CREATE_INFO_KHR,
            .libraryCount = GPL_NUM_LIBS,
            .pLibraries = handles,
        };
        VkGraphicsPipelineCreateInfo info = {
            .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
            .pNext = &link_info,
            .layout = p->layout,
            .renderPass = p->gpl_lib_render_pass,
            .subpass = 0,
        };
        int64_t t0 = nv2a_clock_ns();
        result = pgraph_vk_create_graphics_pipeline_fb(r, &info, true,
                                                       pipeline);
        int64_t link_us = (nv2a_clock_ns() - t0) / 1000;

        qemu_mutex_lock(&r->gpl.lock);
        r->gpl.stats.links++;
        r->gpl.stats.link_us += link_us;
        r->gpl.stats.link_fail += result != VK_SUCCESS;
        qemu_mutex_unlock(&r->gpl.lock);
    }

    bool lto = result == VK_SUCCESS && r->gpl.mode == 2 && target;
    if (lto) {
        /* The job takes the build's references */
        CompileJob *job = g_malloc0(sizeof(CompileJob));
        job->type = COMPILE_JOB_GPL_LTO;
        job->gpl_lto.target = target;
        memcpy(job->gpl_lto.libs, libs, sizeof(libs));
        job->gpl_lto.layout = p->layout;
        job->gpl_lto.render_pass = p->gpl_lib_render_pass;
        qatomic_set(&target->gpl_lto_pending, true);
        qatomic_inc(&r->gpl.lto_inflight);
        pgraph_vk_compile_worker_enqueue(r, job);
    } else {
        for (int i = 0; i < GPL_NUM_LIBS; i++) {
            gpl_lib_unref(r, libs[i]);
        }
    }

    bool fallback = result != VK_SUCCESS;
    if (fallback) {
        /* Same layout, so push_template_index() still holds */
        result = create_monolithic_pipeline(r, p, pipeline);
    }

    qemu_mutex_lock(&r->gpl.lock);
    r->gpl.stats.fallbacks += fallback;
    unsigned int created = r->gpl.stats.lib_new[0] + r->gpl.stats.lib_new[1] +
                           r->gpl.stats.lib_new[2] + r->gpl.stats.lib_new[3];
    if (created != created_before || fallback ||
        (r->gpl.stats.links % 32) == 0) {
        gpl_log_locked(r);
    }
    qemu_mutex_unlock(&r->gpl.lock);

    return result;
}

static void process_gpl_lto_job(PGRAPHVkState *r, CompileJob *job)
{
    PipelineBinding *target = job->gpl_lto.target;

    VkPipeline handles[GPL_NUM_LIBS];
    for (int i = 0; i < GPL_NUM_LIBS; i++) {
        handles[i] = job->gpl_lto.libs[i]->pipeline;
    }
    VkPipelineLibraryCreateInfoKHR link_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LIBRARY_CREATE_INFO_KHR,
        .libraryCount = GPL_NUM_LIBS,
        .pLibraries = handles,
    };
    VkGraphicsPipelineCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .pNext = &link_info,
        .flags = VK_PIPELINE_CREATE_LINK_TIME_OPTIMIZATION_BIT_EXT,
        .layout = job->gpl_lto.layout,
        .renderPass = job->gpl_lto.render_pass,
        .subpass = 0,
    };

    /* Not through pgraph_vk_create_graphics_pipeline_fb(): this runs off the
     * draw path, and [shd413]'s dpc_ms is the stall it must not inflate. */
    VkPipeline pipeline;
    int64_t t0 = nv2a_clock_ns();
    VkResult result = vkCreateGraphicsPipelines(
        r->device, r->vk_pipeline_cache, 1, &info, NULL, &pipeline);
    int64_t us = (nv2a_clock_ns() - t0) / 1000;

    for (int i = 0; i < GPL_NUM_LIBS; i++) {
        gpl_lib_unref(r, job->gpl_lto.libs[i]);
    }

    qemu_mutex_lock(&r->gpl.lock);
    r->gpl.stats.lto_us += us;
    if (result == VK_SUCCESS) {
        r->gpl.stats.lto_done++;
    } else {
        r->gpl.stats.lto_fail++;
    }
    qemu_mutex_unlock(&r->gpl.lock);

    if (result == VK_SUCCESS) {
        target->gpl_lto_pipeline = pipeline;
    }
    smp_wmb();
    qatomic_set(&target->gpl_lto_pending, false);
    qatomic_dec(&r->gpl.lto_inflight);
}

void pgraph_vk_gpl_wait_lto_idle(PGRAPHVkState *r)
{
    while (qatomic_read(&r->gpl.lto_inflight) > 0) {
        g_usleep(1000);
    }
}

static void gpl_init(PGRAPHVkState *r)
{
    qemu_mutex_init(&r->gpl.lock);
    for (int i = 0; i < GPL_NUM_LIBS; i++) {
        r->gpl.libs[i] = g_hash_table_new_full(
            g_bytes_hash, g_bytes_equal, (GDestroyNotify)g_bytes_unref, NULL);
    }
}

void pgraph_vk_gpl_finalize(PGRAPHVkState *r)
{
    qemu_mutex_lock(&r->gpl.lock);
    gpl_flush_locked(r);
    qemu_mutex_unlock(&r->gpl.lock);
    for (int i = 0; i < GPL_NUM_LIBS; i++) {
        g_hash_table_destroy(r->gpl.libs[i]);
        r->gpl.libs[i] = NULL;
    }
    if (r->gpl.layout != VK_NULL_HANDLE) {
        vkDestroyPipelineLayout(r->device, r->gpl.layout, NULL);
        r->gpl.layout = VK_NULL_HANDLE;
    }
    qemu_mutex_destroy(&r->gpl.lock);
}

/*
 * #569 P3: the worker pool, the pipeline pre-build and the pipeline cache
 * saves.
 *
 * POOL. HAKUX_COMPILE_WORKERS threads (1-4, default 3; the scheduler places
 * them, since the Thor pauses cpu3-7 when hot, #507) share
 * r->compile_worker.queue and sleep on its condvar. A pipeline job is taken
 * first, since a draw waits on it, then module jobs, then the rest (LTO).
 * pool->idle_cond is broadcast whenever anything a worker took has ended, so
 * wait_idle counts finished jobs, not dequeued ones, and the draw thread
 * waits for a pending pipeline on it instead of polling.
 *
 * PRE-BUILD. Every monolithic draw pipeline a title creates is appended to
 * pipeline_keys/<title id>.bin (pgraph_vk_prebuild_note): the hashes of its
 * module keys, which shader_module_keys.bin holds, and the rest of its create
 * state, with no handles. The title id is default.xbe's, read from the disc
 * at renderer init. At the next launch of the title, renderer init resolves
 * each record's modules from the module cache the startup warm-up filled,
 * and the pool builds the pipelines into the VkPipelineCache in the
 * background, in the order the title first met them. A draw that then meets
 * one finds the driver's binaries in the cache. Pre-build jobs run behind
 * every draw-path job and on at most workers - 1 threads, and they bypass
 * pgraph_vk_create_graphics_pipeline_fb, so [shd413]'s dpc_ms stays the draw
 * path's own create time. A job owns a copy of its SPIR-V (VkShaderModules
 * made for the batch) and a render pass made before PFIFO draws, so no
 * render-thread object crosses to a worker. The GLSL is generated again from
 * the keys, so an update that changes the generators still pre-builds, and a
 * driver update wipes only the pipeline cache (renderer.c). HAKUX_PREBUILD=0
 * turns the pre-build off (records are still written).
 *
 * SAVES. The draw thread (maybe_save_pipeline_cache) and the workers mark the
 * cache dirty. While it is dirty a worker wakes every second and writes it
 * when the VM has stopped (the Android app pausing: vm_stop), when no new
 * pipeline has come for 3 s and the last save is 10 s old (a load has
 * ended), when the last save is 30 s old, and when a pre-build ends. The
 * runstate is polled because renderer init runs on the PFIFO thread, outside
 * the BQL a change-state handler is registered under. Before this, a
 * sync-mode save ran on the PFIFO thread, at most every 30 s and only after
 * another miss, and async mode saved only through a clear pipeline's miss or
 * at teardown.
 */
#define COMPILE_WORKERS_MAX 4
#define COMPILE_WORKERS_DEFAULT 3
#define PLC_SAVE_INTERVAL_NS (30 * 1000000000LL)
#define PLC_SAVE_MIN_NS (10 * 1000000000LL)
#define PLC_SAVE_QUIET_NS (3 * 1000000000LL)
#define PREBUILD_MAX_RECORDS 2048
#define PREBUILD_FILE_MAGIC 0x31425048u /* "HPB1" */
#define PREBUILD_FILE_VERSION 1

#define PB_RAST_WORDS                                                   \
    ((offsetof(VkPipelineRasterizationStateCreateInfo, lineWidth) +     \
      sizeof(float) -                                                   \
      offsetof(VkPipelineRasterizationStateCreateInfo, flags)) /        \
     sizeof(uint32_t))
#define PB_DS_WORDS                                                     \
    ((sizeof(VkPipelineDepthStencilStateCreateInfo) -                   \
      offsetof(VkPipelineDepthStencilStateCreateInfo, flags)) /         \
     sizeof(uint32_t))

typedef struct PrebuildFileHeader {
    uint32_t magic, version, record_size, reserved;
} PrebuildFileHeader;

/* Built on a zeroed struct, so equal pipelines are equal bytes */
typedef struct PrebuildRecord {
    uint64_t module_hash[3];    /* vs, gs (0: none), fs */
    RenderPassState rp;
    uint32_t topology;
    uint32_t has_color, has_zeta;
    /* the create infos from flags to their last member, all 4-byte fields */
    uint32_t rast[PB_RAST_WORDS];
    uint32_t ds[PB_DS_WORDS];
    VkPipelineColorBlendAttachmentState blend;
    float blend_constants[4];
    uint32_t num_dynamic_states;
    VkDynamicState dynamic_states[20];
    uint32_t num_bindings, num_attrs;
    VkVertexInputBindingDescription bindings[NV2A_VERTEXSHADER_ATTRIBUTES];
    VkVertexInputAttributeDescription attrs[NV2A_VERTEXSHADER_ATTRIBUTES];
    uint32_t num_push_ranges;
    VkPushConstantRange push_ranges[2];
} PrebuildRecord;

typedef struct PrebuildJob {
    QSIMPLEQ_ENTRY(PrebuildJob) entry;
    PrebuildRecord rec;
    VkShaderModule modules[3];  /* the batch's; VK_NULL_HANDLE: no gs */
    VkRenderPass render_pass;
} PrebuildJob;

typedef struct CompilePool {
    QemuThread threads[COMPILE_WORKERS_MAX];
    int num_threads;
    QemuCond idle_cond;         /* something a worker took has ended */
    int running;                /* CompileJobs being processed */

    /* pre-build; under r->compile_worker.lock */
    QSIMPLEQ_HEAD(, PrebuildJob) pb_queue;
    int pb_queued, pb_running, pb_limit;
    bool pb_active;             /* queued, and not yet finished or stopped */
    GArray *pb_modules;         /* VkShaderModule, the batch's own */
    int64_t pb_t0_ns;
    unsigned int pb_total, pb_ok, pb_fail, pb_met;
    uint64_t pb_create_us;
    GHashTable *met;            /* records the draw path created this run */

    /* saves; under r->compile_worker.lock */
    bool save_enabled, save_dirty, saving;
    const char *save_reason;    /* set: save now */
    int64_t last_save_ns, last_dirty_ns;
    unsigned int saves;

    /* records; PFIFO thread and renderer init/finalize only */
    uint32_t title_id;
    char *rec_path;
    GHashTable *rec_seen;       /* fast_hash of each record in the file */
    unsigned int rec_new, rec_known;
    uint64_t rec_new_us, rec_known_us;
} CompilePool;

static void pool_log(const char *fmt, ...) G_GNUC_PRINTF(1, 2);
static void pool_log(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
#ifdef __ANDROID__
    __android_log_vprint(ANDROID_LOG_INFO, "hakuX-perf", fmt, ap);
#else
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
#endif
    va_end(ap);
}

static int compile_job_rank(const CompileJob *job)
{
    switch (job->type) {
    case COMPILE_JOB_PIPELINE:
        return 0;
    case COMPILE_JOB_SHADER_MODULE:
        return 1;
    default:
        return 2;
    }
}

/* The most urgent queued job, oldest first within a rank. Caller holds the
 * lock; the queue is not empty. */
static CompileJob *compile_worker_take(PGRAPHVkState *r)
{
    CompileJob *best = NULL, *job;
    QSIMPLEQ_FOREACH(job, &r->compile_worker.queue, entry) {
        if (!best || compile_job_rank(job) < compile_job_rank(best)) {
            best = job;
            if (compile_job_rank(best) == 0) {
                break;
            }
        }
    }
    QSIMPLEQ_REMOVE(&r->compile_worker.queue, best, CompileJob, entry);
    r->compile_worker.queue_depth--;
    return best;
}

/* Why a save is due now, or NULL. Caller holds the lock. */
static const char *pool_save_due(CompilePool *pool, int64_t now)
{
    if (!pool->save_enabled || pool->saving) {
        return NULL;
    }
    if (pool->save_reason) {
        return pool->save_reason;
    }
    if (!pool->save_dirty) {
        return NULL;
    }
    int64_t since = now - pool->last_save_ns;
    if (!runstate_is_running()) {
        return "stop";
    }
    if (since >= PLC_SAVE_INTERVAL_NS) {
        return "timer";
    }
    if (since >= PLC_SAVE_MIN_NS &&
        now - pool->last_dirty_ns >= PLC_SAVE_QUIET_NS) {
        return "quiet";
    }
    return NULL;
}

static void prebuild_release_modules(PGRAPHVkState *r, CompilePool *pool)
{
    for (guint i = 0; i < pool->pb_modules->len; i++) {
        vkDestroyShaderModule(
            r->device, g_array_index(pool->pb_modules, VkShaderModule, i),
            NULL);
    }
    g_array_set_size(pool->pb_modules, 0);
}

/* Build one recorded pipeline into the VkPipelineCache and drop it */
static bool prebuild_run(PGRAPHVkState *r, PrebuildJob *pb, int64_t *us)
{
    const PrebuildRecord *rec = &pb->rec;

    /* create_pipeline()'s layout for this record */
    VkDescriptorSetLayout set_layouts[2] = {
        r->push_descriptors_supported ? r->push_tex_set_layout :
                                        r->descriptor_set_layout,
        r->push_ubo_set_layout,
    };
    VkPipelineLayoutCreateInfo layout_info = {
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 2,
        .pSetLayouts = set_layouts,
        .pushConstantRangeCount = rec->num_push_ranges,
        .pPushConstantRanges = rec->push_ranges,
    };
    VkPipelineLayout layout;
    if (vkCreatePipelineLayout(r->device, &layout_info, NULL, &layout) !=
        VK_SUCCESS) {
        *us = 0;
        return false;
    }

    static const VkShaderStageFlagBits stages[3] = {
        VK_SHADER_STAGE_VERTEX_BIT,
        VK_SHADER_STAGE_GEOMETRY_BIT,
        VK_SHADER_STAGE_FRAGMENT_BIT,
    };
    PipelineCreateParams *p = g_new0(PipelineCreateParams, 1);
    p->device = r->device;
    p->vk_pipeline_cache = r->vk_pipeline_cache;
    for (int i = 0; i < 3; i++) {
        if (pb->modules[i] == VK_NULL_HANDLE) {
            continue;
        }
        p->shader_stages[p->num_shader_stages++] =
            (VkPipelineShaderStageCreateInfo){
                .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                .stage = stages[i],
                .module = pb->modules[i],
                .pName = "main",
            };
    }
    memcpy(p->binding_descs, rec->bindings, sizeof(rec->bindings));
    memcpy(p->attr_descs, rec->attrs, sizeof(rec->attrs));
    p->num_binding_descs = rec->num_bindings;
    p->num_attr_descs = rec->num_attrs;
    p->topology = rec->topology;
    p->rasterizer.sType =
        VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO;
    memcpy(&p->rasterizer.flags, rec->rast, sizeof(rec->rast));
    p->depth_stencil.sType =
        VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO;
    memcpy(&p->depth_stencil.flags, rec->ds, sizeof(rec->ds));
    p->has_zeta = rec->has_zeta;
    p->color_blend_attachment = rec->blend;
    p->has_color = rec->has_color;
    memcpy(p->blend_constants, rec->blend_constants,
           sizeof(p->blend_constants));
    memcpy(p->dynamic_states, rec->dynamic_states,
           sizeof(rec->dynamic_states));
    p->num_dynamic_states = rec->num_dynamic_states;
    p->layout = layout;
    p->render_pass = pb->render_pass;

    VkPipeline pipeline;
    int64_t t0 = nv2a_clock_ns();
    pcfb_quiet = true;
    VkResult result = create_monolithic_pipeline(r, p, &pipeline);
    pcfb_quiet = false;
    *us = (nv2a_clock_ns() - t0) / 1000;

    if (result == VK_SUCCESS) {
        vkDestroyPipeline(r->device, pipeline, NULL);
    }
    vkDestroyPipelineLayout(r->device, layout, NULL);
    g_free(p);
    return result == VK_SUCCESS;
}

/* A pre-build job ended. Caller holds the lock. */
static void prebuild_job_ended(PGRAPHVkState *r, CompilePool *pool, bool ok,
                               int64_t us)
{
    pool->pb_running--;
    pool->pb_ok += ok;
    pool->pb_fail += !ok;
    pool->pb_create_us += us;
    if (!pool->pb_active || pool->pb_running || pool->pb_queued) {
        return;
    }
    pool->pb_active = false;
    prebuild_release_modules(r, pool);
    pool_log("[pb569] done title=%08X jobs=%u ok=%u fail=%u met=%u "
             "create_ms=%.1f wall_ms=%.1f",
             pool->title_id, pool->pb_total, pool->pb_ok - pool->pb_met,
             pool->pb_fail, pool->pb_met, pool->pb_create_us / 1000.0,
             (nv2a_clock_ns() - pool->pb_t0_ns) / 1e6);
    if (pool->pb_ok > pool->pb_met) {
        pool->save_reason = "prebuild";
    }
}

static void *compile_worker_func(void *opaque)
{
    PGRAPHVkState *r = opaque;
    CompilePool *pool = r->compile_worker.pool;

    qemu_mutex_lock(&r->compile_worker.lock);
    while (true) {
        CompileJob *job = NULL;
        PrebuildJob *pb = NULL;
        const char *save = NULL;

        while (true) {
            int64_t now = nv2a_clock_ns();
            if (!QSIMPLEQ_EMPTY(&r->compile_worker.queue)) {
                job = compile_worker_take(r);
                pool->running++;
                break;
            }
            if (r->compile_worker.shutdown) {
                qemu_mutex_unlock(&r->compile_worker.lock);
                return NULL;
            }
            save = pool_save_due(pool, now);
            if (save) {
                pool->save_reason = NULL;
                pool->save_dirty = false;
                pool->saving = true;
                break;
            }
            if (!QSIMPLEQ_EMPTY(&pool->pb_queue) &&
                pool->pb_running < pool->pb_limit) {
                pb = QSIMPLEQ_FIRST(&pool->pb_queue);
                QSIMPLEQ_REMOVE_HEAD(&pool->pb_queue, entry);
                pool->pb_queued--;
                pool->pb_running++;
                uint64_t h = fast_hash((const uint8_t *)&pb->rec,
                                       sizeof(pb->rec));
                if (g_hash_table_contains(pool->met, &h)) {
                    /* the draw path built it first: in the cache already */
                    g_free(pb);
                    pb = NULL;
                    pool->pb_met++;
                    prebuild_job_ended(r, pool, true, 0);
                    continue;
                }
                break;
            }
            if (pool->save_enabled && pool->save_dirty && !pool->saving) {
                qemu_cond_timedwait(&r->compile_worker.cond,
                                    &r->compile_worker.lock, 1000);
            } else {
                qemu_cond_wait(&r->compile_worker.cond,
                               &r->compile_worker.lock);
            }
        }

        qemu_mutex_unlock(&r->compile_worker.lock);

        bool pb_ok = false;
        int64_t pb_us = 0;
        if (job) {
            switch (job->type) {
            case COMPILE_JOB_SHADER_MODULE:
                process_shader_module_job(r, job);
                break;
            case COMPILE_JOB_PIPELINE:
                process_pipeline_job(r, job);
                break;
            case COMPILE_JOB_GPL_LTO:
                process_gpl_lto_job(r, job);
                break;
            }

            g_free(job);
        } else if (pb) {
            pb_ok = prebuild_run(r, pb, &pb_us);
            g_free(pb);
        } else {
            int64_t t0 = nv2a_clock_ns();
            pgraph_vk_save_pipeline_cache(r);
            pool_log("[plc569] save=%s n=%u ms=%.1f", save, pool->saves + 1,
                     (nv2a_clock_ns() - t0) / 1e6);
        }

        qemu_mutex_lock(&r->compile_worker.lock);
        if (job) {
            pool->running--;
        } else if (pb) {
            prebuild_job_ended(r, pool, pb_ok, pb_us);
        } else {
            pool->saving = false;
            pool->last_save_ns = nv2a_clock_ns();
            pool->saves++;
        }
        qemu_cond_broadcast(&pool->idle_cond);
    }
}

void pgraph_vk_compile_worker_enqueue(PGRAPHVkState *r, CompileJob *job)
{
    qemu_mutex_lock(&r->compile_worker.lock);
    QSIMPLEQ_INSERT_TAIL(&r->compile_worker.queue, job, entry);
    r->compile_worker.queue_depth++;
    qemu_cond_signal(&r->compile_worker.cond);
    qemu_mutex_unlock(&r->compile_worker.lock);
}

void pgraph_vk_compile_worker_note_dirty(PGRAPHVkState *r)
{
    CompilePool *pool = r->compile_worker.pool;
    qemu_mutex_lock(&r->compile_worker.lock);
    pool->last_dirty_ns = nv2a_clock_ns();
    if (!pool->save_dirty) {
        pool->save_dirty = true;
        /* a sleeping worker starts its one-second checks */
        qemu_cond_broadcast(&r->compile_worker.cond);
    }
    qemu_mutex_unlock(&r->compile_worker.lock);
}

/* The draw thread, in async mode: a pipeline job for this binding is queued
 * or running */
void pgraph_vk_compile_worker_wait_pipeline(PGRAPHVkState *r,
                                            PipelineBinding *binding)
{
    CompilePool *pool = r->compile_worker.pool;
    qemu_mutex_lock(&r->compile_worker.lock);
    while (qatomic_read(&binding->pending)) {
        qemu_cond_wait(&pool->idle_cond, &r->compile_worker.lock);
    }
    qemu_mutex_unlock(&r->compile_worker.lock);
}

void pgraph_vk_compile_worker_init(PGRAPHVkState *r)
{
    qemu_mutex_init(&r->compile_worker.lock);
    qemu_cond_init(&r->compile_worker.cond);
    QSIMPLEQ_INIT(&r->compile_worker.queue);
    r->compile_worker.shutdown = false;
    r->compile_worker.queue_depth = 0;

    CompilePool *pool = g_new0(CompilePool, 1);
    r->compile_worker.pool = pool;
    qemu_cond_init(&pool->idle_cond);
    QSIMPLEQ_INIT(&pool->pb_queue);
    pool->pb_modules = g_array_new(false, false, sizeof(VkShaderModule));
    pool->met = g_hash_table_new_full(g_int64_hash, g_int64_equal, g_free,
                                      NULL);

    int n = COMPILE_WORKERS_DEFAULT;
    const char *e = getenv("HAKUX_COMPILE_WORKERS");
    if (e && e[0] >= '1' && e[0] <= '0' + COMPILE_WORKERS_MAX && !e[1]) {
        n = e[0] - '0';
    }
    pool->num_threads = n;
    /* async mode keeps a worker free for the draw path's jobs */
    pool->pb_limit = xemu_get_async_compile() ? MAX(1, n - 1) : n;

    gpl_init(r);
    static const char *const names[COMPILE_WORKERS_MAX] = {
        "pgraph.vk.compile", "pgraph.vk.comp1", "pgraph.vk.comp2",
        "pgraph.vk.comp3",
    };
    for (int i = 0; i < n; i++) {
        qemu_thread_create(&pool->threads[i], names[i], compile_worker_func,
                           r, QEMU_THREAD_JOINABLE);
    }
}

void pgraph_vk_compile_worker_wait_idle(PGRAPHVkState *r,
                                        int total_jobs,
                                        void (*progress_cb)(int current,
                                                            int total))
{
    if (total_jobs <= 0) {
        return;
    }

    CompilePool *pool = r->compile_worker.pool;
    if (progress_cb) {
        progress_cb(0, total_jobs);
    }

    /* Jobs finished, not dequeued: a dequeued job may still be compiling */
    qemu_mutex_lock(&r->compile_worker.lock);
    int reported = -1;
    while (true) {
        int remaining = r->compile_worker.queue_depth + pool->running;
        if (remaining <= 0) {
            break;
        }
        if (progress_cb && remaining != reported) {
            reported = remaining;
            qemu_mutex_unlock(&r->compile_worker.lock);
            progress_cb(MAX(0, total_jobs - remaining), total_jobs);
            qemu_mutex_lock(&r->compile_worker.lock);
            continue;
        }
        qemu_cond_wait(&pool->idle_cond, &r->compile_worker.lock);
    }
    qemu_mutex_unlock(&r->compile_worker.lock);

    if (progress_cb) {
        progress_cb(total_jobs, total_jobs);
    }
}

void pgraph_vk_compile_worker_shutdown(PGRAPHVkState *r)
{
    CompilePool *pool = r->compile_worker.pool;

    pgraph_vk_prebuild_stop(r);

    qemu_mutex_lock(&r->compile_worker.lock);
    r->compile_worker.shutdown = true;
    qemu_cond_broadcast(&r->compile_worker.cond);
    qemu_mutex_unlock(&r->compile_worker.lock);

    for (int i = 0; i < pool->num_threads; i++) {
        qemu_thread_join(&pool->threads[i]);
    }

    CompileJob *job;
    while ((job = QSIMPLEQ_FIRST(&r->compile_worker.queue)) != NULL) {
        QSIMPLEQ_REMOVE_HEAD(&r->compile_worker.queue, entry);
        if (job->type == COMPILE_JOB_GPL_LTO) {
            for (int i = 0; i < GPL_NUM_LIBS; i++) {
                gpl_lib_unref(r, job->gpl_lto.libs[i]);
            }
            qatomic_dec(&r->gpl.lto_inflight);
        }
        g_free(job);
    }

    qemu_mutex_destroy(&r->compile_worker.lock);
    qemu_cond_destroy(&r->compile_worker.cond);
    qemu_cond_destroy(&pool->idle_cond);
    g_array_free(pool->pb_modules, true);
    g_hash_table_destroy(pool->met);
    g_free(pool);
    r->compile_worker.pool = NULL;
    pgraph_vk_gpl_finalize(r);
}

/* default.xbe's certificate title id from the disc image, or 0. The same
 * walk as ReadDiscTitleId() in xemu_android.cpp, which runs before Vulkan
 * exists and does not export it. */
static uint32_t pb_le32(const uint8_t *p)
{
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static bool pb_pread(int fd, void *buf, size_t len, uint64_t off)
{
    uint8_t *b = buf;
    while (len) {
        ssize_t n = pread(fd, b, len, off);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n <= 0) {
            return false;
        }
        b += n;
        len -= n;
        off += n;
    }
    return true;
}

static uint32_t pb_disc_title_id(const char *path)
{
    static const uint64_t starts[] = { 0, 0x18300000ull, 0xFD90000ull,
                                       0x2080000ull };
    static const char magic[] = "MICROSOFT*XBOX*MEDIA";
    const uint64_t sector = 2048;

    if (!path || !path[0]) {
        return 0;
    }
    int fd = qemu_open_old(path, O_RDONLY);
    if (fd < 0) {
        return 0;
    }

    uint32_t tid = 0;
    for (int i = 0; i < ARRAY_SIZE(starts); i++) {
        uint64_t base = starts[i];
        uint8_t vd[2048];
        if (!pb_pread(fd, vd, sizeof(vd), base + 32 * sector) ||
            memcmp(vd, magic, strlen(magic)) ||
            memcmp(vd + 0x7EC, magic, strlen(magic))) {
            continue;
        }
        uint32_t root_sector = pb_le32(vd + 0x14);
        uint32_t root_size = pb_le32(vd + 0x18);
        if (root_size < 14 || root_size > (1u << 20)) {
            break;
        }
        uint8_t *dir = g_malloc(root_size);
        uint32_t xbe_sector = 0, xbe_size = 0;
        if (pb_pread(fd, dir, root_size, base + root_sector * sector)) {
            GArray *stack = g_array_new(false, false, sizeof(uint32_t));
            uint32_t off = 0;
            g_array_append_val(stack, off);
            for (int visits = 0; stack->len && visits < 4096; visits++) {
                off = g_array_index(stack, uint32_t, stack->len - 1);
                g_array_set_size(stack, stack->len - 1);
                if (off + 14 > root_size) {
                    continue;
                }
                const uint8_t *e = dir + off;
                uint32_t left = e[0] | (e[1] << 8);
                uint32_t right = e[2] | (e[3] << 8);
                if (left == 0xFFFF) {
                    continue; /* padding */
                }
                uint8_t name_len = e[13];
                if (off + 14 + name_len <= root_size && name_len == 11 &&
                    !g_ascii_strncasecmp((const char *)e + 14, "default.xbe",
                                         11)) {
                    xbe_sector = pb_le32(e + 4);
                    xbe_size = pb_le32(e + 8);
                    break;
                }
                if (left) {
                    uint32_t v = left * 4;
                    g_array_append_val(stack, v);
                }
                if (right) {
                    uint32_t v = right * 4;
                    g_array_append_val(stack, v);
                }
            }
            g_array_free(stack, true);
        }
        g_free(dir);
        if (xbe_size < 0x180) {
            break;
        }

        uint64_t xbe = base + xbe_sector * sector;
        uint8_t hdr[0x180], t[4];
        if (!pb_pread(fd, hdr, sizeof(hdr), xbe) || memcmp(hdr, "XBEH", 4)) {
            break;
        }
        uint32_t base_addr = pb_le32(hdr + 0x104);
        uint32_t cert_addr = pb_le32(hdr + 0x118);
        if (cert_addr < base_addr || cert_addr - base_addr + 12 > xbe_size) {
            break;
        }
        if (pb_pread(fd, t, sizeof(t), xbe + (cert_addr - base_addr) + 8)) {
            tid = pb_le32(t);
        }
        break;
    }
    qemu_close(fd);
    return tid;
}

void pgraph_vk_prebuild_note(PGRAPHVkState *r, const RenderPassState *rp,
                             const PipelineCreateParams *p,
                             const VkPushConstantRange *push_ranges,
                             int num_push_ranges)
{
    CompilePool *pool = r->compile_worker.pool;
    if (!pool || !pool->rec_path || !r->shader_binding ||
        p->num_shader_stages < 2 || num_push_ranges > 2) {
        return;
    }

    PrebuildRecord rec;
    memset(&rec, 0, sizeof(rec));
    pgraph_vk_shader_binding_module_hashes(r, r->shader_binding,
                                           rec.module_hash);
    rec.rp = *rp;
    rec.topology = p->topology;
    rec.has_color = p->has_color;
    rec.has_zeta = p->has_zeta;
    memcpy(rec.rast, &p->rasterizer.flags, sizeof(rec.rast));
    memcpy(rec.ds, &p->depth_stencil.flags, sizeof(rec.ds));
    rec.blend = p->color_blend_attachment;
    memcpy(rec.blend_constants, p->blend_constants,
           sizeof(rec.blend_constants));
    rec.num_dynamic_states = p->num_dynamic_states;
    memcpy(rec.dynamic_states, p->dynamic_states,
           p->num_dynamic_states * sizeof(VkDynamicState));
    rec.num_bindings = p->num_binding_descs;
    rec.num_attrs = p->num_attr_descs;
    memcpy(rec.bindings, p->binding_descs,
           p->num_binding_descs * sizeof(rec.bindings[0]));
    memcpy(rec.attrs, p->attr_descs,
           p->num_attr_descs * sizeof(rec.attrs[0]));
    rec.num_push_ranges = num_push_ranges;
    memcpy(rec.push_ranges, push_ranges,
           num_push_ranges * sizeof(rec.push_ranges[0]));

    uint64_t h = fast_hash((const uint8_t *)&rec, sizeof(rec));
    qemu_mutex_lock(&r->compile_worker.lock);
    if (pool->pb_active) {
        g_hash_table_add(pool->met, g_memdup2(&h, sizeof(h)));
    }
    qemu_mutex_unlock(&r->compile_worker.lock);
    /*
     * One line per draw-path create: known ones were in the title's file at
     * launch or met earlier this run, new ones were not. us is this create's
     * wall time (sync mode; -1 when it was queued for the worker). A known
     * create that the pre-build reached is a cache hit.
     */
    bool sync = !xemu_get_async_compile();
    int64_t us = sync ? pcfb_last_us : 0;
    bool known = g_hash_table_contains(pool->rec_seen, &h);
    if (known) {
        pool->rec_known++;
        pool->rec_known_us += us;
    } else {
        g_hash_table_add(pool->rec_seen, g_memdup2(&h, sizeof(h)));
        FILE *f = fopen(pool->rec_path, "ab");
        if (f) {
            fwrite(&rec, sizeof(rec), 1, f);
            fclose(f);
        }
        pool->rec_new++;
        pool->rec_new_us += us;
    }
    pool_log("[pb569] rec %s us=%lld known=%u known_ms=%.1f new=%u "
             "new_ms=%.1f",
             known ? "known" : "new", sync ? (long long)us : -1LL,
             pool->rec_known, pool->rec_known_us / 1000.0, pool->rec_new,
             pool->rec_new_us / 1000.0);
}

typedef struct PrebuildModule {
    VkShaderModule module;      /* VK_NULL_HANDLE: could not be made */
} PrebuildModule;

/* The batch's module for a key hash, made on first use. Renderer init. */
static VkShaderModule prebuild_module(PGRAPHVkState *r, CompilePool *pool,
                                      GHashTable *keys, GHashTable *made,
                                      uint64_t hash)
{
    PrebuildModule *m = g_hash_table_lookup(made, &hash);
    if (m) {
        return m->module;
    }
    m = g_new0(PrebuildModule, 1);
    g_hash_table_insert(made, g_memdup2(&hash, sizeof(hash)), m);

    const ShaderModuleCacheKey *key = g_hash_table_lookup(keys, &hash);
    GBytes *spirv = key ? pgraph_vk_prebuild_module_spirv(r, key) : NULL;
    if (!spirv) {
        return VK_NULL_HANDLE;
    }
    gsize len;
    const void *code = g_bytes_get_data(spirv, &len);
    VkShaderModuleCreateInfo info = {
        .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = len,
        .pCode = code,
    };
    if (vkCreateShaderModule(r->device, &info, NULL, &m->module) ==
        VK_SUCCESS) {
        g_array_append_val(pool->pb_modules, m->module);
    } else {
        m->module = VK_NULL_HANDLE;
    }
    g_bytes_unref(spirv);
    return m->module;
}

/* Queue the title's recorded pipelines. Renderer init. */
static void prebuild_enqueue(PGRAPHVkState *r, CompilePool *pool,
                             const PrebuildRecord *recs, size_t n,
                             unsigned int *unresolved)
{
    const char *base = xemu_settings_get_base_path();
    char *path = g_strdup_printf("%sshader_module_keys.bin", base);
    gchar *data = NULL;
    gsize len = 0;
    g_file_get_contents(path, &data, &len, NULL);
    g_free(path);

    size_t num_keys = data ? len / sizeof(ShaderModuleCacheKey) : 0;
    const ShaderModuleCacheKey *key_data = (const ShaderModuleCacheKey *)data;
    uint64_t *key_hashes = g_new(uint64_t, num_keys + 1);
    GHashTable *keys = g_hash_table_new(g_int64_hash, g_int64_equal);
    for (size_t i = 0; i < num_keys; i++) {
        key_hashes[i] = pgraph_vk_hash_shader_module_key(&key_data[i]);
        g_hash_table_insert(keys, &key_hashes[i], (gpointer)&key_data[i]);
    }
    GHashTable *made =
        g_hash_table_new_full(g_int64_hash, g_int64_equal, g_free, g_free);

    QSIMPLEQ_HEAD(, PrebuildJob) jobs = QSIMPLEQ_HEAD_INITIALIZER(jobs);
    unsigned int count = 0;
    *unresolved = 0;
    for (size_t i = 0; i < n && count < PREBUILD_MAX_RECORDS; i++) {
        const PrebuildRecord *rec = &recs[i];
        VkShaderModule modules[3] = { VK_NULL_HANDLE };
        bool ok = true;
        for (int s = 0; s < 3 && ok; s++) {
            if (s == 1 && !rec->module_hash[s]) {
                continue;
            }
            modules[s] =
                prebuild_module(r, pool, keys, made, rec->module_hash[s]);
            ok = modules[s] != VK_NULL_HANDLE;
        }
        if (!ok) {
            (*unresolved)++;
            continue;
        }
        PrebuildJob *pb = g_new0(PrebuildJob, 1);
        pb->rec = *rec;
        memcpy(pb->modules, modules, sizeof(modules));
        pb->render_pass = pgraph_vk_prebuild_render_pass(r, &pb->rec.rp);
        QSIMPLEQ_INSERT_TAIL(&jobs, pb, entry);
        count++;
    }
    g_hash_table_destroy(made);
    g_hash_table_destroy(keys);
    g_free(key_hashes);
    g_free(data);

    qemu_mutex_lock(&r->compile_worker.lock);
    QSIMPLEQ_CONCAT(&pool->pb_queue, &jobs);
    pool->pb_queued += count;
    pool->pb_total = count;
    pool->pb_active = count > 0;
    pool->pb_t0_ns = nv2a_clock_ns();
    qemu_cond_broadcast(&r->compile_worker.cond);
    qemu_mutex_unlock(&r->compile_worker.lock);

    if (!count) {
        prebuild_release_modules(r, pool);
    }
}

void pgraph_vk_prebuild_start(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    CompilePool *pool = r->compile_worker.pool;

    if (!g_config.perf.cache_shaders) {
        return;
    }
    int64_t t0 = nv2a_clock_ns();

    qemu_mutex_lock(&r->compile_worker.lock);
    pool->save_enabled = true;
    pool->last_save_ns = t0;
    qemu_mutex_unlock(&r->compile_worker.lock);

    pool->title_id = pb_disc_title_id(g_config.sys.files.dvd_path);
    if (!pool->title_id) {
        pool_log("[pb569] no title id from the disc: no pre-build, no "
                 "records");
        return;
    }

    const char *base = xemu_settings_get_base_path();
    char *dir = g_strdup_printf("%spipeline_keys", base);
    g_mkdir_with_parents(dir, 0755);
    char *path = g_strdup_printf("%s/%08X.bin", dir, pool->title_id);
    g_free(dir);

    gchar *data = NULL;
    gsize len = 0;
    const PrebuildRecord *recs = NULL;
    size_t n = 0;
    if (g_file_get_contents(path, &data, &len, NULL) &&
        len >= sizeof(PrebuildFileHeader)) {
        const PrebuildFileHeader *hdr = (const PrebuildFileHeader *)data;
        if (hdr->magic == PREBUILD_FILE_MAGIC &&
            hdr->version == PREBUILD_FILE_VERSION &&
            hdr->record_size == sizeof(PrebuildRecord)) {
            recs = (const PrebuildRecord *)(data + sizeof(*hdr));
            n = (len - sizeof(*hdr)) / sizeof(PrebuildRecord);
        }
    }
    if (!recs) {
        /* absent, or another build's layout: start the title's file again */
        PrebuildFileHeader hdr = {
            .magic = PREBUILD_FILE_MAGIC,
            .version = PREBUILD_FILE_VERSION,
            .record_size = sizeof(PrebuildRecord),
        };
        if (!g_file_set_contents(path, (const gchar *)&hdr, sizeof(hdr),
                                 NULL)) {
            g_free(path);
            g_free(data);
            return;
        }
    }
    pool->rec_path = path;
    pool->rec_seen = g_hash_table_new_full(g_int64_hash, g_int64_equal,
                                           g_free, NULL);
    for (size_t i = 0; i < n; i++) {
        uint64_t h = fast_hash((const uint8_t *)&recs[i], sizeof(recs[i]));
        g_hash_table_add(pool->rec_seen, g_memdup2(&h, sizeof(h)));
    }

    const char *e = getenv("HAKUX_PREBUILD");
    bool enabled = !(e && !strcmp(e, "0"));
    unsigned int unresolved = 0;
    if (enabled && n) {
        prebuild_enqueue(r, pool, recs, n, &unresolved);
    }
    pool_log("[pb569] start title=%08X records=%zu jobs=%u unresolved=%u "
             "modules=%u workers=%d pb_workers=%d enabled=%d setup_ms=%.1f",
             pool->title_id, n, pool->pb_total, unresolved,
             pool->pb_modules->len, pool->num_threads, pool->pb_limit,
             enabled, (nv2a_clock_ns() - t0) / 1e6);
    g_free(data);
}

void pgraph_vk_prebuild_stop(PGRAPHVkState *r)
{
    CompilePool *pool = r->compile_worker.pool;
    if (!pool) {
        return;
    }

    qemu_mutex_lock(&r->compile_worker.lock);
    pool->save_enabled = false;
    unsigned int cancelled = 0;
    PrebuildJob *pb;
    while ((pb = QSIMPLEQ_FIRST(&pool->pb_queue)) != NULL) {
        QSIMPLEQ_REMOVE_HEAD(&pool->pb_queue, entry);
        g_free(pb);
        cancelled++;
    }
    pool->pb_queued = 0;
    while (pool->pb_running || pool->saving) {
        qemu_cond_wait(&pool->idle_cond, &r->compile_worker.lock);
    }
    if (pool->pb_active) {
        pool->pb_active = false;
        pool_log("[pb569] stopped title=%08X jobs=%u ok=%u fail=%u met=%u "
                 "cancelled=%u", pool->title_id, pool->pb_total,
                 pool->pb_ok - pool->pb_met, pool->pb_fail, pool->pb_met,
                 cancelled);
    }
    qemu_mutex_unlock(&r->compile_worker.lock);
    prebuild_release_modules(r, pool);

    if (pool->rec_path) {
        pool_log("[pb569] records title=%08X new=%u", pool->title_id,
                 pool->rec_new);
    }
    g_free(pool->rec_path);
    pool->rec_path = NULL;
    if (pool->rec_seen) {
        g_hash_table_destroy(pool->rec_seen);
        pool->rec_seen = NULL;
    }
}

#endif /* OPT_ASYNC_COMPILE */
