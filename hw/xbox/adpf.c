/*
 * #544 ADPF performance-hint sessions for the emulator's hot threads.
 *
 * Android's Performance Hint API takes, per session, a target work duration
 * and the actual duration of each cycle, and moves clocks and placement for
 * the session's threads to meet the target. That is the alternative to the
 * vendor floors of the handhelds' MAX mode (docs/lanes/adpf/NOTES.md; the
 * thermal review's row 5 and section 3.2). The devices run Android 13 and the
 * app's minSdk is 29, so the API 33 subset is loaded with dlsym: no
 * setThreads (a session is created once all its threads exist), no power
 * efficiency flag, no CPU/GPU split.
 *
 * HAKUX_ADPF selects, read once:
 *   unset, 0  nothing: no thread, no read, no log (the default)
 *   log       measure and log as `1` does, but create no session: the A arm
 *   1         two sessions, reported once per guest flip
 *   probe     no emulator session; a probe thread that answers whether the
 *             HAL does anything with a hint (below)
 *
 * The sessions. 0 is the vCPU thread. 1 is the PFIFO thread plus the Vulkan
 * render thread. The target is the guest frame period, k VBLANK periods,
 * where k is the fewest VBLANKs between two flips seen over the last 10 s
 * (clamped 1-4): a title capped at 30 keeps k = 2 however often it misses,
 * one that sometimes makes 60 gets k = 1. HAKUX_ADPF_TARGET_US fixes it. Each
 * flip reports, per session, the CPU time its threads used since the
 * previous flip (their thread CPU clocks; for session 1 the larger of the two
 * threads', since they run side by side), never the flip interval: at a
 * capped rate the interval always equals the target and hides the slack.
 *
 * One [adpf] line per 2 s (tag hakuX, WARN), from the PFIFO thread at a flip:
 *   w, mode, vbp_us (VBLANK period), k, target_us, flips; per session s0 and
 *   s1: st (0 not created, 1 live, -1 create failed), n (reports), mean_us and
 *   max_us (the durations reported), err (reports that returned non-zero),
 *   um (the first thread's uclamp.min from sched_getattr, -1 unreadable);
 *   the thread tids and the CPU each last ran on (tid@cpu, ! if its clock
 *   no longer reads: the thread is dead); and per cpufreq policy its
 *   scaling_cur_freq and scaling_min_freq in MHz (p<n>=cur/min).
 *
 * The probe (HAKUX_ADPF=probe). A thread of its own runs a light fixed load:
 * every 16.67 ms it spins 3 ms, counting loop iterations, then sleeps. It
 * holds a session of its own with that period as the target and cycles three
 * 10 s phases: none (no report), low (reports target / 4) and high (reports
 * 4 x target). If the HAL acts on hints, the high phase raises the probe's
 * iteration rate (a faster clock, or a bigger core) or its uclamp.min, or the
 * policies' min/cur frequency, against none and low. One [adpf-probe] line
 * per phase: ph, n (periods), ipus (spin iterations per us), cpu (periods
 * per CPU the spin ran on), um (uclamp.min, max over the phase), err, and
 * per policy the mean cur/min MHz over the phase's samples.
 */
#include "qemu/osdep.h"
#include "hw/xbox/adpf.h"

#ifndef __ANDROID__

void hakux_adpf_thread_start(HakuxAdpfRole role) { }
void hakux_adpf_thread_add(HakuxAdpfRole role, QemuThread *thread) { }
void hakux_adpf_gpu_threads_done(void) { }
void hakux_adpf_flip(int64_t vblank_period_ns) { }

#else

#include <android/log.h>
#include <dlfcn.h>
#include <sys/syscall.h>
#include "qemu/atomic.h"

#define ADPF_LOG(...) __android_log_print(ANDROID_LOG_WARN, "hakuX", __VA_ARGS__)

#define ADPF_WINDOW_NS  2000000000LL
#define ADPF_KWINDOWS   5               /* k is the minimum over 5 windows */
#define ADPF_KMAX       4
#define ADPF_NPOL       4
#define ADPF_MAXCPU     16

/* The API 33 subset of <android/performance_hint.h>. */
typedef struct APerformanceHintManager APerformanceHintManager;
typedef struct APerformanceHintSession APerformanceHintSession;

static struct {
    APerformanceHintManager *(*get_manager)(void);
    APerformanceHintSession *(*create)(APerformanceHintManager *,
                                       const int32_t *, size_t, int64_t);
    int64_t (*preferred_rate)(APerformanceHintManager *);
    int (*update_target)(APerformanceHintSession *, int64_t);
    int (*report)(APerformanceHintSession *, int64_t);
    void (*close)(APerformanceHintSession *);
    APerformanceHintManager *mgr;
} api;

enum { ADPF_OFF, ADPF_LOG_ONLY, ADPF_ON, ADPF_PROBE };
static const char *const mode_name[] = { "off", "log", "on", "probe" };
static int adpf_mode = -1;
static int64_t target_fixed_ns;

typedef struct AdpfThread {
    int ready;                  /* written last, with release */
    pid_t tid;
    clockid_t clk;
    int64_t last_ns;            /* CPU time at the previous flip, -1 none */
    int64_t delta_ns;           /* since the previous flip, -1 none */
} AdpfThread;

static AdpfThread thr[HAKUX_ADPF_NROLES];
static bool gpu_done;

typedef struct AdpfSession {
    int state;                  /* 0 not created, 1 live, -1 create failed */
    APerformanceHintSession *s;
    uint64_t n, err, sum_ns, max_ns;
} AdpfSession;

static AdpfSession sess[2];

static int npol;
static int pol_id[ADPF_NPOL];

static int64_t now_ns(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static int64_t thread_cpu_ns(clockid_t clk)
{
    struct timespec ts;

    if (clock_gettime(clk, &ts) != 0) {
        return -1;
    }
    return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static long read_long(const char *path)
{
    char buf[32];
    long v = -1;
    FILE *f = fopen(path, "r");

    if (f) {
        if (fgets(buf, sizeof(buf), f)) {
            v = strtol(buf, NULL, 10);
        }
        fclose(f);
    }
    return v;
}

static void find_policies(void)
{
    char path[80];

    for (int i = 0; i < ADPF_MAXCPU && npol < ADPF_NPOL; i++) {
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpufreq/policy%d/scaling_cur_freq", i);
        if (access(path, R_OK) == 0) {
            pol_id[npol++] = i;
        }
    }
}

/* Policy n's scaling_<which>_freq in MHz, -1 unreadable. */
static long pol_mhz(int n, const char *which)
{
    char path[96];
    long khz;

    snprintf(path, sizeof(path),
             "/sys/devices/system/cpu/cpufreq/policy%d/scaling_%s_freq",
             pol_id[n], which);
    khz = read_long(path);
    return khz < 0 ? -1 : khz / 1000;
}

/* uclamp.min of a thread of this process, -1 unreadable. */
static int uclamp_min(pid_t tid)
{
    struct {
        uint32_t size, policy;
        uint64_t flags;
        int32_t nice;
        uint32_t priority;
        uint64_t runtime, deadline, period;
        uint32_t util_min, util_max;
    } a;

    memset(&a, 0, sizeof(a));
    if (syscall(__NR_sched_getattr, tid, &a, sizeof(a), 0) != 0 ||
        a.size < sizeof(a)) {
        return -1;
    }
    return a.util_min;
}

/* The CPU a thread of this process last ran on, -1 unreadable. */
static int last_cpu(pid_t tid)
{
    char path[64], buf[512];
    char *p;
    int field = 2, cpu = -1;
    FILE *f;

    snprintf(path, sizeof(path), "/proc/self/task/%d/stat", tid);
    f = fopen(path, "r");
    if (!f) {
        return -1;
    }
    p = fgets(buf, sizeof(buf), f) ? strrchr(buf, ')') : NULL;
    fclose(f);
    /* Field 39 is processor; p is at the end of field 2, comm. */
    while (p && *p) {
        if (*p++ == ' ' && ++field == 39) {
            cpu = atoi(p);
            break;
        }
    }
    return cpu;
}

static bool load_api(void)
{
    void *lib = dlopen("libandroid.so", RTLD_NOW | RTLD_LOCAL);

    if (!lib) {
        ADPF_LOG("[adpf] dlopen libandroid.so failed: %s", dlerror());
        return false;
    }
    api.get_manager = dlsym(lib, "APerformanceHint_getManager");
    api.create = dlsym(lib, "APerformanceHint_createSession");
    api.preferred_rate = dlsym(lib, "APerformanceHint_getPreferredUpdateRateNanos");
    api.update_target = dlsym(lib, "APerformanceHint_updateTargetWorkDuration");
    api.report = dlsym(lib, "APerformanceHint_reportActualWorkDuration");
    api.close = dlsym(lib, "APerformanceHint_closeSession");
    if (!api.get_manager || !api.create || !api.preferred_rate ||
        !api.update_target || !api.report || !api.close) {
        ADPF_LOG("[adpf] symbols missing: getManager=%d createSession=%d "
                 "rate=%d update=%d report=%d close=%d",
                 !!api.get_manager, !!api.create, !!api.preferred_rate,
                 !!api.update_target, !!api.report, !!api.close);
        return false;
    }
    api.mgr = api.get_manager();
    ADPF_LOG("[adpf] api: manager=%s preferred_rate_ns=%" PRId64,
             api.mgr ? "ok" : "NULL",
             api.mgr ? api.preferred_rate(api.mgr) : (int64_t)-1);
    return api.mgr != NULL;
}

/* ---- the probe ---------------------------------------------------------- */

#define PROBE_PERIOD_NS  16666667LL
#define PROBE_SPIN_NS    3000000LL
#define PROBE_PHASE_NS   10000000000LL
#define PROBE_SAMPLE_EVERY 25           /* periods between frequency samples */

static const char *const probe_ph_name[] = { "none", "low", "high" };

static void *probe_fn(void *arg)
{
    pid_t tid = gettid();
    int32_t tids[1] = { tid };
    APerformanceHintSession *s = api.create(api.mgr, tids, 1, PROBE_PERIOD_NS);
    int64_t next = now_ns(), phase_t0 = next;
    int ph = 0;
    uint64_t n = 0, iters = 0, spin_ns = 0, err = 0, samples = 0;
    uint32_t cpu_n[ADPF_MAXCPU];
    uint64_t cur_sum[ADPF_NPOL], min_sum[ADPF_NPOL];
    int um_max = -1;

    ADPF_LOG("[adpf-probe] tid=%d session=%s target_ns=%lld phase_s=%lld",
             tid, s ? "ok" : "NULL", PROBE_PERIOD_NS,
             PROBE_PHASE_NS / 1000000000LL);
    if (!s) {
        return NULL;
    }
    memset(cpu_n, 0, sizeof(cpu_n));
    memset(cur_sum, 0, sizeof(cur_sum));
    memset(min_sum, 0, sizeof(min_sum));

    for (;;) {
        volatile uint64_t x = 1;
        int64_t t0 = now_ns(), t1;
        uint64_t it = 0;
        unsigned cpu = ~0u;

        syscall(__NR_getcpu, &cpu, NULL, NULL);

        do {
            for (int i = 0; i < 1024; i++) {
                x = x * 6364136223846793005ULL + 1442695040888963407ULL;
            }
            it += 1024;
            t1 = now_ns();
        } while (t1 - t0 < PROBE_SPIN_NS);
        iters += it;
        spin_ns += t1 - t0;
        if (cpu < ADPF_MAXCPU) {
            cpu_n[cpu]++;
        }
        if (ph == 1 && api.report(s, PROBE_PERIOD_NS / 4) != 0) {
            err++;
        } else if (ph == 2 && api.report(s, PROBE_PERIOD_NS * 4) != 0) {
            err++;
        }
        if (n++ % PROBE_SAMPLE_EVERY == 0) {
            int um = uclamp_min(tid);

            um_max = MAX(um_max, um);
            for (int i = 0; i < npol; i++) {
                cur_sum[i] += MAX(pol_mhz(i, "cur"), 0);
                min_sum[i] += MAX(pol_mhz(i, "min"), 0);
            }
            samples++;
        }

        if (t1 - phase_t0 >= PROBE_PHASE_NS) {
            char cpus[160], pols[128];
            int off = 0;

            for (int i = 0; i < ADPF_MAXCPU && i < sysconf(_SC_NPROCESSORS_CONF); i++) {
                off += snprintf(cpus + off, sizeof(cpus) - off, "%s%u",
                                i ? "/" : "", cpu_n[i]);
            }
            off = 0;
            pols[0] = 0;
            for (int i = 0; i < npol && samples; i++) {
                off += snprintf(pols + off, sizeof(pols) - off,
                                " p%d=%" PRIu64 "/%" PRIu64, pol_id[i],
                                cur_sum[i] / samples, min_sum[i] / samples);
            }
            ADPF_LOG("[adpf-probe] ph=%s n=%" PRIu64 " ipus=%.1f cpu=%s um=%d "
                     "err=%" PRIu64 "%s",
                     probe_ph_name[ph], n,
                     spin_ns ? iters * 1000.0 / spin_ns : 0.0, cpus, um_max,
                     err, pols);
            ph = (ph + 1) % 3;
            phase_t0 = t1;
            n = iters = spin_ns = err = samples = 0;
            um_max = -1;
            memset(cpu_n, 0, sizeof(cpu_n));
            memset(cur_sum, 0, sizeof(cur_sum));
            memset(min_sum, 0, sizeof(min_sum));
        }

        next += PROBE_PERIOD_NS;
        if (next < t1) {
            next = t1;          /* overran: no catch-up burst */
        } else {
            struct timespec ts = {
                .tv_sec = next / 1000000000LL,
                .tv_nsec = next % 1000000000LL,
            };
            clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL);
        }
    }
    return NULL;
}

/* ---- the sessions ------------------------------------------------------- */

/* Once, from whichever of the vCPU and PFIFO threads starts first. */
static void adpf_init_once(void)
{
    const char *v;

    v = getenv("HAKUX_ADPF");
    adpf_mode = !v || !v[0] || !strcmp(v, "0") ? ADPF_OFF
              : !strcmp(v, "log") ? ADPF_LOG_ONLY
              : !strcmp(v, "probe") ? ADPF_PROBE
              : ADPF_ON;
    if (adpf_mode == ADPF_OFF) {
        return;
    }
    v = getenv("HAKUX_ADPF_TARGET_US");
    target_fixed_ns = v ? MAX(atoll(v), 0) * 1000 : 0;
    find_policies();
    ADPF_LOG("[adpf] mode=%s target_fixed_us=%" PRId64 " policies=%d",
             mode_name[adpf_mode], target_fixed_ns / 1000, npol);
    if (adpf_mode == ADPF_LOG_ONLY) {
        return;
    }
    if (!load_api()) {
        ADPF_LOG("[adpf] unavailable: mode %s runs as log",
                 mode_name[adpf_mode]);
        adpf_mode = ADPF_LOG_ONLY;
        return;
    }
    if (adpf_mode == ADPF_PROBE) {
        QemuThread t;

        qemu_thread_create(&t, "hakux.adpf_probe", probe_fn, NULL,
                           QEMU_THREAD_DETACHED);
    }
}

static bool adpf_init(void)
{
    static pthread_once_t once = PTHREAD_ONCE_INIT;

    pthread_once(&once, adpf_init_once);
    return adpf_mode != ADPF_OFF;
}

static void add_thread(HakuxAdpfRole role, pthread_t pt)
{
    AdpfThread *t = &thr[role];
    clockid_t clk;

    if (qatomic_read(&t->ready) || pthread_getcpuclockid(pt, &clk) != 0) {
        return;                 /* one thread per role: the first vCPU */
    }
    t->tid = pthread_gettid_np(pt);
    t->clk = clk;
    t->last_ns = -1;
    t->delta_ns = -1;
    qatomic_store_release(&t->ready, 1);
    ADPF_LOG("[adpf] thread role=%d tid=%d", role, t->tid);
}

void hakux_adpf_thread_start(HakuxAdpfRole role)
{
    /* PFIFO starts before the vCPU runs; the probe needs no role. */
    if (adpf_init() && adpf_mode != ADPF_PROBE) {
        add_thread(role, pthread_self());
    }
}

void hakux_adpf_thread_add(HakuxAdpfRole role, QemuThread *thread)
{
    if (adpf_init() && adpf_mode != ADPF_PROBE) {
        add_thread(role, thread->thread);
    }
}

void hakux_adpf_gpu_threads_done(void)
{
    gpu_done = true;
}

static bool thread_ready(HakuxAdpfRole role)
{
    return qatomic_load_acquire(&thr[role].ready);
}

static void session_create(int i, const HakuxAdpfRole *roles, int nroles,
                           int64_t target)
{
    int32_t tids[HAKUX_ADPF_NROLES];
    int n = 0;

    for (int r = 0; r < nroles; r++) {
        if (thread_ready(roles[r])) {
            tids[n++] = thr[roles[r]].tid;
        }
    }
    sess[i].s = api.create(api.mgr, tids, n, target);
    sess[i].state = sess[i].s ? 1 : -1;
    ADPF_LOG("[adpf] session %d: %s tids=%d%s%d target_us=%" PRId64,
             i, sess[i].s ? "created" : "FAILED", tids[0],
             n > 1 ? "," : "", n > 1 ? tids[1] : 0, target / 1000);
}

static void session_report(int i, int64_t ns)
{
    AdpfSession *s = &sess[i];

    if (ns <= 0) {
        return;                 /* the API refuses a non-positive duration */
    }
    s->n++;
    s->sum_ns += ns;
    s->max_ns = MAX(s->max_ns, (uint64_t)ns);
    if (s->state == 1 && api.report(s->s, ns) != 0) {
        s->err++;
    }
}

static const HakuxAdpfRole s0_roles[] = { HAKUX_ADPF_VCPU };
static const HakuxAdpfRole s1_roles[] = { HAKUX_ADPF_PFIFO, HAKUX_ADPF_RENDER };

void hakux_adpf_flip(int64_t vbp)
{
    static int64_t last_flip, window_t;
    static int kwin[ADPF_KWINDOWS], kwin_n, kmin_cur = ADPF_KMAX, k = 1;
    static int64_t target;
    static unsigned w, flips;
    int64_t now;

    if (adpf_mode <= ADPF_OFF || adpf_mode == ADPF_PROBE || vbp <= 0) {
        return;
    }
    now = now_ns();
    flips++;

    /* The guest frame period, in VBLANKs. */
    if (last_flip) {
        int kf = (int)((now - last_flip + vbp / 2) / vbp);

        kmin_cur = MIN(kmin_cur, MAX(kf, 1));
    }
    last_flip = now;
    if (!target) {
        target = target_fixed_ns ? target_fixed_ns : vbp;
    }

    /* The sessions, once their threads exist. */
    if (adpf_mode == ADPF_ON) {
        if (!sess[0].state && thread_ready(HAKUX_ADPF_VCPU)) {
            session_create(0, s0_roles, 1, target);
        }
        if (!sess[1].state && gpu_done && thread_ready(HAKUX_ADPF_PFIFO)) {
            session_create(1, s1_roles, 2, target);
        }
    }

    /* Each thread's CPU time since the previous flip. */
    for (int r = 0; r < HAKUX_ADPF_NROLES; r++) {
        AdpfThread *t = &thr[r];
        int64_t c;

        if (!thread_ready(r)) {
            continue;
        }
        c = thread_cpu_ns(t->clk);
        t->delta_ns = c >= 0 && t->last_ns >= 0 ? c - t->last_ns : -1;
        t->last_ns = c;
    }
    session_report(0, thr[HAKUX_ADPF_VCPU].delta_ns);
    session_report(1, MAX(thr[HAKUX_ADPF_PFIFO].delta_ns,
                          thr[HAKUX_ADPF_RENDER].delta_ns));

    if (!window_t) {
        window_t = now;
        return;
    }
    if (now - window_t < ADPF_WINDOW_NS) {
        return;
    }

    /* The window is over: the target for the next, then the line. */
    kwin[kwin_n++ % ADPF_KWINDOWS] = kmin_cur;
    kmin_cur = ADPF_KMAX;
    k = ADPF_KMAX;
    for (int i = 0; i < MIN(kwin_n, ADPF_KWINDOWS); i++) {
        k = MIN(k, kwin[i]);
    }
    {
        int64_t t = target_fixed_ns ? target_fixed_ns : k * vbp;

        if (t != target) {
            target = t;
            for (int i = 0; i < 2; i++) {
                if (sess[i].state == 1) {
                    api.update_target(sess[i].s, target);
                }
            }
        }
    }
    {
        char ss[2][96], th[96], pols[96];
        int off = 0;

        for (int i = 0; i < 2; i++) {
            AdpfSession *s = &sess[i];
            HakuxAdpfRole r0 = i ? HAKUX_ADPF_PFIFO : HAKUX_ADPF_VCPU;

            snprintf(ss[i], sizeof(ss[i]),
                     " s%d: st=%d n=%" PRIu64 " mean_us=%" PRIu64
                     " max_us=%" PRIu64 " err=%" PRIu64 " um=%d",
                     i, s->state, s->n, s->n ? s->sum_ns / s->n / 1000 : 0,
                     s->max_ns / 1000, s->err,
                     thread_ready(r0) ? uclamp_min(thr[r0].tid) : -1);
            s->n = s->err = s->sum_ns = s->max_ns = 0;
        }
        th[0] = 0;
        for (int r = 0; r < HAKUX_ADPF_NROLES; r++) {
            if (thread_ready(r)) {
                off += snprintf(th + off, sizeof(th) - off, " %s=%d@%d%s",
                                r == HAKUX_ADPF_VCPU ? "vcpu"
                                : r == HAKUX_ADPF_PFIFO ? "pfifo" : "render",
                                thr[r].tid, last_cpu(thr[r].tid),
                                thr[r].last_ns < 0 ? "!" : "");
            }
        }
        off = 0;
        pols[0] = 0;
        for (int i = 0; i < npol; i++) {
            off += snprintf(pols + off, sizeof(pols) - off, " p%d=%ld/%ld",
                            pol_id[i], pol_mhz(i, "cur"), pol_mhz(i, "min"));
        }
        ADPF_LOG("[adpf] w=%u mode=%s span_us=%" PRId64 " flips=%u vbp_us=%"
                 PRId64 " k=%d target_us=%" PRId64 "%s%s%s%s",
                 w++, mode_name[adpf_mode], (now - window_t) / 1000, flips,
                 vbp / 1000, k, target / 1000, ss[0], ss[1], th, pols);
    }
    flips = 0;
    window_t = now;
}

#endif
