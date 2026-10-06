/*
 * Geforce NV2A PGRAPH Vulkan Renderer
 *
 * Copyright (c) 2024 Matt Borgerson
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

void pgraph_vk_init_reports(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;

    VK_LOG("init_reports: begin");

    QSIMPLEQ_INIT(&r->report_queue);
    QSIMPLEQ_INIT(&r->report_pool);
    r->num_queries_in_flight = 0;
    r->max_queries_in_flight = 1024;
    r->new_query_needed = false;
    r->query_in_flight = false;
    r->zpass_pixel_count_result = 0;

    r->report_pool_entries =
        g_malloc_n(r->max_queries_in_flight, sizeof(QueryReport));
    for (int i = 0; i < r->max_queries_in_flight; i++) {
        QSIMPLEQ_INSERT_TAIL(&r->report_pool,
                              &r->report_pool_entries[i], entry);
    }

    r->query_results =
        g_malloc_n(r->max_queries_in_flight, sizeof(uint64_t));

    VkQueryPoolCreateInfo pool_create_info = (VkQueryPoolCreateInfo){
        .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
        .queryType = VK_QUERY_TYPE_OCCLUSION,
        .queryCount = r->max_queries_in_flight,
    };
    VK_CHECK(
        vkCreateQueryPool(r->device, &pool_create_info, NULL, &r->query_pool));
}

void pgraph_vk_finalize_reports(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;

    QSIMPLEQ_INIT(&r->report_queue);
    QSIMPLEQ_INIT(&r->report_pool);

    g_free(r->report_pool_entries);
    r->report_pool_entries = NULL;
    g_free(r->query_results);
    r->query_results = NULL;

    vkDestroyQueryPool(r->device, r->query_pool, NULL);
}

static QueryReport *alloc_report(PGRAPHVkState *r)
{
    QueryReport *report = QSIMPLEQ_FIRST(&r->report_pool);
    if (report) {
        QSIMPLEQ_REMOVE_HEAD(&r->report_pool, entry);
    } else {
        report = g_malloc(sizeof(QueryReport));
    }
    return report;
}

static void free_report(PGRAPHVkState *r, QueryReport *report)
{
    QSIMPLEQ_INSERT_TAIL(&r->report_pool, report, entry);
}

void pgraph_vk_clear_report_value(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    QueryReport *report = alloc_report(r);
    report->clear = true;
    report->parameter = 0;
    report->query_count = r->num_queries_in_flight;
    QSIMPLEQ_INSERT_TAIL(&r->report_queue, report, entry);

    r->new_query_needed = true;
}

void pgraph_vk_get_report(NV2AState *d, uint32_t parameter)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    uint8_t type = GET_MASK(parameter, NV097_GET_REPORT_TYPE);
    assert(type == NV097_GET_REPORT_TYPE_ZPASS_PIXEL_CNT);

    QueryReport *report = alloc_report(r);
    report->clear = false;
    report->parameter = parameter;
    report->query_count = r->num_queries_in_flight;
    QSIMPLEQ_INSERT_TAIL(&r->report_queue, report, entry);

    r->new_query_needed = true;
}

/*
 * #804 instrumentation, off unless asked for, for reading what the guest gets
 * back from its visibility tests:
 *
 *   HAKUX_OCCL_LOG=<s>  from <s> seconds after the first report is processed,
 *                       one hakuX-lane line per guest frame (pg->frame_time)
 *                       with the queries read, how many were nonzero, how
 *                       many submitted frames were still running on the GPU
 *                       when they were read, and the first values the guest
 *                       was handed. Capped at OCCL_MAX_LINES lines.
 *   HAKUX_OCCL_WAIT=0   skip the fence wait below (the code before #804's fix),
 *                       so one build gives both sides of the comparison.
 */
#ifdef __ANDROID__
#define OCCL_LOG(...) \
    __android_log_print(ANDROID_LOG_INFO, "hakuX-lane", __VA_ARGS__)
#else
#define OCCL_LOG(...) do { \
        fprintf(stderr, __VA_ARGS__); fprintf(stderr, "\n"); } while (0)
#endif
#define OCCL_MAX_LINES 6000
#define OCCL_MAX_VALUES 48

static struct {
    int enabled;          /* -1 unread, 0 off, 1 on */
    int wait;             /* the #804 fence wait: 1 on (default), 0 off */
    int64_t after_us;
    int64_t t0;
    uint32_t lines;
    uint32_t frame;       /* pg->frame_time the counters below belong to */
    uint32_t procs, queries, q_nonzero, pending, reports, r_nonzero;
    uint64_t r_max;
    int nvals;
    char vals[OCCL_MAX_VALUES * 8 + 1];
} occl = { .enabled = -1, .wait = 1 };

static void occl_init(void)
{
    const char *e = getenv("HAKUX_OCCL_LOG");
    occl.enabled = e && e[0];
    occl.after_us = occl.enabled ? (int64_t)atoi(e) * 1000000 : 0;
    const char *w = getenv("HAKUX_OCCL_WAIT");
    occl.wait = !(w && !strcmp(w, "0"));
    if (occl.enabled || !occl.wait) {
        OCCL_LOG("[occl804] config log=%d after_s=%d wait=%d", occl.enabled,
                 (int)(occl.after_us / 1000000), occl.wait);
    }
}

static bool occl_on(void)
{
    if (!occl.enabled || occl.lines >= OCCL_MAX_LINES) {
        return false;
    }
    int64_t now = g_get_monotonic_time();
    if (!occl.t0) {
        occl.t0 = now;
    }
    return now - occl.t0 >= occl.after_us;
}

static void occl_flush(uint32_t next_frame)
{
    if (occl.procs) {
        OCCL_LOG("[occl804] f=%u wait=%d procs=%u q=%u qnz=%u pend=%u "
                 "rep=%u repnz=%u repmax=%" PRIu64 " v=%s",
                 occl.frame, occl.wait, occl.procs, occl.queries,
                 occl.q_nonzero, occl.pending, occl.reports, occl.r_nonzero,
                 occl.r_max, occl.nvals ? occl.vals : "-");
        occl.lines++;
    }
    occl.frame = next_frame;
    occl.procs = occl.queries = occl.q_nonzero = occl.pending = 0;
    occl.reports = occl.r_nonzero = 0;
    occl.r_max = 0;
    occl.nvals = 0;
    occl.vals[0] = 0;
}

static void occl_report(uint64_t value)
{
    occl.reports++;
    if (value) {
        occl.r_nonzero++;
    }
    if (value > occl.r_max) {
        occl.r_max = value;
    }
    if (occl.nvals < OCCL_MAX_VALUES) {
        size_t len = strlen(occl.vals);
        snprintf(occl.vals + len, sizeof(occl.vals) - len, "%s%" PRIu64,
                 occl.nvals ? "," : "", MIN(value, (uint64_t)9999999));
        occl.nvals++;
    }
}

void pgraph_vk_process_pending_reports_internal(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    NV2A_VK_DGROUP_BEGIN("Processing queries");

    assert(!r->in_command_buffer);

    uint64_t *query_results = r->query_results;

    if (occl.enabled < 0) {
        occl_init();
    }
    bool log = occl_on() && (r->num_queries_in_flight > 0 ||
                             !QSIMPLEQ_EMPTY(&r->report_queue));
    if (log) {
        if (pg->frame_time != occl.frame) {
            occl_flush(pg->frame_time);
        }
        occl.procs++;
        for (int i = 0; i < r->num_active_frames; i++) {
            if (qatomic_read(&r->frame_submitted[i]) &&
                vkGetFenceStatus(r->device, r->frame_fences[i]) ==
                    VK_NOT_READY) {
                occl.pending++;
            }
        }
    }

    if (r->num_queries_in_flight > 0 && occl.wait) {
        /*
         * #804: the queries were recorded into a command buffer that a
         * deferred finish (FLIP_STALL, PRESENTING, STALLED,
         * SURFACE_DOWN_FLUSH) has submitted and not waited for. Each one was
         * reset with vkCmdResetQueryPool, which is a GPU command: until the
         * GPU reaches it, the slot still reads as available and holds the
         * count from the last command buffer that used the same index
         * (Turnip keeps availability in GPU-written memory,
         * tu_query_pool.cc), so WAIT_BIT below returns that old count at
         * once. The guest then gets the previous frame's visibility for this
         * frame's test. Wait for every submitted frame first; only a finish
         * that recorded a query pays for it.
         */
        for (int i = 0; i < r->num_active_frames; i++) {
            if (qatomic_read(&r->frame_submitted[i])) {
                VK_CHECK(vkWaitForFences(r->device, 1, &r->frame_fences[i],
                                         VK_TRUE, UINT64_MAX));
            }
        }
    }

    if (r->num_queries_in_flight > 0) {
        size_t size_of_results = r->num_queries_in_flight * sizeof(uint64_t);
        VkResult result;
        do {
            result = vkGetQueryPoolResults(
                r->device, r->query_pool, 0, r->num_queries_in_flight,
                size_of_results, query_results, sizeof(uint64_t),
                VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);
        } while (result == VK_NOT_READY);

        if (log) {
            occl.queries += r->num_queries_in_flight;
            for (int i = 0; i < r->num_queries_in_flight; i++) {
                if (query_results[i]) {
                    occl.q_nonzero++;
                }
            }
        }
    }

    // Write out queries
    int num_results_counted = 0;
    const int result_divisor =
        pg->surface_scale_factor * pg->surface_scale_factor;

    QueryReport *report;
    while ((report = QSIMPLEQ_FIRST(&r->report_queue)) != NULL) {
        assert(report->query_count >= num_results_counted);
        assert(report->query_count <= r->num_queries_in_flight);

        while (num_results_counted < report->query_count) {
            r->zpass_pixel_count_result +=
                query_results[num_results_counted++];
        }

        if (report->clear) {
            NV2A_VK_DPRINTF("Cleared");
            r->zpass_pixel_count_result = 0;
        } else {
            pgraph_write_zpass_pixel_cnt_report(
                d, report->parameter,
                r->zpass_pixel_count_result / result_divisor);
            if (log) {
                occl_report(r->zpass_pixel_count_result / result_divisor);
            }
        }

        QSIMPLEQ_REMOVE_HEAD(&r->report_queue, entry);
        free_report(r, report);
    }

    // Add remaining results
    while (num_results_counted < r->num_queries_in_flight) {
        r->zpass_pixel_count_result += query_results[num_results_counted++];
    }

    r->num_queries_in_flight = 0;
    NV2A_VK_DGROUP_END();
}

void pgraph_vk_process_pending_reports(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    uint32_t *dma_get = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET];
    uint32_t *dma_put = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT];

    if (*dma_get == *dma_put && r->in_command_buffer) {
        if (pg->draw_time != r->last_stall_draw_time) {
            pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED);
            r->last_stall_draw_time = pg->draw_time;
        } else {
            OPT_STAT_INC(stall_batched);
        }
    }
}
