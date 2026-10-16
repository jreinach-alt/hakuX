/*
 * Geforce NV2A PGRAPH Vulkan Renderer
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

#include "hw/xbox/nv2a/nv2a_int.h"
#include "renderer.h"
#include "texture_dump.h"
#include "texture_replace.h"
#include "qemu/error-report.h"
#include "qemu/fast-hash.h"
#include "ui/xemu-settings.h"

extern bool xemu_get_frame_skip(void);
#ifdef __ANDROID__
#include <android/log.h>
#define DBG_LOG(...) __android_log_print(ANDROID_LOG_INFO, "hakuX-vk-dbg", __VA_ARGS__)
#else
#define DBG_LOG(...) fprintf(stderr, __VA_ARGS__)
#endif

#include "gloffscreen.h"

#include <sys/stat.h>
#include <unistd.h>

#ifdef __ANDROID__
#include <android/log.h>
#endif

typedef struct {
    uint32_t vendor_id;
    uint32_t device_id;
    uint32_t driver_version;
    uint8_t  pipeline_cache_uuid[VK_UUID_SIZE];
    /* Fingerprint of the shader cache key's layout. The caches on disk store
     * ShaderState blobs verbatim, so a build whose struct layout differs
     * reinterprets them as garbage -- in practice an assertion inside shader
     * generation during warmup, thousands of lines from the actual cause.
     * Including the sizes here wipes the cache automatically on the common
     * case; bump SHADER_STATE_LAYOUT_VERSION by hand when a field changes
     * without changing any of the sizes. */
    uint32_t shader_state_layout;
} GpuDriverIdentity;

/* Bump when ShaderState/PshState/VshState change layout but not size. A new
 * enum VALUE counts: 2 is PRIM_TYPE_TRIANGLES_ADJACENCY (#224). Persisted
 * geometry-shader keys carrying it abort any build without the case at
 * startup (geom.c's default: assert), so builds on either side of it must
 * see different versions and wipe the cache rather than regenerate it.
 * 3 is VshState/GeomState.aa_offset_x (#286): a key stored without it would
 * regenerate as a non-CC2 shader for a CC2 draw.
 * 4 is GenGeomGlslOptions.no_point_size (#34), which sits in padding: a key
 * persisted before it reads as 0 and would regenerate a geometry shader
 * that writes gl_PointSize on a device without the feature.
 * 5 is GeomState.line_cull_face/line_front_ccw (#13): GeomState grows, but
 * ShaderState's size need not follow if PshState's alignment absorbs it, and
 * a key stored without them would regenerate a line-mode shader that culls
 * nothing. */
#define SHADER_STATE_LAYOUT_VERSION 5

static void remove_directory_recursive(const char *path)
{
    GDir *dir = g_dir_open(path, 0, NULL);
    if (!dir) {
        return;
    }
    const gchar *name;
    while ((name = g_dir_read_name(dir)) != NULL) {
        gchar *child = g_build_filename(path, name, NULL);
        if (g_file_test(child, G_FILE_TEST_IS_DIR)) {
            remove_directory_recursive(child);
        } else {
            unlink(child);
        }
        g_free(child);
    }
    g_dir_close(dir);
    rmdir(path);
}

static void check_driver_identity_and_wipe_caches(PGRAPHVkState *r)
{
    if (!g_config.perf.cache_shaders) {
        return;
    }

    const char *base = xemu_settings_get_base_path();
    char *id_path = g_strdup_printf("%sgpu_driver_id.bin", base);

    GpuDriverIdentity current;
    current.vendor_id = r->device_props.vendorID;
    current.device_id = r->device_props.deviceID;
    current.driver_version = r->device_props.driverVersion;
    memcpy(current.pipeline_cache_uuid, r->device_props.pipelineCacheUUID,
           VK_UUID_SIZE);
    current.shader_state_layout = (uint32_t)sizeof(ShaderState) * 2654435761u +
                                  (uint32_t)sizeof(PshState) * 2246822519u +
                                  (uint32_t)sizeof(VshState) * 3266489917u +
                                  SHADER_STATE_LAYOUT_VERSION;

    /*
     * #569 P3 item 4: only the pipeline cache depends on the driver. SPIR-V
     * and the persisted module and pipeline keys depend on the key layout
     * alone, so a driver update keeps them, and the pre-build
     * (vk/compile_worker.c) rebuilds the driver's binaries from them.
     */
    bool match = false, layout_match = false;
    gchar *data = NULL;
    gsize len = 0;
    if (g_file_get_contents(id_path, &data, &len, NULL) &&
        len == sizeof(GpuDriverIdentity)) {
        match = memcmp(data, &current, sizeof(GpuDriverIdentity)) == 0;
        layout_match = ((GpuDriverIdentity *)data)->shader_state_layout ==
                       current.shader_state_layout;
    }
    g_free(data);

    char *plc_path = g_strdup_printf("%svk_pipeline_cache.bin", base);
    if (!match) {
        VK_LOG("Driver or shader-state layout changed -- wiping caches");
#ifdef __ANDROID__
        __android_log_print(ANDROID_LOG_INFO, "hakuX-vk",
            "Cache identity mismatch: wiping %s "
            "(vendor=%04x device=%04x driverVer=%08x layout=%08x)",
            layout_match ? "the pipeline cache (driver only)" :
                           "spv_cache, keys and pipeline cache",
            current.vendor_id, current.device_id, current.driver_version,
            current.shader_state_layout);
#else
        fprintf(stderr, "xemu-vk: Cache identity mismatch: wiping %s "
                "(vendor=%04x device=%04x driverVer=%08x layout=%08x)\n",
                layout_match ? "the pipeline cache (driver only)" :
                               "spv_cache, keys and pipeline cache",
                current.vendor_id, current.device_id, current.driver_version,
                current.shader_state_layout);
#endif

        unlink(plc_path);
        if (!layout_match) {
            char *spv_dir = g_strdup_printf("%sspv_cache", base);
            char *smk_path = g_strdup_printf("%sshader_module_keys.bin", base);
            char *pk_dir = g_strdup_printf("%spipeline_keys", base);
            remove_directory_recursive(spv_dir);
            unlink(smk_path);
            remove_directory_recursive(pk_dir);
            g_free(spv_dir);
            g_free(smk_path);
            g_free(pk_dir);
        }

        g_file_set_contents(id_path, (const gchar *)&current,
                            sizeof(GpuDriverIdentity), NULL);
    }

    /* #569 P3's falsifier arm: start with no pipeline cache file, keys kept */
    const char *wipe = getenv("HAKUX_PLC_WIPE");
    if (wipe && !strcmp(wipe, "1")) {
        int rc = unlink(plc_path);
#ifdef __ANDROID__
        __android_log_print(ANDROID_LOG_INFO, "hakuX-perf",
                            "[pb569] HAKUX_PLC_WIPE=1: vk_pipeline_cache.bin %s",
                            rc == 0 ? "removed" : "absent");
#else
        fprintf(stderr, "[pb569] HAKUX_PLC_WIPE=1: vk_pipeline_cache.bin %s\n",
                rc == 0 ? "removed" : "absent");
#endif
    }
    g_free(plc_path);

    g_free(id_path);
}

/*
 * limits.timestampPeriod is not trusted. The Nova's Adreno reports 33.11 ns
 * (30.2 MHz) while its timestamps tick every 52.08 ns (19.2 MHz), so every GPU
 * phase figure read 0.636 of the true value (#474). In perflog builds, the
 * only ones that print the figures it scales, the period is measured against
 * the CPU clock instead.
 *
 * Each sample submits a command buffer that writes one timestamp and waits
 * for it: the tick was written between the submit and the fence, so the
 * sample's CPU time is that window's middle, uncertain by half its width.
 * Samples with a window over four times the narrowest are dropped.
 *
 * The counter does not run through an idle GPU. The first cut of this slept
 * 100 ms between two groups of samples, and on the Thor the counter advanced
 * 1.2 ms over that 110 ms, for a "period" of 4636 ns. So the samples are taken
 * back to back, and the measurement tests the one thing it depends on: the
 * second half of the span leaves the GPU idle for GPU_TS_CAL_GAP_US after
 * every sample, and the first half does not. A counter that stops in a short
 * idle gap gives the two halves different slopes.
 *
 * The period is the slope of a line through all the kept samples. It is used
 * only when the ticks only rise, the two halves agree within 2%, no sample is
 * further from the line than 2% of the span, and it differs from the reported
 * period by more than 2% and by more than that scatter. Anything else keeps
 * the reported period and logs why, so a driver that reports correctly keeps
 * its value. The period feeds only the GPU phase stats (gpu_ts_readback); no
 * rendering reads it.
 */
#define GPU_TS_CAL_SPAN_NS 120000000LL
#define GPU_TS_CAL_GAP_US 300
#define GPU_TS_CAL_MAX_SAMPLES 1024
#define GPU_TS_CAL_MIN_SAMPLES 8

typedef struct GpuTsSample {
    uint64_t tick;
    int64_t mid_ns;
    int64_t width_ns;
} GpuTsSample;

/* Least-squares slope of CPU ns over ticks, both taken from the first sample
 * so the sums stay small. Returns 0 when the ticks do not spread. */
static double gpu_ts_slope(const GpuTsSample *s, int n)
{
    double mx = 0.0, my = 0.0, sxx = 0.0, sxy = 0.0;

    for (int i = 0; i < n; i++) {
        mx += (double)(s[i].tick - s[0].tick);
        my += (double)(s[i].mid_ns - s[0].mid_ns);
    }
    mx /= n;
    my /= n;
    for (int i = 0; i < n; i++) {
        double dx = (double)(s[i].tick - s[0].tick) - mx;
        double dy = (double)(s[i].mid_ns - s[0].mid_ns) - my;
        sxx += dx * dx;
        sxy += dx * dy;
    }
    return sxx > 0.0 ? sxy / sxx : 0.0;
}

/* The largest distance of a sample from the line of that slope, in ns. */
static double gpu_ts_scatter(const GpuTsSample *s, int n, double slope)
{
    double off = 0.0, worst = 0.0;

    for (int i = 0; i < n; i++) {
        off += (double)(s[i].mid_ns - s[0].mid_ns) -
               slope * (double)(s[i].tick - s[0].tick);
    }
    off /= n;
    for (int i = 0; i < n; i++) {
        double d = (double)(s[i].mid_ns - s[0].mid_ns) -
                   slope * (double)(s[i].tick - s[0].tick) - off;
        worst = MAX(worst, d < 0.0 ? -d : d);
    }
    return worst;
}

static void gpu_ts_calibrate(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    float reported = r->device_props.limits.timestampPeriod;

    r->gpu_ts_period_ns = reported;

    if (!NV2A_PERF_LOG) {
        VK_LOG_ERROR("init: GPU timestamps enabled (period=%.2f ns)",
                     reported);
        return;
    }

    VkQueryPoolCreateInfo ci = {
        .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
        .queryType = VK_QUERY_TYPE_TIMESTAMP,
        .queryCount = 1,
    };
    VkQueryPool pool;
    if (vkCreateQueryPool(r->device, &ci, NULL, &pool) != VK_SUCCESS) {
        VK_LOG_ERROR("init: GPU timestamp period %.3f ns (reported; "
                     "not measured: no query pool)", reported);
        return;
    }

    GpuTsSample *s = g_new(GpuTsSample, GPU_TS_CAL_MAX_SAMPLES);
    int n = 0, split = -1;
    bool rising = true;
    int64_t narrowest = INT64_MAX;
    int64_t start = get_clock();

    while (n < GPU_TS_CAL_MAX_SAMPLES) {
        int64_t elapsed = get_clock() - start;
        if (elapsed >= GPU_TS_CAL_SPAN_NS) {
            break;
        }
        bool gapped = elapsed >= GPU_TS_CAL_SPAN_NS / 2;
        if (gapped && split < 0) {
            split = n;
        }

        VkCommandBuffer cmd = pgraph_vk_begin_single_time_commands(pg);
        vkCmdResetQueryPool(cmd, pool, 0, 1);
        vkCmdWriteTimestamp(cmd, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, pool, 0);
        int64_t t0 = get_clock();
        pgraph_vk_end_single_time_commands(pg, cmd);
        int64_t t1 = get_clock();

        uint64_t tick;
        if (vkGetQueryPoolResults(r->device, pool, 0, 1, sizeof(tick), &tick,
                                  sizeof(tick), VK_QUERY_RESULT_64_BIT) ==
            VK_SUCCESS) {
            if (n > 0 && tick <= s[n - 1].tick) {
                rising = false;
            }
            s[n].tick = tick;
            s[n].mid_ns = t0 + (t1 - t0) / 2;
            s[n].width_ns = t1 - t0;
            narrowest = MIN(narrowest, s[n].width_ns);
            n++;
        }
        if (gapped) {
            g_usleep(GPU_TS_CAL_GAP_US);
        }
    }
    vkDestroyQueryPool(r->device, pool, NULL);

    /* Keep the narrow windows, and keep count of where the halves meet. */
    int taken = n, kept = 0, kept_split = 0;
    for (int i = 0; i < n; i++) {
        if (s[i].width_ns <= 4 * narrowest) {
            if (split >= 0 && i < split) {
                kept_split++;
            }
            s[kept++] = s[i];
        }
    }
    if (split < 0) {
        kept_split = kept;
    }

    const char *why = NULL;
    double measured = 0.0, err = 0.0, halves = 0.0, span_ns = 0.0;

    if (!rising) {
        why = "the counter went back or stood still";
    } else if (kept_split < GPU_TS_CAL_MIN_SAMPLES ||
               kept - kept_split < GPU_TS_CAL_MIN_SAMPLES) {
        why = "too few samples";
    } else {
        double first = gpu_ts_slope(s, kept_split);
        double second = gpu_ts_slope(s + kept_split, kept - kept_split);

        measured = gpu_ts_slope(s, kept);
        span_ns = (double)(s[kept - 1].mid_ns - s[0].mid_ns);
        if (measured <= 0.0 || first <= 0.0 || second <= 0.0 ||
            span_ns <= 0.0) {
            why = "no slope";
        } else {
            err = gpu_ts_scatter(s, kept, measured) / span_ns;
            halves = first > second ? first / second - 1.0
                                    : second / first - 1.0;
            if (halves > 0.02) {
                why = "the counter's rate changes with the GPU's idle gaps";
            } else if (err > 0.02) {
                why = "the samples do not lie on a line";
            }
        }
    }
    g_free(s);

    double ratio = measured > 0.0 ? measured / reported : 1.0;
    double dev = ratio > 1.0 ? ratio - 1.0 : 1.0 - ratio;
    bool use = !why && dev > MAX(0.02, err);

    if (use) {
        r->gpu_ts_period_ns = measured;
    }
    VK_LOG_ERROR("init: GPU timestamp period reported=%.3f ns measured=%.3f ns "
                 "(+-%.2f%%, span %.1f ms, samples %d of %d, halves differ "
                 "%.2f%%) using=%.3f ns (%s%s%s)",
                 reported, measured, err * 100.0, span_ns / 1e6, kept, taken,
                 halves * 100.0, r->gpu_ts_period_ns,
                 use ? "measured" : "reported",
                 why ? "; not measured: " : "", why ? why : "");
}

#if HAVE_EXTERNAL_MEMORY
static GloContext *g_gl_context;
#endif

void pgraph_vk_gl_make_context_current(void)
{
#if HAVE_EXTERNAL_MEMORY
    if (!g_gl_context) {
        g_gl_context = glo_context_create();
    }
    if (g_gl_context) {
        glo_set_current(g_gl_context);
    }
#endif
}

static void early_context_init(void)
{
#if HAVE_EXTERNAL_MEMORY
#ifdef __ANDROID__
    /*
     * On Android, only cache EGL share/config on the SDL thread here.
     * Create/bind the offscreen context later on the renderer thread.
     */
    glo_android_cache_current_egl_state();
#else
    g_gl_context = glo_context_create();
#endif
#endif
}

static void pgraph_vk_init(NV2AState *d, Error **errp)
{
    PGRAPHState *pg = &d->pgraph;

    pg->vk_renderer_state = (PGRAPHVkState *)g_malloc0(sizeof(PGRAPHVkState));
    pg->vk_renderer_state->nv2a = d;
    pg->vk_renderer_state->need_descriptor_rebind = true;
    pg->vk_renderer_state->deferred_downloads_frame = -1;

    pgraph_vk_debug_init();

    pgraph_vk_init_instance(pg, errp);
    if (*errp) {
        return;
    }

#if HAVE_EXTERNAL_MEMORY
    /*
     * After init_instance, not before: on desktop the FD interop extensions
     * are optional now, so whether they were actually enabled is only known
     * once the device exists. Asking earlier read a flag nobody had set yet.
     */
    bool use_external_memory = pgraph_vk_gl_external_memory_available() &&
                               pg->vk_renderer_state->external_memory_fd_enabled;
    if (!use_external_memory) {
#ifdef __ANDROID__
        __android_log_print(ANDROID_LOG_WARN, "hakuX",
                            "pgraph_vk_init: external memory interop unavailable, using download fallback");
#endif
    }
#ifdef __ANDROID__
    __android_log_print(ANDROID_LOG_INFO, "hakuX",
                        "pgraph_vk_init: external memory interop=%s",
                        use_external_memory ? "enabled" : "disabled");
#endif
    pg->vk_renderer_state->display.use_external_memory = use_external_memory;
#endif

    check_driver_identity_and_wipe_caches(pg->vk_renderer_state);

    VK_LOG_ERROR("init: render_thread");
    pgraph_vk_render_thread_init(pg->vk_renderer_state);
    VK_LOG_ERROR("init: command_buffers");
    pgraph_vk_init_command_buffers(pg);
    VK_LOG_ERROR("init: buffers");
    if (!pgraph_vk_init_buffers(d, errp)) {
        VK_LOG_ERROR("init: buffers FAILED");
        return;
    }
    VK_LOG_ERROR("init: surfaces");
    pgraph_vk_init_surfaces(pg);
    pgraph_vk_surface_image_pool_init(pg->vk_renderer_state);
    VK_LOG_ERROR("init: shaders");
    pgraph_vk_init_shaders(pg);
    VK_LOG_ERROR("init: pipelines");
    pgraph_vk_init_pipelines(pg);
#if OPT_ASYNC_COMPILE
    pgraph_vk_prebuild_start(pg);
#endif
    VK_LOG_ERROR("init: textures");
    pgraph_vk_init_textures(pg);
    pgraph_vk_texture_dump_init();
    pgraph_vk_texture_replace_init();
    VK_LOG_ERROR("init: reports");
    pgraph_vk_init_reports(pg);

    {
        PGRAPHVkState *r = pg->vk_renderer_state;
        if (r->device_props.limits.timestampComputeAndGraphics) {
            VkQueryPoolCreateInfo ts_ci = {
                .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
                .queryType = VK_QUERY_TYPE_TIMESTAMP,
                .queryCount = GPU_TS_QUERIES_PER_CB * NUM_SUBMIT_FRAMES,
            };
            VK_CHECK(vkCreateQueryPool(r->device, &ts_ci, NULL,
                                       &r->gpu_ts_pool));
            r->gpu_ts_supported = true;
            gpu_ts_calibrate(pg);
        } else {
            r->gpu_ts_supported = false;
            VK_LOG_ERROR("init: GPU timestamps not supported");
        }
    }

    VK_LOG_ERROR("init: compute");
    pgraph_vk_init_compute(pg);
    VK_LOG_ERROR("init: display");
    pgraph_vk_init_display(pg);

    pg->vk_renderer_state->vram_ram_addr = memory_region_get_ram_addr(d->vram);

    pgraph_vk_update_vertex_ram_buffer(&d->pgraph, 0, d->vram_ptr,
                                   memory_region_size(d->vram));

    pg->vk_renderer_state->frame_staging[0].vertex_ram_initialized = true;

    VK_LOG_ERROR("init: renderer_ready");

}

static void pgraph_vk_finalize(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;

    pgraph_vk_render_thread_shutdown(pg->vk_renderer_state);
    pgraph_vk_finalize_display(pg);
    pgraph_vk_finalize_compute(pg);

    {
        PGRAPHVkState *r = pg->vk_renderer_state;
        if (r->gpu_ts_supported) {
            vkDestroyQueryPool(r->device, r->gpu_ts_pool, NULL);
            r->gpu_ts_pool = VK_NULL_HANDLE;
        }
    }

    pgraph_vk_finalize_reports(pg);
    pgraph_vk_texture_replace_shutdown();
    pgraph_vk_texture_dump_shutdown();
    pgraph_vk_finalize_textures(pg);
#if OPT_ASYNC_COMPILE
    pgraph_vk_prebuild_stop(pg->vk_renderer_state);
#endif
    pgraph_vk_finalize_pipelines(pg);
    pgraph_vk_finalize_shaders(pg);
    pgraph_vk_finalize_surfaces(pg);
    pgraph_vk_surface_image_pool_drain(pg->vk_renderer_state);
    pgraph_vk_finalize_buffers(d);
    pgraph_vk_finalize_command_buffers(pg);
    pgraph_vk_finalize_instance(pg);

    g_free(pg->vk_renderer_state);
    pg->vk_renderer_state = NULL;

#if HAVE_EXTERNAL_MEMORY
    if (g_gl_context) {
        glo_context_destroy(g_gl_context);
        g_gl_context = NULL;
    }
#endif
}

static void pgraph_vk_process_pending(NV2AState *d)
{
    PGRAPHVkState *r = d->pgraph.vk_renderer_state;

    bool need_downloads = qatomic_read(&r->downloads_pending);
    bool need_dirty_dl = qatomic_read(&r->download_dirty_surfaces_pending);
    bool need_sync = qatomic_read(&d->pgraph.sync_pending);
    bool need_flush = qatomic_read(&d->pgraph.flush_pending);

    if (!need_downloads && !need_dirty_dl && !need_sync && !need_flush) {
        return;
    }

    qemu_mutex_unlock(&d->pfifo.lock);

    /* Batch all pending operations into a single render thread dispatch
     * with one completion event.  This eliminates 3 extra event
     * init/wait/destroy cycles and 3 extra render thread wake-ups. */
    QemuEvent pending_event;
    qemu_event_init(&pending_event, false);
    RenderCommand *cmd = g_new0(RenderCommand, 1);
    cmd->type = RCMD_PROCESS_PENDING;
    cmd->pending.downloads = need_downloads;
    cmd->pending.dirty_downloads = need_dirty_dl;
    cmd->pending.sync_display = need_sync;
    cmd->pending.flush = need_flush;
    cmd->pending.completion = &pending_event;
    pgraph_vk_render_thread_enqueue(r, cmd);
    qemu_event_wait(&pending_event);
    qemu_event_destroy(&pending_event);

    qemu_mutex_lock(&d->pfifo.lock);
}

#ifdef __ANDROID__
#define DIAG_LOG(...) __android_log_print(ANDROID_LOG_INFO, "hakuX-diag", __VA_ARGS__)
#else
#define DIAG_LOG(...) fprintf(stderr, "xemu-diag: " __VA_ARGS__)
#endif

static char rt_dump_dir[512] = "";

void nv2a_dbg_set_rt_dump_path(const char *dir)
{
    snprintf(rt_dump_dir, sizeof(rt_dump_dir), "%s", dir);
}

/* Download a surface's VkImage to VRAM using a standalone command buffer.
 * This is safe to call after pgraph_vk_finish when in_command_buffer is false,
 * unlike the normal download path which relies on nondraw commands + finish. */
static void diag_download_surface(NV2AState *d, PGRAPHState *pg,
                                  SurfaceBinding *surface)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    if (!surface || !surface->width || !surface->height) return;

    /* Only handle simple color surfaces (4bpp, no swizzle, no depth/stencil) */
    if (!surface->color || surface->swizzle) return;

    /* The copy below writes BUFFER_STAGING_DST at offset 0. A submitted
     * download batch (the flip's pre-download stays pending across draws
     * since #474) still has its copies there, and the caller's finish does
     * not complete a batch from an earlier frame slot. Retire it first, or
     * it later writes this surface's pixels into its own surfaces' VRAM. */
    pgraph_vk_download_surface_complete_deferred(d);

    VkCommandBuffer cmd = pgraph_vk_begin_single_time_commands(pg);

    /* Transition to TRANSFER_SRC */
    pgraph_vk_transition_image_layout(
        pg, cmd, surface->image, surface->host_fmt.vk_format,
        surface->image_layout, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);

    /* Copy image to staging buffer */
    StorageBuffer *staging = &r->storage_buffers[BUFFER_STAGING_DST];
    VkBufferImageCopy region = {
        .bufferOffset = 0,
        .bufferRowLength = surface->width,
        .bufferImageHeight = surface->height,
        .imageSubresource = {
            .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
            .layerCount = 1,
        },
        .imageExtent = { surface->width, surface->height, 1 },
    };
    unsigned int scaled_w = surface->width, scaled_h = surface->height;
    pgraph_apply_scaling_factor(pg, &scaled_w, &scaled_h);
    region.imageExtent.width = scaled_w;
    region.imageExtent.height = scaled_h;
    region.bufferRowLength = scaled_w;
    region.bufferImageHeight = scaled_h;
    vkCmdCopyImageToBuffer(cmd, surface->image,
                           VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           staging->buffer, 1, &region);

    /* Transition back to GENERAL */
    pgraph_vk_transition_image_layout(
        pg, cmd, surface->image, surface->host_fmt.vk_format,
        VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, VK_IMAGE_LAYOUT_GENERAL);
    surface->image_layout = VK_IMAGE_LAYOUT_GENERAL;

    /* Barrier: transfer writes visible to host reads */
    VkBufferMemoryBarrier barrier = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
        .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .buffer = staging->buffer,
        .size = (VkDeviceSize)scaled_w * scaled_h * surface->fmt.bytes_per_pixel,
    };
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         VK_PIPELINE_STAGE_HOST_BIT, 0, 0, NULL, 1,
                         &barrier, 0, NULL);

    pgraph_vk_end_single_time_commands(pg, cmd);

    /* Invalidate and copy to VRAM */
    size_t dl_size = (size_t)scaled_w * scaled_h * surface->fmt.bytes_per_pixel;
    vmaInvalidateAllocation(r->allocator, staging->allocation, 0, dl_size);

    uint8_t *dst = d->vram_ptr + surface->vram_addr;
    const uint8_t *src = staging->mapped;
    if (pg->surface_scale_factor == 1) {
        for (unsigned int y = 0; y < surface->height; y++) {
            memcpy(dst + y * surface->pitch,
                   src + y * surface->width * surface->fmt.bytes_per_pixel,
                   surface->width * surface->fmt.bytes_per_pixel);
        }
    } else {
        /* Downscale: just copy row by row from scaled dims */
        for (unsigned int y = 0; y < surface->height && y < scaled_h; y++) {
            memcpy(dst + y * surface->pitch,
                   src + y * scaled_w * surface->fmt.bytes_per_pixel,
                   surface->width * surface->fmt.bytes_per_pixel);
        }
    }
}

/* True only if the file was written. The frame dump files the image name and
 * charges its bytes on that answer: a zero bytes_per_pixel (which the caller's
 * width/height test does not cover) or an fopen failure used to be reported
 * only through DIAG_LOG, whose tag no dispatched run's logcat spec keeps, so
 * the dump named a file that was not there and shortened itself for a write
 * that never happened, with nothing in the run's log. */
static bool dump_surface_ppm(NV2AState *d, SurfaceBinding *surface,
                             const char *path)
{
    unsigned int w = surface->width;
    unsigned int h = surface->height;
    unsigned int bpp = surface->fmt.bytes_per_pixel;
    unsigned int pitch = surface->pitch;

    if (!w || !h || !bpp) {
        return false;
    }

    const uint8_t *vram = d->vram_ptr + surface->vram_addr;

    FILE *f = fopen(path, "wb");
    if (!f) {
        DIAG_LOG("dump_surface_ppm: cannot open %s (errno=%d)\n", path, errno);
        return false;
    }

    fprintf(f, "P6\n%u %u\n255\n", w, h);

    for (unsigned int y = 0; y < h; y++) {
        const uint8_t *row = vram + y * pitch;
        for (unsigned int x = 0; x < w; x++) {
            uint8_t rgb[3];
            if (bpp == 4) {
                rgb[0] = row[x * 4 + 2];
                rgb[1] = row[x * 4 + 1];
                rgb[2] = row[x * 4 + 0];
            } else if (bpp == 2) {
                uint16_t px = *(const uint16_t *)(row + x * 2);
                rgb[0] = (px >> 8) & 0xF8;
                rgb[1] = (px >> 3) & 0xFC;
                rgb[2] = (px << 3) & 0xF8;
            } else {
                rgb[0] = rgb[1] = rgb[2] = row[x * bpp];
            }
            fwrite(rgb, 1, 3, f);
        }
    }

    bool ok = ferror(f) == 0;
    if (fclose(f) != 0) {
        ok = false;
    }
    return ok;
}

/*
 * Multi-frame per-draw-call diagnostic capture
 *
 * Captures N consecutive frames with full render state, shader source,
 * and frame-to-frame diffs. Output is a single JSON session file designed
 * to be fed to Claude for rendering issue analysis.
 */

#include <time.h>

#define DIAG_MAX_DRAWS 4096
#define DIAG_MAX_FRAMES 64
#define DIAG_JSON_INITIAL_CAP (512 * 1024)

static volatile int diag_frame_pending = 0;
static volatile int diag_frame_active = 0;
static int diag_draw_index = 0;
static unsigned int diag_frame_num = 0;

/* Multi-frame state */
static int diag_frames_remaining = 0;
static int diag_total_frames = 0;
static int diag_current_frame_index = 0;
static unsigned int diag_session_id = 0;
static char diag_session_dir[700] = "";

static char *diag_json_buf = NULL;
static size_t diag_json_len = 0;
static size_t diag_json_cap = 0;

/* Per-draw fingerprint for frame diffs */
typedef struct DiagDrawFingerprint {
    uint64_t shader_hash;
    uint64_t state_hash;
} DiagDrawFingerprint;

static DiagDrawFingerprint diag_cur_fingerprints[DIAG_MAX_DRAWS];
static DiagDrawFingerprint diag_prev_fingerprints[DIAG_MAX_DRAWS];
static int diag_prev_draw_count = 0;

/* Diff accumulation buffer */
static char *diag_diff_buf = NULL;
static size_t diag_diff_len = 0;
static size_t diag_diff_cap = 0;
static bool diag_first_diff = true;

/* Shader source dedup table */
#define DIAG_MAX_SHADERS 512
typedef struct DiagShaderEntry {
    uint64_t hash;
    char *vsh_glsl;
    char *psh_glsl;
    char *geom_glsl;
} DiagShaderEntry;

static DiagShaderEntry diag_shaders[DIAG_MAX_SHADERS];
static int diag_shader_count = 0;

/* The live frame dump shares this file's per-draw hook but is otherwise a
 * separate instrument; see its header comment further down. Declared here
 * because the hook is defined above it. */
static void fdump_log_draw(NV2AState *d, PGRAPHState *pg, const char *type,
                           int count);

/* Per-frame JSON buffers (each frame's draw_calls array) */
static char **diag_frame_bufs = NULL;
static size_t *diag_frame_lens = NULL;
static unsigned int *diag_frame_nums = NULL;
static int *diag_frame_draw_counts = NULL;

void nv2a_dbg_trigger_diag_frames(int num_frames)
{
    if (num_frames < 1) num_frames = 1;
    if (num_frames > DIAG_MAX_FRAMES) num_frames = DIAG_MAX_FRAMES;
    DIAG_LOG("trigger_diag_frames called: num_frames=%d\n", num_frames);
    qatomic_set(&diag_frame_pending, num_frames);
    DIAG_LOG("diag_frame_pending set to %d\n", num_frames);
}

void nv2a_dbg_trigger_diag_frame(void)
{
    DIAG_LOG("trigger_diag_frame called (single frame)\n");
    nv2a_dbg_trigger_diag_frames(1);
}

bool nv2a_dbg_diag_frame_active(void)
{
    return qatomic_read(&diag_frame_active) != 0;
}

bool nv2a_dbg_diag_frame_pending(void)
{
    return qatomic_read(&diag_frame_pending) != 0;
}

static void diag_json_ensure(size_t needed)
{
    if (diag_json_len + needed <= diag_json_cap) {
        return;
    }
    size_t new_cap = diag_json_cap ? diag_json_cap * 2 : DIAG_JSON_INITIAL_CAP;
    while (new_cap < diag_json_len + needed) {
        new_cap *= 2;
    }
    diag_json_buf = g_realloc(diag_json_buf, new_cap);
    diag_json_cap = new_cap;
}

static void diag_json_append(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    va_list ap2;
    va_copy(ap2, ap);
    int n = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    if (n > 0) {
        diag_json_ensure((size_t)n + 1);
        vsnprintf(diag_json_buf + diag_json_len, (size_t)n + 1, fmt, ap2);
        diag_json_len += (size_t)n;
    }
    va_end(ap2);
}

static void diag_diff_ensure(size_t needed)
{
    if (diag_diff_len + needed <= diag_diff_cap) {
        return;
    }
    size_t new_cap = diag_diff_cap ? diag_diff_cap * 2 : 4096;
    while (new_cap < diag_diff_len + needed) {
        new_cap *= 2;
    }
    diag_diff_buf = g_realloc(diag_diff_buf, new_cap);
    diag_diff_cap = new_cap;
}

static void diag_diff_append(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    va_list ap2;
    va_copy(ap2, ap);
    int n = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    if (n > 0) {
        diag_diff_ensure((size_t)n + 1);
        vsnprintf(diag_diff_buf + diag_diff_len, (size_t)n + 1, fmt, ap2);
        diag_diff_len += (size_t)n;
    }
    va_end(ap2);
}

/* JSON-escape a string (handles \n, \t, \\, \", control chars) */
static void diag_json_append_escaped(const char *s)
{
    if (!s) {
        diag_json_append("null");
        return;
    }
    diag_json_append("\"");
    for (const char *p = s; *p; p++) {
        switch (*p) {
        case '"':  diag_json_append("\\\""); break;
        case '\\': diag_json_append("\\\\"); break;
        case '\n': diag_json_append("\\n"); break;
        case '\r': diag_json_append("\\r"); break;
        case '\t': diag_json_append("\\t"); break;
        default:
            if ((unsigned char)*p < 0x20) {
                diag_json_append("\\u%04x", (unsigned char)*p);
            } else {
                diag_json_ensure(2);
                diag_json_buf[diag_json_len++] = *p;
                diag_json_buf[diag_json_len] = '\0';
            }
        }
    }
    diag_json_append("\"");
}

static const char *diag_get_dump_base_dir(void)
{
    const char *dir;
    if (rt_dump_dir[0]) {
        dir = rt_dump_dir;
    } else {
        dir = xemu_settings_get_base_path();
    }
    DIAG_LOG("dump base dir: %s\n", dir ? dir : "(null)");
    return dir;
}

static void diag_init_session(unsigned int start_frame, int num_frames)
{
    DIAG_LOG("init_session: start_frame=%u num_frames=%d\n",
             start_frame, num_frames);

    diag_session_id = start_frame;
    diag_total_frames = num_frames;
    diag_frames_remaining = num_frames;
    diag_current_frame_index = 0;
    diag_shader_count = 0;
    diag_prev_draw_count = 0;
    diag_diff_len = 0;
    diag_first_diff = true;

    /* Create session directory */
    const char *base = diag_get_dump_base_dir();
    snprintf(diag_session_dir, sizeof(diag_session_dir),
             "%s/diag_session_%u", base, diag_session_id);

    /* Recursive mkdir — create all intermediate directories */
    {
        char tmp[700];
        snprintf(tmp, sizeof(tmp), "%s", diag_session_dir);
        for (char *p = tmp + 1; *p; p++) {
            if (*p == '/') {
                *p = '\0';
                int r = mkdir(tmp, 0755);
                DIAG_LOG("mkdir '%s' -> %d (errno=%d)\n", tmp, r,
                         (r < 0 && errno != EEXIST) ? errno : 0);
                *p = '/';
            }
        }
        int r = mkdir(tmp, 0755);
        DIAG_LOG("mkdir '%s' -> %d (errno=%d)\n", tmp, r,
                 (r < 0 && errno != EEXIST) ? errno : 0);
    }

    /* Allocate per-frame buffers */
    diag_frame_bufs = g_new0(char *, num_frames);
    diag_frame_lens = g_new0(size_t, num_frames);
    diag_frame_nums = g_new0(unsigned int, num_frames);
    diag_frame_draw_counts = g_new0(int, num_frames);

    DIAG_LOG("init_session complete, session_dir=%s\n", diag_session_dir);
}

static void diag_cleanup_session(void)
{
    if (diag_frame_bufs) {
        for (int i = 0; i < diag_total_frames; i++) {
            g_free(diag_frame_bufs[i]);
        }
        g_free(diag_frame_bufs);
        diag_frame_bufs = NULL;
    }
    g_free(diag_frame_lens);
    diag_frame_lens = NULL;
    g_free(diag_frame_nums);
    diag_frame_nums = NULL;
    g_free(diag_frame_draw_counts);
    diag_frame_draw_counts = NULL;

    for (int i = 0; i < diag_shader_count; i++) {
        g_free(diag_shaders[i].vsh_glsl);
        g_free(diag_shaders[i].psh_glsl);
        g_free(diag_shaders[i].geom_glsl);
    }
    diag_shader_count = 0;
}

static int diag_find_or_add_shader(uint64_t hash, const char *vsh,
                                    const char *psh, const char *geom)
{
    for (int i = 0; i < diag_shader_count; i++) {
        if (diag_shaders[i].hash == hash) {
            return i;
        }
    }
    if (diag_shader_count >= DIAG_MAX_SHADERS) {
        return -1;
    }
    int idx = diag_shader_count++;
    diag_shaders[idx].hash = hash;
    diag_shaders[idx].vsh_glsl = vsh ? g_strdup(vsh) : NULL;
    diag_shaders[idx].psh_glsl = psh ? g_strdup(psh) : NULL;
    diag_shaders[idx].geom_glsl = geom ? g_strdup(geom) : NULL;
    return idx;
}

static void diag_write_session_json(void)
{
    DIAG_LOG("write_session_json: building JSON, %d frames, %d shaders\n",
             diag_total_frames, diag_shader_count);

    /* Build final JSON into diag_json_buf */
    diag_json_len = 0;

    diag_json_append("{\n");

    /* capture_info */
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    char timestamp[64];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%S", tm);

    diag_json_append(
        "  \"capture_info\": {\n"
        "    \"frame_count\": %d,\n"
        "    \"start_frame\": %u,\n"
        "    \"timestamp\": \"%s\"\n"
        "  },\n",
        diag_total_frames, diag_session_id, timestamp);

    /* shaders */
    diag_json_append("  \"shaders\": {\n");
    for (int i = 0; i < diag_shader_count; i++) {
        diag_json_append("%s    \"0x%016" PRIx64 "\": {\n",
                         i > 0 ? ",\n" : "",
                         diag_shaders[i].hash);
        diag_json_append("      \"vertex\": ");
        diag_json_append_escaped(diag_shaders[i].vsh_glsl);
        diag_json_append(",\n      \"fragment\": ");
        diag_json_append_escaped(diag_shaders[i].psh_glsl);
        diag_json_append(",\n      \"geometry\": ");
        diag_json_append_escaped(diag_shaders[i].geom_glsl);
        diag_json_append("\n    }");
    }
    diag_json_append("\n  },\n");

    /* frames */
    diag_json_append("  \"frames\": [\n");
    for (int i = 0; i < diag_total_frames; i++) {
        diag_json_append(
            "%s    {\n"
            "      \"frame_number\": %u,\n"
            "      \"frame_index\": %d,\n"
            "      \"draw_count\": %d,\n"
            "      \"draw_calls\": [\n",
            i > 0 ? ",\n" : "",
            diag_frame_nums[i], i, diag_frame_draw_counts[i]);
        if (diag_frame_bufs[i] && diag_frame_lens[i] > 0) {
            diag_json_ensure(diag_frame_lens[i]);
            memcpy(diag_json_buf + diag_json_len, diag_frame_bufs[i],
                   diag_frame_lens[i]);
            diag_json_len += diag_frame_lens[i];
        }
        diag_json_append("\n      ]\n    }");
    }
    diag_json_append("\n  ],\n");

    /* frame_diffs */
    diag_json_append("  \"frame_diffs\": [\n");
    if (diag_diff_buf && diag_diff_len > 0) {
        diag_json_ensure(diag_diff_len);
        memcpy(diag_json_buf + diag_json_len, diag_diff_buf, diag_diff_len);
        diag_json_len += diag_diff_len;
    }
    diag_json_append("\n  ]\n}\n");

    /* Write to file */
    char path[800];
    snprintf(path, sizeof(path), "%s/diag_session.json", diag_session_dir);

    DIAG_LOG("writing JSON to: %s\n", path);
    FILE *f = fopen(path, "w");
    if (!f) {
        DIAG_LOG("ERROR: cannot open %s for writing (errno=%d)\n", path, errno);
        return;
    }
    if (diag_json_buf && diag_json_len > 0) {
        size_t written = fwrite(diag_json_buf, 1, diag_json_len, f);
        DIAG_LOG("fwrite: %zu of %zu bytes written\n", written, diag_json_len);
    }
    fclose(f);
    DIAG_LOG("wrote %zu bytes to %s\n", diag_json_len, path);
}

static const char *diag_stencil_op_name(uint32_t op)
{
    switch (op) {
    case 0x1: return "KEEP";
    case 0x2: return "ZERO";
    case 0x3: return "REPLACE";
    case 0x4: return "INCRSAT";
    case 0x5: return "DECRSAT";
    case 0x6: return "INVERT";
    case 0x7: return "INCR";
    case 0x8: return "DECR";
    default:  return "?";
    }
}

static const char *diag_compare_func_name(uint32_t f)
{
    switch (f) {
    case 0: return "NEVER";
    case 1: return "LESS";
    case 2: return "EQUAL";
    case 3: return "LEQUAL";
    case 4: return "GREATER";
    case 5: return "NOTEQUAL";
    case 6: return "GEQUAL";
    case 7: return "ALWAYS";
    default: return "?";
    }
}

static const char *diag_blend_factor_name(uint32_t f)
{
    switch (f) {
    case 0:  return "ZERO";
    case 1:  return "ONE";
    case 2:  return "SRC_COLOR";
    case 3:  return "INV_SRC_COLOR";
    case 4:  return "SRC_ALPHA";
    case 5:  return "INV_SRC_ALPHA";
    case 6:  return "DST_ALPHA";
    case 7:  return "INV_DST_ALPHA";
    case 8:  return "DST_COLOR";
    case 9:  return "INV_DST_COLOR";
    case 10: return "SRC_ALPHA_SAT";
    case 12: return "CONST_COLOR";
    case 13: return "INV_CONST_COLOR";
    case 14: return "CONST_ALPHA";
    case 15: return "INV_CONST_ALPHA";
    default: return "?";
    }
}

static const char *diag_blend_eq_name(uint32_t eq)
{
    switch (eq) {
    case 0: return "SUB";
    case 1: return "REV_SUB";
    case 2: return "ADD";
    case 3: return "MIN";
    case 4: return "MAX";
    case 5: return "REV_SUB";
    case 6: return "ADD";
    default: return "?";
    }
}

static const char *diag_prim_name(int mode)
{
    switch (mode) {
    case 1: return "POINTS";
    case 2: return "LINES";
    case 3: return "LINE_LOOP";
    case 4: return "LINE_STRIP";
    case 5: return "TRIANGLES";
    case 6: return "TRIANGLE_STRIP";
    case 7: return "TRIANGLE_FAN";
    case 8: return "QUADS";
    case 9: return "QUAD_STRIP";
    case 10: return "POLYGON";
    default: return "?";
    }
}

void nv2a_diag_log_clear(NV2AState *d, PGRAPHState *pg,
                          uint32_t parameter,
                          unsigned int xmin, unsigned int ymin,
                          unsigned int xmax, unsigned int ymax,
                          bool write_color, bool write_zeta)
{
    if (!qatomic_read(&diag_frame_active)) {
        return;
    }
    if (diag_draw_index >= DIAG_MAX_DRAWS) {
        return;
    }

    PGRAPHVkState *r = pg->vk_renderer_state;
    int idx = diag_draw_index++;

    DIAG_LOG("log_clear: frame_idx=%d draw=%d rect=(%u,%u)-(%u,%u) color=%d zeta=%d\n",
             diag_current_frame_index, idx, xmin, ymin, xmax, ymax,
             write_color, write_zeta);

    diag_json_append(
        "%s        {\n"
        "          \"draw_index\": %d,\n"
        "          \"type\": \"clear\",\n"
        "          \"clear_color\": %s,\n"
        "          \"clear_zeta\": %s,\n"
        "          \"clear_rect\": {\"xmin\": %u, \"ymin\": %u, "
                                   "\"xmax\": %u, \"ymax\": %u},\n",
        idx > 0 ? ",\n" : "",
        idx,
        write_color ? "true" : "false",
        write_zeta ? "true" : "false",
        xmin, ymin, xmax, ymax
    );

    if (r->color_binding) {
        diag_json_append(
            "          \"color_surface\": {"
                "\"format\": %u, \"width\": %u, \"height\": %u, "
                "\"pitch\": %u, \"bpp\": %u},\n",
            r->color_binding->shape.color_format,
            r->color_binding->width, r->color_binding->height,
            r->color_binding->pitch, r->color_binding->fmt.bytes_per_pixel
        );
    } else {
        diag_json_append("          \"color_surface\": null,\n");
    }

    if (r->zeta_binding) {
        diag_json_append(
            "          \"zeta_surface\": {"
                "\"format\": %u, \"width\": %u, \"height\": %u, "
                "\"pitch\": %u, \"bpp\": %u}\n",
            r->zeta_binding->shape.zeta_format,
            r->zeta_binding->width, r->zeta_binding->height,
            r->zeta_binding->pitch, r->zeta_binding->fmt.bytes_per_pixel
        );
    } else {
        diag_json_append("          \"zeta_surface\": null\n");
    }

    diag_json_append("        }");

    /* Store a fingerprint for diff tracking */
    memset(&diag_cur_fingerprints[idx], 0, sizeof(diag_cur_fingerprints[idx]));
    diag_cur_fingerprints[idx].state_hash = parameter;
}

void nv2a_diag_log_blit(NV2AState *d, PGRAPHState *pg)
{
    if (!qatomic_read(&diag_frame_active)) {
        return;
    }
    if (diag_draw_index >= DIAG_MAX_DRAWS) {
        return;
    }

    int idx = diag_draw_index++;
    ImageBlitState *ib = &pg->image_blit;
    ContextSurfaces2DState *cs = &pg->context_surfaces_2d;

    DIAG_LOG("log_blit: frame_idx=%d draw=%d src=(%u,%u) dst=(%u,%u) size=%ux%u\n",
             diag_current_frame_index, idx,
             ib->in_x, ib->in_y, ib->out_x, ib->out_y,
             ib->width, ib->height);

    diag_json_append(
        "%s        {\n"
        "          \"draw_index\": %d,\n"
        "          \"type\": \"blit\",\n"
        "          \"src\": {\"x\": %u, \"y\": %u},\n"
        "          \"dst\": {\"x\": %u, \"y\": %u},\n"
        "          \"size\": {\"w\": %u, \"h\": %u},\n"
        "          \"color_format\": %u,\n"
        "          \"src_pitch\": %u,\n"
        "          \"dst_pitch\": %u\n"
        "        }",
        idx > 0 ? ",\n" : "",
        idx,
        ib->in_x, ib->in_y,
        ib->out_x, ib->out_y,
        ib->width, ib->height,
        cs->color_format,
        cs->source_pitch,
        cs->dest_pitch
    );

    memset(&diag_cur_fingerprints[idx], 0, sizeof(diag_cur_fingerprints[idx]));
    diag_cur_fingerprints[idx].state_hash = ib->width | ((uint64_t)ib->height << 32);
}

void nv2a_diag_log_draw_call(NV2AState *d, PGRAPHState *pg,
                             const char *type, int count)
{
    /* The live dump runs first and independently of the diag capture: when a
     * run arms both (marker spec "diag"), the same draws are recorded by both
     * instruments and the live records show the serialisation the capture
     * imposes. When only the live dump is armed, the function returns below
     * before anything calls pgraph_vk_finish. */
    if (nv2a_dbg_framedump_active()) {
        fdump_log_draw(d, pg, type, count);
    }

    if (!qatomic_read(&diag_frame_active)) {
        return;
    }

    if (diag_draw_index >= DIAG_MAX_DRAWS) {
        return;
    }

    PGRAPHVkState *r = pg->vk_renderer_state;
    int idx = diag_draw_index++;

    if (idx == 0 || (idx % 100) == 0) {
        DIAG_LOG("log_draw_call: frame_idx=%d draw=%d type=%s count=%d\n",
                 diag_current_frame_index, idx, type, count);
    }

    uint32_t control_0 = pgraph_vk_reg_r(pg, NV_PGRAPH_CONTROL_0);
    uint32_t control_1 = pgraph_vk_reg_r(pg, NV_PGRAPH_CONTROL_1);
    uint32_t control_2 = pgraph_vk_reg_r(pg, NV_PGRAPH_CONTROL_2);
    uint32_t blend_reg = pgraph_vk_reg_r(pg, NV_PGRAPH_BLEND);
    uint32_t setupraster = pgraph_vk_reg_r(pg, NV_PGRAPH_SETUPRASTER);

    bool blend_en    = blend_reg & NV_PGRAPH_BLEND_EN;
    uint32_t sfactor = GET_MASK(blend_reg, NV_PGRAPH_BLEND_SFACTOR);
    uint32_t dfactor = GET_MASK(blend_reg, NV_PGRAPH_BLEND_DFACTOR);
    uint32_t blend_eq = GET_MASK(blend_reg, NV_PGRAPH_BLEND_EQN);

    bool depth_test  = control_0 & NV_PGRAPH_CONTROL_0_ZENABLE;
    bool depth_write = !!(control_0 & NV_PGRAPH_CONTROL_0_ZWRITEENABLE);
    uint32_t zfunc   = GET_MASK(control_0, NV_PGRAPH_CONTROL_0_ZFUNC);

    bool stencil_test = control_1 & NV_PGRAPH_CONTROL_1_STENCIL_TEST_ENABLE;
    uint32_t stencil_func = GET_MASK(control_1, NV_PGRAPH_CONTROL_1_STENCIL_FUNC);
    uint32_t stencil_ref  = GET_MASK(control_1, NV_PGRAPH_CONTROL_1_STENCIL_REF);
    uint32_t stencil_mask_read  = GET_MASK(control_1,
                                           NV_PGRAPH_CONTROL_1_STENCIL_MASK_READ);
    uint32_t stencil_mask_write = GET_MASK(control_1,
                                           NV_PGRAPH_CONTROL_1_STENCIL_MASK_WRITE);
    uint32_t op_fail  = GET_MASK(control_2, NV_PGRAPH_CONTROL_2_STENCIL_OP_FAIL);
    uint32_t op_zfail = GET_MASK(control_2, NV_PGRAPH_CONTROL_2_STENCIL_OP_ZFAIL);
    uint32_t op_zpass = GET_MASK(control_2, NV_PGRAPH_CONTROL_2_STENCIL_OP_ZPASS);

    bool mask_r = !!(control_0 & NV_PGRAPH_CONTROL_0_RED_WRITE_ENABLE);
    bool mask_g = !!(control_0 & NV_PGRAPH_CONTROL_0_GREEN_WRITE_ENABLE);
    bool mask_b = !!(control_0 & NV_PGRAPH_CONTROL_0_BLUE_WRITE_ENABLE);
    bool mask_a = !!(control_0 & NV_PGRAPH_CONTROL_0_ALPHA_WRITE_ENABLE);

    bool cull_en = !!(setupraster & NV_PGRAPH_SETUPRASTER_CULLENABLE);
    uint32_t cull_face = GET_MASK(setupraster, NV_PGRAPH_SETUPRASTER_CULLCTRL);
    bool front_ccw = !!(setupraster & NV_PGRAPH_SETUPRASTER_FRONTFACE);

    const char *cull_str = "NONE";
    if (cull_en) {
        switch (cull_face) {
        case 1: cull_str = "FRONT"; break;
        case 2: cull_str = "BACK";  break;
        case 3: cull_str = "BOTH";  break;
        }
    }

    /* Compute shader hash and capture source */
    uint64_t shader_hash = 0;
    if (r->shader_binding) {
        shader_hash = fast_hash((const uint8_t *)&r->shader_binding->state,
                                sizeof(ShaderState));
        const char *vsh_src = (r->shader_binding->vsh.module_info &&
                               r->shader_binding->vsh.module_info->glsl)
                              ? r->shader_binding->vsh.module_info->glsl : NULL;
        const char *psh_src = (r->shader_binding->psh.module_info &&
                               r->shader_binding->psh.module_info->glsl)
                              ? r->shader_binding->psh.module_info->glsl : NULL;
        const char *geom_src = (r->shader_binding->geom.module_info &&
                                r->shader_binding->geom.module_info->glsl)
                               ? r->shader_binding->geom.module_info->glsl : NULL;
        diag_find_or_add_shader(shader_hash, vsh_src, psh_src, geom_src);
    }

    /* Compute state fingerprint for diff detection.
     * Must memset to zero to avoid padding bytes causing false diffs. */
    struct {
        uint32_t control_0, control_1, control_2, blend_reg, setupraster;
        uint32_t color_fmt, zeta_fmt;
        uint32_t color_w, color_h, zeta_w, zeta_h;
        uint32_t tex_fmt[NV2A_MAX_TEXTURES];
        int prim_mode;
    } state_block;
    memset(&state_block, 0, sizeof(state_block));
    state_block.control_0 = control_0;
    state_block.control_1 = control_1;
    state_block.control_2 = control_2;
    state_block.blend_reg = blend_reg;
    state_block.setupraster = setupraster;
    state_block.color_fmt = r->color_binding ? r->color_binding->shape.color_format : 0;
    state_block.zeta_fmt = r->zeta_binding ? r->zeta_binding->shape.zeta_format : 0;
    state_block.color_w = r->color_binding ? r->color_binding->width : 0;
    state_block.color_h = r->color_binding ? r->color_binding->height : 0;
    state_block.zeta_w = r->zeta_binding ? r->zeta_binding->width : 0;
    state_block.zeta_h = r->zeta_binding ? r->zeta_binding->height : 0;
    state_block.prim_mode = pg->primitive_mode;
    for (int i = 0; i < NV2A_MAX_TEXTURES; i++) {
        state_block.tex_fmt[i] = pgraph_vk_reg_r(pg, NV_PGRAPH_TEXFMT0 + i * 4);
    }
    diag_cur_fingerprints[idx].shader_hash = shader_hash;
    diag_cur_fingerprints[idx].state_hash =
        fast_hash((const uint8_t *)&state_block, sizeof(state_block));

    diag_json_append(
        "%s        {\n"
        "          \"draw_index\": %d,\n"
        "          \"type\": \"%s\",\n"
        "          \"count\": %d,\n"
        "          \"primitive_mode\": \"%s\",\n"
        "          \"shader_hash\": \"0x%016" PRIx64 "\",\n"
        "          \"blend\": {"
            "\"enabled\": %s, \"src\": \"%s\", \"dst\": \"%s\", "
            "\"eq\": \"%s\"},\n"
        "          \"depth\": {"
            "\"test\": %s, \"write\": %s, \"func\": \"%s\"},\n"
        "          \"stencil\": {"
            "\"test\": %s, \"func\": \"%s\", \"ref\": %u, "
            "\"mask_read\": %u, \"mask_write\": %u, "
            "\"op_fail\": \"%s\", \"op_zfail\": \"%s\", "
            "\"op_zpass\": \"%s\"},\n"
        "          \"color_write_mask\": {"
            "\"r\": %s, \"g\": %s, \"b\": %s, \"a\": %s},\n"
        "          \"cull\": {"
            "\"enabled\": %s, \"face\": \"%s\", \"front_ccw\": %s},\n",
        idx > 0 ? ",\n" : "",
        idx,
        type,
        count,
        diag_prim_name(pg->primitive_mode),
        shader_hash,
        blend_en ? "true" : "false",
        diag_blend_factor_name(sfactor),
        diag_blend_factor_name(dfactor),
        diag_blend_eq_name(blend_eq),
        depth_test ? "true" : "false",
        depth_write ? "true" : "false",
        diag_compare_func_name(zfunc),
        stencil_test ? "true" : "false",
        diag_compare_func_name(stencil_func),
        stencil_ref, stencil_mask_read, stencil_mask_write,
        diag_stencil_op_name(op_fail),
        diag_stencil_op_name(op_zfail),
        diag_stencil_op_name(op_zpass),
        mask_r ? "true" : "false",
        mask_g ? "true" : "false",
        mask_b ? "true" : "false",
        mask_a ? "true" : "false",
        cull_en ? "true" : "false",
        cull_str,
        front_ccw ? "true" : "false"
    );

    if (r->color_binding) {
        diag_json_append(
            "          \"color_surface\": {"
                "\"format\": %u, \"width\": %u, \"height\": %u, "
                "\"pitch\": %u, \"bpp\": %u},\n",
            r->color_binding->shape.color_format,
            r->color_binding->width, r->color_binding->height,
            r->color_binding->pitch, r->color_binding->fmt.bytes_per_pixel
        );
    } else {
        diag_json_append("          \"color_surface\": null,\n");
    }

    if (r->zeta_binding) {
        diag_json_append(
            "          \"zeta_surface\": {"
                "\"format\": %u, \"width\": %u, \"height\": %u, "
                "\"pitch\": %u, \"bpp\": %u},\n",
            r->zeta_binding->shape.zeta_format,
            r->zeta_binding->width, r->zeta_binding->height,
            r->zeta_binding->pitch, r->zeta_binding->fmt.bytes_per_pixel
        );
    } else {
        diag_json_append("          \"zeta_surface\": null,\n");
    }

    diag_json_append("          \"textures\": [");
    for (int i = 0; i < NV2A_MAX_TEXTURES; i++) {
        bool tex_en = pgraph_is_texture_enabled(pg, i);
        /* Coordinate state for this stage: texgen modes from CSV1 and the
         * texture matrix from the transform constant file. */
        unsigned int tg[4] = { 0, 0, 0, 0 };
        float mat[16] = { 0 };
        {
            static const unsigned int matbase[4] = {
                NV_IGRAPH_XF_XFCTX_T0MAT, NV_IGRAPH_XF_XFCTX_T1MAT,
                NV_IGRAPH_XF_XFCTX_T2MAT, NV_IGRAPH_XF_XFCTX_T3MAT,
            };
            unsigned int csv = (i < 2) ? NV_PGRAPH_CSV1_A : NV_PGRAPH_CSV1_B;
            unsigned int msk[4] = {
                (i % 2) ? NV_PGRAPH_CSV1_A_T1_S : NV_PGRAPH_CSV1_A_T0_S,
                (i % 2) ? NV_PGRAPH_CSV1_A_T1_T : NV_PGRAPH_CSV1_A_T0_T,
                (i % 2) ? NV_PGRAPH_CSV1_A_T1_R : NV_PGRAPH_CSV1_A_T0_R,
                (i % 2) ? NV_PGRAPH_CSV1_A_T1_Q : NV_PGRAPH_CSV1_A_T0_Q,
            };
            for (int j = 0; j < 4; j++) {
                tg[j] = GET_MASK(pgraph_reg_r(pg, csv), msk[j]);
            }
            for (int row = 0; row < 4; row++) {
                for (int c = 0; c < 4; c++) {
                    uint32_t w = pg->vsh_constants[matbase[i] + row][c];
                    memcpy(&mat[row * 4 + c], &w, sizeof(float));
                }
            }
        }
        uint32_t tex_fmt = pgraph_vk_reg_r(pg, NV_PGRAPH_TEXFMT0 + i * 4);
        unsigned int color_format = GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_COLOR);
        unsigned int dimensionality = GET_MASK(tex_fmt,
                                               NV_PGRAPH_TEXFMT0_DIMENSIONALITY);
        unsigned int log_w = GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_BASE_SIZE_U);
        unsigned int log_h = GET_MASK(tex_fmt, NV_PGRAPH_TEXFMT0_BASE_SIZE_V);
        uint32_t tex_addr = pgraph_vk_reg_r(pg, NV_PGRAPH_TEXADDRESS0 + i * 4);
        unsigned int addru = GET_MASK(tex_addr, NV_PGRAPH_TEXADDRESS0_ADDRU);
        unsigned int addrv = (tex_addr >> 8) & 0x7;
        uint32_t border_color = pgraph_vk_reg_r(pg,
                                    NV_PGRAPH_BORDERCOLOR0 + i * 4);

        static const char *addr_names[] = {
            "?", "WRAP", "MIRROR", "CLAMP_TO_EDGE", "BORDER", "CLAMP_OGL"
        };
        const char *addru_name = addru < 6 ? addr_names[addru] : "?";
        const char *addrv_name = addrv < 6 ? addr_names[addrv] : "?";

        /* Report actual VkFormat and whether native BC was used */
        const char *vk_fmt_name = "RGBA8";
        bool is_native_bc = false;
        TextureBinding *tb = r->texture_bindings[i];
        if (tb && tb->image != VK_NULL_HANDLE) {
            VkFormat fmt = tb->image_config.format;
            if (fmt == VK_FORMAT_BC1_RGBA_UNORM_BLOCK) {
                vk_fmt_name = "BC1"; is_native_bc = true;
            } else if (fmt == VK_FORMAT_BC2_UNORM_BLOCK) {
                vk_fmt_name = "BC2"; is_native_bc = true;
            } else if (fmt == VK_FORMAT_BC3_UNORM_BLOCK) {
                vk_fmt_name = "BC3"; is_native_bc = true;
            } else if (fmt == VK_FORMAT_B8G8R8A8_UNORM) {
                vk_fmt_name = "BGRA8";
            }
        }

        unsigned int mip_levels = GET_MASK(tex_fmt,
                                           NV_PGRAPH_TEXFMT0_MIPMAP_LEVELS);

        diag_json_append(
            "%s{\"stage\": %d, \"enabled\": %s, \"color_format\": %u, "
            "\"dim\": %u, \"width\": %u, \"height\": %u, "
            "\"levels\": %u, "
            "\"vk_format\": \"%s\", \"native_bc\": %s, "
            "\"addru\": \"%s\", \"addrv\": \"%s\", "
            "\"border_color\": \"0x%08x\", "
            /* Coordinate state. Everything else about a draw was already
             * here, which is why chasing Galleon's shearing ground one field
             * at a time was wasted effort -- but the vertex side was not.
             * A matrix left over from another material shears the sampling
             * while every flag above stays put, so record the enable, the
             * four texgen modes and the matrix itself. */
            "\"matrix_enable\": %s, "
            "\"texgen\": [%u, %u, %u, %u], "
            "\"matrix\": [%.6f, %.6f, %.6f, %.6f, %.6f, %.6f, %.6f, %.6f, "
            "%.6f, %.6f, %.6f, %.6f, %.6f, %.6f, %.6f, %.6f]}",
            i > 0 ? ", " : "",
            i,
            tex_en ? "true" : "false",
            color_format,
            dimensionality,
            1u << log_w, 1u << log_h,
            mip_levels,
            vk_fmt_name, is_native_bc ? "true" : "false",
            addru_name, addrv_name,
            border_color,
            pg->texture_matrix_enable[i] ? "true" : "false",
            tg[0], tg[1], tg[2], tg[3],
            mat[0], mat[1], mat[2], mat[3],
            mat[4], mat[5], mat[6], mat[7],
            mat[8], mat[9], mat[10], mat[11],
            mat[12], mat[13], mat[14], mat[15]
        );
    }
    diag_json_append("],\n");

    /* Dump combiner constants (c0_0..c1_8) from registers */
    diag_json_append("          \"combiner_constants\": [");
    for (int i = 0; i < 9; i++) {
        uint32_t factor0, factor1;
        if (i == 8) {
            factor0 = pgraph_vk_reg_r(pg, NV_PGRAPH_SPECFOGFACTOR0);
            factor1 = pgraph_vk_reg_r(pg, NV_PGRAPH_SPECFOGFACTOR1);
        } else {
            factor0 = pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINEFACTOR0 + i * 4);
            factor1 = pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINEFACTOR1 + i * 4);
        }
        float c0[4], c1[4];
        pgraph_argb_pack32_to_rgba_float(factor0, c0);
        pgraph_argb_pack32_to_rgba_float(factor1, c1);
        diag_json_append(
            "%s{\"stage\": %d, "
            "\"c0\": [%.4f, %.4f, %.4f, %.4f], "
            "\"c1\": [%.4f, %.4f, %.4f, %.4f]}",
            i > 0 ? ", " : "", i,
            c0[0], c0[1], c0[2], c0[3],
            c1[0], c1[1], c1[2], c1[3]);
    }
    diag_json_append("],\n");

    /* Per-draw surface dumps.
     *
     * After pgraph_vk_finish, in_command_buffer is false. The normal
     * download path (download_surface_to_buffer) records into nondraw
     * commands then calls pgraph_vk_finish again, but that second finish
     * is a no-op when in_command_buffer is false — the copy never submits.
     *
     * Use diag_download_surface which creates a standalone single-time
     * command buffer, independent of the main rendering flow. */
    pgraph_vk_finish(pg, VK_FINISH_REASON_SURFACE_DOWN);

    {
        char color_fname[128] = "";
        char depth_fname[128] = "";

        if (r->color_binding) {
            diag_download_surface(d, pg, r->color_binding);
            snprintf(color_fname, sizeof(color_fname),
                     "f%d_draw%d_color.ppm", diag_current_frame_index, idx);
            char path[800];
            snprintf(path, sizeof(path), "%s/%s", diag_session_dir, color_fname);
            dump_surface_ppm(d, r->color_binding, path);
        }

        /* Depth surfaces use complex formats (D24S8, etc.) that need
         * compute shader conversion — skip per-draw depth dumps for now
         * to keep the diagnostic path simple and reliable. */
        if (r->zeta_binding) {
            /* TODO: implement depth download via diag path */
        }

        if (color_fname[0]) {
            diag_json_append("          \"color_image\": \"%s\",\n", color_fname);
        } else {
            diag_json_append("          \"color_image\": null,\n");
        }
        if (depth_fname[0]) {
            diag_json_append("          \"depth_image\": \"%s\"\n", depth_fname);
        } else {
            diag_json_append("          \"depth_image\": null\n");
        }
    }

    diag_json_append("        }");
}

/*
 * Live frame dump -- the second per-draw instrument, and the one that does not
 * stop the GPU in order to look at it.
 *
 * WHY IT IS NOT THE DIAG CAPTURE ABOVE. #77 (Galleon's deck and ground
 * stipple, 10-14 frames per 100) has had every per-draw field the diag capture
 * records ruled out by measurement: format, dimensions, level count, pitch,
 * swizzle flag, texture-matrix enable and texgen mode, over 115 addresses and
 * 22,493 binds with zero variation while the artifact was on screen. What the
 * capture cannot record is what is left. nv2a_diag_log_draw_call above calls
 * pgraph_vk_finish(VK_FINISH_REASON_SURFACE_DOWN) BEFORE EVERY DRAW, and that
 * finish flushes the draw queue and the reorder window (vk/draw.c:3188-3217)
 * and waits on a fence. Under a diag capture, therefore:
 *
 *   - no draw is ever merged with the one after it, so a merged draw is never
 *     logged -- not because logging misses it, because merging cannot happen;
 *   - nothing is ever in flight across a draw boundary, so a missing barrier
 *     or a stale binding is masked by the serialisation;
 *   - texture reuse keyed on submit_time against submit_count
 *     (vk/texture.c:2074) sees one submit per draw, which is not the schedule
 *     the artifact appears under.
 *
 * An instrument that removes the behaviour under suspicion cannot see it.
 *
 * So this path records the same draws and adds NO Vulkan work whatsoever: no
 * pgraph_vk_finish, no command buffer, no vkCmd*, no fence wait, no queue
 * submit. Everything it writes is host-side state already in memory --
 * registers, bindings, and the scheduler's own counters. The one image it
 * writes per frame is the DISPLAY surface read out of guest VRAM at
 * flip_stall, AFTER the flip's own pgraph_vk_finish has already run, so it
 * adds no synchronisation of its own either.
 *
 * THE COLUMN THAT PROVES THAT, so the claim is measured and not asserted:
 * every draw record carries `cb_draws` (r->draws_in_cb) and `submits`
 * (r->submit_count). A per-draw finish submits the command buffer at every
 * draw, so under the Debug Capture path cb_draws can never climb above 1 and
 * submits rises once per draw. Under this path cb_draws climbs across the
 * frame and submits is flat between flips. The dump falsifies its own headline
 * claim from its own contents; no external trace is needed.
 *
 * WHAT IT CANNOT SEE, stated so that a null result is not over-read:
 *
 *   - no per-draw image. Reading a surface back mid-frame is exactly what
 *     forces the finish. Per draw you get state and schedule; per frame you
 *     get the picture. A draw-level pixel attribution still needs the old
 *     path, with the old blindness.
 *   - clears and blits. Their hooks (vk/draw.c:6711, vk/blit.c:450) are gated
 *     on nv2a_dbg_diag_frame_active() at the CALL SITE, in files this lane
 *     does not hold. Draws only.
 *   - merging, when merging is off. draw_merge and draw_reorder are prefs that
 *     default false (vk/draw.c:32, SettingsActivity.kt:68), so the session
 *     header records both. A dump taken with them off says nothing about
 *     merged draws and must not be read as if it did; it still shows deferred
 *     submission and command-buffer batching, which are on by default.
 *
 * ARMING. A marker file, the way apu.c arms the PCM capture
 * (hw/xbox/mcpx/apu/apu.c:892), and for the same reason: the only existing
 * trigger is a button in MainActivity, which needs a person holding the
 * device, and a soak has nobody. The marker is polled once a second at the
 * flip, so
 *
 *     adb shell 'echo 30 > <files>/frame_dump.on'
 *
 * arms it mid-run, once the title has reached the scene that matters.
 *
 * The marker is UNLINKED the instant it is read, and the previous dump's files
 * are deleted when a new one is armed. Both are the audio harness's scars: a
 * marker left behind by one experiment armed eight unrelated soaks, and a
 * capture left on the device was pulled and measured as a later run's data. A
 * frame dump is an order of magnitude more bytes than a PCM capture, so it
 * gets a byte cap for the same reason the PCM one has.
 */

/*
 * The dump's own lifecycle lines go to the tag the harness actually keeps.
 * DIAG_LOG above uses `hakuX-diag`, and neither logcat spec that serves a
 * dispatched run lists it (dispatcher.sh:1089, soak_title.sh:32, both ending
 * `*:S`), so every line the diag capture prints about itself is dropped from
 * the record of the run that produced it -- which is how a dump that never
 * armed and a dump whose file could not be opened look identical afterwards.
 * `hakuX` is in both specs, but soak_title's fallback keeps it at :W, so the
 * handful of lifecycle lines here are WARN on purpose. They are rare: armed,
 * held, closed, failed. Both spec strings live in files this lane does not
 * hold, or the tag would have been added there instead.
 */
#ifdef __ANDROID__
#define FDUMP_LOG(...) \
    __android_log_print(ANDROID_LOG_WARN, "hakuX", __VA_ARGS__)
#else
#define FDUMP_LOG(...) fprintf(stderr, "xemu-framedump: " __VA_ARGS__)
#endif

/* Both are prefs with no header of their own (vk/draw.c:987-995); the Android
 * entry point declares them the same way. g_vulkan_driver_info is instance.c's
 * one-line driver identity, recorded so a dump is attributable to a driver
 * without a second artifact. */
extern bool xemu_get_draw_merge(void);
extern bool xemu_get_draw_reorder(void);
extern char g_vulkan_driver_info[256];

#define FDUMP_MARKER_NAME     "frame_dump.on"
#define FDUMP_PREFIX          "framedump_"
#define FDUMP_DEFAULT_FRAMES  30
#define FDUMP_MAX_FRAMES      600
#define FDUMP_DEFAULT_MB      96
#define FDUMP_POLL_NS         (1000LL * 1000 * 1000)
#define FDUMP_BUF_BYTES       (256 * 1024)
/*
 * 2: frame records carry `img_sync`, the fence slot the per-frame image waited
 *    on.
 * 3: the completion is CHECKED to have covered the display surface, and a
 *    frame where it did not writes no image at all (`img_sync` is
 *    FDUMP_IMG_STALE and `"image"` is null).
 *
 * The images of a schema-1 or schema-2 dump must not be paired with the draw
 * records they are filed under. Schema 1 never completed the flip's
 * pre-recorded download, so every PPM is one completed download old. Schema 2
 * completed whatever was outstanding but never tested that the display surface
 * was among it, so a PPM is this frame's only on the frames where the flip's
 * pre-record succeeded -- and `img_sync` said nothing about which those were.
 * See fdump_end_frame.
 *
 * 4: images as in 3. Each draw record adds the fixed-function state ("rs",
 *    "clip", "aa", "zf", "zeta") and, per texture stage, the surface at the
 *    stage's address ("srf", "s2t"); each shader hash gets one
 *    {"t":"shader"} record with its combiner registers and GLSL. A schema-3
 *    reader that ignores unknown fields reads a schema-4 dump unchanged.
 * 5: as 4, plus the vertex RAM the draw reads and every change to it. Each
 *    draw record adds "rot" (the command-buffer rotation it was recorded in)
 *    and "vr" (per array attribute, the VRAM byte range of its elements). A
 *    {"t":"vup"} record is written for every upload into the vertex RAM
 *    staging buffer that CHANGES bytes, with the changed span. The staging
 *    buffer is per rotation, not per draw, so a vup in the same "rot" as an
 *    earlier draw, with a later "n" and a changed span inside that draw's
 *    "vr", rewrites what the earlier draw will read when the command buffer
 *    runs. "hzf":1 on a vup: HAKUX_VTX_HAZARD (vk/vertex.c) finished the
 *    command buffer before that upload. With the `vtxNN` token, a draw
 *    of at most NN indices also logs its elements' raw position, diffuse and
 *    texcoord0 words ("v") and the composite matrix and viewport offset
 *    ("cm"), so its screen coverage can be recomputed offline.
 * 6: as 5, plus, with the `rtt` token, readbacks of small render targets. A
 *    draw that renders to a colour target of at most FDUMP_RTT_MAX_TEXELS, or
 *    samples a colour surface that small, FINISHES the command buffer after
 *    its record's other fields and adds "rb": one entry per image read, as
 *    the GPU left it after this draw. "k" is "color" (the draw's own
 *    target), "srf" (the image of the surface at stage "s"'s address) or
 *    "tex" (the texture image stage "s" sampled, when that is a copy of the
 *    surface and not the surface itself, "s2t":0). "file" is level 0 raw:
 *    row-major, unswizzled, w*h texels in the host format "vkfmt" (44 is
 *    B8G8R8A8_UNORM), or null when it was not written. The finishes change
 *    the schedule the dump is measuring; see per_draw_finish in the header.
 * 7: as 6, plus, with `rtt`, the draw that CONSUMES a small target: one whose
 *    own colour target is larger but which samples a colour surface of at
 *    most FDUMP_RTT_MAX_TEXELS (GTA San Andreas's projected shadow). Up to
 *    FDUMP_CONS_PER_FRAME such draws a frame, FDUMP_CONS_MAX a dump, also get
 *    "pre" (its colour target before it ran) and "zpre" (its zeta's depth
 *    aspect before it ran), read in pgraph_vk_fdump_pre_draw after a finish
 *    and before anything of the draw is recorded, and "post" (its colour
 *    target after it). pre and post differ exactly where the draw wrote.
 *    zpre's texels are 4 bytes for D24_UNORM_S8_UINT (129: depth in the low
 *    24 bits) and D32_SFLOAT_S8_UINT (130: a float), 2 for D16_UNORM (124).
 * 8: as 7, plus three things for a texture a small target is drawn FROM that
 *    was never a render surface (GTA San Andreas's 32x32 shadow gradient).
 *    With `rtt`, a draw into a small colour target also reads back the
 *    texture image of each enabled stage that has no surface at its address
 *    ("k":"tex", "addr" the stage's texture address), up to
 *    FDUMP_TEX_MAX_TEXELS. With `vtxNN`, an inline_array draw of at most NN
 *    vertices logs "ia": its vertex size in bytes ("vs"), each enabled
 *    attribute as [index, byte offset in the vertex, size, count, format]
 *    ("attrs"), and the raw words ("w"). And the `watchNN` token: from the
 *    arm, only draws into a small colour target are logged (each with its
 *    `rtt` readbacks), "n" still counts every draw in the frame, a frame with
 *    none writes no record and does not count against the frame number, no
 *    image, no consumer readbacks and no vup records are written, and the dump
 *    closes after NN logged draws. Armed at startup, it records how a texture
 *    made by draws at the title's start was made.
 * 9: as 8, plus the `gd` token (#939: two renderings of one guest frame
 *    alternate, and the question is whether the guest's input differs
 *    between them or the host draws the same input two ways). Each draw
 *    record gets "gd", two halves:
 *    - the guest's input, as the words that changed since the previous
 *      LOGGED draw, each a flat [index, value, ...] list present only when
 *      something changed: "r" the register file (index is the byte offset,
 *      as NV_PGRAPH_*), "c" the vertex shader constants (constant*4 +
 *      component), "la"/"lb"/"l1" the lighting context arrays, "p" the
 *      transform program, "ff" the fixed-function values kept outside those
 *      (fdump_gd_ff gives the layout) and "va" the attributes' inline values
 *      (attribute*4 + component). The first draw after the arm lists every
 *      non-zero word, so replaying the lists gives each draw's full state.
 *    - the host's: "path" the pre-draw path (0 super-fast, 1 medium-fast,
 *      2 full), "cp" what create_pipeline found (DCEN_CP_* in vk/draw.c),
 *      "ready" the shader binding's, "uv"/"up" whether the binding has the
 *      #569 uber vertex stage / combiner ubershader, "vkp" the VkPipeline
 *      handle, "gu" whether that pipeline links the uber vertex stage, "lto"
 *      a replacement pending, "vu"/"pu" a hash of the vertex/pixel uniform
 *      block as this draw left it, and "ubo" the two dynamic UBO offsets.
 *    And each enabled stage in "tex" gets "gh", a hash of the guest's
 *    texture bytes at the binding's offset and length as of this draw, "th"
 *    the binding's own content hash, and "key" [width, height, levels,
 *    color_format, texture_length]. With `gd`, a draw the host skipped
 *    writes {"t":"skip","f","n","why","shader","pipeline"}, "n" being the
 *    number the next logged draw takes; a skip takes none.
 */
#define FDUMP_SCHEMA          9

/* `img_sync` on a frame record: >= 0 is the fence slot the image waited on
 * before the display surface came back clean, and these two are the cases
 * where no wait happened or where waiting was not enough. */
#define FDUMP_IMG_NO_WAIT     (-1) /* nothing outstanding, VRAM already current */
#define FDUMP_IMG_STALE       (-2) /* display surface still dirty; no image */

/* Set from the Android entry point to the app's external files dir, which is
 * both adb-writable (so the marker can be dropped) and adb-readable (so the
 * dump can be pulled). Empty elsewhere: the desktop falls back to the settings
 * base path, and XEMU_FRAME_DUMP_DIR overrides either. */
static char fdump_dir[512] = "";

/* Schema 4's once-per-shader records; see fdump_log_shader. */
#define FDUMP_MAX_SHADERS     2048

/* Schema 9's "ff" group: the fixed-function values PGRAPHState keeps outside
 * the register file and the constant arrays; see fdump_gd_ff. */
#define FDUMP_GD_FF_WORDS     (3 + NV2A_MAX_LIGHTS * 3 * 4 + 6 + 6 + 8)

static struct {
    FILE *fp;
    char *buf;
    bool images;
    uint64_t shaders_seen[FDUMP_MAX_SHADERS];
    int shaders_n;
    /* Schema 5's `vtxNN`: draws of at most this many indices log their
     * vertex words. 0 is off. */
    int vtx_max;
    /* Schema 6's `rtt`: read back small colour targets and the textures
     * drawn from small surfaces; see fdump_log_draw_readbacks. */
    bool rtt;
    /* Schema 7: the consumer draw whose "pre"/"zpre" pgraph_vk_fdump_pre_draw
     * read (-1: none pending), what it read, and the per-frame and per-dump
     * counts that bound the bytes. */
    int cons_draw;
    int cons_frame;
    int cons_in_frame;
    int cons_total;
    int cons_nrb;
    struct {
        const char *k;
        hwaddr addr;
        uint32_t w, h;
        VkFormat fmt;
        VkImageLayout layout;
        bool ok;
        char file[96];
    } cons_rb[2];
    /* Schema 8's `watchNN`: log only draws into a small colour target, and
     * close after this many (0 is off). watch_in_frame: logged this frame. */
    int watch_max;
    int watch_n;
    int watch_in_frame;
    /* Schema 9's `gd` (#939): per draw, the guest state words that changed
     * since the previous logged draw, and what the host drew with; see
     * fdump_log_draw_gd. The shadows are the state as of that draw, zero at
     * the arm, so the first draw logs every non-zero word. */
    bool gd;
    uint32_t gd_regs[0x2000];
    uint32_t gd_vshc[NV2A_VERTEXSHADER_CONSTANTS * 4];
    uint32_t gd_lta[NV2A_LTCTXA_COUNT * 4];
    uint32_t gd_ltb[NV2A_LTCTXB_COUNT * 4];
    uint32_t gd_lt1[NV2A_LTC1_COUNT * 4];
    uint32_t gd_prog[NV2A_MAX_TRANSFORM_PROGRAM_LENGTH * VSH_TOKEN_SIZE];
    uint32_t gd_ff[FDUMP_GD_FF_WORDS];
    uint32_t gd_va[NV2A_VERTEXSHADER_ATTRIBUTES * 4];
    int frames_remaining;
    int frame_index;
    int draw_index;
    uint64_t draws_total;
    uint64_t bytes_written;
    uint64_t byte_limit;
    uint32_t submit_at_frame_start;
    unsigned session;
    int64_t next_poll_ns;
    bool env_checked;
    bool no_dir_warned;
    char base[600];

    /* Frames whose display surface was still draw_dirty after the completion,
     * so no image was written. Counted rather than only logged per frame: the
     * per-frame line is emitted once and the total goes in the close line and
     * the trailer, so a dispatched run can see the rate without the PPMs. */
    int images_stale;
    bool stale_warned;

    /* Non-zero when THIS dump armed the diag capture (the `diag` token), and
     * the value it asked for, so the teardown in fdump_close cannot cancel a
     * capture somebody else armed. */
    int diag_armed_frames;

    /* An arm that has been seen but not started yet; see the "afterNN" token.
     * Held rather than acted on so that a queued soak, which can only set the
     * environment at startup, can still dump a scene the title takes a minute
     * to reach. */
    bool pending;
    int64_t pending_at_ns;
    char pending_spec[160];
    char pending_by[16];
} fdump;

void nv2a_dbg_set_framedump_dir(const char *dir)
{
    snprintf(fdump_dir, sizeof(fdump_dir), "%s", dir ? dir : "");
}

bool nv2a_dbg_framedump_active(void)
{
    return fdump.fp != NULL;
}

/* NULL means "there is nowhere to write a dump a human can retrieve", which is
 * a state only Android has. The entry point there refuses internal storage on
 * purpose -- it is unreadable to adb on a production build, so a dump written
 * to it is a dump nobody can pull -- and the settings base path IS internal
 * storage (SDL_GetPrefPath). Falling back to it armed the feature into exactly
 * the directory that comment rules out: the marker branch is inert there
 * (nobody can drop a marker either), but an env-armed soak would open the
 * file, log "armed ... -> <path>" at WARN, write 30 frames and ~27 MB of PPMs
 * where `--pull 'framedump_*'` cannot see them, and come back with no dump and
 * a log saying one was written. Unarmed and saying so is the honest state.
 * Desktop keeps the fallback, where it is the right answer. */
static const char *fdump_base_dir(void)
{
    const char *env = getenv("XEMU_FRAME_DUMP_DIR");
    if (env && env[0]) {
        return env;
    }
    if (fdump_dir[0]) {
        return fdump_dir;
    }
#ifdef __ANDROID__
    return NULL;
#else
    return xemu_settings_get_base_path();
#endif
}

/*
 * End the diag capture this dump armed, when the dump ends.
 *
 * The `diag` token used to pass the dump's frame count straight to
 * nv2a_dbg_trigger_diag_frames(), and the two count different things: the
 * dump's number is flip_stall invocations (what fdump_end_frame decrements),
 * the diag session's is GUEST frames (it advances on g_nv2a_stats.frame_count).
 * The lane's own control arm is the measurement that these come apart -- 30
 * frame records, one distinct guest frame -- so `30,diag` closed the dump after
 * about a second and left the control arm running, with its finish before every
 * draw, until the title advanced 29 more guest frames: on the order of 900
 * flip_stalls, serialising every other measurement that soak was queued for,
 * with nothing recording it and nothing the operator wrote bounding it.
 * DIAG_MAX_FRAMES bounds the session's arrays, not its duration.
 *
 * Tearing it down here makes "the control arm is this dump's control" true by
 * construction instead of by coincidence of units, so the number in the spec is
 * only ever an upper bound. The body mirrors the abort path in flip_stall:
 * partial data is written rather than discarded.
 */
static void fdump_end_armed_diag(void)
{
    int armed = fdump.diag_armed_frames;
    if (!armed) {
        return;
    }
    fdump.diag_armed_frames = 0;

    /* Only our own arm: if the value changed, the UI armed a capture over
     * ours and it is not this dump's to cancel. */
    int prev = qatomic_cmpxchg(&diag_frame_pending, armed, 0);
    if (prev != armed && prev != 0) {
        /* FDUMP_LOG, not DIAG_LOG: `hakuX-diag` is absent from both logcat
         * specs that serve a dispatched run, and the whole point of tearing
         * the control arm down here is that its lifetime stopped being
         * invisible. A run that could not see the teardown -- or that a UI
         * capture prevented it -- is back where it started. */
        FDUMP_LOG("framedump: leaving a pending diag arm (%d) it did not "
                  "make\n", prev);
    }

    if (!qatomic_read(&diag_frame_active)) {
        return;
    }
    FDUMP_LOG("framedump closed: ending the diag control arm it armed\n");
    diag_total_frames = diag_current_frame_index;
    if (diag_total_frames > 0) {
        diag_write_session_json();
    }
    diag_cleanup_session();
    qatomic_set(&diag_frame_active, 0);
}

static void fdump_close(const char *why)
{
    if (!fdump.fp) {
        return;
    }

    FILE *fp = fdump.fp;
    fdump.fp = NULL; /* latch off before the slow part, as apu_capture does */

    /* The trailer is the reader's date stamp. A dump whose frames exceed the
     * app's lifetime, or whose trailer is missing entirely, is a file from an
     * earlier run or a truncated one -- both have been filed as measurements
     * on this project before. */
    fprintf(fp,
            "{\"t\":\"end\",\"why\":\"%s\",\"frames\":%d,\"draws\":%" PRIu64
            ",\"bytes\":%" PRIu64 ",\"images_stale\":%d,\"wall\":%lld}\n",
            why, fdump.frame_index, fdump.draws_total, fdump.bytes_written,
            fdump.images_stale, (long long)time(NULL));
    fclose(fp);
    g_free(fdump.buf);
    fdump.buf = NULL;

    FDUMP_LOG("framedump: closed (%s) after %d frames, %" PRIu64 " draws, %"
             PRIu64 " bytes, %d frame(s) with no image (display surface still "
             "dirty)\n", why, fdump.frame_index, fdump.draws_total,
             fdump.bytes_written, fdump.images_stale);

    /* The control arm ends with the dump it is the control for. */
    fdump_end_armed_diag();
}

/* Delete the previous dump's files. See the header comment: an old capture
 * left on the device reads exactly like this run's data. `keep` is this run's
 * own file, which exists by the time this runs -- the clear happens after the
 * output has been opened, so a failed arm cannot destroy the previous dump --
 * and matches FDUMP_PREFIX like any other. */
static void fdump_clear_previous(const char *dir, const char *keep)
{
    GDir *d = g_dir_open(dir, 0, NULL);
    if (!d) {
        return;
    }
    const gchar *name;
    while ((name = g_dir_read_name(d)) != NULL) {
        if (keep && !strcmp(name, keep)) {
            continue;
        }
        if (g_str_has_prefix(name, FDUMP_PREFIX)) {
            gchar *p = g_build_filename(dir, name, NULL);
            unlink(p);
            g_free(p);
        }
    }
    g_dir_close(d);
}

/*
 * Marker/env spec: whitespace- or comma-separated tokens, all optional.
 *   <integer>   frames to dump            (default 30, capped at 600)
 *   images      write one display PPM per frame (default on). Costs one fence
 *               wait per frame at the flip -- see fdump_end_frame, the image
 *               is otherwise a frame behind the records it is filed under.
 *   noimages    do not write images -- records only, ~1 MB for the whole dump
 *               instead of ~900 KB per frame on top of it, and no fence wait
 *   capNN       byte cap in MB            (default 96)
 *   diag        ALSO trigger the old Debug Capture path alongside. This is the
 *               A/B: one run, one instrument, two triggers, and the
 *               cb_draws/submits columns differ. It is not the default because
 *               it reintroduces the per-draw finish. The frame count is an
 *               upper bound on it, not its duration -- the two instruments
 *               count different things -- so the capture is torn down when the
 *               dump closes; see fdump_end_armed_diag.
 *   afterNN     start NN seconds after this arm was SEEN, not immediately.
 *               For a marker that is NN seconds from the touch; for the
 *               environment it is NN seconds from startup, which is the only
 *               way a queued soak reaches a scene a title takes a minute to
 *               get to -- request.sh can set an env var and cannot touch a
 *               file on the device mid-run.
 *   vtxNN       schema 5: a draw of at most NN indices (capped at 256) logs
 *               its vertices' raw words; see FDUMP_SCHEMA.
 *   rtt         schema 6: read back small render targets and the textures
 *               sampled from them, per draw; schema 7: and the full colour
 *               target and depth around a draw that samples one; see
 *               FDUMP_SCHEMA. This one FINISHES the command buffer at each
 *               such draw.
 *   watchNN     schema 8: log only draws into a small colour target, until NN
 *               (capped at 4096) are logged; no images. See FDUMP_SCHEMA.
 *   gd          schema 9: per draw, the guest state that changed since the
 *               previous logged draw and the host's identity for the draw,
 *               and a record for each draw the host skipped. See FDUMP_SCHEMA.
 */
static void fdump_parse_spec(const char *spec, int *frames, bool *images,
                             int *cap_mb, bool *also_diag, int *after_s,
                             int *vtx_max, bool *rtt, int *watch_max, bool *gd)
{
    char buf[160];
    snprintf(buf, sizeof(buf), "%s", spec ? spec : "");

    char *save = NULL;
    for (char *tok = strtok_r(buf, " ,\t\r\n", &save); tok;
         tok = strtok_r(NULL, " ,\t\r\n", &save)) {
        if (!strcmp(tok, "images")) {
            *images = true;
        } else if (!strcmp(tok, "noimages")) {
            *images = false;
        } else if (!strcmp(tok, "diag")) {
            *also_diag = true;
        } else if (!strcmp(tok, "rtt")) {
            *rtt = true;
        } else if (!strcmp(tok, "gd")) {
            *gd = true;
        } else if (!strncmp(tok, "after", 5)) {
            long v = strtol(tok + 5, NULL, 10);
            if (v >= 0 && v <= 3600) {
                *after_s = (int)v;
            }
        } else if (!strncmp(tok, "cap", 3)) {
            long v = strtol(tok + 3, NULL, 10);
            if (v >= 1 && v <= 4096) {
                *cap_mb = (int)v;
            }
        } else if (!strncmp(tok, "vtx", 3)) {
            long v = strtol(tok + 3, NULL, 10);
            if (v >= 0) {
                *vtx_max = (int)MIN(v, 256L);
            }
        } else if (!strncmp(tok, "watch", 5)) {
            long v = strtol(tok + 5, NULL, 10);
            if (v >= 0) {
                *watch_max = (int)MIN(v, 4096L);
            }
        } else {
            char *end = NULL;
            long v = strtol(tok, &end, 10);
            if (end != tok && v >= 1) {
                *frames = (int)MIN(v, (long)FDUMP_MAX_FRAMES);
            }
        }
    }
}

static void fdump_begin(NV2AState *d, const char *armed_by, const char *spec)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    int frames = FDUMP_DEFAULT_FRAMES;
    bool images = true;
    int cap_mb = FDUMP_DEFAULT_MB;
    bool also_diag = false;
    int after_s = 0;
    int vtx_max = 0;
    bool rtt = false;
    int watch_max = 0;
    bool gd = false;
    fdump_parse_spec(spec, &frames, &images, &cap_mb, &also_diag, &after_s,
                     &vtx_max, &rtt, &watch_max, &gd);
    if (watch_max) {
        images = false;
    }

    const char *base = fdump_base_dir();
    if (!base || !base[0]) {
        /* Android with no adb-readable directory; see fdump_base_dir. */
        FDUMP_LOG("framedump: armed by %s but there is no dump directory -- "
                  "not arming\n", armed_by);
        return;
    }
    snprintf(fdump.base, sizeof(fdump.base), "%s", base);

    fdump.session = (unsigned)time(NULL);
    fdump.images = images;
    fdump.frames_remaining = frames;
    fdump.frame_index = 0;
    fdump.draw_index = 0;
    fdump.draws_total = 0;
    fdump.bytes_written = 0;
    fdump.byte_limit = (uint64_t)cap_mb * 1024 * 1024;
    fdump.submit_at_frame_start = qatomic_read(&r->submit_count);
    fdump.images_stale = 0;
    fdump.stale_warned = false;
    fdump.shaders_n = 0;
    fdump.vtx_max = vtx_max;
    fdump.rtt = rtt;
    fdump.cons_draw = -1;
    fdump.cons_frame = -1;
    fdump.cons_in_frame = 0;
    fdump.cons_total = 0;
    fdump.cons_nrb = 0;
    fdump.watch_max = watch_max;
    fdump.watch_n = 0;
    fdump.watch_in_frame = 0;
    fdump.gd = gd;
    memset(fdump.gd_regs, 0, sizeof(fdump.gd_regs));
    memset(fdump.gd_vshc, 0, sizeof(fdump.gd_vshc));
    memset(fdump.gd_lta, 0, sizeof(fdump.gd_lta));
    memset(fdump.gd_ltb, 0, sizeof(fdump.gd_ltb));
    memset(fdump.gd_lt1, 0, sizeof(fdump.gd_lt1));
    memset(fdump.gd_prog, 0, sizeof(fdump.gd_prog));
    memset(fdump.gd_ff, 0, sizeof(fdump.gd_ff));
    memset(fdump.gd_va, 0, sizeof(fdump.gd_va));

    char self[64];
    snprintf(self, sizeof(self), "%s%u.jsonl", FDUMP_PREFIX, fdump.session);
    char path[700];
    snprintf(path, sizeof(path), "%s/%s", fdump.base, self);
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        FDUMP_LOG("framedump: cannot open %s (errno=%d)\n", path, errno);
        return;
    }
    /* Only now delete the previous dump. Clearing first meant an arm that
     * could not open its output -- read-only path, full filesystem -- left
     * the previous run's dump deleted and no new one in its place. The
     * session id is a timestamp, so the new file never collides with an old
     * one and nothing depends on the order. */
    fdump_clear_previous(fdump.base, self);
    fdump.buf = g_malloc(FDUMP_BUF_BYTES);
    setvbuf(fp, fdump.buf, _IOFBF, FDUMP_BUF_BYTES);
    fdump.fp = fp;

    /* The header is the run's own provenance. draw_merge and draw_reorder are
     * in it because a dump taken with them off cannot speak about merging, and
     * the scale factor is in it because a capture upscaled 2.25x was read as a
     * spectral finding on this very issue.
     *
     * `per_draw_finish` says whether a finish is forced between draws in THIS
     * run, and it is `also_diag || rtt` because those are the only things
     * that force one here: the `diag` token arms the old capture alongside,
     * and the `rtt` token (schema 6) finishes at each draw it reads back.
     * Without them this path issues no Vulkan call at all. It was a bare `false`
     * literal until it was caught -- which would have printed "no finish" on
     * the control arm, the one run where a finish is forced on purpose. A
     * field that cannot say the thing it exists to detect is not a check.
     *
     * It is still only a statement about what was ARMED. The measurement is
     * `cb_draws` and `submits` on every draw record below; if the two ever
     * disagree with this field, believe the draw records, because they are
     * read from the scheduler and this is read from the spec. */
    fdump.bytes_written += fprintf(
        fp,
        "{\"t\":\"session\",\"schema\":%d,\"id\":%u,\"armed_by\":\"%s\","
        "\"spec\":\"%s\",\"frames\":%d,\"images\":%s,\"cap_mb\":%d,"
        "\"after_s\":%d,\"vtx\":%d,\"rtt\":%s,\"watch\":%d,\"gd\":%s,"
        "\"wall\":%lld,\"uptime_ms\":%lld,\"draw_merge\":%s,"
        "\"draw_reorder\":%s,\"surface_scale\":%d,\"submit_frames\":%d,"
        "\"per_draw_finish\":%s,\"also_diag\":%s,\"driver\":\"%s\"}\n",
        FDUMP_SCHEMA, fdump.session, armed_by, spec ? spec : "", frames,
        images ? "true" : "false", cap_mb, after_s, vtx_max,
        rtt ? "true" : "false", watch_max, gd ? "true" : "false",
        (long long)time(NULL),
        (long long)(qemu_clock_get_ns(QEMU_CLOCK_REALTIME) / 1000000),
        xemu_get_draw_merge() ? "true" : "false",
        xemu_get_draw_reorder() ? "true" : "false",
        pg->surface_scale_factor, r->num_active_frames,
        (also_diag || rtt) ? "true" : "false",
        also_diag ? "true" : "false", g_vulkan_driver_info);

    FDUMP_LOG("framedump: armed by %s, %d frames, images=%d, cap=%d MB -> %s\n",
             armed_by, frames, (int)images, cap_mb, path);

    if (also_diag) {
        /* The comparison arm, on purpose and on the record: this run WILL
         * serialise. Its draw records are the control the headline claim is
         * measured against.
         *
         * `frames` is an UPPER BOUND here and nothing more, because the two
         * instruments count in different units -- flip_stalls here, guest
         * frames there. What actually ends this capture is fdump_close ->
         * fdump_end_armed_diag; see that function for the run it cost.
         *
         * The clamp the trigger applies is applied here too: what lands in
         * diag_frame_pending is what that teardown has to match. */
        fdump.diag_armed_frames = MIN(frames, DIAG_MAX_FRAMES);
        nv2a_dbg_trigger_diag_frames(frames);
    }
}

/* Start now, or hold the arm until its "afterNN" has elapsed. The spec is
 * parsed twice -- here for the delay and again in fdump_begin -- rather than
 * carried in a struct, so that what the session header records is what
 * fdump_begin actually read and not a copy that could drift from it. */
static void fdump_arm(NV2AState *d, const char *armed_by, const char *spec,
                      int64_t now)
{
    int frames = FDUMP_DEFAULT_FRAMES;
    bool images = true;
    int cap_mb = FDUMP_DEFAULT_MB;
    bool also_diag = false;
    int after_s = 0;
    int vtx_max = 0;
    bool rtt = false;
    int watch_max = 0;
    bool gd = false;
    fdump_parse_spec(spec, &frames, &images, &cap_mb, &also_diag, &after_s,
                     &vtx_max, &rtt, &watch_max, &gd);

    if (after_s <= 0) {
        fdump_begin(d, armed_by, spec);
        return;
    }

    fdump.pending = true;
    fdump.pending_at_ns = now + (int64_t)after_s * 1000000000LL;
    snprintf(fdump.pending_spec, sizeof(fdump.pending_spec), "%s",
             spec ? spec : "");
    snprintf(fdump.pending_by, sizeof(fdump.pending_by), "%s", armed_by);
    FDUMP_LOG("framedump: armed by %s, holding %d s before the first frame\n",
             armed_by, after_s);
}

static void fdump_poll_marker(NV2AState *d)
{
    int64_t now = qemu_clock_get_ns(QEMU_CLOCK_REALTIME);
    if (now < fdump.next_poll_ns) {
        return;
    }
    fdump.next_poll_ns = now + FDUMP_POLL_NS;

    if (fdump.fp) {
        return; /* a dump in progress does not consume a new arm */
    }

    /* Nowhere to write anything a human could retrieve: say so once and stay
     * unarmed, rather than arming into internal storage. See fdump_base_dir.
     * One line per run, on the tag a dispatched run keeps -- the entry point's
     * own WARN covers only the case where it got as far as looking. */
    const char *base = fdump_base_dir();
    if (!base || !base[0]) {
        if (!fdump.no_dir_warned) {
            fdump.no_dir_warned = true;
            FDUMP_LOG("framedump: no adb-readable dump directory; the frame "
                      "dump is unarmed this run\n");
        }
        return;
    }

    /* An arm already seen and waiting out its "afterNN". */
    if (fdump.pending) {
        if (now >= fdump.pending_at_ns) {
            fdump.pending = false;
            fdump_begin(d, fdump.pending_by, fdump.pending_spec);
        }
        return;
    }

    /* The env is read once. It arms at startup, which is what a queued soak
     * can set today (request.sh --env); the marker is what arms mid-run. */
    if (!fdump.env_checked) {
        fdump.env_checked = true;
        const char *env = getenv("XEMU_FRAME_DUMP");
        if (env && env[0] && strcmp(env, "0")) {
            fdump_arm(d, "env", env, now);
            return;
        }
    }

    char marker[700];
    snprintf(marker, sizeof(marker), "%s/%s", base, FDUMP_MARKER_NAME);
    FILE *fp = fopen(marker, "rb");
    if (!fp) {
        return;
    }
    char line[160] = { 0 };
    if (!fgets(line, sizeof(line), fp)) {
        line[0] = '\0';
    }
    fclose(fp);
    unlink(marker); /* one touch, one dump */

    fdump_arm(d, "marker", line, now);
}

/* A JSON string body, escaped, for the shader record below. Returns the bytes
 * written, or -1 on a write error. */
static int fdump_put_escaped(FILE *fp, const char *s)
{
    int total = 0;
    for (const char *p = s; *p; p++) {
        int n;
        unsigned char c = (unsigned char)*p;
        if (c == '"' || c == '\\') {
            n = fprintf(fp, "\\%c", c);
        } else if (c == '\n') {
            n = fprintf(fp, "\\n");
        } else if (c < 0x20) {
            n = fprintf(fp, "\\u%04x", c);
        } else {
            n = fputc(c, fp) == EOF ? -1 : 1;
        }
        if (n < 0) {
            return -1;
        }
        total += n;
    }
    return total;
}

/*
 * Schema 4 (gtasagpu1011): the per-draw fixed-function state, raw, and once
 * per shader hash the register combiner setup and the fragment GLSL it
 * produced.
 *
 * Schema 3 named the colour surface and the texture bindings and nothing
 * else, so a draw's blend, depth, stencil, colour mask, cull and depth target
 * were only in the serialising diag capture -- which stops the title, and so
 * cannot be taken over the stretch of a soak an intermittent artifact needs.
 * The registers go out undecoded (the diag capture's decode, above, is the
 * key): nothing is lost to a decode, and the cost is one fprintf of host-side
 * state, still no Vulkan work.
 *
 * The shader table is per dump and bounded; a hash past the bound is still
 * named in every draw record, it just has no "shader" record of its own.
 */
static bool fdump_put_glsl(const char *key, const ShaderModuleInfo *mi)
{
    int n = fprintf(fdump.fp, ",\"%s\":\"", key);
    if (n < 0) {
        return false;
    }
    fdump.bytes_written += n;
    if (mi && mi->glsl) {
        n = fdump_put_escaped(fdump.fp, mi->glsl);
        if (n < 0) {
            return false;
        }
        fdump.bytes_written += n;
    }
    n = fprintf(fdump.fp, "\"");
    if (n < 0) {
        return false;
    }
    fdump.bytes_written += n;
    return true;
}

static bool fdump_log_shader(PGRAPHState *pg, uint64_t shader_hash)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    ShaderBinding *sb = r->shader_binding;

    if (!sb) {
        return true;
    }
    for (int i = 0; i < fdump.shaders_n; i++) {
        if (fdump.shaders_seen[i] == shader_hash) {
            return true;
        }
    }
    if (fdump.shaders_n >= FDUMP_MAX_SHADERS) {
        return true;
    }
    fdump.shaders_seen[fdump.shaders_n++] = shader_hash;

    /* A line of its own, written ahead of the draw record that first used
     * it; fdump_log_draw has not opened its own line yet when this runs. */
    int n = fprintf(fdump.fp,
                    "{\"t\":\"shader\",\"f\":%d,\"shader\":\"%016" PRIx64 "\","
                    "\"uber_vs\":%d,"
                    "\"combinectl\":\"0x%08x\",\"specfog\":[\"0x%08x\","
                    "\"0x%08x\"],\"shaderprog\":\"0x%08x\","
                    "\"shaderctl\":\"0x%08x\",\"csv0_d\":\"0x%08x\","
                    "\"csv0_c\":\"0x%08x\",\"stages\":[",
                    fdump.frame_index, shader_hash,
                    sb->vsh.uber_module_info != NULL,
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINECTL),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINESPECFOG0),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINESPECFOG1),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_SHADERPROG),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_SHADERCTL),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_CSV0_D),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_CSV0_C));
    if (n < 0) {
        return false;
    }
    fdump.bytes_written += n;
    for (int i = 0; i < 8; i++) {
        n = fprintf(fdump.fp,
                    "%s[\"0x%08x\",\"0x%08x\",\"0x%08x\",\"0x%08x\","
                    "\"0x%08x\",\"0x%08x\"]",
                    i ? "," : "",
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINECOLORI0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINECOLORO0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINEALPHAI0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINEALPHAO0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINEFACTOR0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_COMBINEFACTOR1 + i * 4));
        if (n < 0) {
            return false;
        }
        fdump.bytes_written += n;
    }
    n = fprintf(fdump.fp, "]");
    if (n < 0) {
        return false;
    }
    fdump.bytes_written += n;
    if (!fdump_put_glsl("vsh", sb->vsh.module_info) ||
        !fdump_put_glsl("geom", sb->geom.module_info) ||
        !fdump_put_glsl("psh", sb->psh.module_info)) {
        return false;
    }
    n = fprintf(fdump.fp, "}\n");
    if (n < 0) {
        return false;
    }
    fdump.bytes_written += n;
    return true;
}

static bool fdump_log_draw_state(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    const SurfaceShape *ss = &pg->surface_shape;

    int n = fprintf(
        fdump.fp,
        "\"rs\":{\"c0\":\"0x%08x\",\"c1\":\"0x%08x\",\"c2\":\"0x%08x\","
        "\"c3\":\"0x%08x\",\"blend\":\"0x%08x\",\"bcol\":\"0x%08x\","
        "\"sr\":\"0x%08x\",\"clipmode\":\"0x%08x\",\"zmin\":\"0x%08x\","
        "\"zmax\":\"0x%08x\",\"csv0_d\":\"0x%08x\"},"
        "\"clip\":[%u,%u,%u,%u],\"aa\":%u,\"zf\":%u,",
        pgraph_vk_reg_r(pg, NV_PGRAPH_CONTROL_0),
        pgraph_vk_reg_r(pg, NV_PGRAPH_CONTROL_1),
        pgraph_vk_reg_r(pg, NV_PGRAPH_CONTROL_2),
        pgraph_vk_reg_r(pg, NV_PGRAPH_CONTROL_3),
        pgraph_vk_reg_r(pg, NV_PGRAPH_BLEND),
        pgraph_vk_reg_r(pg, NV_PGRAPH_BLENDCOLOR),
        pgraph_vk_reg_r(pg, NV_PGRAPH_SETUPRASTER),
        pgraph_vk_reg_r(pg, NV_PGRAPH_SHADERCLIPMODE),
        pgraph_vk_reg_r(pg, NV_PGRAPH_ZCLIPMIN),
        pgraph_vk_reg_r(pg, NV_PGRAPH_ZCLIPMAX),
        pgraph_vk_reg_r(pg, NV_PGRAPH_CSV0_D),
        ss->clip_x, ss->clip_y, ss->clip_width, ss->clip_height,
        ss->anti_aliasing, ss->z_format);
    if (n < 0) {
        fdump_close("write error");
        return false;
    }
    fdump.bytes_written += n;

    if (r->zeta_binding) {
        n = fprintf(fdump.fp,
                    "\"zeta\":{\"addr\":\"0x%x\",\"w\":%u,\"h\":%u,"
                    "\"fmt\":%u,\"swizzle\":%d},",
                    (unsigned)r->zeta_binding->vram_addr,
                    r->zeta_binding->width, r->zeta_binding->height,
                    r->zeta_binding->shape.zeta_format,
                    (int)r->zeta_binding->swizzle);
    } else {
        n = fprintf(fdump.fp, "\"zeta\":null,");
    }
    if (n < 0) {
        fdump_close("write error");
        return false;
    }
    fdump.bytes_written += n;
    return true;
}

/* Schema 5. The lowest and highest element a draw from vertex arrays reads,
 * and how many elements it reads. False for the inline kinds: their vertices
 * travel in the pushbuffer and are copied per draw, so no later upload can
 * change what they read. */
static bool fdump_element_range(PGRAPHState *pg, const char *type,
                                uint32_t *lo, uint32_t *hi, unsigned *n)
{
    uint32_t mn = UINT32_MAX, mx = 0;
    unsigned total = 0;

    if (!strcmp(type, "inline_elements")) {
        for (unsigned i = 0; i < pg->inline_elements_length; i++) {
            mn = MIN(mn, pg->inline_elements[i]);
            mx = MAX(mx, pg->inline_elements[i]);
        }
        total = pg->inline_elements_length;
    } else if (!strcmp(type, "draw_arrays")) {
        for (unsigned i = 0; i < pg->draw_arrays_length; i++) {
            if (pg->draw_arrays_count[i] <= 0) {
                continue;
            }
            uint32_t s = (uint32_t)pg->draw_arrays_start[i];
            mn = MIN(mn, s);
            mx = MAX(mx, s + (uint32_t)pg->draw_arrays_count[i] - 1);
            total += pg->draw_arrays_count[i];
        }
    }
    if (mn > mx) {
        return false;
    }
    *lo = mn;
    *hi = mx;
    *n = total;
    return true;
}

/* The VRAM offset of an array attribute's element 0, as vertex.c computes
 * it, and the DMA limit it was mapped under; false when it maps nothing. */
static bool fdump_attr_base(NV2AState *d, PGRAPHState *pg,
                            const VertexAttribute *attr, hwaddr *base,
                            hwaddr *dma_len)
{
    uint8_t *p = (uint8_t *)nv_dma_map(
        d, attr->dma_select ? pg->dma_vertex_b : pg->dma_vertex_a, dma_len);
    if (attr->offset >= *dma_len) {
        return false;
    }
    *base = p + attr->offset - d->vram_ptr;
    return true;
}

/* One element of one attribute as raw words, "-" when the attribute is off.
 * A uniform attribute (no array, or stride 0) prints its persistent value
 * with a "u" prefix: that is what every vertex of the draw gets. */
static int fdump_put_element(NV2AState *d, PGRAPHState *pg, int a,
                             uint32_t idx)
{
    const VertexAttribute *attr = &pg->vertex_attributes[a];
    uint32_t w[4] = { 0, 0, 0, 0 };
    int nw;

    if (!attr->count || !attr->stride) {
        memcpy(w, attr->inline_value, sizeof(w));
        return fprintf(fdump.fp, "\"u%08x %08x %08x %08x\"", w[0], w[1], w[2],
                       w[3]);
    }
    hwaddr base, dma_len;
    size_t bytes = MIN((size_t)attr->size * attr->count, sizeof(w));
    if (!fdump_attr_base(d, pg, attr, &base, &dma_len) ||
        attr->offset + (hwaddr)idx * attr->stride + bytes > dma_len) {
        return fprintf(fdump.fp, "\"-\"");
    }
    memcpy(w, d->vram_ptr + base + (hwaddr)idx * attr->stride, bytes);
    nw = (int)((bytes + 3) / 4);
    switch (nw) {
    case 1:
        return fprintf(fdump.fp, "\"%08x\"", w[0]);
    case 2:
        return fprintf(fdump.fp, "\"%08x %08x\"", w[0], w[1]);
    case 3:
        return fprintf(fdump.fp, "\"%08x %08x %08x\"", w[0], w[1], w[2]);
    default:
        return fprintf(fdump.fp, "\"%08x %08x %08x %08x\"", w[0], w[1], w[2],
                       w[3]);
    }
}

/* Schema 5's per-draw vertex fields, after "tex"; see FDUMP_SCHEMA. */
static bool fdump_log_draw_vertices(NV2AState *d, PGRAPHState *pg,
                                    const char *type)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    uint32_t lo, hi;
    unsigned total;
    int n;

    n = fprintf(fdump.fp, ",\"rot\":%" PRIu64 ",\"vr\":[", r->frame_rotations);
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;

    bool arrays = fdump_element_range(pg, type, &lo, &hi, &total);
    bool first = true;
    for (int i = 0; arrays && i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
        const VertexAttribute *attr = &pg->vertex_attributes[i];
        hwaddr base, dma_len;
        if (!attr->count || !attr->stride ||
            !fdump_attr_base(d, pg, attr, &base, &dma_len)) {
            continue;
        }
        n = fprintf(fdump.fp,
                    "%s[%d,\"0x%" HWADDR_PRIx "\",\"0x%" HWADDR_PRIx
                    "\",%u,%u,%u,%u]",
                    first ? "" : ",", i, base + (hwaddr)lo * attr->stride,
                    base + (hwaddr)hi * attr->stride +
                        (hwaddr)attr->size * attr->count,
                    attr->stride, attr->format, attr->size, attr->count);
        if (n < 0) {
            goto fail;
        }
        fdump.bytes_written += n;
        first = false;
    }
    n = fprintf(fdump.fp, "]");
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;

    /* Schema 8's "ia": an inline_array's vertices are in the pushbuffer, not
     * VRAM. The layout is the one flush_draw computed for this draw (vk/
     * draw.c sets inline_array_offset just before it), so recomputing the
     * vertex size the same way reads the same words. */
    if (!arrays && fdump.vtx_max && !strcmp(type, "inline_array")) {
        unsigned vs = 0;
        for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
            const VertexAttribute *attr = &pg->vertex_attributes[i];
            if (attr->count) {
                vs = ROUND_UP(vs, attr->size);
                vs += attr->size * attr->count;
                vs = ROUND_UP(vs, attr->size);
            }
        }
        unsigned len = pg->inline_array_length;
        if (vs && len * 4 / vs <= (unsigned)fdump.vtx_max) {
            n = fprintf(fdump.fp, ",\"ia\":{\"vs\":%u,\"attrs\":[", vs);
            if (n < 0) {
                goto fail;
            }
            fdump.bytes_written += n;
            bool afirst = true;
            for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
                const VertexAttribute *attr = &pg->vertex_attributes[i];
                if (!attr->count) {
                    continue;
                }
                n = fprintf(fdump.fp, "%s[%d,%u,%u,%u,%u]", afirst ? "" : ",",
                            i, attr->inline_array_offset, attr->size,
                            attr->count, attr->format);
                if (n < 0) {
                    goto fail;
                }
                fdump.bytes_written += n;
                afirst = false;
            }
            n = fprintf(fdump.fp, "],\"w\":\"");
            if (n < 0) {
                goto fail;
            }
            fdump.bytes_written += n;
            for (unsigned j = 0; j < len; j++) {
                n = fprintf(fdump.fp, "%s%08x", j ? " " : "",
                            pg->inline_array[j]);
                if (n < 0) {
                    goto fail;
                }
                fdump.bytes_written += n;
            }
            n = fprintf(fdump.fp, "\"}");
            if (n < 0) {
                goto fail;
            }
            fdump.bytes_written += n;
        }
    }

    if (!arrays || !fdump.vtx_max || total > (unsigned)fdump.vtx_max) {
        return true;
    }

    /* Elements in draw order: index, position, diffuse, texcoord0. */
    n = fprintf(fdump.fp, ",\"v\":[");
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;
    unsigned k = 0;
    bool elements = !strcmp(type, "inline_elements");
    unsigned groups = elements ? 1 : pg->draw_arrays_length;
    for (unsigned g = 0; g < groups; g++) {
        unsigned cnt = elements ? pg->inline_elements_length
                                : (unsigned)MAX(pg->draw_arrays_count[g], 0);
        for (unsigned j = 0; j < cnt; j++, k++) {
            uint32_t idx = elements ? pg->inline_elements[j]
                                    : (uint32_t)pg->draw_arrays_start[g] + j;
            n = fprintf(fdump.fp, "%s[%u,", k ? "," : "", idx);
            if (n < 0) {
                goto fail;
            }
            fdump.bytes_written += n;
            static const int attrs[] = { 0, 3, 9 };
            for (int a = 0; a < ARRAY_SIZE(attrs); a++) {
                n = fdump_put_element(d, pg, attrs[a], idx);
                if (n < 0) {
                    goto fail;
                }
                fdump.bytes_written += n;
                n = fprintf(fdump.fp, a + 1 < ARRAY_SIZE(attrs) ? "," : "]");
                if (n < 0) {
                    goto fail;
                }
                fdump.bytes_written += n;
            }
        }
    }

    /* c[0..3] are the composite matrix's columns, so oPos[j] =
     * dot(position, c[j]); 0x3a/0x3b are the viewport scale and offset. */
    n = fprintf(fdump.fp, "],\"cm\":[");
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;
    static const int consts[] = { 0, 1, 2, 3, NV_IGRAPH_XF_XFCTX_VPSCL,
                                  NV_IGRAPH_XF_XFCTX_VPOFF };
    for (int c = 0; c < ARRAY_SIZE(consts); c++) {
        const uint32_t *v = pg->vsh_constants[consts[c]];
        n = fprintf(fdump.fp, "%s\"%08x %08x %08x %08x\"", c ? "," : "", v[0],
                    v[1], v[2], v[3]);
        if (n < 0) {
            goto fail;
        }
        fdump.bytes_written += n;
    }
    n = fprintf(fdump.fp, "]");
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;
    return true;

fail:
    fdump_close("write error");
    return false;
}

/* Schema 5: an upload into the vertex RAM staging buffer, called by
 * pgraph_vk_update_vertex_ram_buffer before it copies `data` over `old`. Only
 * an upload that changes bytes is written, with the first and last changed
 * byte; `n` is the draw it is syncing for (the next draw record).
 * `hazard_finished`: HAKUX_VTX_HAZARD finished the command buffer first, so
 * `rot` is the new one and `old` the new slot's copy ("hzf":1; written even
 * when that copy already matches). */
void pgraph_vk_fdump_vertex_upload(PGRAPHVkState *r, hwaddr offset,
                                   const uint8_t *old, const uint8_t *data,
                                   size_t size, bool hazard_finished)
{
    if (!fdump.fp || fdump.watch_max ||
        fdump.bytes_written >= fdump.byte_limit) {
        return;
    }
    bool same = !memcmp(old, data, size);
    if (same && !hazard_finished) {
        return;
    }
    size_t a = 0, b = size;
    if (!same) {
        while (old[a] == data[a]) {
            a++;
        }
        while (old[b - 1] == data[b - 1]) {
            b--;
        }
    }
    int n = fprintf(fdump.fp,
                    "{\"t\":\"vup\",\"f\":%d,\"n\":%d,\"rot\":%" PRIu64 ","
                    "\"lo\":\"0x%" HWADDR_PRIx "\",\"hi\":\"0x%" HWADDR_PRIx
                    "\",\"clo\":\"0x%" HWADDR_PRIx "\",\"chi\":\"0x%"
                    HWADDR_PRIx "\"%s}\n",
                    fdump.frame_index, fdump.draw_index, r->frame_rotations,
                    offset, offset + (hwaddr)size, offset + (hwaddr)a,
                    offset + (hwaddr)b, hazard_finished ? ",\"hzf\":1" : "");
    if (n > 0) {
        fdump.bytes_written += n;
    }
}

/* Schema 6 (`rtt`): render targets of at most this many texels are read
 * back. GTA San Andreas draws CJ's shadow through 64x64 and 32x32 targets
 * (docs/lanes/gtasagpu1011/NOTES.md); a 640x480 frame is never read here. */
#define FDUMP_RTT_MAX_TEXELS  (64 * 64)

/* Schema 8: the largest non-surface texture read back for a small-target
 * draw (1 MB at 4 bytes a texel). */
#define FDUMP_TEX_MAX_TEXELS  (512 * 512)

/* Schema 7: at most this many consumer draws a frame, and a dump, get the
 * full-size "pre", "zpre" and "post" readbacks (3 x 1.2 MB at 640x480 1x). */
#define FDUMP_CONS_PER_FRAME  2
#define FDUMP_CONS_MAX        24

static void fdump_rtt_barrier(VkCommandBuffer cmd, VkImage image,
                              VkImageAspectFlags aspect, VkImageLayout from,
                              VkImageLayout to)
{
    VkImageMemoryBarrier b = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT,
        .dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT,
        .oldLayout = from,
        .newLayout = to,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = image,
        .subresourceRange = {
            .aspectMask = aspect,
            .levelCount = VK_REMAINING_MIP_LEVELS,
            .layerCount = VK_REMAINING_ARRAY_LAYERS,
        },
    };
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                         VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 0, NULL, 0,
                         NULL, 1, &b);
}

/*
 * Schema 6: copy level 0 of an image to BUFFER_STAGING_DST and write it raw to
 * the dump directory as `name`. True if the file was written. `fmt` is the
 * image's format: B8G8R8A8 or R8G8B8A8 colour, or (schema 7) the depth aspect
 * of D24_UNORM_S8_UINT, D32_SFLOAT_S8_UINT or D16_UNORM; anything else is
 * refused.
 *
 * The caller has finished the command buffer, so the draw just recorded and
 * everything before it have executed, and this reads the image as that draw
 * left it. The image goes back to `layout`. The barriers are full ones
 * because the shared transition helper has no SHADER_READ_ONLY ->
 * TRANSFER_SRC, and a dump does not need the narrow masks.
 */
static bool fdump_read_image(NV2AState *d, PGRAPHState *pg, VkImage image,
                             VkImageLayout layout, VkFormat fmt, uint32_t w,
                             uint32_t h, const char *name)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    StorageBuffer *staging = &r->storage_buffers[BUFFER_STAGING_DST];
    VkImageAspectFlags barrier_aspect, copy_aspect;
    size_t texel;

    switch (fmt) {
    case VK_FORMAT_B8G8R8A8_UNORM:
    case VK_FORMAT_R8G8B8A8_UNORM:
        barrier_aspect = copy_aspect = VK_IMAGE_ASPECT_COLOR_BIT;
        texel = 4;
        break;
    case VK_FORMAT_D24_UNORM_S8_UINT:
    case VK_FORMAT_D32_SFLOAT_S8_UINT:
        /* A layout transition of a combined format names both aspects; the
         * copy takes one. */
        barrier_aspect = VK_IMAGE_ASPECT_DEPTH_BIT | VK_IMAGE_ASPECT_STENCIL_BIT;
        copy_aspect = VK_IMAGE_ASPECT_DEPTH_BIT;
        texel = 4;
        break;
    case VK_FORMAT_D16_UNORM:
        barrier_aspect = copy_aspect = VK_IMAGE_ASPECT_DEPTH_BIT;
        texel = 2;
        break;
    default:
        return false;
    }

    size_t size = (size_t)w * h * texel;

    if (image == VK_NULL_HANDLE || !w || !h ||
        layout == VK_IMAGE_LAYOUT_UNDEFINED || size > staging->buffer_size) {
        return false;
    }

    /* As diag_download_surface: retire a download batch still pending in the
     * staging buffer before this overwrites it. */
    pgraph_vk_download_surface_complete_deferred(d);

    VkCommandBuffer cmd = pgraph_vk_begin_single_time_commands(pg);
    fdump_rtt_barrier(cmd, image, barrier_aspect, layout,
                      VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
    VkBufferImageCopy region = {
        .bufferRowLength = w,
        .bufferImageHeight = h,
        .imageSubresource = {
            .aspectMask = copy_aspect,
            .layerCount = 1,
        },
        .imageExtent = { w, h, 1 },
    };
    vkCmdCopyImageToBuffer(cmd, image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           staging->buffer, 1, &region);
    fdump_rtt_barrier(cmd, image, barrier_aspect,
                      VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, layout);
    VkBufferMemoryBarrier hb = {
        .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
        .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
        .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .buffer = staging->buffer,
        .size = size,
    };
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         VK_PIPELINE_STAGE_HOST_BIT, 0, 0, NULL, 1, &hb, 0,
                         NULL);
    pgraph_vk_end_single_time_commands(pg, cmd);
    vmaInvalidateAllocation(r->allocator, staging->allocation, 0, size);

    char path[800];
    snprintf(path, sizeof(path), "%s/%s", fdump.base, name);
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        return false;
    }
    bool ok = fwrite(staging->mapped, 1, size, fp) == size;
    ok = (fclose(fp) == 0) && ok;
    if (ok) {
        fdump.bytes_written += size;
    }
    return ok;
}

static bool fdump_rtt_small(const SurfaceBinding *s)
{
    return s && s->color &&
           (uint64_t)s->width * s->height <= FDUMP_RTT_MAX_TEXELS;
}

/* Schema 7: the draw renders into a colour target that is not small and
 * samples a colour surface that is. Registers and surface bindings only, so
 * it answers the same before the draw is recorded as after. */
static bool fdump_is_consumer(NV2AState *d, PGRAPHState *pg)
{
    SurfaceBinding *c = pg->vk_renderer_state->color_binding;

    if (!c || !c->color || fdump_rtt_small(c)) {
        return false;
    }
    for (int i = 0; i < NV2A_MAX_TEXTURES; i++) {
        if (pgraph_is_texture_enabled(pg, i) &&
            fdump_rtt_small(pgraph_vk_surface_get(
                d, pgraph_get_texture_phys_addr(pg, i)))) {
            return true;
        }
    }
    return false;
}

/*
 * Schema 7: "pre" and "zpre" for a consumer draw (see FDUMP_SCHEMA). Called by
 * flush_draw_one_pass (vk/draw.c) after its early returns and before it
 * records anything of the draw, which is where a buffer-space finish can
 * already happen. The draw's record (fdump_log_draw_readbacks) lists them and
 * adds "post"; a draw that is then skipped unlogged leaves its files
 * unlisted, and fdump.cons_draw no longer matches the next record.
 */
void pgraph_vk_fdump_pre_draw(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    if (!fdump.fp || !fdump.rtt || fdump.watch_max ||
        fdump.bytes_written >= fdump.byte_limit ||
        fdump.cons_total >= FDUMP_CONS_MAX) {
        return;
    }
    if (fdump.cons_frame != fdump.frame_index) {
        fdump.cons_frame = fdump.frame_index;
        fdump.cons_in_frame = 0;
    }
    if (fdump.cons_in_frame >= FDUMP_CONS_PER_FRAME ||
        !fdump_is_consumer(d, pg)) {
        return;
    }
    fdump.cons_in_frame++;
    fdump.cons_total++;
    fdump.cons_draw = fdump.draw_index;
    fdump.cons_nrb = 0;

    pgraph_vk_finish(pg, VK_FINISH_REASON_SURFACE_DOWN);

    SurfaceBinding *bind[2] = { r->color_binding, r->zeta_binding };
    static const char *const kind[2] = { "pre", "zpre" };
    for (int j = 0; j < 2; j++) {
        SurfaceBinding *s = bind[j];
        if (!s) {
            continue;
        }
        __typeof__(fdump.cons_rb[0]) *e = &fdump.cons_rb[fdump.cons_nrb++];
        e->k = kind[j];
        e->addr = s->vram_addr;
        e->w = s->width;
        e->h = s->height;
        pgraph_apply_scaling_factor(pg, &e->w, &e->h);
        e->fmt = s->host_fmt.vk_format;
        e->layout = s->image_layout;
        snprintf(e->file, sizeof(e->file), "%s%u_f%03d_n%04d_%s0.bin",
                 FDUMP_PREFIX, fdump.session, fdump.frame_index,
                 fdump.draw_index, e->k);
        e->ok = fdump_read_image(d, pg, s->image, s->image_layout, e->fmt,
                                 e->w, e->h, e->file);
    }
}

/* Schema 6's "rb", last in the draw record: after the vertex fields, because
 * they read "rot" and the finish below advances it. See FDUMP_SCHEMA. */
static bool fdump_log_draw_readbacks(NV2AState *d, PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    struct {
        const char *k;
        int s;
        hwaddr addr;
        VkImage image;
        VkImageLayout layout;
        uint32_t w, h;
        VkFormat fmt;
    } rb[2 * NV2A_MAX_TEXTURES + 2];
    int nrb = 0;
    /* Schema 7: this is the consumer draw pgraph_vk_fdump_pre_draw read. */
    int npre = fdump.cons_draw == fdump.draw_index - 1 ? fdump.cons_nrb : 0;
    bool post = npre > 0;
    fdump.cons_draw = -1;

    for (int i = 0; i < NV2A_MAX_TEXTURES; i++) {
        if (!pgraph_is_texture_enabled(pg, i)) {
            continue;
        }
        SurfaceBinding *ts =
            pgraph_vk_surface_get(d, pgraph_get_texture_phys_addr(pg, i));
        TextureBinding *tb = r->texture_bindings[i];
        if (!ts) {
            /* Schema 8: a texture that was never a surface, drawn from into
             * a small target. */
            if (tb && fdump_rtt_small(r->color_binding) &&
                (uint64_t)tb->image_config.width * tb->image_config.height <=
                    FDUMP_TEX_MAX_TEXELS) {
                rb[nrb].k = "tex";
                rb[nrb].s = i;
                rb[nrb].addr = pgraph_get_texture_phys_addr(pg, i);
                rb[nrb].image = tb->image;
                rb[nrb].layout = tb->current_layout;
                rb[nrb].w = tb->image_config.width;
                rb[nrb].h = tb->image_config.height;
                rb[nrb].fmt = tb->image_config.format;
                nrb++;
            }
            continue;
        }
        if (!fdump_rtt_small(ts)) {
            continue;
        }
        if (tb && !r->tex_surface_direct[i]) {
            rb[nrb].k = "tex";
            rb[nrb].s = i;
            rb[nrb].addr = ts->vram_addr;
            rb[nrb].image = tb->image;
            rb[nrb].layout = tb->current_layout;
            rb[nrb].w = tb->image_config.width;
            rb[nrb].h = tb->image_config.height;
            rb[nrb].fmt = tb->image_config.format;
            nrb++;
        }
        rb[nrb].k = "srf";
        rb[nrb].s = i;
        rb[nrb].addr = ts->vram_addr;
        rb[nrb].image = ts->image;
        rb[nrb].layout = ts->image_layout;
        rb[nrb].w = ts->width;
        rb[nrb].h = ts->height;
        pgraph_apply_scaling_factor(pg, &rb[nrb].w, &rb[nrb].h);
        rb[nrb].fmt = ts->host_fmt.vk_format;
        nrb++;
    }
    SurfaceBinding *c = r->color_binding;
    if (fdump_rtt_small(c)) {
        rb[nrb].k = "color";
        rb[nrb].s = -1;
        rb[nrb].addr = c->vram_addr;
        rb[nrb].image = c->image;
        rb[nrb].layout = c->image_layout;
        rb[nrb].w = c->width;
        rb[nrb].h = c->height;
        pgraph_apply_scaling_factor(pg, &rb[nrb].w, &rb[nrb].h);
        rb[nrb].fmt = c->host_fmt.vk_format;
        nrb++;
    }
    if (post && c) {
        rb[nrb].k = "post";
        rb[nrb].s = -1;
        rb[nrb].addr = c->vram_addr;
        rb[nrb].image = c->image;
        rb[nrb].layout = c->image_layout;
        rb[nrb].w = c->width;
        rb[nrb].h = c->height;
        pgraph_apply_scaling_factor(pg, &rb[nrb].w, &rb[nrb].h);
        rb[nrb].fmt = c->host_fmt.vk_format;
        nrb++;
    }
    if (!nrb && !npre) {
        return true;
    }

    if (nrb) {
        pgraph_vk_finish(pg, VK_FINISH_REASON_SURFACE_DOWN);
    }

    int n = fprintf(fdump.fp, ",\"rb\":[");
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;

    /* The consumer's "pre" and "zpre", already read and written. */
    for (int j = 0; j < npre; j++) {
        const __typeof__(fdump.cons_rb[0]) *e = &fdump.cons_rb[j];
        n = fprintf(fdump.fp,
                    "%s{\"k\":\"%s\",\"s\":-1,\"addr\":\"0x%" HWADDR_PRIx
                    "\",\"w\":%u,\"h\":%u,\"vkfmt\":%d,\"layout\":%d,"
                    "\"file\":%s%s%s}",
                    j ? "," : "", e->k, e->addr, e->w, e->h, (int)e->fmt,
                    (int)e->layout, e->ok ? "\"" : "null",
                    e->ok ? e->file : "", e->ok ? "\"" : "");
        if (n < 0) {
            goto fail;
        }
        fdump.bytes_written += n;
    }

    for (int j = 0; j < nrb; j++) {
        char name[128];
        snprintf(name, sizeof(name), "%s%u_f%03d_n%04d_%s%d.bin",
                 FDUMP_PREFIX, fdump.session, fdump.frame_index,
                 fdump.draw_index - 1, rb[j].k, rb[j].s < 0 ? 0 : rb[j].s);
        bool ok = fdump_read_image(d, pg, rb[j].image, rb[j].layout,
                                   rb[j].fmt, rb[j].w, rb[j].h, name);
        n = fprintf(fdump.fp,
                    "%s{\"k\":\"%s\",\"s\":%d,\"addr\":\"0x%" HWADDR_PRIx
                    "\",\"w\":%u,\"h\":%u,\"vkfmt\":%d,\"layout\":%d,"
                    "\"file\":%s%s%s}",
                    (j || npre) ? "," : "", rb[j].k, rb[j].s, rb[j].addr,
                    rb[j].w, rb[j].h, (int)rb[j].fmt, (int)rb[j].layout,
                    ok ? "\"" : "null", ok ? name : "", ok ? "\"" : "");
        if (n < 0) {
            goto fail;
        }
        fdump.bytes_written += n;
    }

    n = fprintf(fdump.fp, "]");
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;
    return true;

fail:
    fdump_close("write error");
    return false;
}

/* Schema 9: the "ff" group's layout, in this order. */
static void fdump_gd_ff(PGRAPHState *pg, uint32_t *w)
{
    int k = 0;
    memcpy(&w[k++], &pg->material_alpha, 4);
    memcpy(&w[k++], &pg->material_alpha_back, 4);
    w[k++] = pg->color_material_back;
    memcpy(&w[k], pg->light_infinite_half_vector, NV2A_MAX_LIGHTS * 12);
    k += NV2A_MAX_LIGHTS * 3;
    memcpy(&w[k], pg->light_infinite_direction, NV2A_MAX_LIGHTS * 12);
    k += NV2A_MAX_LIGHTS * 3;
    memcpy(&w[k], pg->light_local_position, NV2A_MAX_LIGHTS * 12);
    k += NV2A_MAX_LIGHTS * 3;
    memcpy(&w[k], pg->light_local_attenuation, NV2A_MAX_LIGHTS * 12);
    k += NV2A_MAX_LIGHTS * 3;
    memcpy(&w[k], pg->specular_params, 6 * 4);
    k += 6;
    memcpy(&w[k], pg->specular_params_back, 6 * 4);
    k += 6;
    memcpy(&w[k], pg->point_params, 8 * 4);
    k += 8;
    assert(k == FDUMP_GD_FF_WORDS);
}

/* Schema 9: the words of cur that differ from shadow, as ,"key":[i,v,...],
 * and the shadow brought up to date. Nothing is written when nothing
 * changed. step skips words (the register file is indexed by byte offset,
 * every fourth entry used). */
static bool fdump_put_delta(const char *key, uint32_t *shadow,
                            const uint32_t *cur, int n, int step)
{
    bool open = false;
    int w;

    for (int i = 0; i < n; i += step) {
        if (cur[i] == shadow[i]) {
            continue;
        }
        if (open) {
            w = fprintf(fdump.fp, ",%d,%u", i, cur[i]);
        } else {
            w = fprintf(fdump.fp, ",\"%s\":[%d,%u", key, i, cur[i]);
            open = true;
        }
        if (w < 0) {
            return false;
        }
        fdump.bytes_written += w;
        shadow[i] = cur[i];
    }
    if (open) {
        w = fprintf(fdump.fp, "]");
        if (w < 0) {
            return false;
        }
        fdump.bytes_written += w;
    }
    return true;
}

/* Schema 9's "gd"; see FDUMP_SCHEMA. */
static bool fdump_log_draw_gd(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;
    ShaderBinding *sb = r->shader_binding;
    PipelineBinding *pb = r->pipeline_binding;
    uint64_t vu = 0, pu = 0;
    uint8_t path = 0, cp = 0;
    int n;

    if (sb && sb->vsh.upload_info) {
        const ShaderUniformLayout *l = &sb->vsh.upload_info->uniforms;
        vu = fast_hash(l->allocation, l->total_size);
    }
    if (sb && sb->psh.module_info) {
        const ShaderUniformLayout *l = &sb->psh.module_info->uniforms;
        pu = fast_hash(l->allocation, l->total_size);
    }
    pgraph_vk_draw_path(&path, &cp);

    n = fprintf(fdump.fp,
                ",\"gd\":{\"path\":%u,\"cp\":%u,\"ready\":%d,\"uv\":%d,"
                "\"up\":%d,\"vkp\":\"0x%" PRIx64 "\",\"gu\":%d,\"lto\":%d,"
                "\"vu\":\"%016" PRIx64 "\",\"pu\":\"%016" PRIx64 "\","
                "\"ubo\":[%zu,%zu]",
                path, cp, sb ? (int)qatomic_read(&sb->ready) : -1,
                sb ? (int)(sb->vsh.uber_loc != -1) : -1,
                sb ? (int)(sb->psh.uber_comb_loc != -1) : -1,
                pb ? (uint64_t)(uintptr_t)pb->pipeline : 0,
                pb ? (int)pb->gpl_uber : -1,
                pb ? (int)pb->gpl_lto_pending : -1, vu, pu,
                r->uniform_buffer_offsets[0], r->uniform_buffer_offsets[1]);
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;

    uint32_t ff[FDUMP_GD_FF_WORDS];
    uint32_t va[NV2A_VERTEXSHADER_ATTRIBUTES * 4];
    fdump_gd_ff(pg, ff);
    for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
        memcpy(&va[i * 4], pg->vertex_attributes[i].inline_value, 16);
    }
    if (!fdump_put_delta("r", fdump.gd_regs, pg->regs_, 0x2000, 4) ||
        !fdump_put_delta("c", fdump.gd_vshc, &pg->vsh_constants[0][0],
                         NV2A_VERTEXSHADER_CONSTANTS * 4, 1) ||
        !fdump_put_delta("la", fdump.gd_lta, &pg->ltctxa[0][0],
                         NV2A_LTCTXA_COUNT * 4, 1) ||
        !fdump_put_delta("lb", fdump.gd_ltb, &pg->ltctxb[0][0],
                         NV2A_LTCTXB_COUNT * 4, 1) ||
        !fdump_put_delta("l1", fdump.gd_lt1, &pg->ltc1[0][0],
                         NV2A_LTC1_COUNT * 4, 1) ||
        !fdump_put_delta("p", fdump.gd_prog, &pg->program_data[0][0],
                         NV2A_MAX_TRANSFORM_PROGRAM_LENGTH * VSH_TOKEN_SIZE,
                         1) ||
        !fdump_put_delta("ff", fdump.gd_ff, ff, FDUMP_GD_FF_WORDS, 1) ||
        !fdump_put_delta("va", fdump.gd_va, va,
                         NV2A_VERTEXSHADER_ATTRIBUTES * 4, 1)) {
        goto fail;
    }

    n = fprintf(fdump.fp, "}");
    if (n < 0) {
        goto fail;
    }
    fdump.bytes_written += n;
    return true;

fail:
    fdump_close("write error");
    return false;
}

/* Schema 9's per-stage "gh"/"th"/"key"; see FDUMP_SCHEMA. */
static int fdump_put_tex_gd(NV2AState *d, const TextureBinding *tb)
{
    const TextureKey *k = &tb->key;
    hwaddr vram_size = memory_region_size(d->vram);
    uint64_t gh = 0;

    if (k->texture_vram_offset < vram_size) {
        gh = fast_hash(d->vram_ptr + k->texture_vram_offset,
                       MIN(k->texture_length,
                           vram_size - k->texture_vram_offset));
    }
    return fprintf(fdump.fp,
                   ",\"gh\":\"%016" PRIx64 "\",\"th\":\"%016" PRIx64 "\","
                   "\"key\":[%u,%u,%u,%u,%" PRIu64 "]",
                   gh, tb->hash, k->state.width, k->state.height,
                   k->state.levels, k->state.color_format,
                   (uint64_t)k->texture_length);
}

/* Schema 9: a draw the host skipped. vk/draw.c calls it only with a dump
 * armed. */
void pgraph_vk_fdump_log_skip(NV2AState *d, const char *why)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    if (!fdump.fp || !fdump.gd || fdump.watch_max) {
        return;
    }
    uint64_t shader_hash = 0;
    if (r->shader_binding) {
        shader_hash = fast_hash((const uint8_t *)&r->shader_binding->state,
                                sizeof(ShaderState));
    }
    int n = fprintf(fdump.fp,
                    "{\"t\":\"skip\",\"f\":%d,\"n\":%d,\"why\":\"%s\","
                    "\"shader\":\"%016" PRIx64 "\",\"pipeline\":\"%p\"}\n",
                    fdump.frame_index, fdump.draw_index, why, shader_hash,
                    (void *)r->pipeline_binding);
    if (n < 0) {
        fdump_close("write error");
        return;
    }
    fdump.bytes_written += n;
}

/* Per draw. One buffered fprintf and, without `rtt`, no Vulkan call and no
 * allocation. */
static void fdump_log_draw(NV2AState *d, PGRAPHState *pg, const char *type,
                           int count)
{
    PGRAPHVkState *r = pg->vk_renderer_state;

    if (fdump.bytes_written >= fdump.byte_limit) {
        fdump_close("byte cap reached");
        return;
    }

    /* Schema 8's `watchNN`: "n" counts this draw, the record is skipped. */
    if (fdump.watch_max && !fdump_rtt_small(r->color_binding)) {
        fdump.draw_index++;
        return;
    }

    int idx = fdump.draw_index++;
    fdump.draws_total++;

    uint64_t shader_hash = 0;
    if (r->shader_binding) {
        shader_hash = fast_hash((const uint8_t *)&r->shader_binding->state,
                                sizeof(ShaderState));
    }
    if (!fdump_log_shader(pg, shader_hash)) {
        fdump_close("write error");
        return;
    }

    int n = fprintf(
        fdump.fp,
        "{\"t\":\"draw\",\"f\":%d,\"n\":%d,\"kind\":\"%s\",\"count\":%d,"
        /* The schedule. cb_draws and submits are the falsifier columns; the
         * queue counts say whether this draw was sitting in a merge window. */
        "\"cb\":%d,\"cb_draws\":%d,\"submits\":%u,\"vkframe\":%d,"
        "\"in_rp\":%d,\"dq\":%d,\"dq_active\":%d,\"rw\":%d,\"rw_active\":%d,"
        "\"prim\":%d,\"shader\":\"%016" PRIx64 "\",\"pipeline\":\"%p\",",
        fdump.frame_index, idx, type, count,
        (int)r->in_command_buffer, r->draws_in_cb,
        qatomic_read(&r->submit_count), r->current_frame,
        (int)r->in_render_pass, r->draw_queue.count,
        (int)r->draw_queue.active, r->reorder_window.count,
        (int)r->reorder_window.active, pg->primitive_mode, shader_hash,
        (void *)r->pipeline_binding);
    if (n < 0) {
        fdump_close("write error");
        return;
    }
    fdump.bytes_written += n;

    if (r->color_binding) {
        n = fprintf(fdump.fp,
                    "\"color\":{\"addr\":\"0x%x\",\"w\":%u,\"h\":%u,"
                    "\"pitch\":%u,\"fmt\":%u,\"swizzle\":%d,\"dirty\":%d},",
                    (unsigned)r->color_binding->vram_addr,
                    r->color_binding->width, r->color_binding->height,
                    r->color_binding->pitch,
                    r->color_binding->shape.color_format,
                    (int)r->color_binding->swizzle,
                    (int)qatomic_read(&r->color_binding->draw_dirty));
    } else {
        n = fprintf(fdump.fp, "\"color\":null,");
    }
    if (n < 0) {
        fdump_close("write error");
        return;
    }
    fdump.bytes_written += n;

    if (!fdump_log_draw_state(pg)) {
        return;
    }

    /* Per stage: the guest's view (raw registers, so nothing is lost to a
     * decode) and the HOST binding identity. The second is the new one -- an
     * image handle that does not change when the guest's texture does, or
     * changes when it does not, is a stale binding, and that is one of the
     * things the serialised capture cannot show. */
    n = fprintf(fdump.fp, "\"tex\":[");
    if (n < 0) {
        fdump_close("write error");
        return;
    }
    fdump.bytes_written += n;

    for (int i = 0; i < NV2A_MAX_TEXTURES; i++) {
        TextureBinding *tb = r->texture_bindings[i];
        n = fprintf(fdump.fp,
                    "%s{\"s\":%d,\"en\":%d,\"fmt\":\"0x%08x\","
                    "\"off\":\"0x%08x\",\"addr\":\"0x%08x\","
                    "\"ctl0\":\"0x%08x\",\"ctl1\":\"0x%08x\","
                    "\"fil\":\"0x%08x\",\"img\":\"%p\",\"submit_time\":%u",
                    i > 0 ? "," : "", i,
                    (int)pgraph_is_texture_enabled(pg, i),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_TEXFMT0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_TEXOFFSET0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_TEXADDRESS0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_TEXCTL0_0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_TEXCTL1_0 + i * 4),
                    pgraph_vk_reg_r(pg, NV_PGRAPH_TEXFILTER0 + i * 4),
                    tb ? (void *)(uintptr_t)tb->image : NULL,
                    tb ? tb->submit_time : 0u);
        if (n < 0) {
            fdump_close("write error");
            return;
        }
        fdump.bytes_written += n;

        if (fdump.gd && tb && pgraph_is_texture_enabled(pg, i)) {
            n = fdump_put_tex_gd(d, tb);
            if (n < 0) {
                fdump_close("write error");
                return;
            }
            fdump.bytes_written += n;
        }

        /* Schema 4: the surface at this stage's address, if any, and whether
         * the stage sampled that surface's own image (s2t). A render-to-
         * texture whose texture shows nothing is told apart here: no surface
         * (the texture came from VRAM the GPU never wrote), a surface the
         * compatibility test refused (a VRAM upload after a download), or
         * the surface's image bound directly. Only enabled stages: a disabled
         * stage's offset register is whatever the last material left. */
        SurfaceBinding *ts = NULL;
        if (pgraph_is_texture_enabled(pg, i)) {
            ts = pgraph_vk_surface_get(d, pgraph_get_texture_phys_addr(pg, i));
        }
        if (ts) {
            n = fprintf(fdump.fp,
                        ",\"s2t\":%d,\"srf\":{\"w\":%u,\"h\":%u,\"pitch\":%u,"
                        "\"fmt\":%u,\"color\":%d,\"swizzle\":%d,\"dirty\":%d,"
                        "\"upl\":%d,\"dlp\":%d}}",
                        (int)r->tex_surface_direct[i], ts->width, ts->height,
                        ts->pitch,
                        ts->color ? ts->shape.color_format
                                  : ts->shape.zeta_format,
                        (int)ts->color, (int)ts->swizzle,
                        (int)qatomic_read(&ts->draw_dirty),
                        (int)ts->upload_pending, (int)ts->download_pending);
        } else {
            n = fprintf(fdump.fp, ",\"s2t\":%d,\"srf\":null}",
                        (int)r->tex_surface_direct[i]);
        }
        if (n < 0) {
            fdump_close("write error");
            return;
        }
        fdump.bytes_written += n;
    }

    n = fprintf(fdump.fp, "]");
    if (n < 0) {
        fdump_close("write error");
        return;
    }
    fdump.bytes_written += n;

    if (!fdump_log_draw_vertices(d, pg, type)) {
        return;
    }

    if (fdump.gd && !fdump_log_draw_gd(pg)) {
        return;
    }

    if (fdump.rtt && !fdump_log_draw_readbacks(d, pg)) {
        return;
    }

    n = fprintf(fdump.fp, "}\n");
    if (n < 0) {
        fdump_close("write error");
        return;
    }
    fdump.bytes_written += n;

    if (fdump.watch_max) {
        fdump.watch_in_frame++;
        if (++fdump.watch_n >= fdump.watch_max) {
            fdump_close("watch count reached");
        }
    }
}

/* End of a dumped frame. Runs at flip_stall, after the flip's own
 * pgraph_vk_finish.
 *
 * That finish does NOT put this frame's pixels in guest VRAM, and this used to
 * say it did. FLIP_STALL is in the deferred set (vk/draw.c), so off the render
 * thread the caller spin-waits for vkQueueSubmit and not for the fence, and the
 * copy the flip pre-recorded (pgraph_vk_prerecord_display_download) is still
 * sitting in the staging buffer: pgraph_vk_complete_staged_downloads() is the
 * only writer of staging->VRAM and nothing on this path had called it. Reading
 * d->vram_ptr here therefore returned the most recently COMPLETED display
 * download -- the previous frame in the steady state, older when the display
 * thread had not presented -- filed under this frame's draw records, with
 * nothing in the file saying so. For #77, whose whole method is "decide from
 * the PPMs which frames show the artifact, then read those frames' draws", a
 * systematic one-frame shift hands the artifact's state to its neighbour, and
 * because the lag depends on the display thread it is not even a constant
 * offset a reader could undo afterwards.
 *
 * So when images are on, complete the outstanding download first. It costs one
 * fence wait per FRAME, at the flip, where a stall already lives -- not a
 * finish per draw: nothing here submits, and cb_draws/submits are untouched.
 * Under `noimages` it costs nothing, because nothing calls it.
 *
 * THE COMPLETION IS NOT ITSELF THE PAIRING. It completes whatever downloads
 * were outstanding, and the display surface is among them only when the flip's
 * pgraph_vk_prerecord_display_download() recorded one. That call has early
 * returns which are ordinary per-frame events rather than corner cases: an
 * eviction, a shelving or a non-TCG flush earlier in the frame leaves
 * num_deferred_downloads non-zero (vk/surface.c), and a finish that ended the
 * command buffer with no draw since leaves !in_command_buffer. On such a frame
 * the completion runs, waits a real fence, writes somebody else's copy into
 * VRAM, and the display surface's pixels never left its VkImage -- which is
 * exactly the one-frame-behind image above, in a narrower state, and the
 * earlier version of this code recorded a fence slot for it as though the
 * pairing had been established.
 *
 * The test costs nothing and is exact: a download that landed clears its
 * surface's draw_dirty (vk/surface.c, both the batched entries and the display
 * pre-download). So after the completion, draw_dirty on the display surface IS
 * the question "does VRAM hold this frame". Still dirty means it does not, and
 * the frame writes NO image -- `"image": null`, `img_sync: FDUMP_IMG_STALE`,
 * counted for the close line. Deliberately not fixed by forcing a download
 * here: that is a pgraph_vk_finish(SURFACE_DOWN) at every flip, a cost the
 * headline claim must not quietly acquire.
 *
 * So `img_sync` on a frame that names an image is the pairing, checkable from
 * the artifact rather than from this comment: >= 0 is the fence slot waited on
 * before the display surface came back clean, and -1 (FDUMP_IMG_NO_WAIT) means
 * nothing was outstanding and the surface was already clean, so VRAM held the
 * frame either way. -2 (FDUMP_IMG_STALE) appears only on frames with no
 * image. */
static void fdump_end_frame(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    char image[128] = "";
    unsigned int iw = 0, ih = 0;
    int img_sync = FDUMP_IMG_NO_WAIT;

    /* Schema 8's `watchNN`: a frame that logged no draw writes nothing and
     * does not count; "f" still advances, so it numbers flips. */
    if (fdump.watch_max && !fdump.watch_in_frame) {
        fdump.submit_at_frame_start = qatomic_read(&r->submit_count);
        fdump.frame_index++;
        fdump.draw_index = 0;
        return;
    }

    if (fdump.images) {
        if (r->num_deferred_downloads > 0) {
            /* Which fence the completion below will wait on, read before the
             * call clears it. The same two cases the callee distinguishes. */
            img_sync = r->display_predownload_pending
                           ? r->display_predownload_frame_index
                           : r->deferred_downloads_frame;
        }
        pgraph_vk_download_surface_complete_deferred(d);

        VGADisplayParams vdp;
        d->vga.get_params(&d->vga, &vdp);
        SurfaceBinding *disp =
            pgraph_vk_surface_get_within(d, d->pcrtc.start + vdp.line_offset);
        if (disp && disp->width && disp->height && disp->draw_dirty) {
            /* The completion above did not cover this surface -- the flip's
             * pre-record bailed -- so VRAM still holds an older frame. See the
             * header comment: write nothing rather than a picture the record
             * would claim belongs to these draws. */
            img_sync = FDUMP_IMG_STALE;
            fdump.images_stale++;
            if (!fdump.stale_warned) {
                fdump.stale_warned = true;
                FDUMP_LOG("framedump: no image for f%d and any later frame "
                          "like it: the display surface was still dirty after "
                          "the download completion, so VRAM holds an older "
                          "frame. Count is in the close line.\n",
                          fdump.frame_index);
            }
        } else if (disp && disp->width && disp->height) {
            char name[128];
            snprintf(name, sizeof(name), "%s%u_f%03d.ppm", FDUMP_PREFIX,
                     fdump.session, fdump.frame_index);
            char path[800];
            snprintf(path, sizeof(path), "%s/%s", fdump.base, name);
            /* Only name the file if it was actually written: the record used
             * to carry the name and charge iw*ih*3 to the cap whether or not
             * the write happened, so a failed dump shortened itself for bytes
             * that do not exist and pointed at a file that is not there. */
            if (dump_surface_ppm(d, disp, path)) {
                snprintf(image, sizeof(image), "%s", name);
                iw = disp->width;
                ih = disp->height;
                fdump.bytes_written += (uint64_t)iw * ih * 3;
            } else {
                /* On the tag a dispatched run keeps, unlike the callee's own
                 * DIAG_LOG line. The record below carries "image": null. */
                FDUMP_LOG("framedump: image %s not written\n", path);
            }
        }
    }

    uint32_t submits = qatomic_read(&r->submit_count);
    int n = fprintf(fdump.fp,
                    "{\"t\":\"frame\",\"f\":%d,\"draws\":%d,"
                    "\"submits_in_frame\":%u,\"submits\":%u,"
                    "\"nv2a_frame\":%u,\"image\":%s%s%s,\"w\":%u,\"h\":%u,"
                    "\"img_sync\":%d,"
                    "\"diag_active\":%d,\"wall\":%lld}\n",
                    fdump.frame_index, fdump.draw_index,
                    submits - fdump.submit_at_frame_start, submits,
                    g_nv2a_stats.frame_count,
                    image[0] ? "\"" : "null", image, image[0] ? "\"" : "",
                    iw, ih, img_sync, qatomic_read(&diag_frame_active),
                    (long long)time(NULL));
    if (n > 0) {
        fdump.bytes_written += n;
    }
    fflush(fdump.fp);

    fdump.submit_at_frame_start = submits;
    fdump.frame_index++;
    fdump.draw_index = 0;
    fdump.cons_draw = -1;
    if (fdump.watch_max) {
        fdump.watch_in_frame = 0;
    } else {
        fdump.frames_remaining--;
    }

    if (fdump.frames_remaining <= 0) {
        fdump_close("all frames dumped");
    } else if (fdump.bytes_written >= fdump.byte_limit) {
        fdump_close("byte cap reached");
    }
}

static void pgraph_vk_flip_stall(NV2AState *d)
{
    if (qatomic_read(&diag_frame_pending) || qatomic_read(&diag_frame_active)) {
        DIAG_LOG("flip_stall: ENTER pending=%d active=%d\n",
                 qatomic_read(&diag_frame_pending),
                 qatomic_read(&diag_frame_active));
    }
#ifdef XBOX
    {
        extern volatile int32_t *xbox_ram_fp_active_ptr;
        extern uintptr_t *xbox_ram_fp_vram_base_ptr;
        if (xbox_ram_fp_active_ptr &&
            !qatomic_read(xbox_ram_fp_active_ptr)) {
            if (xbox_ram_fp_vram_base_ptr) {
                pcibus_t bar1 = pci_get_bar_addr(PCI_DEVICE(d), 1);
                *xbox_ram_fp_vram_base_ptr = (uintptr_t)bar1;
                error_report("[TLB-FP] vram_pci_base=0x%lx (BAR1)",
                             (unsigned long)bar1);
            }
            qatomic_set(xbox_ram_fp_active_ptr, 1);
            error_report("[TLB-FP] activated after first flip");
        }
    }
#endif
    {
        static int dbg_flip = 0;
        if (dbg_flip < 30 || qatomic_read(&diag_frame_pending) || qatomic_read(&diag_frame_active)) {
            PGRAPHVkState *r = d->pgraph.vk_renderer_state;
            DIAG_LOG("flip_stall entered: pending=%d active=%d\n",
                     qatomic_read(&diag_frame_pending),
                     qatomic_read(&diag_frame_active));
            DBG_LOG("[FLIP] flip_stall: in_cb=%d frame=%d submit=%d",
                    r->in_command_buffer, r->current_frame,
                    (int)r->submit_count);
            dbg_flip++;
        }
    }
    /*
     * Pre-record framebuffer download into the current command buffer before
     * the flip stall finish submits it. This piggybacks the surface-to-staging
     * copy onto the same GPU submission as the frame's draws, eliminating a
     * separate SURFACE_DOWN finish (one fewer vkQueueSubmit + fence cycle).
     */
    pgraph_vk_prerecord_display_download(d);

    pgraph_vk_finish(&d->pgraph, VK_FINISH_REASON_FLIP_STALL);

    {
        PGRAPHVkState *r = d->pgraph.vk_renderer_state;
        r->frame_was_skipped = r->frame_skip_active;
        if (r->frame_skip_active) {
            r->blend_after_skip = true;
        }

        if (xemu_get_frame_skip() && d->defer_count >= 6) {
            int dc = d->defer_count;
            int skip_pattern;
            if (dc >= 21)      skip_pattern = 3;
            else if (dc >= 16) skip_pattern = 2;
            else if (dc >= 11) skip_pattern = 1;
            else               skip_pattern = 0;

            r->skip_counter++;
            switch (skip_pattern) {
            case 0: r->frame_skip_active = (r->skip_counter % 4) == 0; break; /* 25% */
            case 1: r->frame_skip_active = (r->skip_counter % 5) == 0; break; /* 20% */
            case 2: r->frame_skip_active = (r->skip_counter % 3) == 0; break; /* 33% */
            case 3: r->frame_skip_active = (r->skip_counter % 2) == 0; break; /* 50% */
            default: r->frame_skip_active = false; break;
            }
        } else {
            r->frame_skip_active = false;
            r->skip_counter = 0;
        }
    }

    if (qatomic_read(&diag_frame_active)) {
        DIAG_LOG("flip_stall: diag active, frame_idx=%d/%d, %d draws captured, json_len=%zu\n",
                 diag_current_frame_index, diag_total_frames,
                 diag_draw_index, diag_json_len);
        /* Save current frame's draw call data */
        int fi = diag_current_frame_index;
        if (fi < diag_total_frames) {
            diag_frame_bufs[fi] = diag_json_buf ? g_strndup(diag_json_buf, diag_json_len) : NULL;
            diag_frame_lens[fi] = diag_json_len;
            diag_frame_nums[fi] = diag_frame_num;
            diag_frame_draw_counts[fi] = diag_draw_index;

            /* Dump final framebuffer PPM for this frame.
             * Always dump the display surface (not just the bound color
             * surface) so we can see exactly what the display path shows,
             * including CPU-written content.
             */
            {
                PGRAPHVkState *diag_r = d->pgraph.vk_renderer_state;
                pgraph_vk_finish(&d->pgraph, VK_FINISH_REASON_SURFACE_DOWN);

                /* Dump bound color surface if draw-dirty */
                if (diag_r->color_binding && diag_r->color_binding->draw_dirty) {
                    pgraph_vk_surface_download_if_dirty(d, diag_r->color_binding);
                    char ppm_path[800];
                    snprintf(ppm_path, sizeof(ppm_path),
                             "%s/frame_%d_final_color.ppm", diag_session_dir, fi);
                    dump_surface_ppm(d, diag_r->color_binding, ppm_path);
                }
                if (diag_r->zeta_binding && diag_r->zeta_binding->draw_dirty) {
                    pgraph_vk_surface_download_if_dirty(d, diag_r->zeta_binding);
                    char ppm_path[800];
                    snprintf(ppm_path, sizeof(ppm_path),
                             "%s/frame_%d_final_depth.ppm", diag_session_dir, fi);
                    dump_surface_ppm(d, diag_r->zeta_binding, ppm_path);
                }

                /* Always dump the display surface VRAM content */
                VGADisplayParams vdp;
                d->vga.get_params(&d->vga, &vdp);
                hwaddr disp_addr = d->pcrtc.start + vdp.line_offset;
                SurfaceBinding *disp_surf =
                    pgraph_vk_surface_get_within(d, disp_addr);
                if (disp_surf) {
                    /* Download VkImage to VRAM first if GPU rendered to it */
                    if (disp_surf->draw_dirty) {
                        pgraph_vk_surface_download_if_dirty(d, disp_surf);
                    }
                    char ppm_path[800];
                    snprintf(ppm_path, sizeof(ppm_path),
                             "%s/frame_%d_display.ppm", diag_session_dir, fi);
                    dump_surface_ppm(d, disp_surf, ppm_path);
                    DIAG_LOG("dumped display surface: vram=0x%x %ux%u to %s\n",
                             (unsigned)disp_surf->vram_addr,
                             disp_surf->width, disp_surf->height, ppm_path);
                } else {
                    DIAG_LOG("no display surface found at addr=0x%lx\n",
                             (unsigned long)disp_addr);
                }
            }

            /* Compute frame diff against previous frame */
            if (fi > 0) {
                int max_draws = diag_draw_index > diag_prev_draw_count
                                ? diag_draw_index : diag_prev_draw_count;
                int changed_count = 0;
                char changed_list[4096] = "";
                size_t cl_len = 0;
                bool draw_count_changed =
                    (diag_draw_index != diag_prev_draw_count);

                for (int di = 0; di < max_draws; di++) {
                    bool changed = false;
                    if (di >= diag_draw_index || di >= diag_prev_draw_count) {
                        changed = true;
                    } else if (diag_cur_fingerprints[di].shader_hash !=
                                   diag_prev_fingerprints[di].shader_hash ||
                               diag_cur_fingerprints[di].state_hash !=
                                   diag_prev_fingerprints[di].state_hash) {
                        changed = true;
                    }
                    if (changed) {
                        changed_count++;
                        size_t prev_len = cl_len;
                        int n = snprintf(changed_list + cl_len,
                                         sizeof(changed_list) - cl_len,
                                         "%s%d", cl_len > 0 ? ", " : "", di);
                        if (n > 0 && cl_len + n < sizeof(changed_list)) {
                            cl_len += n;
                        } else {
                            /* Overflowed — revert to last good position */
                            changed_list[prev_len] = '\0';
                            cl_len = prev_len;
                            break;
                        }
                    }
                }

                diag_diff_append(
                    "%s    {\n"
                    "      \"from_frame\": %d,\n"
                    "      \"to_frame\": %d,\n"
                    "      \"draw_count_changed\": %s,\n"
                    "      \"from_draw_count\": %d,\n"
                    "      \"to_draw_count\": %d,\n"
                    "      \"changed_draw_count\": %d,\n"
                    "      \"draws_with_state_changes\": [%s],\n"
                    "      \"summary\": \"%d draw(s) changed state out of %d total\"\n"
                    "    }",
                    diag_first_diff ? "" : ",\n",
                    fi - 1, fi,
                    draw_count_changed ? "true" : "false",
                    diag_prev_draw_count, diag_draw_index,
                    changed_count, changed_list,
                    changed_count, max_draws);
                diag_first_diff = false;
            }

            /* Save current fingerprints as previous for next frame */
            memcpy(diag_prev_fingerprints, diag_cur_fingerprints,
                   sizeof(DiagDrawFingerprint) * diag_draw_index);
            diag_prev_draw_count = diag_draw_index;
        }

        diag_current_frame_index++;
        diag_frames_remaining--;

        DIAG_LOG("frame %u captured (%d/%d, %d draw calls)\n",
                 diag_frame_num, diag_current_frame_index, diag_total_frames,
                 diag_draw_index);

        if (diag_frames_remaining <= 0) {
            /* All frames captured — write session JSON and clean up */
            DIAG_LOG("all frames done, writing session JSON...\n");
            diag_write_session_json();
            diag_cleanup_session();
            qatomic_set(&diag_frame_active, 0);
            DIAG_LOG("session %u complete\n", diag_session_id);
        } else {
            /* Reset for next frame */
            DIAG_LOG("resetting for next frame, %d remaining\n",
                     diag_frames_remaining);
            diag_draw_index = 0;
            diag_json_len = 0;
            diag_frame_num = g_nv2a_stats.frame_count;
        }
    }

    {
        int pending = qatomic_read(&diag_frame_pending);
        if (pending > 0) {
            /* If a previous session is still active, finalize it first */
            if (qatomic_read(&diag_frame_active)) {
                DIAG_LOG("flip_stall: aborting active session, writing partial data\n");
                diag_total_frames = diag_current_frame_index;
                if (diag_total_frames > 0) {
                    diag_write_session_json();
                }
                diag_cleanup_session();
                qatomic_set(&diag_frame_active, 0);
            }

            DIAG_LOG("flip_stall: pending=%d, starting capture\n", pending);
            qatomic_set(&diag_frame_pending, 0);
            diag_frame_num = g_nv2a_stats.frame_count;
            diag_draw_index = 0;
            diag_json_len = 0;
            diag_init_session(diag_frame_num, pending);
            qatomic_set(&diag_frame_active, 1);
            DIAG_LOG("capture started: %d frames at frame %u\n",
                     pending, diag_frame_num);
        }
    }

    /* The live frame dump closes the frame here, after the flip's own
     * pgraph_vk_finish above, and then looks for a new arm. With images on
     * that costs ONE FENCE WAIT per frame -- the completion of the download
     * the flip pre-recorded, see fdump_end_frame -- and none under `noimages`.
     * Neither call submits or records Vulkan work, and nothing here is per
     * draw, which is the claim the dump exists to make. */
    if (fdump.fp) {
        fdump_end_frame(d);
    }
    fdump_poll_marker(d);

    pgraph_vk_debug_frame_terminator();
}

static void pgraph_vk_pre_savevm_trigger(NV2AState *d)
{
    qatomic_set(&d->pgraph.vk_renderer_state->download_dirty_surfaces_pending, true);
    qemu_event_reset(&d->pgraph.vk_renderer_state->dirty_surfaces_download_complete);
}

static void pgraph_vk_pre_savevm_wait(NV2AState *d)
{
    qemu_event_wait(&d->pgraph.vk_renderer_state->dirty_surfaces_download_complete);
}

static void pgraph_vk_pre_shutdown_trigger(NV2AState *d)
{
    // qatomic_set(&d->pgraph.vk_renderer_state->shader_cache_writeback_pending, true);
    // qemu_event_reset(&d->pgraph.vk_renderer_state->shader_cache_writeback_complete);
}

static void pgraph_vk_pre_shutdown_wait(NV2AState *d)
{
    // qemu_event_wait(&d->pgraph.vk_renderer_state->shader_cache_writeback_complete);   
}

static int pgraph_vk_get_framebuffer_surface(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    qemu_mutex_lock(&d->pfifo.lock);

    VGADisplayParams vga_display_params;
    d->vga.get_params(&d->vga, &vga_display_params);

    SurfaceBinding *surface = pgraph_vk_surface_get_within(
        d, d->pcrtc.start + vga_display_params.line_offset);
    if (surface == NULL || !surface->color) {
        qemu_mutex_unlock(&d->pfifo.lock);
        return 0;
    }

    assert(surface->color);

    surface->frame_time = pg->frame_time;

#if HAVE_EXTERNAL_MEMORY
    if (r->display.use_external_memory) {
        DisplayImage *ready = &r->display.images[r->display.display_idx];
        if (ready->valid) {
            if (ready->fence_submitted) {
                VK_CHECK(vkWaitForFences(r->device, 1, &ready->fence,
                                         VK_TRUE, UINT64_MAX));
                ready->fence_submitted = false;
            }
            int tex = ready->gl_texture_id;

            qemu_event_reset(&d->pgraph.sync_complete);
            qatomic_set(&pg->sync_pending, true);
            pfifo_kick(d);
            qemu_mutex_unlock(&d->pfifo.lock);
            return tex;
        }
        qemu_event_reset(&d->pgraph.sync_complete);
        qatomic_set(&pg->sync_pending, true);
        pfifo_kick(d);
        qemu_mutex_unlock(&d->pfifo.lock);
        qemu_event_wait(&d->pgraph.sync_complete);
        ready = &r->display.images[r->display.display_idx];
        if (ready->valid && ready->fence_submitted) {
            VK_CHECK(vkWaitForFences(r->device, 1, &ready->fence,
                                     VK_TRUE, UINT64_MAX));
            ready->fence_submitted = false;
        }
        return ready->valid ? ready->gl_texture_id : 0;
    }
    qemu_mutex_unlock(&d->pfifo.lock);
    pgraph_vk_wait_for_surface_download(surface);
    return 0;
#else
    qemu_mutex_unlock(&d->pfifo.lock);
    pgraph_vk_wait_for_surface_download(surface);
    return 0;
#endif
}

static PGRAPHRenderer pgraph_vk_renderer = {
    .type = CONFIG_DISPLAY_RENDERER_VULKAN,
    .name = "Vulkan",
    .ops = {
        .init = pgraph_vk_init,
        .early_context_init = early_context_init,
        .finalize = pgraph_vk_finalize,
        .clear_report_value = pgraph_vk_clear_report_value,
        .clear_surface = pgraph_vk_clear_surface,
        .draw_begin = pgraph_vk_draw_begin,
        .draw_end = pgraph_vk_draw_end,
        .flip_stall = pgraph_vk_flip_stall,
        .flush_draw = pgraph_vk_flush_draw,
        .get_report = pgraph_vk_get_report,
        .image_blit = pgraph_vk_image_blit,
        .solid_line = pgraph_vk_solid_line,
        .pre_savevm_trigger = pgraph_vk_pre_savevm_trigger,
        .pre_savevm_wait = pgraph_vk_pre_savevm_wait,
        .pre_shutdown_trigger = pgraph_vk_pre_shutdown_trigger,
        .pre_shutdown_wait = pgraph_vk_pre_shutdown_wait,
        .process_pending = pgraph_vk_process_pending,
        .process_pending_reports = pgraph_vk_process_pending_reports,
        .surface_update = pgraph_vk_surface_update,
        .set_surface_scale_factor = pgraph_vk_set_surface_scale_factor,
        .get_surface_scale_factor = pgraph_vk_get_surface_scale_factor,
        .get_framebuffer_surface = pgraph_vk_get_framebuffer_surface,
    }
};

static void __attribute__((constructor)) register_renderer(void)
{
    pgraph_renderer_register(&pgraph_vk_renderer);
}

void pgraph_vk_force_register(void)
{
    static bool registered = false;
    if (registered) {
        return;
    }
    pgraph_renderer_register(&pgraph_vk_renderer);
    registered = true;
}

void pgraph_vk_check_memory_budget(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;

    VkPhysicalDeviceMemoryProperties const *props;
    vmaGetMemoryProperties(r->allocator, &props);

    g_autofree VmaBudget *budgets = g_malloc_n(props->memoryHeapCount, sizeof(VmaBudget));
    vmaGetHeapBudgets(r->allocator, budgets);

    /* Use a high threshold — only trim when genuinely near exhaustion.
     * The previous 0.6 on Android caused constant trim cycles because
     * non-texture allocations (surfaces, buffers) alone exceeded 60%. */
#ifdef __ANDROID__
    const double budget_threshold = 0.85;
#else
    const double budget_threshold = 0.90;
#endif

    /* Find the worst over-budget heap and compute excess bytes */
    size_t max_excess = 0;
    for (uint32_t i = 0; i < props->memoryHeapCount; i++) {
        VmaBudget *b = &budgets[i];
        if (b->budget == 0) {
            continue;
        }
        size_t target = (size_t)(b->budget * budget_threshold);
        if (b->statistics.allocationBytes > target) {
            size_t excess = b->statistics.allocationBytes - target;
            if (excess > max_excess) {
                max_excess = excess;
            }
        }
    }

    if (max_excess > 0) {
        pgraph_vk_trim_texture_cache_bytes(pg, max_excess);
    }
}
