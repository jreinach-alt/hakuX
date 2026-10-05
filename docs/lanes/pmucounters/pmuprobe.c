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
 * pmuprobe [secs]            counting: open, controls, slice lines
 * pmuprobe secs EV PERIOD    sampling (HAKUX_PMU=2) of raw event EV (hex):
 *                            smp/smph lines for this binary's busy loop
 */
int main(int argc, char **argv)
{
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
