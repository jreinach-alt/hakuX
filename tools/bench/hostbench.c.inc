/*
 * hakuX host characterisation harness (lane.perfarch, #68).
 *
 * Lanes cannot run a binary on a handheld: request.sh launches the app and
 * nothing else. So the micro-benchmarks and the thread-placement sampler the
 * performance-architecture study needs live INSIDE the emulator, off by
 * default, and are selected per run with `request.sh --env`:
 *
 *   HAKUX_HOSTBENCH=1       at TCG init, pin to each online CPU in turn and
 *                           time LDR/LDAPR/LDAR/STR/STLR/DMB kernels, the
 *                           mixes the TSO options would emit, and
 *                           flush_idcache_range; report CTR_EL0 and HWCAPs.
 *                           Adds ~5 s to boot. Output: tag hakuX-lane,
 *                           lines starting "perfarch hb".
 *   HAKUX_TOPO=<ms>[,<s>]   start a sampler thread (pinned to the little
 *                           cores) that reads /proc/self/task/<tid>/{stat,
 *                           schedstat} every <ms> (default 100) and reports
 *                           per-thread CPU residency, migrations and runqueue
 *                           wait, plus per-policy CPU clocks, GPU clock and
 *                           thermal, every <s> (default 10). Lines start
 *                           "perfarch topo".
 *
 * Both cost one getenv() each at TCG init when unset. Included from
 * tcg/aarch64/tcg-target.c.inc because that is the first code on every
 * Android run that executes after xemu_android.cpp has applied the env_vars
 * pref, and before any vCPU thread exists. Reader:
 * tools/bench/hostbench_report.py.
 *
 * Define HOSTBENCH_STANDALONE to build it as its own executable
 * (tools/bench/hostbench_main.c) for a host that CAN be reached directly.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include <sched.h>
#include <pthread.h>
#include <unistd.h>
#include <dirent.h>
#include <fcntl.h>
#include <sys/syscall.h>
#if defined(__linux__)
#include <sys/auxv.h>
#endif
#if defined(__ANDROID__)
#include <android/log.h>
#endif

#define HB_MAX_CPUS 16

static void hb_log(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void hb_log(const char *fmt, ...)
{
    char buf[768];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
#if defined(__ANDROID__)
    __android_log_print(ANDROID_LOG_INFO, "hakuX-lane", "perfarch %s", buf);
#else
    fprintf(stderr, "perfarch %s\n", buf);
#endif
}

static uint64_t hb_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + ts.tv_nsec;
}

/* Read a small sysfs/procfs file into buf; returns length or -1. */
static int hb_read(const char *path, char *buf, int len)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    int n;
    if (fd < 0) {
        return -1;
    }
    n = read(fd, buf, len - 1);
    close(fd);
    if (n < 0) {
        return -1;
    }
    buf[n] = 0;
    return n;
}

static long long hb_read_ll(const char *path)
{
    char b[64];
    if (hb_read(path, b, sizeof(b)) <= 0) {
        return -1;
    }
    return strtoll(b, NULL, 0);
}

static int hb_ncpus(void)
{
    long n = sysconf(_SC_NPROCESSORS_CONF);
    if (n < 1) {
        n = 1;
    }
    return n > HB_MAX_CPUS ? HB_MAX_CPUS : (int)n;
}

/*
 * Affinity by raw syscall on a plain bitmask: bionic declares cpu_set_t and
 * sched_setaffinity only under __USE_GNU, which is fixed at the first
 * <sched.h> -- and inside QEMU that inclusion is osdep.h's, not ours.
 */
typedef unsigned long hb_mask;

static int hb_setaffinity(hb_mask m)
{
    return syscall(__NR_sched_setaffinity, 0, sizeof(m), &m) == 0 ? 0 : -1;
}

static hb_mask __attribute__((unused)) hb_getaffinity(void)
{
    hb_mask m = 0;
    if (syscall(__NR_sched_getaffinity, 0, sizeof(m), &m) < 0) {
        m = ~0ul;
    }
    return m;
}

static int hb_getcpu(void)
{
    unsigned cpu = 0;
    if (syscall(__NR_getcpu, &cpu, NULL, NULL) != 0) {
        return -1;
    }
    return (int)cpu;
}

static int __attribute__((unused)) hb_pin(int cpu)
{
    if (hb_setaffinity(1ul << cpu) != 0) {
        return -1;
    }
    sched_yield();
    return hb_getcpu() == cpu ? 0 : -1;
}

__attribute__((unused)) static void *hb_alloc(size_t align, size_t len)
{
    void *p = NULL;
    return posix_memalign(&p, align, len) == 0 ? p : NULL;
}

#if defined(__aarch64__)

/*
 * Kernels. Each is one asm loop so the compiler cannot move, merge or drop
 * anything: 8 operations per iteration, addresses in x9..x16 (eight distinct
 * 64-byte lines), data in x0..x7. x18 is the platform register on Android
 * and is never touched.
 */
#define HB_SETUP_LINES                                                  \
    "add x9,  %[p], #0\n"   "add x10, %[p], #64\n"                      \
    "add x11, %[p], #128\n" "add x12, %[p], #192\n"                     \
    "add x13, %[p], #256\n" "add x14, %[p], #320\n"                     \
    "add x15, %[p], #384\n" "add x16, %[p], #448\n"
#define HB_X8(op)                                                        \
    op " x0, [x9]\n"  op " x1, [x10]\n" op " x2, [x11]\n" op " x3, [x12]\n" \
    op " x4, [x13]\n" op " x5, [x14]\n" op " x6, [x15]\n" op " x7, [x16]\n"
#define HB_X8B(pre, op)                                                   \
    pre op " x0, [x9]\n"  pre op " x1, [x10]\n" pre op " x2, [x11]\n"      \
    pre op " x3, [x12]\n" pre op " x4, [x13]\n" pre op " x5, [x14]\n"      \
    pre op " x6, [x15]\n" pre op " x7, [x16]\n"
#define HB_CLOBBERS "x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7", "x9", \
    "x10", "x11", "x12", "x13", "x14", "x15", "x16", "memory", "cc"

#define HB_KERNEL(name, body)                                            \
    static void __attribute__((noinline)) name(uint64_t n, uint64_t *p)  \
    {                                                                    \
        asm volatile(".arch_extension rcpc\n"                           \
                     HB_SETUP_LINES                                      \
                     "mov x0, #1\n mov x1, #2\n mov x2, #3\n mov x3, #4\n" \
                     "mov x4, #5\n mov x5, #6\n mov x6, #7\n mov x7, #8\n" \
                     "1:\n" body                                         \
                     "subs %[n], %[n], #1\n"                             \
                     "b.ne 1b\n"                                         \
                     : [n] "+r"(n) : [p] "r"(p) : HB_CLOBBERS);          \
    }

/* Loop overhead: eight independent ALU ops. */
HB_KERNEL(hb_k_alu, "add x0, x0, #1\n add x1, x1, #1\n add x2, x2, #1\n"
                    "add x3, x3, #1\n add x4, x4, #1\n add x5, x5, #1\n"
                    "add x6, x6, #1\n add x7, x7, #1\n")
/* Single-instruction throughput, L1-resident. */
HB_KERNEL(hb_k_ldr,   HB_X8("ldr"))
HB_KERNEL(hb_k_ldapr, HB_X8("ldapr"))
HB_KERNEL(hb_k_ldar,  HB_X8("ldar"))
HB_KERNEL(hb_k_str,   HB_X8("str"))
HB_KERNEL(hb_k_stlr,  HB_X8("stlr"))
HB_KERNEL(hb_k_dmb,   "dmb ish\n dmb ish\n dmb ish\n dmb ish\n"
                      "dmb ish\n dmb ish\n dmb ish\n dmb ish\n")
/* What the barrier regimes put in front of each guest access. */
HB_KERNEL(hb_k_ldr_dmbld, HB_X8B("dmb ishld\n", "ldr"))
HB_KERNEL(hb_k_str_dmb,   HB_X8B("dmb ish\n", "str"))

/*
 * A guest-like unit: two loads, a dependent add, one store of the result.
 * Four units per iteration = 8 loads + 4 stores + 8 adds ... reported per
 * UNIT (n * 4). Three regimes:
 *   plain  -- today's XBOX elision: no ordering at all.
 *   rcpc   -- the prototype: LDAPR for loads, STLR for stores (x86-TSO).
 *   revert -- #54's full revert: DMB ISHLD before loads, DMB ISH before
 *             stores (tcg_out_mb's table for LD_LD and LD_ST|ST_ST).
 */
#define HB_UNIT(L, S, a, b, c) \
    L " x0, [" a "]\n add x2, x2, x0\n" \
    L " x1, [" b "]\n add x2, x2, x1\n" \
    S " x2, [" c "]\n"
#define HB_MIX(L, S) \
    HB_UNIT(L, S, "x9",  "x10", "x11") HB_UNIT(L, S, "x12", "x13", "x14") \
    HB_UNIT(L, S, "x15", "x16", "x9")  HB_UNIT(L, S, "x10", "x11", "x12")
HB_KERNEL(hb_k_mix_plain,  HB_MIX("ldr", "str"))
HB_KERNEL(hb_k_mix_rcpc,   HB_MIX("ldapr", "stlr"))
HB_KERNEL(hb_k_mix_revert, HB_MIX("dmb ishld\n ldr", "dmb ish\n str"))
/*
 * Store then reload of the SAME address (spills, stack, read-modify-write):
 * the case where LDAPR is supposed to beat LDAR, because an RCpc acquire may
 * be satisfied before an earlier release store drains.
 */
#define HB_SL(S, L, a) S " x2, [" a "]\n " L " x2, [" a "]\n add x2, x2, #1\n"
#define HB_SLX(S, L) HB_SL(S, L, "x9") HB_SL(S, L, "x10") HB_SL(S, L, "x11") \
                     HB_SL(S, L, "x12")
HB_KERNEL(hb_k_sl_plain, HB_SLX("str", "ldr"))
HB_KERNEL(hb_k_sl_rcpc,  HB_SLX("stlr", "ldapr"))
HB_KERNEL(hb_k_sl_rcsc,  HB_SLX("stlr", "ldar"))
HB_KERNEL(hb_k_sl_revert, HB_SLX("dmb ish\n str", "dmb ishld\n ldr"))

/*
 * Cache-missing loads: 8 independent loads per iteration over a 32 MB
 * buffer at a 4160-byte stride, addresses computed from a counter so there
 * is no pointer chase. Measures what each regime does to memory-level
 * parallelism, which an L1-resident loop cannot see.
 */
#define HB_MISS_SETUP "mov x9, #0\n mov x10, #4160\n"
#define HB_MISS_ONE(L)                                  \
    "add x9, x9, x10\n and x9, x9, %[m]\n"              \
    "add x11, %[p], x9\n" L " x0, [x11]\n"
#define HB_MISS_KERNEL(name, L)                                          \
    static void __attribute__((noinline))                               \
    name(uint64_t n, uint64_t *p, uint64_t mask)                         \
    {                                                                    \
        asm volatile(".arch_extension rcpc\n" HB_MISS_SETUP "1:\n"       \
                     HB_MISS_ONE(L) HB_MISS_ONE(L) HB_MISS_ONE(L)        \
                     HB_MISS_ONE(L) HB_MISS_ONE(L) HB_MISS_ONE(L)        \
                     HB_MISS_ONE(L) HB_MISS_ONE(L)                       \
                     "subs %[n], %[n], #1\n b.ne 1b\n"                   \
                     : [n] "+r"(n) : [p] "r"(p), [m] "r"(mask)           \
                     : HB_CLOBBERS);                                     \
    }
HB_MISS_KERNEL(hb_m_ldr,   "ldr")
HB_MISS_KERNEL(hb_m_ldapr, "ldapr")
HB_MISS_KERNEL(hb_m_ldr_dmbld, "dmb ishld\n ldr")

typedef void (*hb_kfn)(uint64_t, uint64_t *);

/* Minimum over reps of ns per op, calibrated to ~target_ns per rep. */
static double hb_time(hb_kfn fn, uint64_t *p, int ops_per_iter)
{
    const uint64_t target_ns = 4000000;
    uint64_t n = 1024, t;
    double best = 1e30;
    int r;

    for (;;) {
        t = hb_ns();
        fn(n, p);
        t = hb_ns() - t;
        if (t > target_ns / 4 || n > (1ull << 30)) {
            break;
        }
        n *= 4;
    }
    n = (uint64_t)((double)n * target_ns / (t ? t : 1)) + 1;
    for (r = 0; r < 3; r++) {
        double v;
        t = hb_ns();
        fn(n, p);
        t = hb_ns() - t;
        v = (double)t / ((double)n * ops_per_iter);
        if (v < best) {
            best = v;
        }
    }
    return best;
}

static double hb_time_miss(void (*fn)(uint64_t, uint64_t *, uint64_t),
                           uint64_t *p, uint64_t mask)
{
    uint64_t n = 1u << 16, t;
    double best = 1e30;
    int r;
    for (r = 0; r < 3; r++) {
        double v;
        t = hb_ns();
        fn(n, p, mask);
        t = hb_ns() - t;
        v = (double)t / ((double)n * 8);
        if (v < best) {
            best = v;
        }
    }
    return best;
}

static void hb_spin_ms(int ms)
{
    uint64_t end = hb_ns() + (uint64_t)ms * 1000000ull;
    volatile uint64_t x = 0;
    while (hb_ns() < end) {
        x++;
    }
}

#ifdef HOSTBENCH_STANDALONE
static void hb_flush_idcache(uintptr_t rx, uintptr_t rw, size_t len)
{
    __builtin___clear_cache((char *)rw, (char *)rw + len);
}
#else
#define hb_flush_idcache flush_idcache_range
#endif

static void hb_bench_cpu(int cpu, uint64_t *lines, uint64_t *big,
                         uint64_t big_mask, uint32_t *code)
{
    char path[128];
    uint64_t ctr = 0, midr;
    long long khz_before, khz_after;
    double alu, v[20];
    size_t sizes[4] = { 4, 64, 1024, 4096 };
    double fl[4];
    int i, k;

    if (hb_pin(cpu) != 0) {
        hb_log("hb cpu=%d pin=FAILED", cpu);
        return;
    }
    hb_spin_ms(30);    /* let the governor raise this core's clock */

    snprintf(path, sizeof(path),
             "/sys/devices/system/cpu/cpu%d/regs/identification/midr_el1",
             cpu);
    midr = (uint64_t)hb_read_ll(path);
    asm volatile("mrs %0, ctr_el0" : "=r"(ctr));
    snprintf(path, sizeof(path),
             "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq", cpu);
    khz_before = hb_read_ll(path);

    alu = hb_time(hb_k_alu, lines, 8);
    v[0] = hb_time(hb_k_ldr, lines, 8);
    v[1] = hb_time(hb_k_ldapr, lines, 8);
    v[2] = hb_time(hb_k_ldar, lines, 8);
    v[3] = hb_time(hb_k_str, lines, 8);
    v[4] = hb_time(hb_k_stlr, lines, 8);
    v[5] = hb_time(hb_k_dmb, lines, 8);
    v[6] = hb_time(hb_k_ldr_dmbld, lines, 8);
    v[7] = hb_time(hb_k_str_dmb, lines, 8);
    v[8] = hb_time(hb_k_mix_plain, lines, 4);
    v[9] = hb_time(hb_k_mix_rcpc, lines, 4);
    v[10] = hb_time(hb_k_mix_revert, lines, 4);
    v[11] = hb_time(hb_k_sl_plain, lines, 4);
    v[12] = hb_time(hb_k_sl_rcpc, lines, 4);
    v[13] = hb_time(hb_k_sl_rcsc, lines, 4);
    v[14] = hb_time(hb_k_sl_revert, lines, 4);
    v[15] = hb_time_miss(hb_m_ldr, big, big_mask);
    v[16] = hb_time_miss(hb_m_ldapr, big, big_mask);
    v[17] = hb_time_miss(hb_m_ldr_dmbld, big, big_mask);

    /* flush_idcache_range on a freshly written range, as tb_gen_code and
     * tb_target_set_jmp_target do (4 bytes = one patched branch). */
    for (k = 0; k < 4; k++) {
        const int reps = 2000;
        uint64_t t = hb_ns();
        for (i = 0; i < reps; i++) {
            code[(i * 16) & 1023] = 0xd503201f + (i & 1) * 0; /* NOP */
            hb_flush_idcache((uintptr_t)code, (uintptr_t)code, sizes[k]);
        }
        fl[k] = (double)(hb_ns() - t) / reps;
    }

    snprintf(path, sizeof(path),
             "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq", cpu);
    khz_after = hb_read_ll(path);

    hb_log("hb cpu=%d midr=0x%llx ctr=0x%llx idc=%d dic=%d khz=%lld/%lld "
           "alu=%.3f", cpu, (unsigned long long)midr,
           (unsigned long long)ctr, (int)((ctr >> 28) & 1),
           (int)((ctr >> 29) & 1), khz_before, khz_after, alu);
    hb_log("hb cpu=%d op_ns ldr=%.3f ldapr=%.3f ldar=%.3f str=%.3f "
           "stlr=%.3f dmb=%.3f dmbld_ldr=%.3f dmb_str=%.3f",
           cpu, v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7]);
    hb_log("hb cpu=%d unit_ns mix_plain=%.3f mix_rcpc=%.3f mix_revert=%.3f "
           "sl_plain=%.3f sl_rcpc=%.3f sl_rcsc=%.3f sl_revert=%.3f",
           cpu, v[8], v[9], v[10], v[11], v[12], v[13], v[14]);
    hb_log("hb cpu=%d miss_ns ldr=%.3f ldapr=%.3f dmbld_ldr=%.3f "
           "flush_ns b4=%.1f b64=%.1f b1k=%.1f b4k=%.1f",
           cpu, v[15], v[16], v[17], fl[0], fl[1], fl[2], fl[3]);
}

static void hakux_hostbench_run(void)
{
    int ncpu = hb_ncpus(), cpu;
    hb_mask saved;
    const size_t big_bytes = 32u << 20;
    uint64_t *lines = hb_alloc(4096, 4096);
    uint64_t *big = hb_alloc(4096, big_bytes);
    uint32_t *code = hb_alloc(4096, 4096);
    unsigned long hw = 0, hw2 = 0;
    uint64_t t0 = hb_ns();

    if (!lines || !big || !code) {
        hb_log("hb alloc FAILED");
        free(lines); free(big); free(code);
        return;
    }
    memset(lines, 1, 4096);
    memset(big, 1, big_bytes);
    memset(code, 0, 4096);
#if defined(__linux__)
    hw = getauxval(AT_HWCAP);
    hw2 = getauxval(AT_HWCAP2);
#endif
    /* Bits: ATOMICS 8, LRCPC 15, USCAT 25, ILRCPC 26; HWCAP2 SVE2 1. */
    hb_log("hb begin ncpu=%d hwcap=0x%lx hwcap2=0x%lx lse=%d lrcpc=%d "
           "ilrcpc=%d uscat=%d sve2=%d", ncpu, hw, hw2,
           (int)((hw >> 8) & 1), (int)((hw >> 15) & 1),
           (int)((hw >> 26) & 1), (int)((hw >> 25) & 1),
           (int)((hw2 >> 1) & 1));

    saved = hb_getaffinity();
    for (cpu = 0; cpu < ncpu; cpu++) {
        hb_bench_cpu(cpu, lines, big, (big_bytes - 1) & ~63ull, code);
    }
    hb_setaffinity(saved);
    hb_log("hb end ms=%llu", (unsigned long long)((hb_ns() - t0) / 1000000));
    free(lines);
    free(big);
    free(code);
}

#else  /* !__aarch64__ */

static void hakux_hostbench_run(void)
{
    hb_log("hb unsupported host (not aarch64)");
}

#endif /* __aarch64__ */

/* ------------------------------------------------------------------------
 * Topology sampler.
 */

#define HB_MAX_TASKS 256

typedef struct {
    int tid;
    int seen;
    int last_cpu;
    char comm[20];
    unsigned long long prev_run_ns, prev_wait_ns;
    unsigned long long run_ns_cpu[HB_MAX_CPUS];   /* this window */
    unsigned long long wait_ns;                   /* this window */
    unsigned migrations;                          /* this window */
} HbTask;

typedef struct {
    int lead_cpu;
    char name[16];
    unsigned long long sum_khz;
    long long min_khz, max_khz, cap_khz;
    unsigned n;
} HbPolicy;

static HbTask hb_tasks[HB_MAX_TASKS];
static int hb_ntasks;

static HbTask *hb_task(int tid)
{
    int i;
    for (i = 0; i < hb_ntasks; i++) {
        if (hb_tasks[i].tid == tid) {
            return &hb_tasks[i];
        }
    }
    if (hb_ntasks == HB_MAX_TASKS) {
        return NULL;
    }
    memset(&hb_tasks[hb_ntasks], 0, sizeof(HbTask));
    hb_tasks[hb_ntasks].tid = tid;
    hb_tasks[hb_ntasks].last_cpu = -1;
    return &hb_tasks[hb_ntasks++];
}

/* Field 39 of /proc/<pid>/task/<tid>/stat: CPU last run on. */
static int hb_stat_cpu(const char *buf)
{
    const char *p = strrchr(buf, ')');
    int field = 2;
    if (!p) {
        return -1;
    }
    p++;
    while (*p && field < 39) {
        if (*p == ' ') {
            field++;
        }
        p++;
    }
    return *p ? atoi(p) : -1;
}

static void hb_sample_tasks(void)
{
    DIR *d = opendir("/proc/self/task");
    struct dirent *e;
    char path[96], buf[512];
    if (!d) {
        return;
    }
    while ((e = readdir(d)) != NULL) {
        int tid = atoi(e->d_name), cpu;
        unsigned long long run, wait;
        HbTask *t;
        if (tid <= 0 || !(t = hb_task(tid))) {
            continue;
        }
        snprintf(path, sizeof(path), "/proc/self/task/%d/stat", tid);
        if (hb_read(path, buf, sizeof(buf)) <= 0) {
            continue;
        }
        cpu = hb_stat_cpu(buf);
        if (!t->comm[0]) {
            const char *a = strchr(buf, '('), *b = strrchr(buf, ')');
            if (a && b && b > a) {
                int n = (int)(b - a - 1);
                if (n > (int)sizeof(t->comm) - 1) {
                    n = sizeof(t->comm) - 1;
                }
                memcpy(t->comm, a + 1, n);
                t->comm[n] = 0;
            }
        }
        snprintf(path, sizeof(path), "/proc/self/task/%d/schedstat", tid);
        if (hb_read(path, buf, sizeof(buf)) <= 0 ||
            sscanf(buf, "%llu %llu", &run, &wait) != 2) {
            continue;
        }
        if (t->seen && cpu >= 0 && cpu < HB_MAX_CPUS) {
            /* Attribute the interval's run time to the CPU it ended on:
             * exact when it did not move, an approximation when it did. */
            t->run_ns_cpu[cpu] += run - t->prev_run_ns;
            t->wait_ns += wait - t->prev_wait_ns;
            if (t->last_cpu >= 0 && cpu != t->last_cpu &&
                run != t->prev_run_ns) {
                t->migrations++;
            }
        }
        t->prev_run_ns = run;
        t->prev_wait_ns = wait;
        t->last_cpu = cpu;
        t->seen = 1;
    }
    closedir(d);
}

static int hb_npol;
static HbPolicy hb_pol[8];

static void hb_find_policies(void)
{
    int i;
    char path[96], buf[64];
    for (i = 0; i < HB_MAX_CPUS && hb_npol < 8; i++) {
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpufreq/policy%d/related_cpus", i);
        if (hb_read(path, buf, sizeof(buf)) > 0) {
            HbPolicy *p = &hb_pol[hb_npol++];
            memset(p, 0, sizeof(*p));
            p->lead_cpu = i;
            snprintf(p->name, sizeof(p->name), "p%d", i);
            p->min_khz = -1;
        }
    }
}

static void hb_sample_freq(void)
{
    int i;
    char path[96];
    for (i = 0; i < hb_npol; i++) {
        HbPolicy *p = &hb_pol[i];
        long long cur, cap;
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpufreq/policy%d/scaling_cur_freq",
                 p->lead_cpu);
        cur = hb_read_ll(path);
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpufreq/policy%d/scaling_max_freq",
                 p->lead_cpu);
        cap = hb_read_ll(path);
        if (cur < 0) {
            continue;
        }
        p->sum_khz += cur;
        p->n++;
        if (p->min_khz < 0 || cur < p->min_khz) {
            p->min_khz = cur;
        }
        if (cur > p->max_khz) {
            p->max_khz = cur;
        }
        p->cap_khz = cap;
    }
}

static int hb_ncpu_topo;
static unsigned long long hb_gpu_sum, hb_gpu_busy_sum;
static long long hb_gpu_max;
static unsigned hb_gpu_n;

static void hb_sample_gpu(void)
{
    long long f = hb_read_ll("/sys/class/kgsl/kgsl-3d0/gpuclk");
    long long b = hb_read_ll("/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage");
    if (f >= 0) {
        hb_gpu_sum += f;
        if (f > hb_gpu_max) {
            hb_gpu_max = f;
        }
        hb_gpu_n++;
    }
    if (b >= 0) {
        hb_gpu_busy_sum += b;
    }
}

static void hb_report_thermal(void)
{
    int i;
    char path[96], type[48], line[512];
    int off = 0;
    long long cpu_max = -1, gpu_max = -1, skin = -1;
    int readable = 0;
    for (i = 0; i < 128; i++) {
        long long t;
        snprintf(path, sizeof(path),
                 "/sys/class/thermal/thermal_zone%d/type", i);
        if (hb_read(path, type, sizeof(type)) <= 0) {
            continue;
        }
        snprintf(path, sizeof(path),
                 "/sys/class/thermal/thermal_zone%d/temp", i);
        t = hb_read_ll(path);
        if (t < 0) {
            continue;
        }
        readable++;
        if (strstr(type, "cpu")) {
            cpu_max = t > cpu_max ? t : cpu_max;
        } else if (strstr(type, "gpu")) {
            gpu_max = t > gpu_max ? t : gpu_max;
        } else if (strstr(type, "skin") || strstr(type, "sys-therm")) {
            skin = t > skin ? t : skin;
        }
    }
    off += snprintf(line + off, sizeof(line) - off,
                    "topo thermal zones_readable=%d cpu_max_mC=%lld "
                    "gpu_max_mC=%lld skin_mC=%lld", readable, cpu_max,
                    gpu_max, skin);
    hb_log("%s", line);
}

static void hb_report(double window_s)
{
    int i, c;
    char line[700];

    for (i = 0; i < hb_ntasks; i++) {
        HbTask *t = &hb_tasks[i];
        unsigned long long run = 0;
        int off;
        for (c = 0; c < hb_ncpu_topo; c++) {
            run += t->run_ns_cpu[c];
        }
        /* Report threads busier than 3% of one core. */
        if (run > (unsigned long long)(window_s * 0.03e9)) {
            off = snprintf(line, sizeof(line),
                           "topo tid=%d comm=%s busy=%.1f%% mig/s=%.1f "
                           "rqwait_ms/s=%.2f cpu%%=", t->tid, t->comm,
                           100.0 * run / (window_s * 1e9),
                           t->migrations / window_s,
                           t->wait_ns / 1e6 / window_s);
            for (c = 0; c < hb_ncpu_topo && off < (int)sizeof(line) - 8;
                 c++) {
                off += snprintf(line + off, sizeof(line) - off, "%s%.0f",
                                c ? "/" : "", 100.0 * t->run_ns_cpu[c] / run);
            }
            hb_log("%s", line);
        }
        memset(t->run_ns_cpu, 0, sizeof(t->run_ns_cpu));
        t->wait_ns = 0;
        t->migrations = 0;
    }
    {
        int off = snprintf(line, sizeof(line), "topo freq win_s=%.1f",
                           window_s);
        for (i = 0; i < hb_npol; i++) {
            HbPolicy *p = &hb_pol[i];
            if (p->n) {
                off += snprintf(line + off, sizeof(line) - off,
                                " %s=%llu(%lld-%lld,cap%lld)", p->name,
                                p->sum_khz / p->n / 1000, p->min_khz / 1000,
                                p->max_khz / 1000, p->cap_khz / 1000);
            }
            p->sum_khz = 0;
            p->n = 0;
            p->min_khz = -1;
            p->max_khz = 0;
        }
        if (hb_gpu_n) {
            off += snprintf(line + off, sizeof(line) - off,
                            " gpu_mhz=%llu(max%lld) gpu_busy%%=%llu",
                            hb_gpu_sum / hb_gpu_n / 1000000,
                            hb_gpu_max / 1000000,
                            hb_gpu_busy_sum / hb_gpu_n);
        } else {
            off += snprintf(line + off, sizeof(line) - off,
                            " gpu=unreadable");
        }
        hb_gpu_sum = hb_gpu_busy_sum = 0;
        hb_gpu_max = 0;
        hb_gpu_n = 0;
        hb_log("%s", line);
    }
    hb_report_thermal();
}

static int hb_topo_period_ms = 100, hb_topo_report_s = 10;

static void *hb_topo_thread(void *arg)
{
    uint64_t last = hb_ns();
    (void)arg;
    /* Stay on the little cores so the sampler does not perturb what it
     * measures. On SD 8 Gen 2 that is cpu0-2 (A510). */
    hb_setaffinity(hb_ncpu_topo >= 3 ? 0x7ul : 0x1ul);
    hb_find_policies();
    hb_log("topo start period_ms=%d report_s=%d policies=%d",
           hb_topo_period_ms, hb_topo_report_s, hb_npol);
    for (;;) {
        uint64_t now;
        hb_sample_tasks();
        hb_sample_freq();
        hb_sample_gpu();
        now = hb_ns();
        if (now - last >= (uint64_t)hb_topo_report_s * 1000000000ull) {
            hb_report((now - last) / 1e9);
            last = now;
        }
        usleep(hb_topo_period_ms * 1000);
    }
    return NULL;
}

static void hakux_topo_start(const char *spec)
{
    pthread_t th;
    int ms = 0, s = 0;
    if (sscanf(spec, "%d,%d", &ms, &s) >= 1 && ms >= 10) {
        hb_topo_period_ms = ms;
    }
    if (s >= 1) {
        hb_topo_report_s = s;
    }
    hb_ncpu_topo = hb_ncpus();
    if (pthread_create(&th, NULL, hb_topo_thread, NULL) == 0) {
        pthread_detach(th);
    } else {
        hb_log("topo start FAILED");
    }
}

/* ------------------------------------------------------------------------
 * vCPU placement prototype: HAKUX_PLACE_VCPU=prime | <hex cpu mask>.
 *
 * XEMU_OPT_THREAD_AFFINITY, the fork's own pinning, is compiled out (it
 * defaults to 0 and the Android CMake never sets it), and its 90%-of-max
 * threshold would have put qemu-main AND every thread it spawns on the one
 * prime core. This pins only the vCPU thread, identified as the thread that
 * generates code: called from tcg_out_tb_start, so on the first translation.
 * "prime" = the CPUs whose cpuinfo_max_freq equals the highest (cpu7, the
 * Cortex-X3, on SD 8 Gen 2).
 */
static int hb_place_state;   /* 0 = not yet looked, 1 = done */

static hb_mask hb_prime_mask(void)
{
    long long f[HB_MAX_CPUS], max = 0;
    int i, n = hb_ncpus();
    hb_mask m = 0;
    char path[96];
    for (i = 0; i < n; i++) {
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq", i);
        f[i] = hb_read_ll(path);
        if (f[i] > max) {
            max = f[i];
        }
    }
    for (i = 0; i < n && max > 0; i++) {
        if (f[i] == max) {
            m |= 1ul << i;
        }
    }
    return m;
}

static void hakux_place_vcpu_once(void)
{
    const char *spec;
    hb_mask m;
    if (hb_place_state) {
        return;
    }
    hb_place_state = 1;
    spec = getenv("HAKUX_PLACE_VCPU");
    if (!spec || !spec[0] || strcmp(spec, "0") == 0) {
        const char *topo = getenv("HAKUX_TOPO");
        if (topo && topo[0] && strcmp(topo, "0") != 0) {
            /* Name the vCPU tid so the sampler's rows can be read by role
             * in the unpinned arm too. */
            hb_log("place vcpu tid=%ld spec=none -> NOT PINNED",
                   (long)syscall(__NR_gettid));
        }
        return;
    }
    m = strcmp(spec, "prime") == 0 ? hb_prime_mask()
                                   : strtoul(spec, NULL, 16);
    if (m == 0) {
        hb_log("place vcpu spec=%s -> empty mask, not pinned", spec);
        return;
    }
    hb_log("place vcpu tid=%ld spec=%s mask=0x%lx -> %s", (long)syscall(__NR_gettid),
           spec, m, hb_setaffinity(m) == 0 ? "PINNED" : "FAILED");
}

/* The one entry point: two getenv() calls when neither is set. */
static void hakux_hostbench_maybe_run(void)
{
    const char *hb = getenv("HAKUX_HOSTBENCH");
    const char *topo = getenv("HAKUX_TOPO");
    if (hb && hb[0] && strcmp(hb, "0") != 0) {
        hakux_hostbench_run();
    }
    if (topo && topo[0] && strcmp(topo, "0") != 0) {
        hakux_topo_start(topo);
    }
}
