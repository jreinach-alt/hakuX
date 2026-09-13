/* Standalone behaviour test for the starvation accounting in apu.c.
 *
 * A worktree cannot build the native side, so the logic is extracted VERBATIM
 * from hw/xbox/mcpx/apu/apu.c (starve_extract.c, produced by sed and diffed
 * back against the source) and exercised against stubs. Same approach the
 * capture harness used.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>

/* --- stubs for the two things the extracted code touches --- */

#define qatomic_set(p, v) (*(p) = (v))
#define qatomic_read(p)   (*(p))

static char g_log[64][512];
static int g_log_n;
#define APU_CAP_LOG(fmt, ...)                                                 \
    do {                                                                      \
        snprintf(g_log[g_log_n % 64], sizeof(g_log[0]), fmt, ##__VA_ARGS__);  \
        g_log_n++;                                                            \
    } while (0)

static struct { FILE *fp; } apu_capture;

typedef struct MCPXAPUState {
    struct {
        int device_buffer_bytes;
        int fifo_capacity_bytes;
    } monitor;
} MCPXAPUState;

#include "apu_starve_extract.c"

/* --- the tests --- */

static int checks, failures;

static void ck(const char *name, long long got, long long want)
{
    checks++;
    bool ok = got == want;
    if (!ok) {
        failures++;
    }
    printf("%-58s %s  (got %lld, want %lld)\n", name, ok ? "ok" : "FAIL",
           got, want);
}

static void reset(void)
{
    memset(&apu_starve, 0, sizeof(apu_starve));
    g_log_n = 0;
}

/* apu_starve_report holds its cadence in function-local statics, which is the
 * right shape in the emulator (one APU, one output stream) and inconvenient
 * here. Rather than reach into them, every test below runs on a fresh process
 * cadence by advancing the clock monotonically and never rewinding it, which
 * is what the real caller does too.
 */
static int64_t clock_ms;

int main(void)
{
    MCPXAPUState d = { .monitor = { .device_buffer_bytes = 8192,
                                    .fifo_capacity_bytes = 49152 } };
    const int BUF = 8192;

    /* 1. A fully served callback counts as a callback and nothing else. */
    reset();
    apu_starve_account(BUF, BUF);
    ck("served: callbacks", apu_starve.callbacks, 1);
    ck("served: short_calls", apu_starve.short_calls, 0);
    ck("served: empty_calls", apu_starve.empty_calls, 0);
    ck("served: bytes_asked", apu_starve.bytes_asked, BUF);
    ck("served: bytes_short", apu_starve.bytes_short, 0);

    /* 2. A partial fill records the shortfall exactly, not the whole buffer.
     *    Getting this wrong by using free_b instead of (free_b - copied) would
     *    turn a 1% loss into a 100% one and is the obvious way to write it. */
    reset();
    apu_starve_account(BUF, BUF - 1024);
    ck("partial: short_calls", apu_starve.short_calls, 1);
    ck("partial: bytes_short is the shortfall", apu_starve.bytes_short, 1024);
    ck("partial: not counted as empty", apu_starve.empty_calls, 0);
    ck("partial: max_short", apu_starve.max_short, 1024);

    /* 3. A callback that gets nothing is both short and empty, and the whole
     *    buffer is the shortfall. */
    reset();
    apu_starve_account(BUF, 0);
    ck("empty: short_calls", apu_starve.short_calls, 1);
    ck("empty: empty_calls", apu_starve.empty_calls, 1);
    ck("empty: bytes_short is the whole buffer", apu_starve.bytes_short, BUF);

    /* 4. max_short keeps the worst, not the last. */
    reset();
    apu_starve_account(BUF, BUF - 4096);
    apu_starve_account(BUF, BUF - 100);
    ck("max_short keeps the worst", apu_starve.max_short, 4096);
    ck("max_short: totals still accumulate", apu_starve.bytes_short, 4196);

    /* 5. copied > free_b cannot underflow the counter. Defensive: the caller
     *    cannot produce it today, but bytes_short is unsigned and a negative
     *    shortfall would wrap to 1.8e19 and read as total starvation. */
    reset();
    apu_starve_account(BUF, BUF + 512);
    ck("over-served: not short", apu_starve.short_calls, 0);
    ck("over-served: no phantom bytes", apu_starve.bytes_short, 0);

    /* 6. The report's first call only arms the cadence; it must not log, or a
     *    run would emit a line before a single interval had elapsed. */
    reset();
    clock_ms = 1000;
    apu_starve_report(&d, clock_ms);
    ck("first call arms, does not log", g_log_n, 0);

    /* 7. Under 5 s, nothing is emitted even with starvation present. */
    apu_starve_account(BUF, 0);
    clock_ms += 4000;
    apu_starve_report(&d, clock_ms);
    ck("under 5 s: silent", g_log_n, 0);

    /* 8. At 5 s the first report fires. It fires even on a clean interval --
     *    this is the alive line, and it is the whole reason the instrument can
     *    be distinguished from an instrument that never ran. */
    clock_ms += 1500;
    apu_starve_report(&d, clock_ms);
    ck("at 5 s: one line", g_log_n, 1);
    ck("line names the shortfall", strstr(g_log[0], "8192/8192 bytes") != NULL, 1);
    ck("line reports 100% of that interval",
       strstr(g_log[0], "100.0000%") != NULL, 1);
    ck("line reports capture state", strstr(g_log[0], "capture off") != NULL, 1);
    ck("line reports device buffer", strstr(g_log[0], "device buf 8192 B") != NULL, 1);

    /* 9. A clean 5 s interval after the first report stays silent. 23 served
     *    callbacks and not one short: nothing to say. */
    for (int i = 0; i < 23; i++) {
        apu_starve_account(BUF, BUF);
    }
    clock_ms += 6000;
    apu_starve_report(&d, clock_ms);
    ck("clean interval after first report: silent", g_log_n, 1);

    /* 10. ... until the 30 s heartbeat, which proves a long clean run is
     *     clean rather than unmonitored. */
    clock_ms += 31000;
    apu_starve_report(&d, clock_ms);
    ck("30 s heartbeat fires on a clean run", g_log_n, 2);
    /* NOTE: this expectation was wrong on the first run and the code was
     * right. I wrote "0/0 bytes", reasoning that a clean interval has nothing
     * in it. The line actually reads "0/188416 bytes": the report's window is
     * measured from the last LINE, not the last call, so the heartbeat covers
     * the 23 served callbacks that the silent check at step 9 did not consume.
     * That is the correct behaviour -- the denominator has to match the window
     * the line claims -- and the expectation is what changed. Recorded because
     * "the test failed so I changed the test" is the shape of a mistake, and
     * this one needed checking before it was the right move. */
    ck("heartbeat denominator covers the whole window",
       strstr(g_log[1], "0/188416 bytes") != NULL, 1);
    ck("heartbeat shortfall is zero",
       strstr(g_log[1], "0.0000% of output") != NULL, 1);

    /* 11. A starved interval reports its own delta, not the cumulative total.
     *     Reporting cumulatively would make a single early burst look like
     *     permanent starvation for the rest of the run. */
    for (int i = 0; i < 20; i++) {
        apu_starve_account(BUF, BUF);
    }
    apu_starve_account(BUF, BUF - 2048);
    clock_ms += 6000;
    apu_starve_report(&d, clock_ms);
    ck("starved interval logs", g_log_n, 3);
    ck("delta callbacks, not cumulative",
       strstr(g_log[2], "1/21 callbacks") != NULL, 1);
    ck("delta bytes, not cumulative",
       strstr(g_log[2], "2048/172032 bytes") != NULL, 1);

    /* 12. The percentage is the loudness actually lost: 2048 of 172032. */
    ck("percentage of the interval", strstr(g_log[2], "1.1905%") != NULL, 1);

    /* 13. The capture flag tracks apu_capture.fp, because a starvation figure
     *     taken with the capture armed describes the capture run. */
    apu_capture.fp = (FILE *)1;
    apu_starve_account(BUF, 0);
    clock_ms += 6000;
    apu_starve_report(&d, clock_ms);
    ck("capture ARMED is reported",
       strstr(g_log[3], "capture ARMED") != NULL, 1);
    apu_capture.fp = NULL;

    for (int i = 0; i < g_log_n; i++) {
        printf("LOG[%d] %s\n", i, g_log[i]);
    }
    printf("\n%d checks, %d passed, %d failed\n",
           checks, checks - failures, failures);
    return failures ? 1 : 0;
}
