/*
 * hakuX frametrace (#433): per-frame critical-path telemetry.
 *
 * HAKUX_FRAMETRACE=1 turns it on; unset, every hook below is one load and
 * one never-taken branch, and nothing else runs. It changes no guest-visible
 * state: it reads clocks, /proc schedstat and counters that already exist.
 *
 * What it records, one HakuxFtFrame per guest flip (FLIP_STALL reaching the
 * PFIFO thread), all durations in microseconds over the flip-to-flip period:
 *
 *   - the period, the VBLANKs and the presents (the guest's READ_3D
 *     increment, written from its VBLANK ISR) since the previous flip;
 *   - per thread row (vCPU, PFIFO, render, main loop): on-CPU, run-queue wait
 *     and blocked time from that thread's /proc schedstat, and the time inside
 *     each instrumented wait, by reason (HAKUX_FT_W_*);
 *   - for the vCPU's lock waits, what the HOLDER was doing over the wait,
 *     time-weighted: the wait's span is intersected with the holder's own
 *     recorded waits (its span ring and its wait in progress), each overlap
 *     booked to that wait's class (GPU, render, idle, another lock), and the
 *     rest to RUN (the holder was on its own work, or in a wait shorter than
 *     the 200 us span floor). "A waits on B" means B was in that state while
 *     A was blocked; a wait the holder spent half in a fence is booked half
 *     GPU, half RUN. A holder that never registered is UNK;
 *   - guest idle (the kernel idle loop, spun or halted), PFIFO idle, the
 *     DMA_PUT pfifo.lock wait (user.c's lock_wait_ns), GPU execution time from
 *     the timestamp queries (gpu_ts_readback, read back when the frame's fence
 *     is waited, so about one frame late) and the GPU clock.
 *
 * Waits in progress at a flip are split there (booked + in-progress), so a
 * long wait lands in the frames it spans rather than all in the one it ends
 * in. The holder split of the in-progress part is computed the same way over
 * [start, flip], so the frames' shares add up to the wait's.
 *
 * The attribution rule is hakux_ft_attribute() below, written once and run
 * both on the device (the 1 Hz histogram) and by the selftest
 * (docs/lanes/frametrace/selftest.py), which compiles this header on the host.
 *
 * Off the hot path: the PFIFO thread only fills the record and pushes it to a
 * single-producer ring. A writer thread (100 ms tick) formats the CSV, the
 * 1 Hz hakuX-ft1 summary and the hakuX-ft hitch blocks.
 *
 * Define HAKUX_FT_IMPLEMENTATION in exactly one translation unit (profile.c;
 * the selftest's harness) before including this header.
 */

#ifndef HW_XBOX_NV2A_PGRAPH_PROFILE_H
#define HW_XBOX_NV2A_PGRAPH_PROFILE_H

#include <stdint.h>
#include <stdbool.h>
#include <time.h>

/* Thread rows. MAIN is the main loop; OTHER books waits of any thread that
 * never registered (no schedstat row, no state word, no span ring). */
enum {
    HAKUX_FT_VCPU,
    HAKUX_FT_PFIFO,
    HAKUX_FT_RENDER,
    HAKUX_FT_MAIN,
    HAKUX_FT_NROLE,
    HAKUX_FT_OTHER = HAKUX_FT_NROLE,
    HAKUX_FT_NROW,
};

/* Wait reasons: what a thread is blocked in. */
enum {
    HAKUX_FT_W_BQL,          /* BQL acquire (system/cpus.c) */
    HAKUX_FT_W_PFIFO_LOCK,   /* pfifo.lock acquire (the DMA_PUT store) */
    HAKUX_FT_W_PGRAPH_LOCK,  /* pgraph.lock acquire in PGRAPH MMIO */
    HAKUX_FT_W_HALT,         /* vCPU halted (idle halt or hlt) */
    HAKUX_FT_W_IDLE,         /* PFIFO thread waiting for a kick */
    HAKUX_FT_W_FENCE,        /* vkWaitForFences: waiting on the GPU */
    HAKUX_FT_W_SUBMIT,       /* inside vkQueueSubmit */
    HAKUX_FT_W_RTHREAD,      /* waiting for the render thread */
    HAKUX_FT_W_DOWNLOAD,     /* waiting for a surface download */
    HAKUX_FT_W_OTHER,
    HAKUX_FT_NW,
};

/* Holder classes: what the holder of a lock was doing, booked by overlap. */
enum {
    HAKUX_FT_H_UNK,      /* holder unknown or never registered */
    HAKUX_FT_H_RUN,      /* in no recorded wait: its own work */
    HAKUX_FT_H_GPU,      /* in a fence or download wait */
    HAKUX_FT_H_RENDER,   /* in a submit or render-thread wait */
    HAKUX_FT_H_IDLE,     /* waiting for work */
    HAKUX_FT_H_WAIT,     /* in some other wait (a lock, a halt) */
    HAKUX_FT_NH,
};

/* Pacemaker classes. */
enum {
    HAKUX_FT_C_VSYNC,     /* on time: the guest's own interval set the pace */
    HAKUX_FT_C_RUN,       /* guest-vCPU-run: guest work alone misses the deadline */
    HAKUX_FT_C_BLK_GPU,   /* vCPU blocked on a holder that waited the GPU */
    HAKUX_FT_C_BLK_LOCK,  /* vCPU blocked on a lock whose holder ran (CPU work) */
    HAKUX_FT_C_PGRAPH,    /* the guest waited while the PFIFO thread worked */
    HAKUX_FT_C_GPU,       /* the guest waited while the GPU (or a fence) was busy */
    HAKUX_FT_C_RSUBMIT,   /* waits on the render thread or vkQueueSubmit */
    HAKUX_FT_C_UNATTR,    /* the rule cannot decide */
    HAKUX_FT_NC,
};

#define HAKUX_FT_NA 0xffffffffu   /* a field this build cannot measure */

typedef struct HakuxFtRow {
    uint32_t run, rq, blk;          /* schedstat on-CPU, run queue, the rest */
    uint32_t w[HAKUX_FT_NW];        /* instrumented waits, by reason */
} HakuxFtRow;

typedef struct HakuxFtFrame {
    int64_t t;                      /* flip time, ns, hakux_ft_now() */
    int64_t tp;                     /* last present at or before the flip, ns */
    uint32_t f;                     /* flip number */
    uint32_t P;                     /* period since the previous flip */
    uint32_t vbp;                   /* VBLANK period estimate */
    uint32_t crit;                  /* us charged to the pacemaker */
    uint8_t vb, np, ireq, cls;      /* VBLANKs, presents, asked interval, class */
    uint8_t late, have;             /* deadline missed; HAKUX_FT_HAVE_* bits */
    uint16_t rp, mhz, ins;          /* render passes, GPU MHz (0 none), builder us */
    HakuxFtRow r[HAKUX_FT_NROW];
    uint32_t vh[HAKUX_FT_NH];       /* vCPU lock waits by holder class */
    uint32_t vho[HAKUX_FT_NROLE + 1];   /* ... by holder thread (last: none) */
    uint16_t nw[HAKUX_FT_NROLE];    /* waits that ended, per row */
    uint32_t gidle;                 /* guest idle (HAKUX_FT_NA if unhooked) */
    uint32_t pidle;                 /* PFIFO waiting for work (always on) */
    uint32_t lockw;                 /* DMA_PUT pfifo.lock wait (user.c) */
    uint32_t gpu;                   /* GPU execution read back this frame */
} HakuxFtFrame;

#define HAKUX_FT_HAVE_ROW(r)  (1u << (r))   /* rows 0..3 have schedstat */
#define HAKUX_FT_HAVE_GIDLE   (1u << 4)
#define HAKUX_FT_HAVE_VBLANK  (1u << 5)     /* hakux_ft_vblank() is hooked */

/* What profile.c hands over at each flip, read before the per-frame
 * accumulators it names are reset. */
typedef struct HakuxFtExt {
    int64_t lockw_ns;       /* g_nv2a_stats.cpu_working.lock_wait_ns */
    int64_t pidle_ns;       /* g_nv2a_stats.pacing.renderer_idle_acc_ns */
    int64_t gpu_ns;         /* g_nv2a_stats.phase_working.gpu_total_ns */
    int rp;                 /* g_nv2a_stats.phase_working.gpu_rp_count */
    unsigned vblank_fired;  /* g_nv2a_stats.pacing.vblank_fired */
} HakuxFtExt;

extern int hakux_ft_on;

/* One clock for every timestamp: the ARM generic timer on aarch64, as
 * nv2a_clock_ns(); CLOCK_MONOTONIC elsewhere. */
static inline int64_t hakux_ft_now(void)
{
#if defined(__aarch64__)
    static uint64_t mult;
    uint64_t cnt;
    if (__builtin_expect(!__atomic_load_n(&mult, __ATOMIC_RELAXED), 0)) {
        uint64_t freq;
        asm volatile("mrs %0, cntfrq_el0" : "=r"(freq));
        __atomic_store_n(&mult, ((uint64_t)1000000000ULL << 32) / freq,
                         __ATOMIC_RELAXED);
    }
    asm volatile("mrs %0, cntvct_el0" : "=r"(cnt));
    return (int64_t)(((__uint128_t)cnt *
                      __atomic_load_n(&mult, __ATOMIC_RELAXED)) >> 32);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
#endif
}

static inline bool hakux_ft_enabled(void)
{
    return __builtin_expect(__atomic_load_n(&hakux_ft_on, __ATOMIC_RELAXED),
                            0);
}

/* A wait. t0 == 0 means not recorded (off, or nested in another wait). */
typedef struct HakuxFtWait {
    int64_t t0;
    int8_t holder;          /* holder role, -1 none */
    int8_t reason;
} HakuxFtWait;

void hakux_ft_init(void);                       /* reads the environment */
void hakux_ft_thread(int role);                 /* register the calling thread */
int hakux_ft_role_self(void);                   /* -1 if unregistered */
void hakux_ft_wait_begin_slow(HakuxFtWait *w, int reason, int holder);
void hakux_ft_wait_end_slow(HakuxFtWait *w);
void hakux_ft_gidle_begin(void);                /* vCPU: guest idle starts */
void hakux_ft_gidle_end(void);                  /* vCPU: guest idle ends */
void hakux_ft_present(void);                    /* guest INCREMENT (present) */
void hakux_ft_vblank(void);                     /* VBLANK fired */
void hakux_ft_flip(const HakuxFtExt *x);         /* PFIFO thread, at the flip */
extern int hakux_ft_bql_owner;                  /* role holding the BQL */
extern void (*hakux_ft_log)(const char *tag, const char *line);

static inline void hakux_ft_wait_begin(HakuxFtWait *w, int reason, int holder)
{
    w->t0 = 0;
    if (hakux_ft_enabled()) {
        hakux_ft_wait_begin_slow(w, reason, holder);
    }
}

static inline void hakux_ft_wait_end(HakuxFtWait *w)
{
    if (__builtin_expect(w->t0 != 0, 0)) {
        hakux_ft_wait_end_slow(w);
    }
}

static inline int hakux_ft_reason_class(int reason)
{
    switch (reason) {
    case HAKUX_FT_W_FENCE:
    case HAKUX_FT_W_DOWNLOAD:
        return HAKUX_FT_H_GPU;
    case HAKUX_FT_W_SUBMIT:
    case HAKUX_FT_W_RTHREAD:
        return HAKUX_FT_H_RENDER;
    case HAKUX_FT_W_IDLE:
        return HAKUX_FT_H_IDLE;
    default:
        return HAKUX_FT_H_WAIT;
    }
}

static inline uint32_t hakux_ft_sub0(uint32_t a, uint32_t b)
{
    return a > b ? a - b : 0;
}

/*
 * THE ATTRIBUTION RULE. Written down here and in NOTES.md; the selftest
 * pins each branch with a synthetic frame that must flip when its premise
 * flips.
 *
 * The vCPU's timeline partitions the frame period P: every instant it is
 * running guest work, running the guest's idle loop, queued, or blocked
 * (in a named wait or not). The guest produces the frame, so the frame's
 * critical path runs along that timeline.
 *
 *  D, the deadline, is the guest's own interval: ireq VBLANKs (inferred from
 *  the flips, or HAKUX_FRAMETRACE_VB) times the VBLANK period.
 *
 *  1. On time (vb <= ireq): VSYNC. The guest asked for this pace.
 *  2. Late, and guest work + run-queue wait > D: RUN. With every wait
 *     removed the frame would still miss.
 *  3. Late otherwise: the waits made it late. Each wait is charged to a
 *     class (a lock wait by the holder's time-weighted state, so one wait
 *     can charge two classes), and the pacemaker is the class with the
 *     largest charge:
 *       lock wait, holder running throughout ............ BLK_LOCK
 *       lock wait, holder in another lock/halt wait ...... BLK_LOCK
 *       lock wait, holder in a GPU wait throughout ....... BLK_GPU
 *       vCPU's own fence or download wait ................ BLK_GPU
 *       lock wait, holder in a render/submit wait ........ RSUBMIT
 *       vCPU's own submit or render-thread wait .......... RSUBMIT
 *       lock wait, holder UNK or IDLE .................... UNATTR
 *       the DMA_PUT wait seen only by lock_wait_ns ....... UNATTR (no holder)
 *       blocked in no named wait ......................... UNATTR
 *       guest idle (the guest itself waited):
 *         GPU busy >= 90% of P ........................... GPU
 *         else the PFIFO thread's largest non-idle share,
 *         if it is at least its idle:
 *           fence/download waits ......................... GPU
 *           submit/render-thread waits ................... RSUBMIT
 *           on-CPU work .................................. PGRAPH
 *           blocked in no named wait ..................... UNATTR
 *         else (both sides idle: the guest waited on time) UNATTR
 *     A largest charge of 0 is UNATTR.
 *
 *  crit: RUN's work; for 3, work + the pacemaker's charge; for VSYNC, work
 *  + the largest charge (what the frame would have cost with no vsync).
 */
static inline void hakux_ft_attribute(HakuxFtFrame *fr,
                                      uint32_t charge[HAKUX_FT_NC])
{
    const HakuxFtRow *v = &fr->r[HAKUX_FT_VCPU];
    const HakuxFtRow *p = &fr->r[HAKUX_FT_PFIFO];
    uint32_t D = fr->vbp * (fr->ireq ? fr->ireq : 1);
    uint32_t gidle = fr->gidle == HAKUX_FT_NA ? 0 : fr->gidle;
    uint32_t halt = v->w[HAKUX_FT_W_HALT];
    uint32_t gidle_on = hakux_ft_sub0(gidle, halt);
    uint32_t work = hakux_ft_sub0(v->run, gidle_on) + v->rq;
    uint32_t extra = hakux_ft_sub0(fr->lockw, v->w[HAKUX_FT_W_PFIFO_LOCK]);
    uint32_t named = extra;
    uint32_t g = gidle > halt ? gidle : halt;
    int best = HAKUX_FT_C_UNATTR;

    for (int i = 0; i < HAKUX_FT_NW; i++) {
        named += v->w[i];
    }
    for (int i = 0; i < HAKUX_FT_NC; i++) {
        charge[i] = 0;
    }
    charge[HAKUX_FT_C_RUN] = work;
    charge[HAKUX_FT_C_BLK_LOCK] = fr->vh[HAKUX_FT_H_RUN] +
                                  fr->vh[HAKUX_FT_H_WAIT];
    charge[HAKUX_FT_C_BLK_GPU] = fr->vh[HAKUX_FT_H_GPU] +
                                 v->w[HAKUX_FT_W_FENCE] +
                                 v->w[HAKUX_FT_W_DOWNLOAD];
    charge[HAKUX_FT_C_RSUBMIT] = fr->vh[HAKUX_FT_H_RENDER] +
                                 v->w[HAKUX_FT_W_SUBMIT] +
                                 v->w[HAKUX_FT_W_RTHREAD];
    charge[HAKUX_FT_C_UNATTR] = fr->vh[HAKUX_FT_H_UNK] +
                                fr->vh[HAKUX_FT_H_IDLE] + extra +
                                v->w[HAKUX_FT_W_OTHER] +
                                hakux_ft_sub0(v->blk, named);
    if (g) {
        if ((uint64_t)fr->gpu * 10 >= (uint64_t)fr->P * 9) {
            charge[HAKUX_FT_C_GPU] += g;
        } else {
            uint32_t pnamed = 0, pfence, prend, punn, pwork;
            uint32_t s[4];
            int cls[4] = { HAKUX_FT_C_GPU, HAKUX_FT_C_RSUBMIT,
                           HAKUX_FT_C_PGRAPH, HAKUX_FT_C_UNATTR };
            int k = 0;

            for (int i = 0; i < HAKUX_FT_NW; i++) {
                if (i != HAKUX_FT_W_IDLE) {
                    pnamed += p->w[i];
                }
            }
            pfence = p->w[HAKUX_FT_W_FENCE] + p->w[HAKUX_FT_W_DOWNLOAD];
            prend = p->w[HAKUX_FT_W_SUBMIT] + p->w[HAKUX_FT_W_RTHREAD];
            punn = hakux_ft_sub0(p->blk, fr->pidle + pnamed);
            pwork = hakux_ft_sub0(fr->P, fr->pidle + pnamed + p->rq + punn);
            s[0] = pfence;
            s[1] = prend;
            s[2] = pwork;
            s[3] = punn;
            for (int i = 1; i < 4; i++) {
                if (s[i] > s[k]) {
                    k = i;
                }
            }
            if (s[k] >= fr->pidle && s[k] > 0) {
                charge[cls[k]] += g;
            } else {
                charge[HAKUX_FT_C_UNATTR] += g;
            }
        }
    }

    for (int i = HAKUX_FT_C_BLK_GPU; i < HAKUX_FT_NC; i++) {
        if (charge[i] > charge[best]) {
            best = i;
        }
    }
    fr->late = fr->ireq ? fr->vb > fr->ireq
                        : (uint64_t)fr->P * 20 > (uint64_t)D * 21;
    if (!fr->late) {
        fr->cls = HAKUX_FT_C_VSYNC;
        fr->crit = work + charge[best];
    } else if (work > D) {
        fr->cls = HAKUX_FT_C_RUN;
        fr->crit = work;
    } else {
        fr->cls = charge[best] ? best : HAKUX_FT_C_UNATTR;
        fr->crit = work + charge[best];
    }
}

/* Short names, for the summary, the CSV and the reader. */
static const char *const hakux_ft_cls_name[HAKUX_FT_NC] __attribute__((unused)) = {
    "vsync", "run", "bgpu", "block", "pgraph", "gpu", "rsub", "unattr"
};
static const char *const hakux_ft_w_name[HAKUX_FT_NW] __attribute__((unused)) = {
    "bql", "pfl", "pgl", "halt", "idle", "fence", "submit", "rthr", "dl", "oth"
};
static const char *const hakux_ft_h_name[HAKUX_FT_NH] __attribute__((unused)) = {
    "unk", "run", "gpu", "rnd", "idle", "wait"
};
static const char *const hakux_ft_row_name[HAKUX_FT_NROW] __attribute__((unused)) = {
    "v", "p", "r", "m", "o"
};

#ifdef HAKUX_FT_IMPLEMENTATION
/* ------------------------------------------------------------------------ */

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#if defined(__linux__)
#include <sys/syscall.h>
#endif
#ifdef __ANDROID__
#include <android/log.h>
#endif

int hakux_ft_on;
int hakux_ft_bql_owner = -1;

#define FT_SPAN_RING 4096           /* per role */
#define FT_FRAME_RING 1024
#define FT_PRESENT_RING 1024
#define FT_HIST 600                 /* the writer's frame history */
#define FT_SPAN_MIN_NS 200000       /* spans shorter than this are not kept */
#define FT_DUMP_SPAN_MIN_NS 500000  /* nor dumped */
#define FT_DUMP_SPANS_MAX 400
#define FT_HITCH_BEFORE 60
#define FT_HITCH_AFTER 10
#define FT_HITCH_MIN_NS 50000000LL

typedef struct FtSpan {
    int64_t t0;
    uint32_t dur_us;
    uint8_t reason;
    int8_t holder;
    uint8_t gpu_pct;        /* lock waits: share booked to the holder's GPU */
    uint8_t run_pct;        /* ... and to its own work */
} FtSpan;

typedef struct FtRole {
    /* Written by the role's own thread only. */
    uint32_t sq;                    /* seqlock, odd while updating */
    uint32_t st;                    /* state word, seq << 5 | st */
    int64_t wt0;                    /* in-progress wait start, 0 none */
    int8_t wholder;
    uint8_t wreason;
    uint64_t acc[HAKUX_FT_NW];      /* booked wait ns */
    uint64_t hold[HAKUX_FT_NH];     /* booked lock-wait ns by holder class */
    uint64_t hrole[HAKUX_FT_NROLE + 1]; /* ... by holder role, last: none */
    uint64_t nwait;                 /* waits ended */
    uint64_t gacc;                  /* guest idle ns booked (vCPU) */
    int64_t gt0;                    /* guest idle in progress since, 0 none */
    uint32_t span_head;
    FtSpan span[FT_SPAN_RING];
    /* Set once at registration. */
    int tid;
    int ssfd;
} __attribute__((aligned(64))) FtRole;

static FtRole ft_role[HAKUX_FT_NROLE];
static uint64_t ft_other_acc[HAKUX_FT_NW];   /* atomic adds, any thread */
static __thread int8_t ft_self = -1;
static __thread uint8_t ft_depth;

/* Presents (vCPU) and VBLANKs (the VBLANK timer's thread). */
static int64_t ft_present_t[FT_PRESENT_RING];
static uint32_t ft_present_head;
static int64_t ft_vblank_t[FT_PRESENT_RING];
static uint32_t ft_vblank_head;

/* Frames, PFIFO thread -> writer. */
static HakuxFtFrame ft_frames[FT_FRAME_RING];
static uint32_t ft_frame_head;

/* Configuration. */
static int ft_force_ireq;           /* HAKUX_FRAMETRACE_VB */
static int ft_csv_wanted = 1;       /* HAKUX_FRAMETRACE_CSV=0 turns it off */
static char ft_dir[256];
static int ft_mhz_fd = -1;
static int ft_mhz_div = 1;          /* sysfs unit -> MHz */

/* Logging, overridable by the selftest. On Android every line goes out on
 * hakuX-lane as "[<tag>] <line>": the dispatcher's logcat keeps only the
 * tags in LOGCAT_SPEC (dispatcher.sh), and a hakuX-ft tag of its own was
 * dropped whole on the first device run. */
static void ft_log_default(const char *tag, const char *line)
{
#ifdef __ANDROID__
    __android_log_print(ANDROID_LOG_INFO, "hakuX-lane", "[%s] %s", tag, line);
#else
    fprintf(stderr, "%s: %s\n", tag, line);
#endif
}
void (*hakux_ft_log)(const char *tag, const char *line) = ft_log_default;

static int ft_gettid(void)
{
#if defined(__linux__)
    return (int)syscall(SYS_gettid);
#else
    return 0;
#endif
}

#define FT_LD(p) __atomic_load_n((p), __ATOMIC_RELAXED)
#define FT_ST(p, v) __atomic_store_n((p), (v), __ATOMIC_RELAXED)

static inline void ft_wbegin(FtRole *r)
{
    FT_ST(&r->sq, r->sq + 1);
    __atomic_thread_fence(__ATOMIC_RELEASE);
}

static inline void ft_wend(FtRole *r)
{
    __atomic_thread_fence(__ATOMIC_RELEASE);
    FT_ST(&r->sq, r->sq + 1);
}

static inline void ft_publish(FtRole *r, uint32_t st)
{
    FT_ST(&r->st, (((r->st >> 5) + 1) << 5) | st);
}

void hakux_ft_init(void)
{
    const char *v = getenv("HAKUX_FRAMETRACE");
    static const struct { const char *path; int div; } mhz[] = {
        { "/sys/class/kgsl/kgsl-3d0/gpuclk", 1000000 },
        { "/sys/class/kgsl/kgsl-3d0/devfreq/cur_freq", 1000000 },
        { "/sys/kernel/gpu/gpu_clock", 1 },
    };
    char line[400];

    if (!v || v[0] != '1') {
        return;
    }
    for (int i = 0; i < HAKUX_FT_NROLE; i++) {
        ft_role[i].ssfd = -1;
    }
    v = getenv("HAKUX_FRAMETRACE_VB");
    ft_force_ireq = v ? atoi(v) : 0;
    if (ft_force_ireq < 0 || ft_force_ireq > 8) {
        ft_force_ireq = 0;
    }
    v = getenv("HAKUX_FRAMETRACE_CSV");
    ft_csv_wanted = !(v && v[0] == '0');
    v = getenv("HAKUX_FRAMETRACE_DIR");
    if (v && v[0]) {
        snprintf(ft_dir, sizeof(ft_dir), "%s", v);
    }
#ifdef __ANDROID__
    if (!ft_dir[0]) {
        /* The app's external files dir, which adb (and --pull) can read: the
         * package is the process name up to its ':xemu' suffix. */
        char cmd[128] = "";
        int fd = open("/proc/self/cmdline", O_RDONLY);
        if (fd >= 0) {
            ssize_t n = read(fd, cmd, sizeof(cmd) - 1);
            close(fd);
            cmd[n > 0 ? n : 0] = 0;
            char *c = strchr(cmd, ':');
            if (c) {
                *c = 0;
            }
            if (cmd[0]) {
                snprintf(ft_dir, sizeof(ft_dir),
                         "/storage/emulated/0/Android/data/%s/files", cmd);
            }
        }
    }
#endif
    for (unsigned i = 0; i < sizeof(mhz) / sizeof(mhz[0]); i++) {
        int fd = open(mhz[i].path, O_RDONLY);
        char b[32];
        if (fd >= 0 && pread(fd, b, sizeof(b) - 1, 0) > 0) {
            ft_mhz_fd = fd;
            ft_mhz_div = mhz[i].div;
            break;
        }
        if (fd >= 0) {
            close(fd);
        }
    }
    snprintf(line, sizeof(line),
             "on: vb=%d csv=%d dir=%s mhz_fd=%d (version 1, rule in "
             "hw/xbox/nv2a/pgraph/profile.h)",
             ft_force_ireq, ft_csv_wanted, ft_dir[0] ? ft_dir : "-",
             ft_mhz_fd);
    hakux_ft_log("hakuX-ft1", line);
    __atomic_store_n(&hakux_ft_on, 1, __ATOMIC_RELEASE);
}

void hakux_ft_thread(int role)
{
    FtRole *r;
    char path[64];

    if (!hakux_ft_enabled() || role < 0 || role >= HAKUX_FT_NROLE) {
        return;
    }
    r = &ft_role[role];
    ft_self = (int8_t)role;
    r->tid = ft_gettid();
    snprintf(path, sizeof(path), "/proc/self/task/%d/schedstat", r->tid);
    r->ssfd = open(path, O_RDONLY);
    ft_publish(r, 1);
    {
        char line[96];
        snprintf(line, sizeof(line), "thread %s tid=%d schedstat=%s",
                 hakux_ft_row_name[role], r->tid, r->ssfd >= 0 ? "y" : "n");
        hakux_ft_log("hakuX-ft1", line);
    }
}

int hakux_ft_role_self(void)
{
    return ft_self;
}

/*
 * What @holder was doing over [a, b], in ns per holder class: its recorded
 * waits (the span ring, newest first: spans are pushed in end order, so the
 * scan stops at the first that ended before @a) and its wait in progress,
 * each overlap booked to that wait's class; the rest RUN. Read under the
 * holder's seqlock, so a wait that ends mid-read is seen once, as a span or
 * as in progress. A holder that never registered books UNK.
 */
static void ft_holder_split(int holder, int64_t a, int64_t b,
                            uint64_t out[HAKUX_FT_NH])
{
    FtRole *h = &ft_role[holder];
    uint64_t tot = b > a ? (uint64_t)(b - a) : 0;

    if (!tot) {
        return;
    }
    if (!FT_LD(&h->st)) {
        out[HAKUX_FT_H_UNK] += tot;
        return;
    }
    for (int tries = 0; tries < 8; tries++) {
        uint64_t part[HAKUX_FT_NH] = { 0 }, used = 0;
        uint32_t s1 = __atomic_load_n(&h->sq, __ATOMIC_ACQUIRE);
        uint32_t head;
        int64_t wt0;
        uint8_t wr;

        if ((s1 & 1) && tries < 7) {
            continue;
        }
        head = FT_LD(&h->span_head);
        wt0 = FT_LD(&h->wt0);
        wr = FT_LD(&h->wreason);
        if (wt0 && wt0 < b && wr < HAKUX_FT_NW) {
            int64_t lo = wt0 > a ? wt0 : a;
            part[hakux_ft_reason_class(wr)] += (uint64_t)(b - lo);
            used += (uint64_t)(b - lo);
        }
        for (uint32_t i = 0; i < 64 && i < head && i < FT_SPAN_RING; i++) {
            const FtSpan *sp = &h->span[(head - 1 - i) % FT_SPAN_RING];
            int64_t st = FT_LD(&sp->t0);
            int64_t e = st + (int64_t)FT_LD(&sp->dur_us) * 1000;
            int64_t lo, hi;

            if (e <= a) {
                break;
            }
            lo = st > a ? st : a;
            hi = e < b ? e : b;
            if (hi > lo) {
                part[hakux_ft_reason_class(FT_LD(&sp->reason))] +=
                    (uint64_t)(hi - lo);
                used += (uint64_t)(hi - lo);
            }
        }
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if (__atomic_load_n(&h->sq, __ATOMIC_RELAXED) != s1 && tries < 7) {
            continue;
        }
        if (used > tot) {           /* overlapping spans: scale down */
            for (int k = 0; k < HAKUX_FT_NH; k++) {
                part[k] = part[k] * tot / used;
            }
            used = tot;
        }
        part[HAKUX_FT_H_RUN] += tot - used;
        for (int k = 0; k < HAKUX_FT_NH; k++) {
            out[k] += part[k];
        }
        return;
    }
}

void hakux_ft_wait_begin_slow(HakuxFtWait *w, int reason, int holder)
{
    int self = ft_self;

    if (ft_depth++) {
        return;                     /* nested: the outer wait covers it */
    }
    w->t0 = hakux_ft_now();
    w->reason = (int8_t)reason;
    w->holder = (int8_t)(holder >= 0 && holder < HAKUX_FT_NROLE &&
                         holder != self ? holder : -1);
    if (self >= 0) {
        FtRole *r = &ft_role[self];
        ft_wbegin(r);
        FT_ST(&r->wt0, w->t0);
        FT_ST(&r->wholder, w->holder);
        FT_ST(&r->wreason, (uint8_t)reason);
        ft_publish(r, 2 + (uint32_t)reason);
        ft_wend(r);
    }
}

void hakux_ft_wait_end_slow(HakuxFtWait *w)
{
    int self = ft_self;
    int64_t now = hakux_ft_now();
    int64_t dur = now - w->t0;
    uint64_t hold[HAKUX_FT_NH] = { 0 };
    bool lockw = w->reason <= HAKUX_FT_W_PGRAPH_LOCK;

    ft_depth = 0;
    if (dur < 0) {
        dur = 0;
    }
    if (lockw && self >= 0) {
        if (w->holder >= 0) {
            ft_holder_split(w->holder, w->t0, now, hold);
        } else {
            hold[HAKUX_FT_H_UNK] = (uint64_t)dur;
        }
    }
    if (self < 0) {
        __atomic_fetch_add(&ft_other_acc[w->reason], (uint64_t)dur,
                           __ATOMIC_RELAXED);
    } else {
        FtRole *r = &ft_role[self];
        ft_wbegin(r);
        FT_ST(&r->acc[w->reason], r->acc[w->reason] + (uint64_t)dur);
        if (lockw) {
            int hr = w->holder >= 0 ? w->holder : HAKUX_FT_NROLE;
            for (int k = 0; k < HAKUX_FT_NH; k++) {
                FT_ST(&r->hold[k], r->hold[k] + hold[k]);
            }
            FT_ST(&r->hrole[hr], r->hrole[hr] + (uint64_t)dur);
        }
        FT_ST(&r->nwait, r->nwait + 1);
        FT_ST(&r->wt0, 0);
        ft_publish(r, 1);
        if (dur >= FT_SPAN_MIN_NS) {
            /* Inside the seqlock: a reader sees this wait once, as the span
             * or as in progress. */
            uint32_t h = r->span_head;
            FtSpan *s = &r->span[h % FT_SPAN_RING];
            FT_ST(&s->t0, w->t0);
            FT_ST(&s->dur_us, (uint32_t)(dur / 1000));
            FT_ST(&s->reason, (uint8_t)w->reason);
            FT_ST(&s->holder, w->holder);
            FT_ST(&s->gpu_pct, (uint8_t)(lockw && dur ?
                                         hold[HAKUX_FT_H_GPU] * 100 / dur : 0));
            FT_ST(&s->run_pct, (uint8_t)(lockw && dur ?
                                         hold[HAKUX_FT_H_RUN] * 100 / dur : 0));
            __atomic_store_n(&r->span_head, h + 1, __ATOMIC_RELEASE);
        }
        ft_wend(r);
    }
    w->t0 = 0;
}

void hakux_ft_gidle_begin(void)
{
    FtRole *r = &ft_role[HAKUX_FT_VCPU];

    if (!hakux_ft_enabled() || ft_self != HAKUX_FT_VCPU || r->gt0) {
        return;
    }
    ft_wbegin(r);
    FT_ST(&r->gt0, hakux_ft_now());
    ft_wend(r);
}

void hakux_ft_gidle_end(void)
{
    FtRole *r = &ft_role[HAKUX_FT_VCPU];
    int64_t d;

    if (!hakux_ft_enabled() || ft_self != HAKUX_FT_VCPU || !r->gt0) {
        return;
    }
    d = hakux_ft_now() - r->gt0;
    ft_wbegin(r);
    FT_ST(&r->gacc, r->gacc + (uint64_t)(d > 0 ? d : 0));
    FT_ST(&r->gt0, 0);
    ft_wend(r);
}

/* Single producer each: the vCPU writes presents, one timer thread VBLANKs. */
void hakux_ft_present(void)
{
    uint32_t h;
    if (!hakux_ft_enabled()) {
        return;
    }
    h = ft_present_head;
    ft_present_t[h % FT_PRESENT_RING] = hakux_ft_now();
    __atomic_store_n(&ft_present_head, h + 1, __ATOMIC_RELEASE);
}

void hakux_ft_vblank(void)
{
    uint32_t h;
    if (!hakux_ft_enabled()) {
        return;
    }
    h = ft_vblank_head;
    ft_vblank_t[h % FT_PRESENT_RING] = hakux_ft_now();
    __atomic_store_n(&ft_vblank_head, h + 1, __ATOMIC_RELEASE);
}

/* ---- the flip: PFIFO thread ---------------------------------------- */

typedef struct FtSnap {
    uint64_t acc[HAKUX_FT_NROW][HAKUX_FT_NW];
    uint64_t hold[HAKUX_FT_NH];     /* vCPU only */
    uint64_t hrole[HAKUX_FT_NROLE + 1]; /* vCPU only */
    uint64_t nwait[HAKUX_FT_NROLE];
    uint64_t gidle;
    uint64_t run[HAKUX_FT_NROLE], rq[HAKUX_FT_NROLE];
    bool ss_ok[HAKUX_FT_NROLE];
} FtSnap;

static bool ft_schedstat(int fd, uint64_t *run, uint64_t *rq)
{
    char b[96];
    ssize_t n;
    char *e;

    if (fd < 0) {
        return false;
    }
    n = pread(fd, b, sizeof(b) - 1, 0);
    if (n <= 0) {
        return false;
    }
    b[n] = 0;
    *run = strtoull(b, &e, 10);
    *rq = strtoull(e, NULL, 10);
    return true;
}

/* Effective totals at @now: booked plus the in-progress wait, read under the
 * role's seqlock so a wait ending mid-read is not counted twice or lost. */
static void ft_snap_role(int i, int64_t now, FtSnap *s)
{
    FtRole *r = &ft_role[i];

    for (int tries = 0; tries < 8; tries++) {
        uint32_t s1 = __atomic_load_n(&r->sq, __ATOMIC_ACQUIRE);
        int64_t wt0, gt0;
        int8_t wholder;
        uint8_t wreason;

        if (s1 & 1) {
            continue;
        }
        for (int k = 0; k < HAKUX_FT_NW; k++) {
            s->acc[i][k] = FT_LD(&r->acc[k]);
        }
        if (i == HAKUX_FT_VCPU) {
            for (int k = 0; k < HAKUX_FT_NH; k++) {
                s->hold[k] = FT_LD(&r->hold[k]);
            }
            for (int k = 0; k <= HAKUX_FT_NROLE; k++) {
                s->hrole[k] = FT_LD(&r->hrole[k]);
            }
            s->gidle = FT_LD(&r->gacc);
            gt0 = FT_LD(&r->gt0);
        } else {
            gt0 = 0;
        }
        s->nwait[i] = FT_LD(&r->nwait);
        wt0 = FT_LD(&r->wt0);
        wholder = FT_LD(&r->wholder);
        wreason = FT_LD(&r->wreason);
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if (__atomic_load_n(&r->sq, __ATOMIC_RELAXED) != s1) {
            continue;
        }
        if (wt0 && now > wt0 && wreason < HAKUX_FT_NW) {
            s->acc[i][wreason] += (uint64_t)(now - wt0);
            if (i == HAKUX_FT_VCPU && wreason <= HAKUX_FT_W_PGRAPH_LOCK) {
                if (wholder >= 0 && wholder < HAKUX_FT_NROLE) {
                    ft_holder_split(wholder, wt0, now, s->hold);
                    s->hrole[wholder] += (uint64_t)(now - wt0);
                } else {
                    s->hold[HAKUX_FT_H_UNK] += (uint64_t)(now - wt0);
                    s->hrole[HAKUX_FT_NROLE] += (uint64_t)(now - wt0);
                }
            }
        }
        if (gt0 && now > gt0) {
            s->gidle += (uint64_t)(now - gt0);
        }
        return;
    }
}

static uint32_t ft_us(uint64_t a, uint64_t b)
{
    uint64_t d = a > b ? (a - b) / 1000 : 0;
    return d > 0xfffffffeu ? 0xfffffffeu : (uint32_t)d;
}

static pthread_t ft_writer_thread;
static void *ft_writer(void *opaque);

static struct {
    bool started;
    int64_t t;
    uint32_t f;
    unsigned vblank_fired;
    uint32_t present_head;
    FtSnap snap;
    /* VBLANK period: from the VBLANK count over >= 1 s */
    int64_t vbp_t0;
    unsigned vbp_n0;
    uint32_t vbp_us;
    /* the guest's interval: VBLANKs per flip over the last 256 flips */
    uint8_t vbh[256];
    uint32_t vbh_n;
    uint16_t vbh_cnt[9];
} ft;

static void ft_snap_all(int64_t now, FtSnap *s)
{
    memset(s, 0, sizeof(*s));
    for (int i = 0; i < HAKUX_FT_NROLE; i++) {
        ft_snap_role(i, now, s);
        s->ss_ok[i] = ft_schedstat(ft_role[i].ssfd, &s->run[i], &s->rq[i]);
    }
    for (int k = 0; k < HAKUX_FT_NW; k++) {
        s->acc[HAKUX_FT_OTHER][k] = FT_LD(&ft_other_acc[k]);
    }
}

static uint8_t ft_ireq(uint8_t vb)
{
    uint32_t n;

    if (ft_force_ireq) {
        return (uint8_t)ft_force_ireq;
    }
    if (ft.vbh_n >= 256) {
        ft.vbh_cnt[ft.vbh[ft.vbh_n % 256]]--;
    }
    ft.vbh[ft.vbh_n % 256] = vb > 8 ? 8 : vb;
    ft.vbh_cnt[vb > 8 ? 8 : vb]++;
    ft.vbh_n++;
    n = ft.vbh_n < 256 ? ft.vbh_n : 256;
    if (n < 60) {
        return 0;
    }
    /* The smallest interval the guest uses in at least 5% of its flips. A
     * 30-locked title never flips on 1 VBLANK (GTA SA: 1.6%); a 60 Hz title
     * that often misses still does (Nightfire: 15%). */
    for (int k = 1; k <= 8; k++) {
        if (ft.vbh_cnt[k] * 20u >= n) {
            return (uint8_t)k;
        }
    }
    return 0;
}

void hakux_ft_flip(const HakuxFtExt *x)
{
    int64_t now = hakux_ft_now();
    FtSnap s;
    HakuxFtFrame *fr;
    uint32_t h, ph;
    uint32_t charge[HAKUX_FT_NC];

    if (ft_self < 0) {
        hakux_ft_thread(HAKUX_FT_PFIFO);
    }
    ft_snap_all(now, &s);
    ph = __atomic_load_n(&ft_present_head, __ATOMIC_ACQUIRE);
    if (!ft.started) {
        ft.started = true;
        ft.t = now;
        ft.snap = s;
        ft.vblank_fired = x->vblank_fired;
        ft.present_head = ph;
        ft.vbp_t0 = now;
        ft.vbp_n0 = x->vblank_fired;
        ft.vbp_us = 16683;          /* NTSC until measured */
        pthread_create(&ft_writer_thread, NULL, ft_writer, NULL);
        return;
    }

    h = ft_frame_head;
    fr = &ft_frames[h % FT_FRAME_RING];
    memset(fr, 0, sizeof(*fr));
    fr->t = now;
    fr->f = ++ft.f;
    fr->P = ft_us((uint64_t)now, (uint64_t)ft.t);
    {
        unsigned dv = x->vblank_fired - ft.vblank_fired;
        fr->vb = dv > 255 ? 255 : (uint8_t)dv;
    }
    {
        uint32_t dp = ph - ft.present_head;
        fr->np = dp > 255 ? 255 : (uint8_t)dp;
        fr->tp = ph ? ft_present_t[(ph - 1) % FT_PRESENT_RING] : 0;
    }
    if (now - ft.vbp_t0 >= 1000000000LL) {
        unsigned n = x->vblank_fired - ft.vbp_n0;
        if (n >= 30) {
            ft.vbp_us = (uint32_t)((now - ft.vbp_t0) / 1000 / n);
        }
        ft.vbp_t0 = now;
        ft.vbp_n0 = x->vblank_fired;
    }
    fr->vbp = ft.vbp_us;
    fr->ireq = ft_ireq(fr->vb);

    for (int i = 0; i < HAKUX_FT_NROW; i++) {
        HakuxFtRow *row = &fr->r[i];
        for (int k = 0; k < HAKUX_FT_NW; k++) {
            row->w[k] = ft_us(s.acc[i][k], ft.snap.acc[i][k]);
        }
        if (i < HAKUX_FT_NROLE && s.ss_ok[i] && ft.snap.ss_ok[i]) {
            row->run = ft_us(s.run[i], ft.snap.run[i]);
            row->rq = ft_us(s.rq[i], ft.snap.rq[i]);
            row->blk = hakux_ft_sub0(fr->P, row->run + row->rq);
            fr->have |= HAKUX_FT_HAVE_ROW(i);
        }
    }
    for (int k = 0; k < HAKUX_FT_NH; k++) {
        fr->vh[k] = ft_us(s.hold[k], ft.snap.hold[k]);
    }
    for (int k = 0; k <= HAKUX_FT_NROLE; k++) {
        fr->vho[k] = ft_us(s.hrole[k], ft.snap.hrole[k]);
    }
    for (int k = 0; k < HAKUX_FT_NROLE; k++) {
        uint64_t d = s.nwait[k] - ft.snap.nwait[k];
        fr->nw[k] = (uint16_t)(d > 65535 ? 65535 : d);
    }
    if (s.gidle || ft.snap.gidle) {
        fr->gidle = ft_us(s.gidle, ft.snap.gidle);
        fr->have |= HAKUX_FT_HAVE_GIDLE;
    } else {
        fr->gidle = HAKUX_FT_NA;
    }
    if (__atomic_load_n(&ft_vblank_head, __ATOMIC_RELAXED)) {
        fr->have |= HAKUX_FT_HAVE_VBLANK;
    }
    fr->pidle = (uint32_t)(x->pidle_ns > 0 ? x->pidle_ns / 1000 : 0);
    fr->lockw = (uint32_t)(x->lockw_ns > 0 ? x->lockw_ns / 1000 : 0);
    fr->gpu = (uint32_t)(x->gpu_ns > 0 ? x->gpu_ns / 1000 : 0);
    fr->rp = (uint16_t)(x->rp > 65535 ? 65535 : x->rp < 0 ? 0 : x->rp);
    if (ft_mhz_fd >= 0) {
        char b[32];
        ssize_t n = pread(ft_mhz_fd, b, sizeof(b) - 1, 0);
        if (n > 0) {
            b[n] = 0;
            fr->mhz = (uint16_t)(strtoull(b, NULL, 10) / ft_mhz_div);
        }
    }
    hakux_ft_attribute(fr, charge);

    ft.t = now;
    ft.snap = s;
    ft.vblank_fired = x->vblank_fired;
    ft.present_head = ph;
    fr->ins = (uint16_t)ft_us((uint64_t)hakux_ft_now(), (uint64_t)now);
    __atomic_store_n(&ft_frame_head, h + 1, __ATOMIC_RELEASE);
}

/* ---- the writer --------------------------------------------------------- */

typedef struct FtWriter {
    uint32_t frame_tail, present_tail, span_tail[HAKUX_FT_NROLE];
    HakuxFtFrame hist[FT_HIST];
    uint32_t hist_n;                    /* frames ever added */
    int64_t pres[FT_PRESENT_RING];      /* present times, writer copy */
    uint32_t pres_n;
    FtSpan spans[HAKUX_FT_NROLE][FT_SPAN_RING];
    uint32_t span_n[HAKUX_FT_NROLE];
    uint64_t span_drop;
    FILE *csv;
    char csv_path[320];
    /* summary window */
    int64_t sum_t0;
    uint32_t sum_n, sum_late;
    uint32_t pm[HAKUX_FT_NC], pml[HAKUX_FT_NC];
    uint32_t vbd[5];
    uint32_t P[512], gpu[512];
    int32_t slack[512];
    uint32_t nslack;
    uint64_t vrun, vrq, vblk, vgi, vgw, vw[HAKUX_FT_NW], vh[HAKUX_FT_NH];
    uint64_t vho[HAKUX_FT_NROLE + 1], nw[HAKUX_FT_NROLE];
    uint64_t prun, prq, pblk, pidle, pw[HAKUX_FT_NW], lockw, rrun, rblk;
    uint64_t mhz_sum, ins_sum, crit_sum;
    uint32_t mhz_n, max_ins;
    uint8_t ireq;
    uint32_t median_us;                 /* period median of the last window */
    /* hitch dump in waiting */
    bool pending;
    uint32_t pend_f0, pend_f1;
    uint32_t pend_hitch[8];
    int pend_nh;
    uint32_t hitch_id;
    uint64_t wcpu0;
    int wss;
} FtWriter;

static FtWriter *ftw;

static int ft_cmp_u32(const void *a, const void *b)
{
    uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
    return x < y ? -1 : x > y;
}

static int ft_cmp_i32(const void *a, const void *b)
{
    int32_t x = *(const int32_t *)a, y = *(const int32_t *)b;
    return x < y ? -1 : x > y;
}

static uint32_t ft_pct_u32(uint32_t *v, uint32_t n, int pct)
{
    if (!n) {
        return 0;
    }
    qsort(v, n, sizeof(*v), ft_cmp_u32);
    return v[(uint64_t)(n - 1) * pct / 100];
}

/* The present that released frame @fr: the first after its flip. 0 unknown. */
static int64_t ft_release(FtWriter *w, const HakuxFtFrame *fr)
{
    uint32_t lo = w->pres_n > FT_PRESENT_RING ? w->pres_n - FT_PRESENT_RING : 0;
    for (uint32_t i = lo; i < w->pres_n; i++) {
        int64_t t = w->pres[i % FT_PRESENT_RING];
        if (t > fr->t) {
            return t;
        }
    }
    return 0;
}

static const HakuxFtFrame *ft_hist_get(FtWriter *w, uint32_t f)
{
    const HakuxFtFrame *fr;
    if (!w->hist_n) {
        return NULL;
    }
    fr = &w->hist[(w->hist_n - 1) % FT_HIST];
    if (f > fr->f || fr->f - f >= FT_HIST || fr->f - f >= w->hist_n) {
        return NULL;
    }
    fr = &w->hist[(w->hist_n - 1 - (fr->f - f)) % FT_HIST];
    return fr->f == f ? fr : NULL;
}

static int ft_fmt_frame(char *b, size_t n, const HakuxFtFrame *fr,
                        int64_t slack_ns, bool has_slack)
{
    const HakuxFtRow *v = &fr->r[HAKUX_FT_VCPU], *p = &fr->r[HAKUX_FT_PFIFO];
    const HakuxFtRow *r = &fr->r[HAKUX_FT_RENDER];
    int o = snprintf(b, n,
        "f=%u t=%.3f P=%.2f vb=%u np=%u I=%u c=%s crit=%.2f "
        "v=%.2f/%.2f/%.2f gi=%.2f vw=",
        fr->f, fr->t / 1e6, fr->P / 1e3, fr->vb, fr->np, fr->ireq,
        hakux_ft_cls_name[fr->cls], fr->crit / 1e3,
        v->run / 1e3, v->rq / 1e3, v->blk / 1e3,
        fr->gidle == HAKUX_FT_NA ? -1.0 : fr->gidle / 1e3);
    for (int k = 0; k < HAKUX_FT_NW && o < (int)n; k++) {
        o += snprintf(b + o, n - o, k ? ",%.2f" : "%.2f", v->w[k] / 1e3);
    }
    o += snprintf(b + o, n - o, " vh=");
    for (int k = 0; k < HAKUX_FT_NH && o < (int)n; k++) {
        o += snprintf(b + o, n - o, k ? ",%.2f" : "%.2f", fr->vh[k] / 1e3);
    }
    o += snprintf(b + o, n - o, " vho=%.2f,%.2f,%.2f,%.2f,%.2f nw=%u,%u,%u,%u",
                  fr->vho[0] / 1e3, fr->vho[1] / 1e3, fr->vho[2] / 1e3,
                  fr->vho[3] / 1e3, fr->vho[4] / 1e3,
                  fr->nw[0], fr->nw[1], fr->nw[2], fr->nw[3]);
    o += snprintf(b + o, n - o, " lw=%.2f p=%.2f/%.2f/%.2f pi=%.2f pw=",
                  fr->lockw / 1e3, p->run / 1e3, p->rq / 1e3, p->blk / 1e3,
                  fr->pidle / 1e3);
    for (int k = 0; k < HAKUX_FT_NW && o < (int)n; k++) {
        o += snprintf(b + o, n - o, k ? ",%.2f" : "%.2f", p->w[k] / 1e3);
    }
    o += snprintf(b + o, n - o,
                  " r=%.2f/%.2f/%.2f gpu=%.2f rp=%u mhz=%u",
                  r->run / 1e3, r->rq / 1e3, r->blk / 1e3,
                  fr->gpu / 1e3, fr->rp, fr->mhz);
    if (has_slack) {
        o += snprintf(b + o, n - o, " sl=%.2f", slack_ns / 1e6);
    }
    o += snprintf(b + o, n - o, " ins=%u", fr->ins);
    return o;
}

static void ft_dump_hitch(FtWriter *w)
{
    char line[1024];
    const HakuxFtFrame *f0 = ft_hist_get(w, w->pend_f0);
    const HakuxFtFrame *f1 = ft_hist_get(w, w->pend_f1);
    uint32_t a = w->pend_f0, nf = 0, ns = 0;
    int64_t t0, t1;
    int o;

    while (!f0 && a < w->pend_f1) {
        f0 = ft_hist_get(w, ++a);
    }
    if (!f0 || !f1) {
        w->pending = false;
        return;
    }
    w->hitch_id++;
    o = snprintf(line, sizeof(line), "B %u f0=%u f1=%u med=%.2f thr=%.2f hitch=",
                 w->hitch_id, a, w->pend_f1, w->median_us / 1e3,
                 (w->median_us * 2 > FT_HITCH_MIN_NS / 1000
                  ? w->median_us * 2 : FT_HITCH_MIN_NS / 1000) / 1e3);
    for (int i = 0; i < w->pend_nh && o < (int)sizeof(line); i++) {
        o += snprintf(line + o, sizeof(line) - o, i ? ",%u" : "%u",
                      w->pend_hitch[i]);
    }
    hakux_ft_log("hakuX-ft", line);
    for (uint32_t f = a; f <= w->pend_f1; f++) {
        const HakuxFtFrame *fr = ft_hist_get(w, f);
        if (!fr) {
            continue;
        }
        o = snprintf(line, sizeof(line), "F %u ", w->hitch_id);
        ft_fmt_frame(line + o, sizeof(line) - o, fr, 0, false);
        hakux_ft_log("hakuX-ft", line);
        nf++;
    }
    t0 = f0->t - (int64_t)f0->P * 1000;
    t1 = f1->t;
    for (int r = 0; r < HAKUX_FT_NROLE; r++) {
        uint32_t lo = w->span_n[r] > FT_SPAN_RING ? w->span_n[r] - FT_SPAN_RING
                                                  : 0;
        for (uint32_t i = lo; i < w->span_n[r] && ns < FT_DUMP_SPANS_MAX; i++) {
            const FtSpan *s = &w->spans[r][i % FT_SPAN_RING];
            int64_t e = s->t0 + (int64_t)s->dur_us * 1000;
            if (e < t0 || s->t0 > t1 ||
                (int64_t)s->dur_us * 1000 < FT_DUMP_SPAN_MIN_NS) {
                continue;
            }
            snprintf(line, sizeof(line),
                     "S %u %s %s t=%.3f d=%.2f holder=%s gpu%%=%u run%%=%u",
                     w->hitch_id, hakux_ft_row_name[r],
                     hakux_ft_w_name[s->reason], s->t0 / 1e6,
                     s->dur_us / 1e3,
                     s->holder >= 0 ? hakux_ft_row_name[s->holder] : "-",
                     s->gpu_pct, s->run_pct);
            hakux_ft_log("hakuX-ft", line);
            ns++;
        }
    }
    snprintf(line, sizeof(line), "E %u frames=%u spans=%u span_drop=%llu",
             w->hitch_id, nf, ns, (unsigned long long)w->span_drop);
    hakux_ft_log("hakuX-ft", line);
    w->pending = false;
}

static void ft_summary(FtWriter *w, int64_t now)
{
    char line[2048];
    uint32_t n = w->sum_n ? w->sum_n : 1;
    uint32_t np = w->sum_n < 512 ? w->sum_n : 512;
    uint32_t P50, P95, P99, Pmax = 0, g50, g95;
    int32_t s50 = 0, s05 = 0;
    uint64_t wcpu = 0, wrq;
    int o;
    struct timespec rt;

    for (uint32_t i = 0; i < np; i++) {
        Pmax = w->P[i] > Pmax ? w->P[i] : Pmax;
    }
    P50 = ft_pct_u32(w->P, np, 50);
    P95 = ft_pct_u32(w->P, np, 95);
    P99 = ft_pct_u32(w->P, np, 99);
    w->median_us = P50;
    g50 = ft_pct_u32(w->gpu, np, 50);
    g95 = ft_pct_u32(w->gpu, np, 95);
    if (w->nslack) {
        uint32_t k = w->nslack < 512 ? w->nslack : 512;
        qsort(w->slack, k, sizeof(int32_t), ft_cmp_i32);
        s50 = w->slack[(k - 1) / 2];
        s05 = w->slack[(k - 1) * 5 / 100];
    }
    clock_gettime(CLOCK_REALTIME, &rt);
    if (w->wss >= 0) {
        uint64_t run;
        if (ft_schedstat(w->wss, &run, &wrq)) {
            wcpu = w->wcpu0 ? (run - w->wcpu0) / 1000 : 0;
            w->wcpu0 = run;
        }
    }
    o = snprintf(line, sizeof(line),
        "n=%u rt_ms=%lld t_ms=%.1f I=%u vbp=%.3f pm=",
        w->sum_n, (long long)rt.tv_sec * 1000 + rt.tv_nsec / 1000000,
        now / 1e6, w->ireq, w->hist_n ?
        w->hist[(w->hist_n - 1) % FT_HIST].vbp / 1e3 : 0.0);
    for (int c = 0; c < HAKUX_FT_NC; c++) {
        o += snprintf(line + o, sizeof(line) - o, c ? ",%s:%u" : "%s:%u",
                      hakux_ft_cls_name[c], w->pm[c]);
    }
    o += snprintf(line + o, sizeof(line) - o, " late=%u pml=", w->sum_late);
    for (int c = 0; c < HAKUX_FT_NC; c++) {
        o += snprintf(line + o, sizeof(line) - o, c ? ",%u" : "%u", w->pml[c]);
    }
    o += snprintf(line + o, sizeof(line) - o,
        " p50=%.2f p95=%.2f p99=%.2f max=%.2f gpu50=%.2f gpu95=%.2f mhz=%llu "
        "crit=%.2f vrun=%.2f vgw=%.2f vgi=%.2f vrq=%.2f vblk=%.2f vw=",
        P50 / 1e3, P95 / 1e3, P99 / 1e3, Pmax / 1e3, g50 / 1e3, g95 / 1e3,
        (unsigned long long)(w->mhz_n ? w->mhz_sum / w->mhz_n : 0),
        w->crit_sum / 1e3 / n, w->vrun / 1e3 / n, w->vgw / 1e3 / n,
        w->vgi / 1e3 / n, w->vrq / 1e3 / n, w->vblk / 1e3 / n);
    for (int k = 0; k < HAKUX_FT_NW; k++) {
        o += snprintf(line + o, sizeof(line) - o, k ? ",%.2f" : "%.2f",
                      w->vw[k] / 1e3 / n);
    }
    o += snprintf(line + o, sizeof(line) - o, " vh=");
    for (int k = 0; k < HAKUX_FT_NH; k++) {
        o += snprintf(line + o, sizeof(line) - o, k ? ",%.2f" : "%.2f",
                      w->vh[k] / 1e3 / n);
    }
    o += snprintf(line + o, sizeof(line) - o,
        " vho=%.2f,%.2f,%.2f,%.2f,%.2f nw=%.1f,%.1f,%.1f,%.1f",
        w->vho[0] / 1e3 / n, w->vho[1] / 1e3 / n, w->vho[2] / 1e3 / n,
        w->vho[3] / 1e3 / n, w->vho[4] / 1e3 / n, (double)w->nw[0] / n,
        (double)w->nw[1] / n, (double)w->nw[2] / n, (double)w->nw[3] / n);
    o += snprintf(line + o, sizeof(line) - o,
        " lw=%.2f prun=%.2f prq=%.2f pblk=%.2f pidle=%.2f pw=",
        w->lockw / 1e3 / n, w->prun / 1e3 / n, w->prq / 1e3 / n,
        w->pblk / 1e3 / n, w->pidle / 1e3 / n);
    for (int k = 0; k < HAKUX_FT_NW; k++) {
        o += snprintf(line + o, sizeof(line) - o, k ? ",%.2f" : "%.2f",
                      w->pw[k] / 1e3 / n);
    }
    o += snprintf(line + o, sizeof(line) - o,
        " rrun=%.2f rblk=%.2f sl50=%.2f sl05=%.2f vb=%u/%u/%u/%u/%u "
        "ins=%.1f insmax=%u wcpu_us=%llu",
        w->rrun / 1e3 / n, w->rblk / 1e3 / n, s50 / 1e3, s05 / 1e3,
        w->vbd[0], w->vbd[1], w->vbd[2], w->vbd[3], w->vbd[4],
        (double)w->ins_sum / n, w->max_ins, (unsigned long long)wcpu);
    hakux_ft_log("hakuX-ft1", line);
    if (w->csv) {
        fflush(w->csv);
    }
    {
        /* reset the window; the rings' positions and the history stay */
        w->sum_t0 = now;
        w->sum_n = w->sum_late = w->nslack = w->mhz_n = w->max_ins = 0;
        memset(w->pm, 0, sizeof(w->pm));
        memset(w->pml, 0, sizeof(w->pml));
        memset(w->vbd, 0, sizeof(w->vbd));
        w->vrun = w->vrq = w->vblk = w->vgi = w->vgw = 0;
        memset(w->vw, 0, sizeof(w->vw));
        memset(w->vh, 0, sizeof(w->vh));
        memset(w->vho, 0, sizeof(w->vho));
        memset(w->nw, 0, sizeof(w->nw));
        w->prun = w->prq = w->pblk = w->pidle = w->lockw = 0;
        memset(w->pw, 0, sizeof(w->pw));
        w->rrun = w->rblk = w->mhz_sum = w->ins_sum = w->crit_sum = 0;
    }
}

static void ft_csv_open(FtWriter *w)
{
    time_t tt = time(NULL);
    struct tm tm;
    char ts[32];

    if (!ft_csv_wanted || !ft_dir[0]) {
        return;
    }
    localtime_r(&tt, &tm);
    strftime(ts, sizeof(ts), "%Y%m%d-%H%M%S", &tm);
    snprintf(w->csv_path, sizeof(w->csv_path), "%s/frametrace_%s.csv",
             ft_dir, ts);
    w->csv = fopen(w->csv_path, "w");
    if (w->csv) {
        setvbuf(w->csv, NULL, _IOFBF, 1 << 16);
        fprintf(w->csv, "f,t_ns,P,vb,np,ireq,vbp,late,cls,crit,have,"
                        "v_run,v_rq,v_blk,gidle");
        for (int k = 0; k < HAKUX_FT_NW; k++) {
            fprintf(w->csv, ",v_%s", hakux_ft_w_name[k]);
        }
        for (int k = 0; k < HAKUX_FT_NH; k++) {
            fprintf(w->csv, ",vh_%s", hakux_ft_h_name[k]);
        }
        fprintf(w->csv, ",vho_v,vho_p,vho_r,vho_m,vho_none,nw_v,nw_p,nw_r,nw_m");
        fprintf(w->csv, ",lockw,p_run,p_rq,p_blk,pidle");
        for (int k = 0; k < HAKUX_FT_NW; k++) {
            fprintf(w->csv, ",p_%s", hakux_ft_w_name[k]);
        }
        fprintf(w->csv, ",r_run,r_rq,r_blk");
        for (int k = 0; k < HAKUX_FT_NW; k++) {
            fprintf(w->csv, ",r_%s", hakux_ft_w_name[k]);
        }
        fprintf(w->csv, ",m_run,m_rq,m_blk");
        for (int k = 0; k < HAKUX_FT_NW; k++) {
            fprintf(w->csv, ",o_%s", hakux_ft_w_name[k]);
        }
        fprintf(w->csv, ",gpu,rp,mhz,tp_ns,rel_ns,slack,ins\n");
    }
    {
        char line[400];
        snprintf(line, sizeof(line), "csv=%s", w->csv ? w->csv_path : "none");
        hakux_ft_log("hakuX-ft1", line);
    }
}

static void ft_csv_row(FtWriter *w, const HakuxFtFrame *fr, int64_t rel,
                       int64_t slack, bool has_slack)
{
    FILE *c = w->csv;
    const HakuxFtRow *v = &fr->r[HAKUX_FT_VCPU];

    if (!c) {
        return;
    }
    fprintf(c, "%u,%lld,%u,%u,%u,%u,%u,%u,%s,%u,%u,%u,%u,%u,%d",
            fr->f, (long long)fr->t, fr->P, fr->vb, fr->np, fr->ireq, fr->vbp,
            fr->late, hakux_ft_cls_name[fr->cls], fr->crit, fr->have,
            v->run, v->rq, v->blk,
            fr->gidle == HAKUX_FT_NA ? -1 : (int)fr->gidle);
    for (int k = 0; k < HAKUX_FT_NW; k++) {
        fprintf(c, ",%u", v->w[k]);
    }
    for (int k = 0; k < HAKUX_FT_NH; k++) {
        fprintf(c, ",%u", fr->vh[k]);
    }
    for (int k = 0; k <= HAKUX_FT_NROLE; k++) {
        fprintf(c, ",%u", fr->vho[k]);
    }
    for (int k = 0; k < HAKUX_FT_NROLE; k++) {
        fprintf(c, ",%u", fr->nw[k]);
    }
    fprintf(c, ",%u,%u,%u,%u,%u", fr->lockw, fr->r[1].run, fr->r[1].rq,
            fr->r[1].blk, fr->pidle);
    for (int k = 0; k < HAKUX_FT_NW; k++) {
        fprintf(c, ",%u", fr->r[1].w[k]);
    }
    fprintf(c, ",%u,%u,%u", fr->r[2].run, fr->r[2].rq, fr->r[2].blk);
    for (int k = 0; k < HAKUX_FT_NW; k++) {
        fprintf(c, ",%u", fr->r[2].w[k]);
    }
    fprintf(c, ",%u,%u,%u", fr->r[3].run, fr->r[3].rq, fr->r[3].blk);
    for (int k = 0; k < HAKUX_FT_NW; k++) {
        fprintf(c, ",%u", fr->r[4].w[k]);
    }
    fprintf(c, ",%u,%u,%u,%lld,%lld,", fr->gpu, fr->rp, fr->mhz,
            (long long)fr->tp, (long long)rel);
    if (has_slack) {
        fprintf(c, "%lld", (long long)(slack / 1000));
    }
    fprintf(c, ",%u\n", fr->ins);
}

/* One frame, in order. Exposed for the selftest. */
void hakux_ft_writer_frame(FtWriter *w, const HakuxFtFrame *in, int64_t now);
void hakux_ft_writer_frame(FtWriter *w, const HakuxFtFrame *in, int64_t now)
{
    HakuxFtFrame *fr = &w->hist[w->hist_n % FT_HIST];
    const HakuxFtFrame *prev = w->hist_n ? &w->hist[(w->hist_n - 1) % FT_HIST]
                                         : NULL;
    int64_t rel, prel = 0, slack = 0;
    bool has_slack = false;
    uint32_t thr;
    const HakuxFtRow *v, *p;

    *fr = *in;
    w->hist_n++;
    v = &fr->r[HAKUX_FT_VCPU];
    p = &fr->r[HAKUX_FT_PFIFO];
    if (!w->sum_t0) {
        w->sum_t0 = fr->t;
    }

    /* Slack: the guest's deadline is the release of the previous frame plus
     * its interval; positive = this flip was early by that much. */
    rel = ft_release(w, fr);
    if (prev) {
        prel = ft_release(w, prev);
    }
    if (prel && fr->ireq) {
        slack = prel + (int64_t)fr->ireq * fr->vbp * 1000 - fr->t;
        has_slack = true;
    }
    ft_csv_row(w, fr, rel, slack, has_slack);

    w->sum_n++;
    w->ireq = fr->ireq;
    w->pm[fr->cls]++;
    if (fr->late) {
        w->sum_late++;
        w->pml[fr->cls]++;
    }
    w->vbd[fr->vb > 4 ? 4 : fr->vb]++;
    if (w->sum_n <= 512) {
        w->P[w->sum_n - 1] = fr->P;
        w->gpu[w->sum_n - 1] = fr->gpu;
    }
    if (has_slack && w->nslack < 512) {
        w->slack[w->nslack++] = (int32_t)(slack / 1000);
    }
    w->vrun += v->run;
    w->vrq += v->rq;
    w->vblk += v->blk;
    if (fr->gidle != HAKUX_FT_NA) {
        uint32_t gi_on = hakux_ft_sub0(fr->gidle, v->w[HAKUX_FT_W_HALT]);
        w->vgi += fr->gidle;
        w->vgw += hakux_ft_sub0(v->run, gi_on);
    } else {
        w->vgw += v->run;
    }
    for (int k = 0; k < HAKUX_FT_NW; k++) {
        w->vw[k] += v->w[k];
        w->pw[k] += p->w[k];
    }
    for (int k = 0; k < HAKUX_FT_NH; k++) {
        w->vh[k] += fr->vh[k];
    }
    for (int k = 0; k <= HAKUX_FT_NROLE; k++) {
        w->vho[k] += fr->vho[k];
    }
    for (int k = 0; k < HAKUX_FT_NROLE; k++) {
        w->nw[k] += fr->nw[k];
    }
    w->prun += p->run;
    w->prq += p->rq;
    w->pblk += p->blk;
    w->pidle += fr->pidle;
    w->lockw += fr->lockw;
    w->rrun += fr->r[HAKUX_FT_RENDER].run;
    w->rblk += fr->r[HAKUX_FT_RENDER].blk;
    if (fr->mhz) {
        w->mhz_sum += fr->mhz;
        w->mhz_n++;
    }
    w->ins_sum += fr->ins;
    w->max_ins = fr->ins > w->max_ins ? fr->ins : w->max_ins;
    w->crit_sum += fr->crit;

    /* Hitch: a period over max(2 x the last window's median, 50 ms). */
    thr = w->median_us * 2;
    if (thr < FT_HITCH_MIN_NS / 1000) {
        thr = FT_HITCH_MIN_NS / 1000;
    }
    if (fr->P > thr) {
        if (w->pending && fr->f + FT_HITCH_AFTER - w->pend_f0 > 200) {
            ft_dump_hitch(w);
        }
        if (!w->pending) {
            w->pending = true;
            w->pend_f0 = fr->f > FT_HITCH_BEFORE ? fr->f - FT_HITCH_BEFORE : 1;
            w->pend_nh = 0;
        }
        w->pend_f1 = fr->f + FT_HITCH_AFTER;
        if (w->pend_nh < 8) {
            w->pend_hitch[w->pend_nh++] = fr->f;
        }
    }
    if (w->pending && fr->f >= w->pend_f1) {
        ft_dump_hitch(w);
    }
    if (fr->t - w->sum_t0 >= 1000000000LL) {
        ft_summary(w, fr->t);
    }
    (void)now;
}

/* Drain the producers' rings into the writer. */
static void ft_writer_tick(FtWriter *w, int64_t now)
{
    uint32_t ph = __atomic_load_n(&ft_present_head, __ATOMIC_ACQUIRE);
    uint32_t fh = __atomic_load_n(&ft_frame_head, __ATOMIC_ACQUIRE);

    if (ph - w->present_tail > FT_PRESENT_RING) {
        w->present_tail = ph - FT_PRESENT_RING;
    }
    while (w->present_tail != ph) {
        w->pres[w->pres_n % FT_PRESENT_RING] =
            ft_present_t[w->present_tail % FT_PRESENT_RING];
        w->pres_n++;
        w->present_tail++;
    }
    for (int r = 0; r < HAKUX_FT_NROLE; r++) {
        uint32_t sh = __atomic_load_n(&ft_role[r].span_head, __ATOMIC_ACQUIRE);
        if (sh - w->span_tail[r] > FT_SPAN_RING - 64) {
            w->span_drop += sh - w->span_tail[r] - (FT_SPAN_RING - 64);
            w->span_tail[r] = sh - (FT_SPAN_RING - 64);
        }
        while (w->span_tail[r] != sh) {
            w->spans[r][w->span_n[r] % FT_SPAN_RING] =
                ft_role[r].span[w->span_tail[r] % FT_SPAN_RING];
            w->span_n[r]++;
            w->span_tail[r]++;
        }
    }
    if (fh - w->frame_tail > FT_FRAME_RING - 16) {
        w->frame_tail = fh - (FT_FRAME_RING - 16);
    }
    while (w->frame_tail != fh) {
        const HakuxFtFrame *fr = &ft_frames[w->frame_tail % FT_FRAME_RING];
        /* Wait (up to 300 ms) for the present that releases it. */
        if (now - fr->t < 300000000LL && ft_release(w, fr) == 0) {
            break;
        }
        hakux_ft_writer_frame(w, fr, now);
        w->frame_tail++;
    }
}

static void *ft_writer(void *opaque)
{
    FtWriter *w = calloc(1, sizeof(*w));
    struct timespec ts = { 0, 100000000 };
    char path[64];

    (void)opaque;
    if (!w) {
        return NULL;
    }
    ftw = w;
    snprintf(path, sizeof(path), "/proc/self/task/%d/schedstat", ft_gettid());
    w->wss = open(path, O_RDONLY);
    ft_csv_open(w);
    for (;;) {
        nanosleep(&ts, NULL);
        ft_writer_tick(w, hakux_ft_now());
    }
    return NULL;
}

#endif /* HAKUX_FT_IMPLEMENTATION */
#endif /* HW_XBOX_NV2A_PGRAPH_PROFILE_H */
