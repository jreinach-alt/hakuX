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
 *                         waited for every submitted frame first (#804). Only
 *                         reports whose status word the guest armed (nonzero)
 *                         before GET_REPORT go to that thread; the finish
 *                         still writes the others itself. See ra_internal()
 *                         below.
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
    bool early;        /* answered at queue (HAKUX_REPORT_EARLY): count only */
    int qend;          /* the batch's queries counted before this report */
    uint8_t *dst;      /* the guest's 16-byte report; NULL for a clear */
    uint32_t off;      /* its offset in the report DMA object */
    uint32_t trace;    /* trace record, when tracing */
    uint32_t rs, qs;   /* #1039's serials (HAKUX_ZREP) */
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

/*
 * #1039: HAKUX_ZREP=<path>[,<MB>], off unless set. Each query's count and
 * each report's value as the path that reads them writes them, so a frame
 * dump (schema 10: "zq" on a draw, {"t":"rep"} per report) can say which
 * draws a report counted and what it came to. Nothing is written until a
 * frame dump has been armed once; it stops at <MB> (default 256). Lines:
 *
 *   q <query serial> <samples>
 *   r <report serial> <last query serial> <offset> <value> <early>
 *   c <report serial> <last query serial>        (CLEAR_REPORT_VALUE)
 *
 * <value> is the report's own count, as the guest gets it unless <early> is
 * 1 (HAKUX_REPORT_EARLY answered it with the offset's last value, the
 * previous r line at the same offset). The serials are the dump's "zq" and
 * "rs"/"qs". A report counts every query after the last clear's <last query
 * serial> up to its own.
 */
static struct {
    FILE *fp;
    QemuMutex lock;
    int64_t bytes, cap;
} zr;

static void zr_init(void)
{
    const char *e = getenv("HAKUX_ZREP");
    char path[512];
    const char *comma;
    size_t len;

    if (!e || !*e || zr.fp) {
        return;
    }
    comma = strchr(e, ',');
    len = comma ? (size_t)(comma - e) : strlen(e);
    snprintf(path, sizeof(path), "%.*s", (int)MIN(len, sizeof(path) - 1), e);
    zr.cap = (comma ? MAX(atoi(comma + 1), 1) : 256) * (int64_t)1048576;
    zr.bytes = 0;
    zr.fp = fopen(path, "w");
    qemu_mutex_init(&zr.lock);
    RA_LOG("[zrep1039] %s -> %s (cap %" PRId64 " MB)",
           zr.fp ? "on" : "cannot open", path, zr.cap / 1048576);
}

static bool zr_on(void)
{
    return zr.fp && zr.bytes < zr.cap && pgraph_vk_fdump_armed_once();
}

static void zr_query(uint32_t qs, uint64_t samples)
{
    qemu_mutex_lock(&zr.lock);
    int n = fprintf(zr.fp, "q %u %" PRIu64 "\n", qs, samples);
    zr.bytes += MAX(n, 0);
    qemu_mutex_unlock(&zr.lock);
}

static void zr_report(bool clear, uint32_t rs, uint32_t qs, uint32_t off,
                      uint32_t value, bool early)
{
    qemu_mutex_lock(&zr.lock);
    int n = clear ? fprintf(zr.fp, "c %u %u\n", rs, qs)
                  : fprintf(zr.fp, "r %u %u 0x%x %u %d\n", rs, qs, off, value,
                            (int)early);
    zr.bytes += MAX(n, 0);
    if (zr.bytes >= zr.cap) {
        fprintf(zr.fp, "end cap\n");
        fflush(zr.fp);
    }
    qemu_mutex_unlock(&zr.lock);
}

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
static void re_init(void);

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
    re_init();
    zr_init();

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
    r->query_serial_of =
        g_malloc0_n(pool_create_info.queryCount, sizeof(uint32_t));
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
    g_free(r->query_serial_of);
    r->query_serial_of = NULL;

    vkDestroyQueryPool(r->device, r->query_pool, NULL);
}

/*
 * #1018 (halo1016): two switches for a guest that polls its visibility tests,
 * both on the async reader (HAKUX_REPORT_ASYNC=1, which "Fast renderer paths"
 * sets by default); without it they log so and stay off.
 *
 * HAKUX_REPORT_EARLY (on unless set to 0, since #1018): a GET_REPORT whose
 * status word the guest armed is answered when it is queued, with the count
 * the last GET_REPORT at the same offset was written with. Its own count, once
 * the reader has it, goes to that table and not to the guest. An offset not
 * seen before is written as today. Halo's cinematic queues ~540 armed reports
 * a frame, each offset once a frame, and polls them (0x63482 -> D3D 0x1810f0)
 * until the status word leaves -1; the async reader writes each ~28 ms after
 * it is queued (median, RT arm): handed off at the next flip's finish, read
 * once the GPU has run that whole command buffer. The answer is one test
 * stale, as RPCS3's "relaxed ZCULL sync" answers: a flare or an
 * occlusion-culled object can lag a frame.
 *
 * Only an offset whose last GET_REPORT came in the guest frame before this one
 * is answered early: that is Halo's pattern (one test per offset per frame,
 * polled the next), where the previous count is the same test's, one frame
 * old. An offset already queued this frame would get another test's count; an
 * offset last queued two or more frames ago is a slot ring (NFS Most Wanted
 * cycles four, each reused >= 66.7 ms later, reportasync1010), whose guest
 * reads the slot later and does not wait on it, so an early answer would only
 * make its count older. Both are written as today (skip0, skipn below).
 *
 * The reader compares each early answer with the count its own test came to:
 * stale counts those that differ, vis those where one is 0 and the other not
 * (the guest drew or hid something its own test would have decided the other
 * way, for one frame). Both go on the 2 s window line.
 *
 * HAKUX_REPORT_SUBMIT=<us>: after an armed GET_REPORT is queued, if <us> or
 * more have passed since the last finish, finish now (STALLED), so the GPU
 * starts on the draws before it and the reader writes the report once those
 * have run, nearer to when the NV2A writes it (when it reaches the method).
 * Each such finish is a submit and a frame-slot rotation.
 *
 * An early report is marked in QueryReport.parameter's type byte
 * (RE_EARLY_BIT); GET_REPORT asserted the type before queueing it, and the
 * async path reads only the offset afterwards.
 */
#define RE_HASH 4096
#define RE_RING 16384
#define RE_EARLY_BIT (1u << 31)

static struct {
    int early;
    int64_t submit_us;
    uint64_t tab[RE_HASH];   /* (offset + 1) << 32 | count; 0 = empty */
    /* the PFIFO thread's: each offset's last GET_REPORT and its guest frame */
    uint32_t q_off[RE_HASH]; /* offset + 1; 0 = none */
    int q_frame[RE_HASH];
    int64_t t_fin;           /* end of the last finish, when submit_us */
    int64_t t_win;
    uint32_t n_early, n_cold, n_unarmed, n_submit, n_skip0, n_skipn, n_full;
    /* early answers in queue order, read back in the same order by ra_run */
    struct {
        uint32_t off, val;
    } ring[RE_RING];
    uint32_t ring_w, ring_r;
    uint32_t n_stale, n_vis, n_desync;   /* ra_run's, taken by the window */
} re;

static void ra_write(uint8_t *dst, uint32_t result);

static void re_init(void)
{
    const char *e = getenv("HAKUX_REPORT_EARLY");
    const char *s = getenv("HAKUX_REPORT_SUBMIT");
    re.early = !e || strcmp(e, "0") != 0;
    re.submit_us = s ? MAX(atoi(s), 0) : 0;
    memset(re.tab, 0, sizeof(re.tab));
    memset(re.q_off, 0, sizeof(re.q_off));
    re.ring_w = re.ring_r = 0;
    if (!ra.on && (re.early || re.submit_us)) {
        RA_LOG("[rearly1018] needs HAKUX_REPORT_ASYNC=1: off");
        re.early = 0;
        re.submit_us = 0;
    }
    RA_LOG("[rearly1018] early=%d submit_us=%" PRId64 " HAKUX_REPORT_EARLY=%s",
           re.early, re.submit_us, e ? e : "(unset)");
}

static void re_queued(NV2AState *d, QueryReport *report)
{
    uint8_t *dst = ra_map(d, report->parameter, false);
    int64_t now = g_get_monotonic_time();
    bool armed = dst && ldl_le_p(dst + 12);
    bool answered = false;
    uint32_t off = GET_MASK(report->parameter, NV097_GET_REPORT_OFFSET);
    unsigned h = (off >> 4) % RE_HASH;
    int frame = qatomic_read(&d->pgraph.frame_time);
    /* frames since this offset's last GET_REPORT; -1 if none */
    int gap = re.q_off[h] == off + 1 ? frame - re.q_frame[h] : -1;

    re.q_off[h] = off + 1;
    re.q_frame[h] = frame;
    if (!armed) {
        re.n_unarmed++;
    } else if (re.early && ra.started) {
        uint64_t v = qatomic_read(&re.tab[h]);
        uint32_t w = re.ring_w;
        if ((v >> 32) != (uint64_t)off + 1) {
            re.n_cold++;
        } else if (gap == 0) {
            re.n_skip0++;
        } else if (gap != 1) {
            re.n_skipn++;
        } else if (w - qatomic_load_acquire(&re.ring_r) >= RE_RING) {
            re.n_full++;
        } else {
            re.ring[w % RE_RING].off = off;
            re.ring[w % RE_RING].val = (uint32_t)v;
            qatomic_store_release(&re.ring_w, w + 1);
            ra_write(dst, (uint32_t)v);
            report->parameter |= RE_EARLY_BIT;
            answered = true;
            re.n_early++;
        }
    }
    if (now - re.t_win >= 2000000) {
        RA_LOG("[rearly1018] w early=%u cold=%u unarmed=%u submit=%u "
               "skip0=%u skipn=%u full=%u stale=%u vis=%u desync=%u",
               re.n_early, re.n_cold, re.n_unarmed, re.n_submit, re.n_skip0,
               re.n_skipn, re.n_full, qatomic_xchg(&re.n_stale, 0),
               qatomic_xchg(&re.n_vis, 0), qatomic_xchg(&re.n_desync, 0));
        re.n_early = re.n_cold = re.n_unarmed = re.n_submit = 0;
        re.n_skip0 = re.n_skipn = re.n_full = 0;
        re.t_win = now;
    }
    if (armed && !answered && re.submit_us &&
        now - qatomic_read(&re.t_fin) >= re.submit_us) {
        re.n_submit++;
        pgraph_vk_finish(&d->pgraph, VK_FINISH_REASON_STALLED);
    }
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
    report->rs = ++r->report_serial;
    report->qs = r->query_serial;
    QSIMPLEQ_INSERT_TAIL(&r->report_queue, report, entry);

    r->new_query_needed = true;

    if (nv2a_dbg_framedump_active()) {
        pgraph_vk_fdump_log_report(d, report);
    }
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
    report->rs = ++r->report_serial;
    report->qs = r->query_serial;
    QSIMPLEQ_INSERT_TAIL(&r->report_queue, report, entry);

    r->new_query_needed = true;

    if (nv2a_dbg_framedump_active()) {
        pgraph_vk_fdump_log_report(d, report);
    }

    if (rt.on) {
        rt_queued(d, parameter);
    }
    if (re.early || re.submit_us) {
        re_queued(d, report);
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
 * An early report's own count has come: compare it with the answer the guest
 * got. Early reports reach here in the order re_queued answered them, so the
 * ring's next entry is this report's. If it is not, the entries before this
 * report's (within 64) are skipped and counted as desync, so one lost report
 * does not void the rest of the run; with no entry for it, it counts one and
 * the ring stays. Called from ra_run only, which has one user at a time.
 */
static void re_check(uint32_t off, uint32_t v)
{
    uint32_t r0 = re.ring_r;
    uint32_t w = qatomic_load_acquire(&re.ring_w);

    for (uint32_t i = r0; i != w && i - r0 < 64; i++) {
        if (re.ring[i % RE_RING].off == off) {
            uint32_t ans = re.ring[i % RE_RING].val;
            if (i != r0) {
                qatomic_add(&re.n_desync, i - r0);
            }
            if (ans != v) {
                qatomic_inc(&re.n_stale);
            }
            if ((ans == 0) != (v == 0)) {
                qatomic_inc(&re.n_vis);
            }
            qatomic_store_release(&re.ring_r, i + 1);
            return;
        }
    }
    qatomic_inc(&re.n_desync);
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
    bool zr_w = zr_on();
    if (zr_w) {
        for (int i = 0; i < b->nq; i++) {
            zr_query(r->query_serial_of[b->qfirst + i], ra.results[i]);
        }
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
            if (zr_w) {
                zr_report(true, rep->rs, rep->qs, 0, 0, false);
            }
        } else {
            uint32_t v = ra.sum / b->divisor;
            if (zr_w) {
                zr_report(false, rep->rs, rep->qs, rep->off, v, rep->early);
            }
            if (rt.on) {
                rt_written(rep->trace, rep->dst, t_f);
            }
            if (re.early) {
                qatomic_set(&re.tab[(rep->off >> 4) % RE_HASH],
                            ((uint64_t)rep->off + 1) << 32 | v);
            }
            if (!rep->early) {
                ra_write(rep->dst, v);
            } else {
                re_check(rep->off, v);
            }
        }
    }
    while (counted < b->nq) {
        ra.sum += ra.results[counted++];
    }
    if (zr_w) {
        qemu_mutex_lock(&zr.lock);
        fflush(zr.fp);
        qemu_mutex_unlock(&zr.lock);
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
 * setting), the batch is run here, as #804 did, once the reader is idle. So
 * is a batch holding a report whose status word the guest did not arm (see
 * below): it waits for its own slot's fence, before the finish returns.
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
        bool unarmed = false;
        while ((report = QSIMPLEQ_FIRST(&r->report_queue)) != NULL) {
            assert(report->query_count >= ra.cur_base);
            assert(report->query_count <= r->num_queries_in_flight);
            RaReport *o = &b->reports[b->nreports++];
            o->clear = report->clear;
            o->early = !report->clear && (report->parameter & RE_EARLY_BIT);
            o->qend = report->query_count - ra.cur_base;
            o->dst = report->clear ? NULL : ra_map(d, report->parameter, true);
            o->off = report->clear ? 0 :
                     GET_MASK(report->parameter, NV097_GET_REPORT_OFFSET);
            o->trace = (!report->clear && rt.on) ? rt_handoff(t_e) : 0;
            o->rs = report->rs;
            o->qs = report->qs;
            /* An early report's status word is our own 0, not the guest's. */
            if (o->dst && !o->early && !ldl_le_p(o->dst + 12)) {
                unarmed = true;
            }
            QSIMPLEQ_REMOVE_HEAD(&r->report_queue, entry);
            free_report(r, report);
        }

        /*
         * A report whose status word the guest left at 0 (DONE) is one it
         * will not poll: it reads the count when something else says the GPU
         * is done, a semaphore or a PGRAPH idle wait, as the ZPass pgraph
         * test does. Those batches are written here, before the finish
         * returns, as the synchronous path writes them. A guest that arms the
         * status word before GET_REPORT (NFS MW: 0xffffffff on every report)
         * sees DONE only once the reader has written the count.
         */
        if (b->wait_all || unarmed) {
            int64_t t0 = rt.on ? g_get_monotonic_time() : 0;
            qemu_mutex_lock(&ra.lock);
            while (ra.head || ra.busy) {
                qemu_cond_wait(&ra.cond, &ra.lock);
            }
            qemu_mutex_unlock(&ra.lock);
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

    if (re.submit_us) {
        qatomic_set(&re.t_fin, g_get_monotonic_time());
    }

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
    bool zr_w = zr_on();
    if (zr_w) {
        for (int i = 0; i < r->num_queries_in_flight; i++) {
            zr_query(r->query_serial_of[i], query_results[i]);
        }
    }

    QueryReport *report;
    while ((report = QSIMPLEQ_FIRST(&r->report_queue)) != NULL) {
        assert(report->query_count >= num_results_counted);
        assert(report->query_count <= r->num_queries_in_flight);

        while (num_results_counted < report->query_count) {
            r->zpass_pixel_count_result +=
                query_results[num_results_counted++];
        }

        if (zr_w) {
            zr_report(report->clear, report->rs, report->qs,
                      report->clear ? 0 :
                      GET_MASK(report->parameter, NV097_GET_REPORT_OFFSET),
                      r->zpass_pixel_count_result / result_divisor, false);
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
    if (zr_w) {
        qemu_mutex_lock(&zr.lock);
        fflush(zr.fp);
        qemu_mutex_unlock(&zr.lock);
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

/*
 * #433 (pfifowait1009): default off. When enabled, pfifo.lock is released
 * across the STALLED finish below -- the frame-slot rotation wait inside
 * pgraph_vk_finish (see the HAKUX_STALLFIN comment above: "the rotation
 * waits for the slot two finishes back") and the #804 occlusion-query wait
 * it tail-calls (pgraph_vk_process_pending_reports_internal, the
 * vkWaitForFences/vkGetQueryPoolResults loop above) -- so a vCPU's
 * DMA_PUT/DMA_GET/REF store (user_write, pfifo.lock held there too) does not
 * queue behind either one. Neither wait touches d->pfifo state: the only
 * pfifo.lock-protected reads this function makes are dma_get/dma_put just
 * below, both taken before the lock is ever dropped. The guest still gets
 * the same occlusion values; only what else may run while this function
 * waits for them changes.
 *
 * This is NOT c2dfca18a1 (reverted f6ac723228, see the comment above): that
 * fix freed the vCPU by posting its store instead, which let the vCPU race
 * ahead into the guest's own busy-wait and starve this thread, moving the
 * fence wait from 8 to 21 ms a frame with fps down. Here the vCPU still
 * blocks in user_write -- only on pfifo.lock, which this thread is not
 * otherwise using while parked in the finish -- so it cannot race ahead of
 * where DMA_PUT says it is.
 */
static bool pfifowait_enabled(void)
{
    static int on = -1;
    if (on < 0) {
        const char *v = getenv("HAKUX_PFIFOWAIT");
        on = v && !strcmp(v, "1");
#ifdef __ANDROID__
        if (on) {
            __android_log_print(ANDROID_LOG_INFO, "hakuX-vk",
                                "[pfifowait] pfifo.lock released across "
                                "STALLED finish");
        }
#endif
    }
    return on;
}

/*
 * #1018 (halo1016): HAKUX_REPORT_CATCHUP=1, off unless set. A queued
 * GET_REPORT is written at a caught-up FIFO even when the STALLED finish
 * below would not run: no command buffer is open, or no draw came since the
 * last STALLED finish. Without it such a report waits for the next finish of
 * any kind (every finish writes the queue, pgraph_vk_finish's tail), while a
 * guest polling its status word spins: Halo's cinematic polls each
 * visibility test (D3D at 0x1810f0, from 0x63482) until the word leaves -1.
 * Only a value report counts; a queue holding clears alone is left as it
 * was. The value is the one the next finish would have written: the running
 * count, read after the fences, by the same code.
 */
static bool report_catchup_enabled(void)
{
    static int on = -1;
    if (on < 0) {
        const char *v = getenv("HAKUX_REPORT_CATCHUP");
        on = v && !strcmp(v, "1");
        RA_LOG("[rcatch1018] %s HAKUX_REPORT_CATCHUP=%s", on ? "on" : "off",
               v ? v : "(unset)");
    }
    return on;
}

static bool report_queue_has_value(PGRAPHVkState *r)
{
    QueryReport *report;
    QSIMPLEQ_FOREACH(report, &r->report_queue, entry) {
        if (!report->clear) {
            return true;
        }
    }
    return false;
}

void pgraph_vk_process_pending_reports(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHVkState *r = pg->vk_renderer_state;

    uint32_t *dma_get = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_GET];
    uint32_t *dma_put = &d->pfifo.regs[NV_PFIFO_CACHE1_DMA_PUT];

    if (*dma_get == *dma_put && report_catchup_enabled() &&
        (!r->in_command_buffer || pg->draw_time == r->last_stall_draw_time) &&
        report_queue_has_value(r)) {
        static uint32_t n_open, n_closed;
        static int64_t t_win;
        int64_t now = g_get_monotonic_time();
        if (r->in_command_buffer) {
            n_open++;
        } else {
            n_closed++;
        }
        if (now - t_win >= 2000000) {
            RA_LOG("[rcatch1018] w open=%u closed=%u", n_open, n_closed);
            n_open = n_closed = 0;
            t_win = now;
        }
        pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED);
        r->last_stall_draw_time = pg->draw_time;
        return;
    }

    if (*dma_get == *dma_put && r->in_command_buffer) {
        if (stall_reports_only() && QSIMPLEQ_EMPTY(&r->report_queue)) {
            return;
        }
        if (pg->draw_time != r->last_stall_draw_time) {
            if (pfifowait_enabled()) {
                qemu_mutex_unlock(&d->pfifo.lock);
                pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED);
                qemu_mutex_lock(&d->pfifo.lock);
            } else {
                pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED);
            }
            r->last_stall_draw_time = pg->draw_time;
        } else {
            OPT_STAT_INC(stall_batched);
        }
    }
}
