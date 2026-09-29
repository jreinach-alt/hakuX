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

static void *compile_worker_func(void *opaque)
{
    PGRAPHVkState *r = opaque;

    while (true) {
        qemu_mutex_lock(&r->compile_worker.lock);

        while (QSIMPLEQ_EMPTY(&r->compile_worker.queue) &&
               !r->compile_worker.shutdown) {
            qemu_cond_wait(&r->compile_worker.cond, &r->compile_worker.lock);
        }

        if (r->compile_worker.shutdown &&
            QSIMPLEQ_EMPTY(&r->compile_worker.queue)) {
            qemu_mutex_unlock(&r->compile_worker.lock);
            break;
        }

        CompileJob *job = QSIMPLEQ_FIRST(&r->compile_worker.queue);
        QSIMPLEQ_REMOVE_HEAD(&r->compile_worker.queue, entry);
        r->compile_worker.queue_depth--;

        qemu_mutex_unlock(&r->compile_worker.lock);

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
    }

    return NULL;
}

void pgraph_vk_compile_worker_enqueue(PGRAPHVkState *r, CompileJob *job)
{
    qemu_mutex_lock(&r->compile_worker.lock);
    QSIMPLEQ_INSERT_TAIL(&r->compile_worker.queue, job, entry);
    r->compile_worker.queue_depth++;
    qemu_cond_signal(&r->compile_worker.cond);
    qemu_mutex_unlock(&r->compile_worker.lock);
}

void pgraph_vk_compile_worker_init(PGRAPHVkState *r)
{
    qemu_mutex_init(&r->compile_worker.lock);
    qemu_cond_init(&r->compile_worker.cond);
    QSIMPLEQ_INIT(&r->compile_worker.queue);
    r->compile_worker.shutdown = false;
    r->compile_worker.queue_depth = 0;
    gpl_init(r);
    qemu_thread_create(&r->compile_worker.thread, "pgraph.vk.compile",
                       compile_worker_func, r, QEMU_THREAD_JOINABLE);
}

void pgraph_vk_compile_worker_wait_idle(PGRAPHVkState *r,
                                        int total_jobs,
                                        void (*progress_cb)(int current,
                                                            int total))
{
    if (total_jobs <= 0) {
        return;
    }

    if (progress_cb) {
        progress_cb(0, total_jobs);
    }

    while (true) {
        qemu_mutex_lock(&r->compile_worker.lock);
        int remaining = r->compile_worker.queue_depth;
        qemu_mutex_unlock(&r->compile_worker.lock);

        if (remaining <= 0) {
            break;
        }

        int completed = total_jobs - remaining;
        if (progress_cb) {
            progress_cb(completed, total_jobs);
        }

        g_usleep(50 * 1000); /* 50ms poll interval */
    }

    if (progress_cb) {
        progress_cb(total_jobs, total_jobs);
    }
}

void pgraph_vk_compile_worker_shutdown(PGRAPHVkState *r)
{
    qemu_mutex_lock(&r->compile_worker.lock);
    r->compile_worker.shutdown = true;
    qemu_cond_signal(&r->compile_worker.cond);
    qemu_mutex_unlock(&r->compile_worker.lock);

    qemu_thread_join(&r->compile_worker.thread);

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
    pgraph_vk_gpl_finalize(r);
}

#endif /* OPT_ASYNC_COMPILE */
