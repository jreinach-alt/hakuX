/*
 * lane.pmucounters (#433): the [pmu433] hook outside the emulator.
 *
 * Compiles hakux-pmu.c.inc (the in-process hook) with stand-ins for the QEMU
 * pieces it uses, so that
 *   - the hook's code is compile-checked with the NDK before it is granted,
 *   - one binary, pushed and run with `run-as` in the debug app's context,
 *     answers R0 on a device with no emulator build: which PMUs open, which
 *     events, and whether the control kernels read as expected, and
 *   - `pmuprobe <secs>` after the controls prints slice lines for a busy
 *     loop, the same format the emulator prints.
 *
 * Build: see build_probe.sh. Output goes to stdout, one [pmu433] line each.
 */
#define _GNU_SOURCE
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define likely(x) __builtin_expect(!!(x), 1)
#define NANOSECONDS_PER_SECOND 1000000000LL
#define NV2A_PROF_NUM_FRAMES 300
#define PMU433_LOG(...) do { printf(__VA_ARGS__); printf("\n"); \
                             fflush(stdout); } while (0)
#define g_new(T, n) ((T *)malloc(sizeof(T) * (n)))
#define g_free free

static int64_t get_clock(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static struct {
    unsigned frame_count, frame_ptr;
    struct { int mspf; } frame_history[NV2A_PROF_NUM_FRAMES];
} g_nv2a_stats;

/* No code buffer here: every sample is `host`, in this binary. */
typedef struct TranslationBlock {
    uint64_t pc, page_addr[2];
    uint16_t icount;
    uint8_t tier;
    struct { const void *ptr; size_t size; } tc;
} TranslationBlock;
static uintptr_t tcg_splitwx_diff;
static TranslationBlock *tcg_tb_lookup(uintptr_t tc_ptr) { return NULL; }
static bool in_code_gen_buffer(const void *p) { return false; }

#include "hakux-pmu.c.inc"

/*
 * pmuprobe sched: how many events one group can hold on this PMU, and which
 * events count at all. The 10-05 R0 runs opened three 7-event groups per PMU
 * and every group read enabled-but-never-running (nr=7, time_running 0, from
 * the first read on every core tried). A group that the PMU cannot schedule
 * reads exactly like that, so this asks the PMU directly: a group of n events
 * (the cycles leader first), busy for 50 ms on this thread, is schedulable when
 * time_running moves. Each event is also opened alone, for the same test.
 *
 * PMU433_TEST_HW builds it for the host (x86 generic events), where a known
 * counter limit is the control: the i7-6700K has four programmable counters
 * per thread beside its fixed cycles and instructions, so a group of up to
 * six schedules and seven does not.
 */
#define SCHED_MAX 19
#ifdef PMU433_TEST_HW
static const uint64_t sched_cfg[SCHED_MAX] = {
    PERF_COUNT_HW_CPU_CYCLES, PERF_COUNT_HW_INSTRUCTIONS,
    PERF_COUNT_HW_BRANCH_INSTRUCTIONS, PERF_COUNT_HW_BRANCH_MISSES,
    PERF_COUNT_HW_CACHE_REFERENCES, PERF_COUNT_HW_CACHE_MISSES,
    PERF_COUNT_HW_BUS_CYCLES,
};
static const int sched_nev = 7;
#else
/* the table of pmu433_ev's groups, then the rest of the PMUv3 names we use */
static const uint64_t sched_cfg[SCHED_MAX] = {
    0x11, 0x08, 0x23, 0x24, 0x21, 0x22, 0x7a, 0x01, 0x02, 0x03, 0x05, 0x17,
    0x35, 0x34, 0x14, 0x04, 0x2a, 0x10, 0x19,
};
static const int sched_nev = SCHED_MAX;
#endif

static uint64_t sched_spin_ms(int ms)
{
    int64_t end = get_clock() + ms * 1000000LL;
    uint64_t x = 1;
    while (get_clock() < end) {
        for (int i = 0; i < 1024; i++) {
            x = x * 6364136223846793005ull + 1442695040888963407ull;
        }
    }
    return x;
}

static void sched_attr(struct perf_event_attr *a, uint32_t type, uint64_t cfg,
                       bool leader)
{
    memset(a, 0, sizeof(*a));
    a->size = sizeof(*a);
    a->type = type;
    a->config = cfg;
    a->disabled = leader;
    a->exclude_kernel = 1;
    a->exclude_hv = 1;
    a->read_format = PERF_FORMAT_GROUP | PERF_FORMAT_TOTAL_TIME_ENABLED |
                     PERF_FORMAT_TOTAL_TIME_RUNNING;
}

/* One group of n events (or one event when n is 1). Returns the group's
 * time_running, 0 when it never got a counter. */
static uint64_t sched_run(uint32_t type, const uint64_t *cfg, int n,
                          const char *tag)
{
    struct perf_event_attr a;
    int fd[SCHED_MAX], opened = 0, err = 0;
    uint64_t r[3 + SCHED_MAX] = {0};
    uint64_t run = 0;
    char vals[512] = "";
    int off = 0;

    for (int k = 0; k < n; k++) {
        sched_attr(&a, type, cfg[k], k == 0);
        fd[k] = pmu433_open(&a, k ? fd[0] : -1);
        if (fd[k] < 0) {
            err = errno;
            break;
        }
        opened++;
    }
    if (opened) {
        ioctl(fd[0], PERF_EVENT_IOC_RESET, PERF_IOC_FLAG_GROUP);
        ioctl(fd[0], PERF_EVENT_IOC_ENABLE, PERF_IOC_FLAG_GROUP);
        pmu433_sink = sched_spin_ms(50);
        ioctl(fd[0], PERF_EVENT_IOC_DISABLE, PERF_IOC_FLAG_GROUP);
        ssize_t got = read(fd[0], r, sizeof(r));
        run = got >= 3 * 8 ? r[2] : 0;
        for (int k = 0; k < opened && got >= (ssize_t)((3 + opened) * 8); k++) {
            off += snprintf(vals + off, sizeof(vals) - off, "%s%" PRIu64,
                            k ? "," : "", r[3 + k]);
        }
        PMU433_LOG("[pmu433] sched %s n=%d opened=%d errno=%d got=%zd nr=%"
                   PRIu64 " en=%" PRIu64 " run=%" PRIu64 " v=%s", tag, n,
                   opened, err, got, r[0], r[1], run, vals);
    } else {
        PMU433_LOG("[pmu433] sched %s n=%d opened=0 errno=%d", tag, n, err);
    }
    for (int k = 0; k < opened; k++) {
        close(fd[k]);
    }
    return opened == n ? run : 0;
}

static int sched_main(void)
{
    uint32_t type = PERF_TYPE_HARDWARE;
    int best = 0;

#ifndef PMU433_TEST_HW
    pmu433_find();
    if (!pmu433_npmu) {
        PMU433_LOG("[pmu433] sched: no PMU found");
        return 2;
    }
    type = pmu433_pmu[0].type;
    PMU433_LOG("[pmu433] sched pid=%d cpu=%d pmu=%s type=%u cpus=%s",
               (int)getpid(), pmu433_getcpu(), pmu433_pmu[0].name, type,
               pmu433_pmu[0].cpus);
#else
    PMU433_LOG("[pmu433] sched host pid=%d cpu=%d type=%u",
               (int)getpid(), pmu433_getcpu(), type);
#endif
    for (int n = 1; n <= sched_nev; n++) {
        if (sched_run(type, sched_cfg, n, "group")) {
            best = n;
        }
    }
    PMU433_LOG("[pmu433] sched largest scheduled group=%d", best);
    for (int k = 0; k < sched_nev; k++) {
        sched_run(type, &sched_cfg[k], 1, "single");
    }
    return 0;
}

/*
 * pmuprobe [secs]            counting: open, controls, slice lines
 * pmuprobe secs EV PERIOD    sampling (HAKUX_PMU=2) of raw event EV (hex):
 *                            smp/smph lines for this binary's busy loop
 */
int main(int argc, char **argv)
{
    if (argc > 1 && !strcmp(argv[1], "sched")) {
        return sched_main();
    }
    int secs = argc > 1 ? atoi(argv[1]) : 3;
    if (argc > 3) {
        setenv("HAKUX_PMU", "2", 1);
        setenv("HAKUX_PMU_EV", argv[2], 1);
        setenv("HAKUX_PMU_PERIOD", argv[3], 1);
    }
    setenv("HAKUX_PMU", "1", 0);
    setenv("HAKUX_PMU_CTL", "1", 0);
    PMU433_LOG("[pmu433] probe pid=%d cpu=%d", (int)getpid(), pmu433_getcpu());
    pmu433_tick();                      /* opens, runs the controls */
    if (pmu433_state < 0) {
        return 2;
    }
    int64_t end = get_clock() + secs * NANOSECONDS_PER_SECOND;
    uint64_t x = 1;
    while (get_clock() < end) {
        for (int i = 0; i < 1024; i++) {
            x = x * 6364136223846793005ull + 1442695040888963407ull;
        }
        g_nv2a_stats.frame_count++;
        pmu433_tick();
    }
    pmu433_sink = x;
    return 0;
}
