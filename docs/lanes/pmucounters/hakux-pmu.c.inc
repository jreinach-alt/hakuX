/*
 * #433 [pmu433]: what the CPU's own counters say about the vCPU thread.
 *
 * Off unless HAKUX_PMU is set; unset costs one load and a branch at the
 * [tlb68] gate (1 in 1024 loop returns) and opens nothing.
 *
 *   HAKUX_PMU=1       count, one line per ~1 s slice
 *   HAKUX_PMU_CTL=1   first, run the control kernels below on this thread
 *                     through the same counters, one line each
 *
 * WHY PER PMU. The SD 8 Gen 2 has three or four core types (A510 cpu0-2,
 * A715/A710 cpu3-6, X3 cpu7) and the kernel registers one arm_pmu per type. A generic
 * PERF_TYPE_HARDWARE or PERF_TYPE_RAW event goes to ONE of them (the first
 * registered), and a per-thread event only counts while the thread runs on
 * that PMU's cores: a thread on the X3 would read zero and look idle. So every
 * PMU found under /sys/bus/event_source/devices/ (an entry with a `cpus` file)
 * gets its own groups, by its own `type`, with raw PMUv3 event numbers. Each
 * PMU's time_running then says how long the thread sat on that core type,
 * which is the migration record the brief asks for.
 *
 * GROUPS. cycles (the dedicated counter) + 6 events, the PMUv3 minimum of
 * programmable counters; three groups per PMU, multiplexed by the kernel.
 * Ratios inside a group are exact over that group's running time. Each line
 * prints the raw deltas and each group's running ms; scaling is the reader's.
 *
 *   g0  cyc ins sfe sbe brr brm bis   0x11 0x08 0x23 0x24 0x21 0x22 0x7a
 *   g1  cyc ins l1i itl l1d dtl l2d   0x11 0x08 0x01 0x02 0x03 0x05 0x17
 *   g2  cyc ins iwk dwk l1ia l1da l3d 0x11 0x08 0x35 0x34 0x14 0x04 0x2a
 *
 * sfe/sbe STALL_FRONTEND/BACKEND (cycles), brr/brm BR_RETIRED /
 * BR_MIS_PRED_RETIRED, bis BR_INDIRECT_SPEC, l1i/itl/l1d/dtl/l2d the L1I,
 * L1I TLB, L1D, L1D TLB and L2D refills, iwk/dwk ITLB/DTLB walks, l1ia/l1da
 * L1I/L1D accesses, l3d L3D refill. User mode only (exclude_kernel), which is
 * what perf_event_paranoid 2 allows and is where the JIT runs.
 *
 * Software group (any core): task-clock ns, context switches, migrations.
 *
 * Per slice, from g_nv2a_stats (written by the pgraph thread, read racily;
 * telemetry): fr frames flipped in the slice and fmax the longest of them in
 * ms, so a slow window (> 33 ms) is read apart from a good one on the same
 * line. cpus is the set of CPUs sched_getcpu() saw at the gate.
 *
 * A failed open is a result, not an error: the line names errno and
 * perf_event_paranoid (3 after a reboot until `setprop security.perf_harden
 * 0`; EACCES then) and the thread runs on with the counters off.
 */
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sched.h>
#include <dirent.h>
#include <errno.h>

#ifndef PMU433_LOG
#define PMU433_LOG(...) JC425_LOG(__VA_ARGS__)
#endif

#define PMU433_MAXPMU 6
#define PMU433_NGRP 3
#define PMU433_NEV 7

static const uint16_t pmu433_ev[PMU433_NGRP][PMU433_NEV] = {
    { 0x11, 0x08, 0x23, 0x24, 0x21, 0x22, 0x7a },
    { 0x11, 0x08, 0x01, 0x02, 0x03, 0x05, 0x17 },
    { 0x11, 0x08, 0x35, 0x34, 0x14, 0x04, 0x2a },
};

typedef struct {
    char name[32];
    int type;
    char cpus[24];
    int fd[PMU433_NGRP][PMU433_NEV];      /* [g][0] is the leader */
    uint64_t prev[PMU433_NGRP][2 + PMU433_NEV];  /* en, run, values */
} Pmu433Pmu;

static int pmu433_state;        /* 0 unread, 1 counting, -1 off */
static Pmu433Pmu pmu433_pmu[PMU433_MAXPMU];
static int pmu433_npmu;
static int pmu433_sw[3] = { -1, -1, -1 };
static uint64_t pmu433_swprev[3];

static int pmu433_open(struct perf_event_attr *a, int group)
{
    return (int)syscall(__NR_perf_event_open, a, 0, -1, group,
                        PERF_FLAG_FD_CLOEXEC);
}

static void pmu433_attr(struct perf_event_attr *a, uint32_t type,
                        uint64_t config, bool leader)
{
    memset(a, 0, sizeof(*a));
    a->size = sizeof(*a);
    a->type = type;
    a->config = config;
    a->disabled = leader;
    a->exclude_kernel = 1;
    a->exclude_hv = 1;
    a->read_format = PERF_FORMAT_GROUP | PERF_FORMAT_TOTAL_TIME_ENABLED |
                     PERF_FORMAT_TOTAL_TIME_RUNNING;
}

static bool pmu433_readfile(const char *path, char *buf, size_t n)
{
    FILE *f = fopen(path, "r");
    if (!f) {
        return false;
    }
    bool ok = fgets(buf, (int)n, f) != NULL;
    fclose(f);
    if (ok) {
        buf[strcspn(buf, "\n")] = 0;
    }
    return ok;
}

/* The core-type PMUs: an event_source with a `cpus` file (arm_pmu's). */
static void pmu433_find(void)
{
    DIR *d = opendir("/sys/bus/event_source/devices");
    struct dirent *e;
    char path[160], buf[64];

    if (!d) {
        PMU433_LOG("[pmu433] sysfs event_source unreadable errno=%d; "
                   "falling back to PERF_TYPE_RAW", errno);
    }
    while (d && (e = readdir(d)) && pmu433_npmu < PMU433_MAXPMU) {
        Pmu433Pmu *p = &pmu433_pmu[pmu433_npmu];
        if (e->d_name[0] == '.') {
            continue;
        }
        snprintf(path, sizeof(path), "/sys/bus/event_source/devices/%s/cpus",
                 e->d_name);
        if (!pmu433_readfile(path, p->cpus, sizeof(p->cpus))) {
            continue;
        }
        snprintf(path, sizeof(path), "/sys/bus/event_source/devices/%s/type",
                 e->d_name);
        if (!pmu433_readfile(path, buf, sizeof(buf))) {
            continue;
        }
        p->type = atoi(buf);
        snprintf(p->name, sizeof(p->name), "%s", e->d_name);
        pmu433_npmu++;
    }
    if (d) {
        closedir(d);
    }
    if (!pmu433_npmu) {
        Pmu433Pmu *p = &pmu433_pmu[0];
        snprintf(p->name, sizeof(p->name), "raw");
        snprintf(p->cpus, sizeof(p->cpus), "?");
        p->type = PERF_TYPE_RAW;
        pmu433_npmu = 1;
    }
}

static void pmu433_start(void)
{
    struct perf_event_attr a;
    char buf[16] = "?";
    int opened = 0;

    pmu433_readfile("/proc/sys/kernel/perf_event_paranoid", buf, sizeof(buf));
    pmu433_find();
    for (int i = 0; i < pmu433_npmu; i++) {
        Pmu433Pmu *p = &pmu433_pmu[i];
        char res[PMU433_NGRP][32];

        for (int g = 0; g < PMU433_NGRP; g++) {
            int err = 0;
            for (int k = 0; k < PMU433_NEV; k++) {
                p->fd[g][k] = -1;
            }
            for (int k = 0; k < PMU433_NEV && !err; k++) {
                pmu433_attr(&a, p->type, pmu433_ev[g][k], k == 0);
                p->fd[g][k] = pmu433_open(&a, k ? p->fd[g][0] : -1);
                if (p->fd[g][k] < 0) {
                    err = errno;
                    snprintf(res[g], sizeof(res[g]), "ev%02x:errno%d",
                             pmu433_ev[g][k], err);
                }
            }
            if (err) {
                for (int k = 0; k < PMU433_NEV; k++) {
                    if (p->fd[g][k] >= 0) {
                        close(p->fd[g][k]);
                    }
                    p->fd[g][k] = -1;
                }
                continue;
            }
            snprintf(res[g], sizeof(res[g]), "ok");
            ioctl(p->fd[g][0], PERF_EVENT_IOC_RESET, PERF_IOC_FLAG_GROUP);
            ioctl(p->fd[g][0], PERF_EVENT_IOC_ENABLE, PERF_IOC_FLAG_GROUP);
            opened++;
        }
        PMU433_LOG("[pmu433] open pmu=%s type=%d cpus=%s g0=%s g1=%s g2=%s "
                   "paranoid=%s tid=%d", p->name, p->type, p->cpus,
                   res[0], res[1], res[2], buf, (int)gettid());
    }

    static const uint64_t swc[3] = {
        PERF_COUNT_SW_TASK_CLOCK, PERF_COUNT_SW_CONTEXT_SWITCHES,
        PERF_COUNT_SW_CPU_MIGRATIONS,
    };
    for (int k = 0; k < 3; k++) {
        pmu433_attr(&a, PERF_TYPE_SOFTWARE, swc[k], false);
        a.read_format = 0;
        pmu433_sw[k] = pmu433_open(&a, -1);
    }
    PMU433_LOG("[pmu433] open sw task=%d cs=%d mig=%d groups=%d",
               pmu433_sw[0] >= 0, pmu433_sw[1] >= 0, pmu433_sw[2] >= 0,
               opened);
    pmu433_state = opened ? 1 : -1;
}

/*
 * Read every group of every PMU; out[i][g] gets the deltas since the last
 * read (en, run, values) and prev is advanced. A group that did not open or
 * read short reads as all zero.
 */
static void pmu433_read(uint64_t out[PMU433_MAXPMU][PMU433_NGRP][2 + PMU433_NEV])
{
    for (int i = 0; i < pmu433_npmu; i++) {
        Pmu433Pmu *p = &pmu433_pmu[i];
        for (int g = 0; g < PMU433_NGRP; g++) {
            /* nr, time_enabled, time_running, values[nr] */
            uint64_t r[3 + PMU433_NEV];
            memset(out[i][g], 0, sizeof(out[i][g]));
            if (p->fd[g][0] < 0 ||
                read(p->fd[g][0], r, sizeof(r)) != (ssize_t)sizeof(r) ||
                r[0] != PMU433_NEV) {
                continue;
            }
            for (int k = 0; k < 2 + PMU433_NEV; k++) {
                out[i][g][k] = r[1 + k] - p->prev[g][k];
                p->prev[g][k] = r[1 + k];
            }
        }
    }
}

/* One PMU's groups as " p=NAME g0=RUNMS:v,v,... g1=... g2=..." */
static int pmu433_fmt(char *buf, size_t n, int i,
                      uint64_t d[PMU433_NGRP][2 + PMU433_NEV])
{
    int off = snprintf(buf, n, " p=%s", pmu433_pmu[i].name);
    for (int g = 0; g < PMU433_NGRP && off < (int)n; g++) {
        off += snprintf(buf + off, n - off, " g%d=%.1f", g, d[g][1] / 1e6);
        for (int k = 0; k < PMU433_NEV && off < (int)n; k++) {
            off += snprintf(buf + off, n - off, "%c%" PRIu64, k ? ',' : ':',
                            d[g][2 + k]);
        }
    }
    return off;
}

static uint64_t pmu433_swread(int k)
{
    uint64_t v = 0;
    if (pmu433_sw[k] < 0 || read(pmu433_sw[k], &v, sizeof(v)) != sizeof(v)) {
        return 0;
    }
    uint64_t d = v - pmu433_swprev[k];
    pmu433_swprev[k] = v;
    return d;
}

/* ---- control kernels: known IPC, mispredict rate and miss rates ---- */

static volatile uint64_t pmu433_sink;

static uint64_t pmu433_k_alu1(uint64_t n)
{
    uint64_t x = 0;
    for (uint64_t i = 0; i < n; i++) {
#if defined(__aarch64__)
        /* 64 dependent adds: one per cycle at add latency 1 */
#define A1 "add %0, %0, #1\n\t"
#define A8 A1 A1 A1 A1 A1 A1 A1 A1
        __asm__ volatile(A8 A8 A8 A8 A8 A8 A8 A8 : "+r"(x));
#undef A8
#undef A1
#else
        x += 64;
#endif
    }
    return x;
}

static uint64_t pmu433_k_mul1(uint64_t n)
{
    uint64_t x = 3;
    for (uint64_t i = 0; i < n; i++) {
#if defined(__aarch64__)
        /* 64 dependent multiplies: latency 2 on X3/A715 */
#define M1 "mul %0, %0, %0\n\t"
#define M8 M1 M1 M1 M1 M1 M1 M1 M1
        __asm__ volatile(M8 M8 M8 M8 M8 M8 M8 M8 : "+r"(x));
#undef M8
#undef M1
#else
        x *= x;
#endif
    }
    return x;
}

/* Computed goto among `mask + 1` targets picked by xorshift: an indirect
 * branch whose target is random, so (mask) / (mask + 1) of them mispredict. */
static uint64_t pmu433_k_ind(uint64_t n, unsigned mask)
{
    static void *const tgt[8] = { &&t0, &&t1, &&t2, &&t3,
                                  &&t4, &&t5, &&t6, &&t7 };
    uint64_t s = 0x9e3779b97f4a7c15ull, acc = 0, i = 0;

next:
    if (i++ == n) {
        return acc;
    }
    s ^= s << 13; s ^= s >> 7; s ^= s << 17;
    goto *tgt[(s >> 29) & mask];
t0: acc += 1; goto next;
t1: acc += 3; goto next;
t2: acc += 5; goto next;
t3: acc += 7; goto next;
t4: acc += 11; goto next;
t5: acc += 13; goto next;
t6: acc += 17; goto next;
t7: acc += 19; goto next;
}

/* Pointer chase over a random cycle of 64-byte lines spanning `bytes`. */
static uint64_t pmu433_k_chase(uint64_t n, size_t bytes)
{
    size_t lines = bytes / 64;
    char *m = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    uint32_t *perm = g_new(uint32_t, lines);
    uint64_t s = 0x2545f4914f6cdd1dull;
    void **p;

    if (m == MAP_FAILED) {
        g_free(perm);
        return 0;
    }
    for (size_t i = 0; i < lines; i++) {
        perm[i] = (uint32_t)i;
    }
    for (size_t i = lines - 1; i > 0; i--) {
        s ^= s << 13; s ^= s >> 7; s ^= s << 17;
        size_t j = s % (i + 1);
        uint32_t t = perm[i]; perm[i] = perm[j]; perm[j] = t;
    }
    for (size_t i = 0; i < lines; i++) {
        *(void **)(m + (size_t)perm[i] * 64) =
            m + (size_t)perm[(i + 1) % lines] * 64;
    }
    g_free(perm);
    p = (void **)m;
    for (uint64_t i = 0; i < n; i++) {
        p = (void **)*p;
    }
    pmu433_sink = (uintptr_t)p;
    munmap(m, bytes);
    return n;
}

/*
 * Instruction footprint: `blocks` 64-byte blocks (15 NOPs + B next) chained
 * in a random order and ending in RET, called n times. Footprint larger than
 * L1I (64 KB on X3/A715) refills about once per block; 16 KB does not.
 */
static uint64_t pmu433_k_code(uint64_t n, unsigned blocks)
{
#if defined(__aarch64__)
    size_t bytes = (size_t)blocks * 64;
    uint32_t *c = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    uint32_t *order = g_new(uint32_t, blocks);
    uint64_t s = 0x853c49e6748fea9bull;

    if (c == MAP_FAILED) {
        g_free(order);
        return 0;
    }
    for (unsigned i = 0; i < blocks; i++) {
        order[i] = i;
    }
    for (unsigned i = blocks - 1; i > 1; i--) {   /* keep block 0 first */
        s ^= s << 13; s ^= s >> 7; s ^= s << 17;
        unsigned j = 1 + s % i;
        uint32_t t = order[i]; order[i] = order[j]; order[j] = t;
    }
    for (unsigned i = 0; i < blocks; i++) {
        uint32_t *b = c + order[i] * 16;
        for (int k = 0; k < 15; k++) {
            b[k] = 0xd503201f;                       /* NOP */
        }
        if (i + 1 < blocks) {
            int32_t off = (int32_t)(order[i + 1] * 16) -
                          (int32_t)(order[i] * 16 + 15);
            b[15] = 0x14000000 | ((uint32_t)off & 0x03ffffff);  /* B */
        } else {
            b[15] = 0xd65f03c0;                      /* RET */
        }
    }
    g_free(order);
    if (mprotect(c, bytes, PROT_READ | PROT_EXEC)) {
        munmap(c, bytes);
        return 0;
    }
    __builtin___clear_cache((char *)c, (char *)c + bytes);
    void (*fn)(void) = (void (*)(void))c;
    for (uint64_t i = 0; i < n; i++) {
        fn();
    }
    munmap(c, bytes);
    return n * blocks;
#else
    return 0;
#endif
}

/* Run one kernel with the counters live and log its deltas per PMU. */
static void pmu433_ctl_one(const char *name, int which)
{
    uint64_t d[PMU433_MAXPMU][PMU433_NGRP][2 + PMU433_NEV];
    uint64_t units = 0;
    int c0, c1;
    int64_t t0;
    char buf[1024];

    pmu433_read(d);
    c0 = sched_getcpu();
    t0 = get_clock();
    /*
     * Each kernel runs ~0.3-0.8 s on an X3 so all three groups get time.
     * units: the instructions or iterations a reader divides by -- adds
     * (alu1), multiplies (mul1), indirect branches (ind*), loads (chase*),
     * 64-byte code blocks (code*).
     */
    switch (which) {
    case 0: pmu433_sink = pmu433_k_alu1(25000000); units = 64 * 25000000ull;
            break;
    case 1: pmu433_sink = pmu433_k_mul1(12000000); units = 64 * 12000000ull;
            break;
    case 2: pmu433_sink = pmu433_k_ind(400000000, 0); units = 400000000;
            break;
    case 3: pmu433_sink = pmu433_k_ind(100000000, 7); units = 100000000;
            break;
    case 4: units = pmu433_k_chase(300000000, 16 << 10); break;
    case 5: units = pmu433_k_chase(4000000, 64 << 20); break;
    case 6: units = pmu433_k_code(400000, 256); break;
    case 7: units = pmu433_k_code(8000, 8192); break;
    }
    c1 = sched_getcpu();
    pmu433_read(d);
    for (int i = 0; i < pmu433_npmu; i++) {
        if (!d[i][0][1] && !d[i][1][1] && !d[i][2][1]) {
            continue;
        }
        pmu433_fmt(buf, sizeof(buf), i, d[i]);
        PMU433_LOG("[pmu433] ctl=%s units=%" PRIu64 " ms=%" PRId64
                   " cpu=%d-%d%s", name, units,
                   (get_clock() - t0) / 1000000, c0, c1, buf);
    }
}

static void pmu433_controls(void)
{
    static const char *const names[] = {
        "alu1", "mul1", "ind1", "ind8", "chase16k", "chase64m",
        "code16k", "code512k",
    };
    for (int i = 0; i < 8; i++) {
        pmu433_ctl_one(names[i], i);
    }
}

/* ---- the slice line ---- */

static void pmu433_tick(void)
{
    static int64_t prev_ns;
    static unsigned slice, prev_fc;
    static uint64_t cpus_seen;
    uint64_t d[PMU433_MAXPMU][PMU433_NGRP][2 + PMU433_NEV];
    int64_t now;
    char buf[3072];
    int off = 0;

    if (likely(pmu433_state < 0)) {
        return;
    }
    if (!pmu433_state) {
        const char *e = getenv("HAKUX_PMU");
        if (!e || !*e || !strcmp(e, "0")) {
            pmu433_state = -1;
            return;
        }
        pmu433_start();
        if (pmu433_state < 0) {
            return;
        }
        e = getenv("HAKUX_PMU_CTL");
        if (e && !strcmp(e, "1")) {
            pmu433_controls();
        }
        pmu433_read(d);
        pmu433_swread(0); pmu433_swread(1); pmu433_swread(2);
        prev_ns = get_clock();
        prev_fc = g_nv2a_stats.frame_count;
        return;
    }
    int cpu = sched_getcpu();
    if (cpu >= 0 && cpu < 64) {
        cpus_seen |= 1ull << cpu;
    }
    now = get_clock();
    if (now - prev_ns < NANOSECONDS_PER_SECOND) {
        return;
    }

    /* Frames flipped in the slice and the longest of them. */
    unsigned fc = g_nv2a_stats.frame_count, nf = fc - prev_fc;
    unsigned ptr = g_nv2a_stats.frame_ptr;
    int fmax = 0;
    for (unsigned k = 1; k <= nf && k <= NV2A_PROF_NUM_FRAMES; k++) {
        int ms = g_nv2a_stats.frame_history[(ptr + NV2A_PROF_NUM_FRAMES - k)
                                            % NV2A_PROF_NUM_FRAMES].mspf;
        fmax = ms > fmax ? ms : fmax;
    }

    pmu433_read(d);
    uint64_t tclk = pmu433_swread(0), cs = pmu433_swread(1),
             mig = pmu433_swread(2);
    off = snprintf(buf, sizeof(buf), "[pmu433] s=%u dt=%" PRId64
                   " fr=%u fmax=%d tclk=%.1f cs=%" PRIu64 " mig=%" PRIu64
                   " cpus=%" PRIx64, slice, (now - prev_ns) / 1000000, nf,
                   fmax, tclk / 1e6, cs, mig, cpus_seen);
    for (int i = 0; i < pmu433_npmu && off < (int)sizeof(buf) - 400; i++) {
        if (!d[i][0][1] && !d[i][1][1] && !d[i][2][1]) {
            continue;
        }
        off += pmu433_fmt(buf + off, sizeof(buf) - off, i, d[i]);
    }
    PMU433_LOG("%s", buf);
    slice++;
    prev_ns = now;
    prev_fc = fc;
    cpus_seen = 0;
}
