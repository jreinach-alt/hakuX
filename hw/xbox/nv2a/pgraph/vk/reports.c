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

/*
 * #433 (reportasync1010): two switches, both off unless set, both read once
 * when the renderer starts.
 *
 *   HAKUX_REPORT_ASYNC=1  the occlusion reports are read and written to guest
 *                         memory by a thread of their own, after the GPU has
 *                         finished the command buffer that counted them,
 *                         instead of by the thread running the finish, which
 *                         waited for every submitted frame first (#804). See
 *                         ra_internal() below.
 *   HAKUX_REPORT_TRACE=1  one record per GET_REPORT: when it was queued, when
 *                         the finish handed it off, when its fence passed and
 *                         its value was written, which guest frame each of
 *                         those fell in, when the next flip and the next
 *                         GET_REPORT at the same offset came, and what the
 *                         guest had left in the report before it. Summed per
 *                         2 s window on hakuX-lane ("[rtrace] w ..."), with
 *                         at most four sampled records a second
 *                         ("[rtrace] r ...").
 *
 * The write itself is the bytes pgraph_write_zpass_pixel_cnt_report (pgraph.c)
 * writes: the fixed timestamp, the count, and 0 in the last word, which in
 * the NV notifier layout is the status DONE_SUCCESS (0x8000 in the top half
 * would be IN_PROCESS). The async path stores the status word last, after a
 * write barrier, so a guest that arms the status before GET_REPORT and polls
 * it never sees "done" ahead of the count.
 */
#ifdef __ANDROID__
#define RA_LOG(...) \
    __android_log_print(ANDROID_LOG_INFO, "hakuX-lane", __VA_ARGS__)
#else
#define RA_LOG(...) do { \
        fprintf(stderr, __VA_ARGS__); fprintf(stderr, "\n"); } while (0)
#endif

#define RA_TIMESTAMP 0x0011223344556677ULL
/* Queries one command buffer may hold, as before; async gives every frame
 * slot its own range of this many. */
#define RA_SLOT_QUERIES 1024

typedef struct RaReport {
    bool clear;
    int qend;          /* the batch's queries counted before this report */
    uint8_t *dst;      /* the guest's 16-byte report; NULL for a clear */
    uint32_t trace;    /* trace record, when tracing */
} RaReport;

typedef struct RaBatch {
    struct RaBatch *next;
    int slot;          /* frame slot whose fence covers the queries, or -1 */
    bool wait_all;     /* slot count changed under it: wait as #804 did */
    int qfirst, nq;
    int divisor;
    int nreports;
    RaReport reports[];
} RaBatch;

static struct {
    bool on;
    bool started;
    PGRAPHVkState *r;
    QemuThread thread;
    QemuMutex lock;
    QemuCond cond;
    RaBatch *head, *tail;
    bool busy, quit;
    /* batches queued or running that will read a slot's fence and queries */
    int pending[NUM_SUBMIT_FRAMES];
    /* the slot, query range and slot count the open command buffer uses */
    int cur_slot, cur_base, cur_nframes;
    /* the running count, 32 bits as zpass_pixel_count_result; the reader's
     * alone once started */
    uint32_t sum;
    uint64_t *results;
} ra;

/* Trace: one record per GET_REPORT, in queue order. */
#define RT_RING 8192
#define RT_HASH 4096
#define RT_FLIPS 16
#define RT_NB 10
#define RT_MAX_LINES 8000
#define RT_WINDOW_US 2000000
#define RT_RAW_US 250000

typedef struct RtRec {
    int64_t t_q, t_e, t_f, t_w;
    int frame_q, frame_e;
    uint32_t off;
    uint32_t st_q;
} RtRec;

static struct {
    bool on;
    QemuMutex lock;
    PGRAPHState *pg;
    RtRec *ring;
    uint32_t q_seq, e_seq;
    struct {
        uint32_t off, seq;
        bool valid;
    } last[RT_HASH];
    int64_t flip_t[RT_FLIPS];
    int flip_frame[RT_FLIPS];
    int seen_frame;
    int64_t t0, t_win, t_raw;
    uint32_t lines;
    /* per window */
    uint32_t n, h_e[RT_NB], h_f[RT_NB], h_w[RT_NB], h_flip[RT_NB],
        h_next[RT_NB];
    uint32_t fl_e[4], fl_w[4];
    uint32_t late, flip_b4_w, no_flip, reuse, reuse_b4_w;
    uint32_t armed, st_changed, ts_ours, last_st;
    uint32_t gates, waits;
    int64_t gate_us, wait_us;
} rt;

/* Bucket edges, microseconds: 0.25 0.5 1 2 4 8 16.7 33.3 66.7 ms, and over. */
static const int64_t rt_edges[RT_NB - 1] = {
    250, 500, 1000, 2000, 4000, 8000, 16667, 33333, 66667,
};

static int rt_bucket(int64_t us)
{
    int i = 0;
    while (i < RT_NB - 1 && us >= rt_edges[i]) {
        i++;
    }
    return i;
}

static void rt_hist(char *buf, size_t size, const uint32_t *h)
{
    size_t len = 0;
    buf[0] = 0;
    for (int i = 0; i < RT_NB && len < size; i++) {
        len += snprintf(buf + len, size - len, "%s%u", i ? "," : "", h[i]);
    }
}

static uint8_t *ra_map(NV2AState *d, uint32_t parameter, bool must)
{
    hwaddr len;
    uint8_t *base = (uint8_t *)nv_dma_map(d, d->pgraph.dma_report, &len);
    hwaddr offset = GET_MASK(parameter, NV097_GET_REPORT_OFFSET);
    if (must) {
        assert(offset < len);
    } else if (offset + 16 > len) {
        return NULL;
    }
    return base + offset;
}

static void rt_init(PGRAPHState *pg)
{
    const char *e = getenv("HAKUX_REPORT_TRACE");
    rt.on = e && !strcmp(e, "1");
    if (!rt.on) {
        return;
    }
    qemu_mutex_init(&rt.lock);
    rt.pg = pg;
    rt.ring = g_new0(RtRec, RT_RING);
    rt.seen_frame = pg->frame_time;
    rt.t0 = rt.t_win = g_get_monotonic_time();
}

/* Window line; rt.lock held. */
static void rt_window_locked(int64_t now)
{
    if (now - rt.t_win < RT_WINDOW_US) {
        return;
    }
    if ((rt.n || rt.reuse || rt.gates || rt.waits) &&
        rt.lines < RT_MAX_LINES) {
        char he[96], hf[96], hw[96], hfl[96], hn[96];
        rt_hist(he, sizeof(he), rt.h_e);
        rt_hist(hf, sizeof(hf), rt.h_f);
        rt_hist(hw, sizeof(hw), rt.h_w);
        rt_hist(hfl, sizeof(hfl), rt.h_flip);
        rt_hist(hn, sizeof(hn), rt.h_next);
        RA_LOG("[rtrace] w mode=%s t=%" PRId64 " win_ms=%" PRId64
               " n=%u e=%s f=%s w=%s flip=%s next=%s fle=%u,%u,%u,%u "
               "flw=%u,%u,%u,%u late=%u flipb4w=%u noflip=%u reuse=%u "
               "reuseb4w=%u armed=%u stchg=%u lastst=%08x tsours=%u "
               "gate=%u/%" PRId64 " wait=%u/%" PRId64,
               ra.on ? "async" : "sync", (now - rt.t0) / 1000,
               (now - rt.t_win) / 1000, rt.n, he, hf, hw, hfl, hn,
               rt.fl_e[0], rt.fl_e[1], rt.fl_e[2], rt.fl_e[3], rt.fl_w[0],
               rt.fl_w[1], rt.fl_w[2], rt.fl_w[3], rt.late, rt.flip_b4_w,
               rt.no_flip, rt.reuse, rt.reuse_b4_w, rt.armed, rt.st_changed,
               rt.last_st, rt.ts_ours, rt.gates, rt.gate_us, rt.waits,
               rt.wait_us);
        rt.lines++;
    }
    rt.t_win = now;
    rt.n = 0;
    memset(rt.h_e, 0, sizeof(rt.h_e));
    memset(rt.h_f, 0, sizeof(rt.h_f));
    memset(rt.h_w, 0, sizeof(rt.h_w));
    memset(rt.h_flip, 0, sizeof(rt.h_flip));
    memset(rt.h_next, 0, sizeof(rt.h_next));
    memset(rt.fl_e, 0, sizeof(rt.fl_e));
    memset(rt.fl_w, 0, sizeof(rt.fl_w));
    rt.late = rt.flip_b4_w = rt.no_flip = rt.reuse = rt.reuse_b4_w = 0;
    rt.armed = rt.st_changed = rt.ts_ours = 0;
    rt.gates = rt.waits = 0;
    rt.gate_us = rt.wait_us = 0;
}

/*
 * The guest frame counter (pg->frame_time, FLIP_INCREMENT_WRITE) moved since
 * the last look: stamp the flips with now. Looked at from GET_REPORT and the
 * end of every finish, the FLIP_STALL one included, so a flip's time here is
 * the end of its FLIP_STALL finish, not the method. rt.lock held.
 */
static void rt_flip_locked(int64_t now)
{
    int f = qatomic_read(&rt.pg->frame_time);
    if (f < rt.seen_frame) {
        rt.seen_frame = f;
    }
    for (int k = MAX(rt.seen_frame + 1, f - RT_FLIPS + 1); k <= f; k++) {
        rt.flip_t[(unsigned)k % RT_FLIPS] = now;
        rt.flip_frame[(unsigned)k % RT_FLIPS] = k;
    }
    rt.seen_frame = f;
}

static void rt_queued(NV2AState *d, uint32_t parameter)
{
    int64_t now = g_get_monotonic_time();
    uint32_t off = GET_MASK(parameter, NV097_GET_REPORT_OFFSET);
    uint8_t *p = ra_map(d, parameter, false);

    qemu_mutex_lock(&rt.lock);
    rt_flip_locked(now);
    uint32_t seq = rt.q_seq++;
    RtRec *e = &rt.ring[seq % RT_RING];
    memset(e, 0, sizeof(*e));
    e->t_q = now;
    e->frame_q = rt.seen_frame;
    e->off = off;
    if (p) {
        e->st_q = ldl_le_p(p + 12);
        if (e->st_q) {
            rt.armed++;
            rt.last_st = e->st_q;
        }
        if (ldq_le_p(p) == RA_TIMESTAMP) {
            rt.ts_ours++;
        }
    }

    unsigned h = (off >> 4) % RT_HASH;
    if (rt.last[h].valid && rt.last[h].off == off &&
        seq - rt.last[h].seq < RT_RING) {
        RtRec *prev = &rt.ring[rt.last[h].seq % RT_RING];
        rt.reuse++;
        rt.h_next[rt_bucket(now - prev->t_q)]++;
        if (!prev->t_w) {
            rt.reuse_b4_w++;
        }
    }
    rt.last[h].off = off;
    rt.last[h].seq = seq;
    rt.last[h].valid = true;
    rt_window_locked(now);
    qemu_mutex_unlock(&rt.lock);
}

/* A finish has reached the reports: note any flip. Returns now. */
static int64_t rt_enter(void)
{
    int64_t now = g_get_monotonic_time();
    qemu_mutex_lock(&rt.lock);
    rt_flip_locked(now);
    qemu_mutex_unlock(&rt.lock);
    return now;
}

/* The finish hands the next GET_REPORT in queue order to the write. */
static uint32_t rt_handoff(int64_t now)
{
    qemu_mutex_lock(&rt.lock);
    uint32_t seq = rt.e_seq++;
    RtRec *e = &rt.ring[seq % RT_RING];
    e->t_e = now;
    e->frame_e = rt.seen_frame;
    qemu_mutex_unlock(&rt.lock);
    return seq;
}

/* About to write record seq's value to dst; t_f is when its fence passed. */
static void rt_written(uint32_t seq, const uint8_t *dst, int64_t t_f)
{
    int64_t now = g_get_monotonic_time();
    int frame_w = qatomic_read(&rt.pg->frame_time);
    uint32_t st_w = dst ? ldl_le_p(dst + 12) : 0;

    qemu_mutex_lock(&rt.lock);
    if (rt.q_seq - seq > RT_RING) {
        qemu_mutex_unlock(&rt.lock);
        return;
    }
    RtRec *e = &rt.ring[seq % RT_RING];
    e->t_f = t_f;
    e->t_w = now;
    rt.n++;
    rt.h_e[rt_bucket(e->t_e - e->t_q)]++;
    rt.h_f[rt_bucket(t_f - e->t_q)]++;
    rt.h_w[rt_bucket(now - e->t_q)]++;
    rt.fl_e[MIN(MAX(e->frame_e - e->frame_q, 0), 3)]++;
    rt.fl_w[MIN(MAX(frame_w - e->frame_q, 0), 3)]++;
    if (frame_w > e->frame_e) {
        rt.late++;
    }
    int k = e->frame_q + 1;
    if (rt.flip_frame[(unsigned)k % RT_FLIPS] == k) {
        int64_t t_flip = rt.flip_t[(unsigned)k % RT_FLIPS];
        rt.h_flip[rt_bucket(t_flip - e->t_q)]++;
        if (t_flip < now) {
            rt.flip_b4_w++;
        }
    } else {
        rt.no_flip++;
    }
    if (st_w != e->st_q) {
        rt.st_changed++;
    }
    if (now - rt.t_raw >= RT_RAW_US && rt.lines < RT_MAX_LINES) {
        rt.t_raw = now;
        RA_LOG("[rtrace] r seq=%u off=%x q2e=%" PRId64 " q2f=%" PRId64
               " q2w=%" PRId64 " fq=%d fe=%d fw=%d stq=%08x stw=%08x",
               seq, e->off, e->t_e - e->t_q, t_f - e->t_q, now - e->t_q,
               e->frame_q, e->frame_e, frame_w, e->st_q, st_w);
        rt.lines++;
    }
    rt_window_locked(now);
    qemu_mutex_unlock(&rt.lock);
}

static void rt_add_wait(bool gate, int64_t us)
{
    qemu_mutex_lock(&rt.lock);
    if (gate) {
        rt.gates++;
        rt.gate_us += us;
    } else {
        rt.waits++;
        rt.wait_us += us;
    }
    qemu_mutex_unlock(&rt.lock);
}

static void *ra_reader(void *opaque);

static void ra_start(PGRAPHVkState *r)
{
    ra.r = r;
    ra.head = ra.tail = NULL;
    ra.busy = ra.quit = false;
    memset(ra.pending, 0, sizeof(ra.pending));
    ra.sum = 0;
    ra.results = g_malloc_n(RA_SLOT_QUERIES, sizeof(uint64_t));
    ra.cur_slot = r->current_frame;
    ra.cur_base = ra.cur_slot * RA_SLOT_QUERIES;
    ra.cur_nframes = r->num_active_frames;
    r->num_queries_in_flight = ra.cur_base;
    r->max_queries_in_flight = ra.cur_base + RA_SLOT_QUERIES;
    qemu_mutex_init(&ra.lock);
    qemu_cond_init(&ra.cond);
    qemu_thread_create(&ra.thread, "nv2a.vk.reports", ra_reader, NULL,
                       QEMU_THREAD_JOINABLE);
    ra.started = true;
    RA_LOG("[reportasync] on: %d slots of %d queries", NUM_SUBMIT_FRAMES,
           RA_SLOT_QUERIES);
}

void pgraph_vk_init_reports(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;

    VK_LOG("init_reports: begin");

    const char *async = getenv("HAKUX_REPORT_ASYNC");
    ra.on = async && !strcmp(async, "1");
    rt_init(pg);

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
        .queryCount = ra.on ? NUM_SUBMIT_FRAMES * RA_SLOT_QUERIES
                            : r->max_queries_in_flight,
    };
    VK_CHECK(
        vkCreateQueryPool(r->device, &pool_create_info, NULL, &r->query_pool));

    if (ra.on) {
        ra_start(r);
    }
}

static void ra_stop(void)
{
    qemu_mutex_lock(&ra.lock);
    ra.quit = true;
    qemu_cond_broadcast(&ra.cond);
    qemu_mutex_unlock(&ra.lock);
    qemu_thread_join(&ra.thread);
    qemu_cond_destroy(&ra.cond);
    qemu_mutex_destroy(&ra.lock);
    g_free(ra.results);
    ra.results = NULL;
    ra.started = false;
}

void pgraph_vk_finalize_reports(PGRAPHState *pg)
{
    PGRAPHVkState *r = pg->vk_renderer_state;

    if (ra.started) {
        ra_stop();
    }

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

    if (rt.on) {
        rt_queued(d, parameter);
    }
}

/* The bytes pgraph_write_zpass_pixel_cnt_report writes, status word last. */
static void ra_write(uint8_t *dst, uint32_t result)
{
    stq_le_p(dst, RA_TIMESTAMP);
    stl_le_p(dst + 8, result);
    smp_wmb();
    stl_le_p(dst + 12, 0);
}

/*
 * Read one batch's queries and write its reports, in queue order. On the
 * reader thread, or on the finishing thread for a wait_all batch once the
 * reader is idle; either way ra.sum has one user at a time.
 */
static void ra_run(PGRAPHVkState *r, RaBatch *b)
{
    int64_t t_f = 0;

    if (b->nq > 0) {
        if (b->wait_all) {
            for (int i = 0; i < r->num_active_frames; i++) {
                if (qatomic_read(&r->frame_submitted[i])) {
                    VK_CHECK(vkWaitForFences(r->device, 1,
                                             &r->frame_fences[i], VK_TRUE,
                                             UINT64_MAX));
                }
            }
        } else {
            VK_CHECK(vkWaitForFences(r->device, 1, &r->frame_fences[b->slot],
                                     VK_TRUE, UINT64_MAX));
        }
        VkResult result;
        do {
            result = vkGetQueryPoolResults(
                r->device, r->query_pool, b->qfirst, b->nq,
                b->nq * sizeof(uint64_t), ra.results, sizeof(uint64_t),
                VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);
        } while (result == VK_NOT_READY);
    }
    if (rt.on) {
        t_f = g_get_monotonic_time();
    }

    int counted = 0;
    for (int i = 0; i < b->nreports; i++) {
        RaReport *rep = &b->reports[i];
        assert(rep->qend >= counted && rep->qend <= b->nq);
        while (counted < rep->qend) {
            ra.sum += ra.results[counted++];
        }
        if (rep->clear) {
            ra.sum = 0;
        } else {
            if (rt.on) {
                rt_written(rep->trace, rep->dst, t_f);
            }
            ra_write(rep->dst, ra.sum / b->divisor);
        }
    }
    while (counted < b->nq) {
        ra.sum += ra.results[counted++];
    }
}

static void *ra_reader(void *opaque)
{
    qemu_mutex_lock(&ra.lock);
    for (;;) {
        while (!ra.head && !ra.quit) {
            qemu_cond_wait(&ra.cond, &ra.lock);
        }
        if (!ra.head) {
            break;
        }
        RaBatch *b = ra.head;
        ra.head = b->next;
        if (!ra.head) {
            ra.tail = NULL;
        }
        ra.busy = true;
        qemu_mutex_unlock(&ra.lock);

        ra_run(ra.r, b);

        qemu_mutex_lock(&ra.lock);
        ra.busy = false;
        if (b->slot >= 0) {
            ra.pending[b->slot]--;
        }
        qemu_cond_broadcast(&ra.cond);
        g_free(b);
    }
    qemu_mutex_unlock(&ra.lock);
    return NULL;
}

/*
 * HAKUX_REPORT_ASYNC=1: the end of every finish. Nothing here waits for the
 * GPU.
 *
 * The open command buffer's queries live in its frame slot's own range of the
 * pool (cur_base .. cur_base + RA_SLOT_QUERIES): begin_query (draw.c) takes
 * its index from num_queries_in_flight, which is set to the slot's base
 * below. The reports queued since the last finish, with the guest address of
 * each taken now, as the synchronous write would take it, go to the reader in
 * one batch with that slot. The reader waits for the slot's fence -- the
 * fence of the submission that reset and counted those queries -- then reads
 * them, so the count written is this command buffer's, never the one the slot
 * held before (#804).
 *
 * The batch is pushed before the finish returns, and the finishes that
 * submit with a slot's fence have already submitted (a deferred finish waits
 * for vkQueueSubmit, wait_frame_submitted; the others wait for the fence), so
 * the reader never waits on a fence that has not been submitted.
 *
 * The slot is not used again until its batch is done: the gate below waits
 * for every batch reading the slot the next command buffer will record into,
 * before that command buffer can reset the slot's queries or its finish reset
 * the slot's fence. With three slots the rotation has already waited for that
 * fence (pgraph_vk_finish), so the gate waits only for the read; a finish on
 * the render thread, which does not rotate, waits for its own batch.
 *
 * If the slot count changed under the open command buffer (the submit-frames
 * setting), the batch is run here, as #804 did, once the reader is idle.
 */
static void ra_internal(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;
    int64_t t_e = rt.on ? rt_enter() : 0;

    int nq = r->num_queries_in_flight - ra.cur_base;
    int nrep = 0;
    QueryReport *report;
    QSIMPLEQ_FOREACH(report, &r->report_queue, entry) {
        nrep++;
    }

    if (nq > 0 || nrep > 0) {
        RaBatch *b = g_malloc(sizeof(RaBatch) + nrep * sizeof(RaReport));
        b->next = NULL;
        b->slot = nq > 0 ? ra.cur_slot : -1;
        b->wait_all = r->num_active_frames != ra.cur_nframes;
        b->qfirst = ra.cur_base;
        b->nq = nq;
        b->divisor = pg->surface_scale_factor * pg->surface_scale_factor;
        b->nreports = 0;
        while ((report = QSIMPLEQ_FIRST(&r->report_queue)) != NULL) {
            assert(report->query_count >= ra.cur_base);
            assert(report->query_count <= r->num_queries_in_flight);
            RaReport *o = &b->reports[b->nreports++];
            o->clear = report->clear;
            o->qend = report->query_count - ra.cur_base;
            o->dst = report->clear ? NULL : ra_map(d, report->parameter, true);
            o->trace = (!report->clear && rt.on) ? rt_handoff(t_e) : 0;
            QSIMPLEQ_REMOVE_HEAD(&r->report_queue, entry);
            free_report(r, report);
        }

        if (b->wait_all) {
            int64_t t0 = rt.on ? g_get_monotonic_time() : 0;
            qemu_mutex_lock(&ra.lock);
            while (ra.head || ra.busy) {
                qemu_cond_wait(&ra.cond, &ra.lock);
            }
            qemu_mutex_unlock(&ra.lock);
            b->slot = -1;
            ra_run(r, b);
            g_free(b);
            if (rt.on) {
                rt_add_wait(false, g_get_monotonic_time() - t0);
            }
        } else {
            qemu_mutex_lock(&ra.lock);
            if (b->slot >= 0) {
                ra.pending[b->slot]++;
            }
            if (ra.tail) {
                ra.tail->next = b;
            } else {
                ra.head = b;
            }
            ra.tail = b;
            qemu_cond_broadcast(&ra.cond);
            qemu_mutex_unlock(&ra.lock);
        }
    }

    int slot = r->current_frame;
    qemu_mutex_lock(&ra.lock);
    if (ra.pending[slot] > 0) {
        int64_t t0 = rt.on ? g_get_monotonic_time() : 0;
        while (ra.pending[slot] > 0) {
            qemu_cond_wait(&ra.cond, &ra.lock);
        }
        if (rt.on) {
            qemu_mutex_unlock(&ra.lock);
            rt_add_wait(true, g_get_monotonic_time() - t0);
            qemu_mutex_lock(&ra.lock);
        }
    }
    qemu_mutex_unlock(&ra.lock);

    ra.cur_slot = slot;
    ra.cur_base = slot * RA_SLOT_QUERIES;
    ra.cur_nframes = r->num_active_frames;
    r->num_queries_in_flight = ra.cur_base;
    r->max_queries_in_flight = ra.cur_base + RA_SLOT_QUERIES;
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

    if (ra.started) {
        ra_internal(d);
        NV2A_VK_DGROUP_END();
        return;
    }

    uint64_t *query_results = r->query_results;
    int64_t t_e = rt.on ? rt_enter() : 0;

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

    int64_t t_f = 0;
    if (rt.on) {
        t_f = g_get_monotonic_time();
        if (r->num_queries_in_flight > 0) {
            rt_add_wait(false, t_f - t_e);
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
            if (rt.on) {
                rt_written(rt_handoff(t_e), ra_map(d, report->parameter, false),
                           t_f);
            }
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

/*
 * #433 (gpunonrender): HAKUX_STALLFIN=reports submits the open command buffer
 * at a caught-up FIFO only when a report is queued. Off unless set.
 *
 * Every STALLED finish rotates the frame slot, and the rotation waits for the
 * slot two finishes back (pgraph_vk_finish). Simpsons makes ~8.8 of them a
 * guest frame, with the GPU busy a quarter of it, so the PFIFO thread waits on
 * one small command buffer after another, with pfifo.lock held, and the
 * guest's DMA_PUT waits behind it. Taking the vCPU off the lock alone
 * (c2dfca18a1, reverted in f6ac723228) moved the wait to that fence: 8 to 21
 * ms a frame, fps down.
 *
 * What a guest can observe from a submit here: semaphores are written at the
 * method (pgraph.c, BACK_END_WRITE_SEMAPHORE_RELEASE), and surface bytes the
 * CPU reads are downloaded by their own finishes. The zpass reports are the
 * only guest-visible value written after a finish
 * (pgraph_vk_process_pending_reports_internal). So with a queued report the
 * submit happens as before; without one the draws stay in the command buffer
 * until the flip or another finish submits them.
 */
static bool stall_reports_only(void)
{
    static int on = -1;
    if (on < 0) {
        const char *v = getenv("HAKUX_STALLFIN");
        on = v && !strcmp(v, "reports");
#ifdef __ANDROID__
        if (on) {
            __android_log_print(ANDROID_LOG_INFO, "hakuX-vk",
                                "[stallfin] reports-only on");
        }
#endif
    }
    return on;
}

void pgraph_vk_process_pending_reports(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    uint32_t *dma_get = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET];
    uint32_t *dma_put = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT];

    if (*dma_get == *dma_put && r->in_command_buffer) {
        if (stall_reports_only() && QSIMPLEQ_EMPTY(&r->report_queue)) {
            return;
        }
        if (pg->draw_time != r->last_stall_draw_time) {
            pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED);
            r->last_stall_draw_time = pg->draw_time;
        } else {
            OPT_STAT_INC(stall_batched);
        }
    }
}
