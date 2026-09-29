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

static void process_pipeline_job(PGRAPHVkState *r, CompileJob *job)
{
    PipelineBinding *target = job->pipeline.target;
    PipelineCreateParams *p = &job->pipeline.params;

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

    VkPipeline pipeline;
    VkResult result = pgraph_vk_create_graphics_pipeline_fb(
        r, &pipeline_create_info, true, &pipeline);

    if (result == VK_SUCCESS) {
        target->pipeline = pipeline;
        target->layout = p->layout;
        target->render_pass = p->render_pass;
        target->has_dynamic_line_width = p->has_dynamic_line_width;
    }
    qatomic_set(&target->pending, false);
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
        g_free(job);
    }

    qemu_mutex_destroy(&r->compile_worker.lock);
    qemu_cond_destroy(&r->compile_worker.cond);
}

#endif /* OPT_ASYNC_COMPILE */
