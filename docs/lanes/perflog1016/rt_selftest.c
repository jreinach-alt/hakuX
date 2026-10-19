/*
 * perflog1016 selftest (#433): compiles hw/xbox/nv2a/debug.h on the host and
 * checks the run-time perflog switch -- off by default and booking nothing
 * while off; one log line per flip and none without one; the ON path
 * reaching the timers and counters it gates; the env pin; a perflog build
 * unaffected. Driven by selftest.py, which also builds it against mutated
 * copies of the header and requires each mutant to FAIL the check named for
 * what it removes.
 *
 *     rt_selftest <dir> marker|env|build
 *
 * <dir> is an empty scratch directory the marker is created in. Output: one
 * "PASS <name>" or "FAIL <name>: why" per check, then "RESULT pass=N fail=M".
 */
#define _GNU_SOURCE
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* ---- captured log ------------------------------------------------------ */

static char logbuf[1 << 16];
static size_t loglen;

static void cap_log(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    loglen += vsnprintf(logbuf + loglen, sizeof(logbuf) - loglen, fmt, ap);
    va_end(ap);
    loglen += snprintf(logbuf + loglen, sizeof(logbuf) - loglen, "\n");
    if (loglen >= sizeof(logbuf)) {
        loglen = sizeof(logbuf) - 1;
    }
}

#define NV2A_PERFLOG_RT_LOG(...) cap_log(__VA_ARGS__)
#define NV2A_PERFLOG_RT_IMPLEMENTATION
#include "hw/xbox/nv2a/debug.h"

NV2AStats g_nv2a_stats;

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

static int count_lines(const char *needle)
{
    int n = 0;
    for (const char *p = logbuf; (p = strstr(p, needle)); p++) {
        n++;
    }
    return n;
}

static void spin_us(int us)
{
    struct timespec t0, t;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    do {
        clock_gettime(CLOCK_MONOTONIC, &t);
    } while ((t.tv_sec - t0.tv_sec) * 1000000L
             + (t.tv_nsec - t0.tv_nsec) / 1000 < us);
}

/* ---- the gated code, shaped as the call sites use it -------------------- */

/* A top-level phase with a nested finish, as draw_dispatch is. */
static void timed_draw(int work_us, int finish_us)
{
    NV2A_PHASE_TIMER_BEGIN_EXCL(draw_dispatch);
    spin_us(work_us);
    if (finish_us) {
        NV2A_PHASE_TIMER_BEGIN(finish);
        spin_us(finish_us);
        NV2A_PHASE_TIMER_END(finish);
    }
    nv2a_profile_inc_counter(NV2A_PROF_DRAW_ARRAYS);
    NV2A_PHASE_TIMER_END_EXCL(draw_dispatch);
}

/* Sfp around its texture binds, which are printed beside it as FTx. */
static void timed_sfp(int work_us, int ftx_us)
{
    NV2A_PHASE_TIMER_BEGIN_EXCL_CHILD(draw_sfp, draw_ftx);
    spin_us(work_us);
    {
        NV2A_PHASE_TIMER_BEGIN_EXCL(draw_ftx);
        spin_us(ftx_us);
        NV2A_PHASE_TIMER_END_EXCL(draw_ftx);
    }
    NV2A_PHASE_TIMER_END_EXCL_CHILD(draw_sfp, draw_ftx);
}

static void reset_working(void)
{
    memset(&g_nv2a_stats.phase_working, 0,
           sizeof(g_nv2a_stats.phase_working));
    memset(&g_nv2a_stats.frame_working, 0,
           sizeof(g_nv2a_stats.frame_working));
}

static int64_t booked_total(void)
{
    const FramePhaseTimingWork *w = &g_nv2a_stats.phase_working;
    return w->draw_dispatch_ns + w->finish_ns + w->draw_sfp_ns
           + w->draw_ftx_ns;
}

/* ---- modes -------------------------------------------------------------- */

static void run_marker(const char *dir)
{
    char marker[512];
    snprintf(marker, sizeof(marker), "%s/%s", dir, NV2A_PERFLOG_MARKER);
    unlink(marker);

    /* Off by default: nothing booked, nothing counted, no line. */
    reset_working();
    check(!nv2a_perflog_on(), "off.default_off",
          "nv2a_perflog_on() true before any poll");
    timed_draw(200, 100);
    timed_sfp(200, 100);
    check(booked_total() == 0, "off.books_nothing",
          "booked %lld ns with the switch off", (long long)booked_total());
    check(g_nv2a_stats.frame_working.counters[NV2A_PROF_DRAW_ARRAYS] == 0,
          "off.counts_nothing", "counter %d with the switch off",
          g_nv2a_stats.frame_working.counters[NV2A_PROF_DRAW_ARRAYS]);

    /* A poll with no marker changes nothing and says nothing. */
    nv2a_perflog_poll(dir);
    nv2a_perflog_poll(NULL);
    nv2a_perflog_poll("");
    check(!nv2a_perflog_on() && loglen == 0, "poll.no_marker_stays_off",
          "on=%d, log=\"%s\"", nv2a_perflog_on(), logbuf);

    /* The marker turns it on, with exactly one line naming the frame. */
    g_nv2a_stats.frame_count = 1234;
    FILE *fp = fopen(marker, "w");
    if (fp) {
        fclose(fp);
    }
    nv2a_perflog_poll(dir);
    check(nv2a_perflog_on(), "flip.marker_turns_on",
          "marker present, switch still off");
    check(count_lines("[perflog] runtime tier ON (frame 1234, by marker)")
          == 1, "flip.on_logs_once_with_frame", "log=\"%s\"", logbuf);
    nv2a_perflog_poll(dir);
    nv2a_perflog_poll(dir);
    check(count_lines("[perflog] runtime tier") == 1,
          "flip.no_line_without_a_flip", "log=\"%s\"", logbuf);

    /* ON: the gated code runs and books what it times. */
    reset_working();
    timed_draw(2000, 1000);
    const FramePhaseTimingWork *w = &g_nv2a_stats.phase_working;
    check(w->finish_ns >= 900000 && w->finish_ns < 50000000,
          "on.books_plain_phase", "finish_ns=%lld for a 1 ms finish",
          (long long)w->finish_ns);
    /* Exclusive: the 1 ms finish is in Fin, not in Draw. */
    check(w->draw_dispatch_ns >= 1800000
          && w->draw_dispatch_ns < w->finish_ns + 1800000,
          "on.excl_takes_out_nested_finish",
          "draw_dispatch_ns=%lld finish_ns=%lld for 2 ms + 1 ms",
          (long long)w->draw_dispatch_ns, (long long)w->finish_ns);
    check(g_nv2a_stats.frame_working.counters[NV2A_PROF_DRAW_ARRAYS] == 1,
          "on.counts", "counter %d after one timed draw",
          g_nv2a_stats.frame_working.counters[NV2A_PROF_DRAW_ARRAYS]);
    timed_sfp(2000, 1000);
    check(w->draw_ftx_ns >= 900000
          && w->draw_sfp_ns >= 1800000
          && w->draw_sfp_ns < w->draw_ftx_ns + 1800000,
          "on.excl_child_takes_out_child",
          "draw_sfp_ns=%lld draw_ftx_ns=%lld for 2 ms + 1 ms",
          (long long)w->draw_sfp_ns, (long long)w->draw_ftx_ns);

    /* A phase begun ON and ended OFF books itself whole; one begun OFF and
     * ended ON books nothing (END reads the phase's own t0). */
    reset_working();
    {
        NV2A_PHASE_TIMER_BEGIN(surface_update);
        spin_us(500);
        nv2a_perflog_set(false, "test");
        NV2A_PHASE_TIMER_END(surface_update);
    }
    check(g_nv2a_stats.phase_working.surface_update_ns >= 450000,
          "edge.begun_on_books_whole", "surface_update_ns=%lld",
          (long long)g_nv2a_stats.phase_working.surface_update_ns);
    {
        NV2A_PHASE_TIMER_BEGIN(texture_upload);
        nv2a_perflog_set(true, "test");
        spin_us(500);
        NV2A_PHASE_TIMER_END(texture_upload);
    }
    check(g_nv2a_stats.phase_working.texture_upload_ns == 0,
          "edge.begun_off_books_nothing", "texture_upload_ns=%lld",
          (long long)g_nv2a_stats.phase_working.texture_upload_ns);

    /* Marker gone: off again at the next poll, one OFF line. */
    unlink(marker);
    loglen = 0;
    logbuf[0] = '\0';
    g_nv2a_stats.frame_count = 2000;
    nv2a_perflog_poll(dir);
    check(!nv2a_perflog_on(), "flip.no_marker_turns_off",
          "marker removed, switch still on");
    check(count_lines("[perflog] runtime tier OFF (frame 2000, by marker)")
          == 1, "flip.off_logs_once_with_frame", "log=\"%s\"", logbuf);
    reset_working();
    timed_draw(200, 100);
    check(booked_total() == 0, "off.books_nothing_after_off",
          "booked %lld ns after OFF", (long long)booked_total());
}

static void run_env(const char *dir)
{
    /* selftest.py sets XEMU_PERFLOG_RT=1 and leaves no marker. */
    check(!nv2a_perflog_on(), "env.off_before_first_poll",
          "on before any poll");
    g_nv2a_stats.frame_count = 7;
    nv2a_perflog_poll(dir);
    check(nv2a_perflog_on(), "env.first_poll_turns_on",
          "XEMU_PERFLOG_RT=1, switch off after the first poll");
    check(count_lines("[perflog] runtime tier ON (frame 7, by env)") == 1,
          "env.logs_once", "log=\"%s\"", logbuf);
    nv2a_perflog_poll(dir);
    nv2a_perflog_poll(dir);
    check(nv2a_perflog_on() && count_lines("[perflog] runtime tier") == 1,
          "env.pins_on_without_marker", "on=%d log=\"%s\"",
          nv2a_perflog_on(), logbuf);
}

static void run_build(const char *dir)
{
    /* Compiled with -DNV2A_PERF_LOG=1: timers book with no poll at all,
     * and the poll says once that it has nothing to switch. */
    reset_working();
    timed_draw(1000, 0);
    check(nv2a_perflog_on() && g_nv2a_stats.phase_working.draw_dispatch_ns
          >= 900000, "build.times_without_switch", "on=%d draw=%lld",
          nv2a_perflog_on(),
          (long long)g_nv2a_stats.phase_working.draw_dispatch_ns);
    nv2a_perflog_poll(dir);
    nv2a_perflog_poll(dir);
    check(count_lines("[perflog] perflog build") == 1
          && count_lines("[perflog]") == 1,
          "build.says_inert_once", "log=\"%s\"", logbuf);
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: rt_selftest <dir> marker|env|build\n");
        return 2;
    }
    if (!strcmp(argv[2], "marker")) {
        run_marker(argv[1]);
    } else if (!strcmp(argv[2], "env")) {
        run_env(argv[1]);
    } else if (!strcmp(argv[2], "build")) {
        run_build(argv[1]);
    } else {
        return 2;
    }
    printf("RESULT pass=%d fail=%d\n", npass, nfail);
    return nfail ? 1 : 0;
}
