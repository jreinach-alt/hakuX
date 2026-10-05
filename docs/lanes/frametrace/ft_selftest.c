/*
 * frametrace selftest (#433): compiles hw/xbox/nv2a/pgraph/profile.h on the
 * host and checks the attribution rule, the holder test, the in-progress
 * split, the hitch trigger and the off path. Driven by selftest.py, which
 * also builds it against mutated copies of the header and requires each
 * mutant to FAIL (a check that cannot fail is not a check).
 *
 * Output: one "PASS <name>" or "FAIL <name>: why" per check, then
 * "RESULT pass=N fail=M".
 */
#define _GNU_SOURCE
#define HAKUX_FT_IMPLEMENTATION
#include "hw/xbox/nv2a/pgraph/profile.h"

#include <stdarg.h>

static int npass, nfail;

static void check(bool ok, const char *name, const char *fmt, ...)
{
    if (ok) {
        printf("PASS %s\n", name);
        npass++;
    } else {
        va_list ap;
        printf("FAIL %s: ", name);
        va_start(ap, fmt);
        vprintf(fmt, ap);
        va_end(ap);
        printf("\n");
        nfail++;
    }
}

/* ---- captured log ------------------------------------------------------ */

static char logbuf[1 << 20];
static size_t loglen;
static pthread_mutex_t logmu = PTHREAD_MUTEX_INITIALIZER;

static void cap_log(const char *tag, const char *line)
{
    pthread_mutex_lock(&logmu);
    loglen += snprintf(logbuf + loglen, sizeof(logbuf) - loglen, "%s: %s\n",
                       tag, line);
    if (loglen >= sizeof(logbuf)) {
        loglen = sizeof(logbuf) - 1;
    }
    pthread_mutex_unlock(&logmu);
}

static int count_lines(const char *prefix)
{
    int n = 0;
    size_t pl = strlen(prefix);
    const char *p = logbuf;
    while (p && *p) {
        if (!strncmp(p, prefix, pl)) {
            n++;
        }
        p = strchr(p, '\n');
        if (p) {
            p++;
        }
    }
    return n;
}

/* ---- 1. the rule on synthetic frames ------------------------------------ */

static HakuxFtFrame base_frame(void)
{
    HakuxFtFrame f;
    memset(&f, 0, sizeof(f));
    f.vbp = 16683;
    f.ireq = 1;
    f.vb = 2;                       /* late for a 60 Hz guest */
    f.P = 26000;
    f.gidle = 0;
    f.r[HAKUX_FT_VCPU].run = 12000;
    f.r[HAKUX_FT_VCPU].rq = 500;
    f.r[HAKUX_FT_VCPU].blk = 13500;
    f.r[HAKUX_FT_PFIFO].run = 10000;
    f.r[HAKUX_FT_PFIFO].blk = 16000;
    f.pidle = 4000;
    f.gpu = 12000;
    return f;
}

static int classify(HakuxFtFrame f)
{
    uint32_t charge[HAKUX_FT_NC];
    hakux_ft_attribute(&f, charge);
    return f.cls;
}

static void expect_cls(const char *name, HakuxFtFrame f, int want)
{
    int got = classify(f);
    check(got == want, name, "got %s, want %s", hakux_ft_cls_name[got],
          hakux_ft_cls_name[want]);
}

static void test_rule(void)
{
    HakuxFtFrame f;

    /* The brief's falsifier: the vCPU blocked 9 ms on pfifo.lock while the
     * holder sat in a GPU fence the whole time. */
    f = base_frame();
    f.r[HAKUX_FT_VCPU].w[HAKUX_FT_W_PFIFO_LOCK] = 9000;
    f.lockw = 9000;
    f.vh[HAKUX_FT_H_GPU] = 9000;
    expect_cls("rule.fence_holder_is_bgpu", f, HAKUX_FT_C_BLK_GPU);

    /* The same wait with the fence replaced by a lock hold: the holder ran. */
    f.vh[HAKUX_FT_H_GPU] = 0;
    f.vh[HAKUX_FT_H_RUN] = 9000;
    expect_cls("rule.running_holder_is_block", f, HAKUX_FT_C_BLK_LOCK);

    /* ... or itself sat in another lock. */
    f.vh[HAKUX_FT_H_RUN] = 0;
    f.vh[HAKUX_FT_H_WAIT] = 9000;
    expect_cls("rule.waiting_holder_is_block", f, HAKUX_FT_C_BLK_LOCK);

    /* A holder that never registered: undecided. */
    f.vh[HAKUX_FT_H_WAIT] = 0;
    f.vh[HAKUX_FT_H_UNK] = 9000;
    expect_cls("rule.unknown_holder_is_unattr", f, HAKUX_FT_C_UNATTR);

    /* A holder that ran 4 ms and waited the GPU 5 ms: the larger share. */
    f.vh[HAKUX_FT_H_UNK] = 0;
    f.vh[HAKUX_FT_H_RUN] = 4000;
    f.vh[HAKUX_FT_H_GPU] = 5000;
    expect_cls("rule.split_holder_takes_larger_share", f, HAKUX_FT_C_BLK_GPU);

    /* Holder in a render-thread wait. */
    f.vh[HAKUX_FT_H_RUN] = 0;
    f.vh[HAKUX_FT_H_GPU] = 0;
    f.vh[HAKUX_FT_H_RENDER] = 9000;
    expect_cls("rule.render_holder_is_rsub", f, HAKUX_FT_C_RSUBMIT);

    /* The DMA_PUT wait seen only by lock_wait_ns (no span, no holder). */
    f = base_frame();
    f.lockw = 9000;
    expect_cls("rule.lockw_without_holder_is_unattr", f, HAKUX_FT_C_UNATTR);

    /* On time: the same 9 ms GPU-held wait in a frame that met the
     * guest's interval is the guest's pace. */
    f = base_frame();
    f.vb = 1;
    f.r[HAKUX_FT_VCPU].w[HAKUX_FT_W_PFIFO_LOCK] = 9000;
    f.vh[HAKUX_FT_H_GPU] = 9000;
    expect_cls("rule.on_time_is_vsync", f, HAKUX_FT_C_VSYNC);

    /* A 30-locked guest (ireq 2) on 2 VBLANKs is on time; on 3 it is late. */
    f.ireq = 2;
    f.vb = 2;
    expect_cls("rule.ireq2_vb2_is_vsync", f, HAKUX_FT_C_VSYNC);
    f.vb = 3;
    f.P = 50000;
    f.r[HAKUX_FT_VCPU].run = 25000;
    f.r[HAKUX_FT_VCPU].blk = 24500;
    f.r[HAKUX_FT_VCPU].w[HAKUX_FT_W_PFIFO_LOCK] = 24000;
    f.vh[HAKUX_FT_H_GPU] = 24000;
    expect_cls("rule.ireq2_vb3_is_late", f, HAKUX_FT_C_BLK_GPU);

    /* Guest work alone misses the deadline, even with a GPU-held wait. */
    f = base_frame();
    f.P = 40000;
    f.vb = 3;
    f.r[HAKUX_FT_VCPU].run = 30000;
    f.r[HAKUX_FT_VCPU].blk = 9500;
    f.vh[HAKUX_FT_H_GPU] = 9000;
    expect_cls("rule.work_over_deadline_is_run", f, HAKUX_FT_C_RUN);

    /* Forza's slow half (vcpu60 1.2): 46 ms on-CPU of which 20 ms is the
     * guest idle loop spinning, the GPU busy 44 of 48 ms. */
    f = base_frame();
    f.ireq = 2;
    f.vb = 3;
    f.P = 48000;
    f.r[HAKUX_FT_VCPU].run = 46000;
    f.r[HAKUX_FT_VCPU].rq = 0;
    f.r[HAKUX_FT_VCPU].blk = 2000;
    f.gidle = 20000;
    f.gpu = 44000;
    expect_cls("rule.gidle_with_gpu_saturated_is_gpu", f, HAKUX_FT_C_GPU);
    /* ... and without the guest-idle hook the same frame reads as RUN:
     * why G1 is requested. */
    f.gidle = HAKUX_FT_NA;
    expect_cls("rule.gidle_unmeasured_reads_run", f, HAKUX_FT_C_RUN);

    /* Guest idle while the PFIFO thread works (Nightfire's shape). */
    f = base_frame();
    f.P = 40000;
    f.vb = 3;
    f.r[HAKUX_FT_VCPU].run = 14000;
    f.r[HAKUX_FT_VCPU].rq = 0;
    f.r[HAKUX_FT_VCPU].blk = 26000;
    f.r[HAKUX_FT_VCPU].w[HAKUX_FT_W_HALT] = 26000;
    f.gidle = 26000;
    f.gpu = 10000;
    f.r[HAKUX_FT_PFIFO].run = 30000;
    f.r[HAKUX_FT_PFIFO].rq = 1000;
    f.r[HAKUX_FT_PFIFO].blk = 9000;
    f.pidle = 2000;
    expect_cls("rule.gidle_with_pfifo_busy_is_pgraph", f, HAKUX_FT_C_PGRAPH);
    /* ... with the PFIFO thread in fence waits instead. */
    f.r[HAKUX_FT_PFIFO].run = 8000;
    f.r[HAKUX_FT_PFIFO].blk = 31000;
    f.r[HAKUX_FT_PFIFO].w[HAKUX_FT_W_FENCE] = 29000;
    expect_cls("rule.gidle_with_pfifo_fence_is_gpu", f, HAKUX_FT_C_GPU);
    /* ... with both sides idle: the guest waited on time; undecided. */
    f.r[HAKUX_FT_PFIFO].run = 2000;
    f.r[HAKUX_FT_PFIFO].blk = 37000;
    f.r[HAKUX_FT_PFIFO].w[HAKUX_FT_W_FENCE] = 0;
    f.pidle = 36000;
    expect_cls("rule.gidle_both_idle_is_unattr", f, HAKUX_FT_C_UNATTR);

    /* Blocked in no named wait. */
    f = base_frame();
    expect_cls("rule.unnamed_block_is_unattr", f, HAKUX_FT_C_UNATTR);
}

/* ---- 2. holder state on live threads ------------------------------------ */

static pthread_mutex_t M = PTHREAD_MUTEX_INITIALIZER;
static volatile int hold_ready, v_done;
static int scenario;

static void spin_ms(int ms)
{
    int64_t end = hakux_ft_now() + (int64_t)ms * 1000000;
    while (hakux_ft_now() < end) {
    }
}

static void sleep_ms(int ms)
{
    struct timespec ts = { ms / 1000, (long)(ms % 1000) * 1000000 };
    nanosleep(&ts, NULL);
}

static void flip(unsigned vb)
{
    static unsigned vf;
    HakuxFtExt x = { 0 };
    vf += vb;
    x.vblank_fired = vf;
    hakux_ft_flip(&x);
}

static HakuxFtFrame last_frame(int back)
{
    uint32_t h = __atomic_load_n(&ft_frame_head, __ATOMIC_ACQUIRE);
    return ft_frames[(h - 1 - back) % FT_FRAME_RING];
}

static void *holder_thread(void *arg)
{
    HakuxFtWait w;
    (void)arg;
    hakux_ft_thread(HAKUX_FT_PFIFO);
    for (int sc = 0; sc < 4; sc++) {
        while (__atomic_load_n(&scenario, __ATOMIC_ACQUIRE) != sc + 1) {
        }
        flip(1);                            /* frame boundary before */
        pthread_mutex_lock(&M);
        if (sc == 0) {                      /* fence held under the lock */
            hakux_ft_wait_begin(&w, HAKUX_FT_W_FENCE, -1);
            __atomic_store_n(&hold_ready, 1, __ATOMIC_RELEASE);
            sleep_ms(9);
            hakux_ft_wait_end(&w);
        } else if (sc == 1) {               /* CPU work under the lock */
            __atomic_store_n(&hold_ready, 1, __ATOMIC_RELEASE);
            spin_ms(9);
        } else if (sc == 2) {               /* runs, then waits the GPU */
            __atomic_store_n(&hold_ready, 1, __ATOMIC_RELEASE);
            spin_ms(4);
            hakux_ft_wait_begin(&w, HAKUX_FT_W_FENCE, -1);
            sleep_ms(5);
            hakux_ft_wait_end(&w);
        } else {                            /* a 30 ms fence across flips */
            hakux_ft_wait_begin(&w, HAKUX_FT_W_FENCE, -1);
            __atomic_store_n(&hold_ready, 1, __ATOMIC_RELEASE);
            sleep_ms(10);
            flip(1);
            sleep_ms(10);
            flip(1);
            sleep_ms(10);
            hakux_ft_wait_end(&w);
        }
        pthread_mutex_unlock(&M);
        while (!__atomic_load_n(&v_done, __ATOMIC_ACQUIRE)) {
        }
        flip(2);                            /* the frame: 2 VBLANKs, late */
        __atomic_store_n(&v_done, 0, __ATOMIC_RELEASE);
        __atomic_store_n(&hold_ready, 0, __ATOMIC_RELEASE);
        __atomic_store_n(&scenario, 100 + sc, __ATOMIC_RELEASE);
    }
    return NULL;
}

static void *vcpu_thread(void *arg)
{
    HakuxFtWait w;
    (void)arg;
    hakux_ft_thread(HAKUX_FT_VCPU);
    for (int sc = 0; sc < 4; sc++) {
        while (__atomic_load_n(&scenario, __ATOMIC_ACQUIRE) != sc + 1 ||
               !__atomic_load_n(&hold_ready, __ATOMIC_ACQUIRE)) {
        }
        hakux_ft_wait_begin(&w, HAKUX_FT_W_PFIFO_LOCK, HAKUX_FT_PFIFO);
        pthread_mutex_lock(&M);
        hakux_ft_wait_end(&w);
        pthread_mutex_unlock(&M);
        __atomic_store_n(&v_done, 1, __ATOMIC_RELEASE);
        while (__atomic_load_n(&scenario, __ATOMIC_ACQUIRE) != 100 + sc) {
        }
    }
    return NULL;
}

static void run_scenario(int sc)
{
    __atomic_store_n(&scenario, sc + 1, __ATOMIC_RELEASE);
    while (__atomic_load_n(&scenario, __ATOMIC_ACQUIRE) != 100 + sc) {
        sleep_ms(1);
    }
}

static void test_live(void)
{
    pthread_t h, v;
    HakuxFtFrame f;

    pthread_create(&h, NULL, holder_thread, NULL);
    pthread_create(&v, NULL, vcpu_thread, NULL);

    run_scenario(0);
    f = last_frame(0);
    check(f.vh[HAKUX_FT_H_GPU] >= 7000 && f.vh[HAKUX_FT_H_RUN] < 1500,
          "live.fence_holder_books_gpu", "vh gpu=%u run=%u",
          f.vh[HAKUX_FT_H_GPU], f.vh[HAKUX_FT_H_RUN]);
    check(f.cls == HAKUX_FT_C_BLK_GPU, "live.fence_holder_frame_is_bgpu",
          "cls=%s P=%u vrun=%u", hakux_ft_cls_name[f.cls], f.P,
          f.r[HAKUX_FT_VCPU].run);
    /* who held it: the PFIFO thread; one wait each side */
    check(f.vho[HAKUX_FT_PFIFO] >= 7000 && f.vho[HAKUX_FT_NROLE] < 500 &&
          f.nw[HAKUX_FT_VCPU] == 1 && f.nw[HAKUX_FT_PFIFO] == 1,
          "live.holder_thread_and_wait_counts",
          "vho pfifo=%u none=%u nw v=%u p=%u", f.vho[HAKUX_FT_PFIFO],
          f.vho[HAKUX_FT_NROLE], f.nw[HAKUX_FT_VCPU], f.nw[HAKUX_FT_PFIFO]);

    run_scenario(1);
    f = last_frame(0);
    check(f.vh[HAKUX_FT_H_RUN] >= 7000 && f.vh[HAKUX_FT_H_GPU] < 500,
          "live.running_holder_books_run", "vh gpu=%u run=%u",
          f.vh[HAKUX_FT_H_GPU], f.vh[HAKUX_FT_H_RUN]);
    check(f.cls == HAKUX_FT_C_BLK_LOCK, "live.running_holder_frame_is_block",
          "cls=%s", hakux_ft_cls_name[f.cls]);

    run_scenario(2);
    f = last_frame(0);
    /* ran 4 ms, then waited the GPU 5 ms: booked by overlap */
    check(f.vh[HAKUX_FT_H_RUN] >= 2500 && f.vh[HAKUX_FT_H_RUN] <= 6000 &&
          f.vh[HAKUX_FT_H_GPU] >= 3500 && f.vh[HAKUX_FT_H_GPU] <= 6500,
          "live.changing_holder_split_by_overlap", "vh gpu=%u run=%u",
          f.vh[HAKUX_FT_H_GPU], f.vh[HAKUX_FT_H_RUN]);

    /* A 30 ms wait spanning two flips lands in the three frames it spans. */
    run_scenario(3);
    {
        HakuxFtFrame a = last_frame(2), b = last_frame(1), c = last_frame(0);
        uint32_t wa = a.r[HAKUX_FT_VCPU].w[HAKUX_FT_W_PFIFO_LOCK];
        uint32_t wb = b.r[HAKUX_FT_VCPU].w[HAKUX_FT_W_PFIFO_LOCK];
        uint32_t wc = c.r[HAKUX_FT_VCPU].w[HAKUX_FT_W_PFIFO_LOCK];
        check(wa >= 7000 && wb >= 7000 && wc >= 7000 && wc < 20000,
              "live.wait_split_at_flips", "frames %u/%u/%u us", wa, wb, wc);
        check(a.vh[HAKUX_FT_H_GPU] >= 7000 && b.vh[HAKUX_FT_H_GPU] >= 7000,
              "live.split_wait_keeps_holder_class", "gpu %u/%u",
              a.vh[HAKUX_FT_H_GPU], b.vh[HAKUX_FT_H_GPU]);
    }
    pthread_join(h, NULL);
    pthread_join(v, NULL);
}

/* ---- 3. the hitch trigger ---------------------------------------------- */

static int feed(const uint32_t *P, int n)
{
    FtWriter *w = calloc(1, sizeof(*w));
    int64_t t = 1000000000LL;
    int before;

    w->wss = -1;
    pthread_mutex_lock(&logmu);
    before = count_lines("hakuX-ft: B ");
    pthread_mutex_unlock(&logmu);
    for (int i = 0; i < n; i++) {
        HakuxFtFrame f = base_frame();
        t += (int64_t)P[i] * 1000;
        f.f = (uint32_t)i + 1;
        f.t = t;
        f.P = P[i];
        f.vb = 1;
        hakux_ft_attribute(&f, (uint32_t[HAKUX_FT_NC]){ 0 });
        hakux_ft_writer_frame(w, &f, t);
    }
    free(w);
    return count_lines("hakuX-ft: B ") - before;
}

static void test_hitch(void)
{
    static uint32_t P[400];
    int n;

    loglen = 0;
    logbuf[0] = 0;
    for (int i = 0; i < 200; i++) {
        P[i] = 33333;
    }
    P[149] = 330000;
    n = feed(P, 200);
    check(n == 1 && strstr(logbuf, "B 1 f0=90 f1=160") &&
          strstr(logbuf, "hitch=150") && count_lines("hakuX-ft: F 1 ") == 71 &&
          strstr(logbuf, "E 1 frames=71"),
          "hitch.one_330ms_in_30fps", "blocks=%d F=%d", n,
          count_lines("hakuX-ft: F 1 "));

    /* 50 ms steady: threshold max(2 x 50, 50) = 100; a 90 ms frame is not. */
    for (int i = 0; i < 200; i++) {
        P[i] = 50000;
    }
    P[120] = 90000;
    n = feed(P, 200);
    check(n == 0, "hitch.90ms_in_20fps_is_not", "blocks=%d", n);
    P[120] = 110000;
    n = feed(P, 200);
    check(n == 1, "hitch.110ms_in_20fps_is", "blocks=%d", n);

    /* 60 fps: the 50 ms floor holds; 45 ms is not a hitch, 55 ms is. */
    for (int i = 0; i < 400; i++) {
        P[i] = 16683;
    }
    P[300] = 45000;
    n = feed(P, 400);
    check(n == 0, "hitch.45ms_in_60fps_is_not", "blocks=%d", n);
    P[300] = 55000;
    n = feed(P, 400);
    check(n == 1, "hitch.55ms_in_60fps_is", "blocks=%d", n);

    /* Every summary's histogram counts every frame. */
    {
        const char *p = logbuf;
        int bad = 0, lines = 0;
        while ((p = strstr(p, "hakuX-ft1: n=")) != NULL) {
            unsigned nn, c[HAKUX_FT_NC], sum = 0;
            const char *pm = strstr(p, " pm=");
            lines++;
            sscanf(p, "hakuX-ft1: n=%u", &nn);
            if (!pm || sscanf(pm, " pm=vsync:%u,run:%u,bgpu:%u,block:%u,"
                              "pgraph:%u,gpu:%u,rsub:%u,unattr:%u",
                              &c[0], &c[1], &c[2], &c[3], &c[4], &c[5], &c[6],
                              &c[7]) != 8) {
                bad++;
            } else {
                for (int k = 0; k < HAKUX_FT_NC; k++) {
                    sum += c[k];
                }
                bad += sum != nn;
            }
            p++;
        }
        check(lines > 10 && bad == 0, "summary.histogram_counts_every_frame",
              "lines=%d bad=%d", lines, bad);
    }
}

/* ---- 4. off ------------------------------------------------------------- */

static void test_off(void)
{
    HakuxFtWait w;
    uint64_t before = ft_other_acc[HAKUX_FT_W_BQL];

    hakux_ft_wait_begin(&w, HAKUX_FT_W_BQL, -1);
    sleep_ms(2);
    hakux_ft_wait_end(&w);
    hakux_ft_present();
    check(!hakux_ft_on && w.t0 == 0 && ft_other_acc[HAKUX_FT_W_BQL] == before &&
          ft_present_head == 0,
          "off.records_nothing", "on=%d t0=%lld acc=%llu presents=%u",
          hakux_ft_on, (long long)w.t0,
          (unsigned long long)ft_other_acc[HAKUX_FT_W_BQL], ft_present_head);
}

/* ---- 5. the duty switch (HAKUX_FRAMETRACE_DUTY) ------------------------- */

static void test_duty(void)
{
    const int64_t D = 10000000000LL, T = 1000000000LL;
    FtDuty d = { 0 };
    HakuxFtWait w;
    uint32_t h0, h1;
    HakuxFtFrame f;
    int on1, on2, on3;

    hakux_ft_duty_tick(&d, D, T);
    on1 = hakux_ft_on;
    hakux_ft_duty_tick(&d, D, T + 5 * T);
    on2 = hakux_ft_on;
    hakux_ft_duty_tick(&d, D, T + D + T / 20);
    on3 = hakux_ft_on;
    hakux_ft_wait_begin(&w, HAKUX_FT_W_BQL, -1);
    hakux_ft_wait_end(&w);
    hakux_ft_duty_tick(&d, D, T + 2 * D + T / 20);
    check(on1 == 1 && on2 == 1 && on3 == 0 && w.t0 == 0 && hakux_ft_on == 1 &&
          strstr(logbuf, "duty=off k=1") && strstr(logbuf, "duty=on k=2"),
          "duty.switches_off_then_on", "on %d/%d/%d/%d t0=%lld", on1, on2, on3,
          hakux_ft_on, (long long)w.t0);

    /* Back on after 200 ms off: the first flip is a baseline, the second a
     * frame of its own length. */
    sleep_ms(200);
    h0 = __atomic_load_n(&ft_frame_head, __ATOMIC_ACQUIRE);
    flip(1);
    h1 = __atomic_load_n(&ft_frame_head, __ATOMIC_ACQUIRE);
    sleep_ms(5);
    flip(1);
    f = last_frame(0);
    check(h1 == h0 && f.P >= 4000 && f.P < 50000,
          "duty.first_flip_after_off_is_a_baseline",
          "frames at the first flip %u, next P=%u us", h1 - h0, f.P);

    /* The writer reads no slack across the off span (its deadline would be
     * the release of a frame from before it). */
    {
        FtWriter *wr = calloc(1, sizeof(*wr));
        HakuxFtFrame a = base_frame(), b = base_frame(), c = base_frame();
        uint32_t s_gap, s_next;

        wr->wss = -1;
        /* no 1 Hz summary inside a-c: it would reset nslack */
        wr->sum_t0 = 1020 * T - T / 2;
        a.f = 1; a.t = 1000 * T; a.P = 16683; a.ireq = 1;
        b.f = 2; b.t = 1020 * T; b.P = 16683; b.ireq = 1;   /* 20 s later */
        c.f = 3; c.t = b.t + 16683000; c.P = 16683; c.ireq = 1;
        wr->pres[wr->pres_n++] = a.t + 1000000;
        wr->pres[wr->pres_n++] = b.t + 1000000;
        wr->pres[wr->pres_n++] = c.t + 1000000;
        hakux_ft_writer_frame(wr, &a, a.t);
        hakux_ft_writer_frame(wr, &b, b.t);
        s_gap = wr->nslack;
        hakux_ft_writer_frame(wr, &c, c.t);
        s_next = wr->nslack;
        check(s_gap == 0 && s_next == 1, "duty.no_slack_across_off_span",
              "slack samples after the gap frame %u, after the next %u",
              s_gap, s_next);
        free(wr);
    }
}

int main(void)
{
    hakux_ft_log = cap_log;
    test_off();
    setenv("HAKUX_FRAMETRACE", "1", 1);
    setenv("HAKUX_FRAMETRACE_CSV", "0", 1);
    setenv("HAKUX_FRAMETRACE_VB", "1", 1);
    hakux_ft_init();
    check(hakux_ft_on == 1, "init.on", "on=%d", hakux_ft_on);
    test_rule();
    test_live();
    test_hitch();
    test_duty();
    printf("RESULT pass=%d fail=%d\n", npass, nfail);
    return nfail ? 1 : 0;
}
