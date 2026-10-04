#!/usr/bin/env python3
"""renderer.c's gpu_ts_calibrate, run on the host against simulated counters.

    python3 caltest.py [--keep]

The function's text is cut out of hw/xbox/nv2a/pgraph/vk/renderer.c (from
`#define GPU_TS_CAL_SPAN_NS` to the end of gpu_ts_calibrate) and compiled
with stubs for the Vulkan calls and the clock, so what runs is the shipped
arithmetic and not a model of it. Each world is a counter behaviour and the
period the function must end up using:

  free-running   19.2 MHz whatever the GPU does, driver reports 33.11 ns
                 -> 52.083 measured
  honest driver  the same counter, driver reports 52.083 -> reported kept
  gated          the counter runs only while the GPU works and for 50 us
                 after -> reported kept, "idle gaps"
  napping        the counter stops 5 ms into any idle stretch; back-to-back
                 samples never reach it -> 52.083 measured
  reset          the counter restarts from 0 halfway -> reported kept
  preempted      one sample in nine takes 3 ms more -> 52.083 measured
  first cut      (a mutant, not a world) the sampling replaced by the first
                 cut's: eight samples, one 100 ms sleep, eight samples. In
                 the gated and napping worlds its slope must come out in the
                 hundreds or thousands of ns, as the Thor's 4636 did, and the
                 checks must refuse it. A slope near 52 here would mean the
                 worlds do not contain the idle stretch they claim to.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '../../../hw/xbox/nv2a/pgraph/vk/renderer.c')

STUBS = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NV2A_PERF_LOG 1
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define g_new(T, n) ((T *)malloc(sizeof(T) * (n)))
#define g_free free
#define VK_SUCCESS 0
#define VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO 0
#define VK_QUERY_TYPE_TIMESTAMP 0
#define VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT 0
#define VK_QUERY_RESULT_64_BIT 0
typedef int VkQueryPool;
typedef int VkCommandBuffer;
typedef struct { int sType, queryType, queryCount; } VkQueryPoolCreateInfo;
typedef struct {
    struct { struct { float timestampPeriod; } limits; } device_props;
    float gpu_ts_period_ns;
    int device;
} PGRAPHVkState;
typedef struct { PGRAPHVkState *vk_renderer_state; } PGRAPHState;

static char g_line[512];
#define VK_LOG_ERROR(...) snprintf(g_line, sizeof(g_line), __VA_ARGS__)

/* The simulated machine. Times are ns. */
enum { FREE, GATED, NAPPING, RESET, PREEMPT };
static int g_world;
static int64_t g_now = 1000000000LL;      /* CPU clock */
static double g_ticks;                    /* the GPU's counter */
static int64_t g_busy_until;              /* the GPU works until here */
static int64_t g_counted_to;              /* counter advanced up to here */
static uint64_t g_last_tick;
static unsigned g_seed = 12345, g_nsample;
static bool g_reset_done;
#define TICK_NS (1e9 / 19.2e6)

static unsigned rnd(void)
{
    g_seed = g_seed * 1103515245u + 12345u;
    return (g_seed >> 8) & 0xffffff;
}

/* Advance the counter from g_counted_to to t, by the world's rule. */
static void count_to(int64_t t)
{
    int64_t run_to = t;
    if (g_world == GATED) {
        run_to = MIN(t, g_busy_until + 50000);
    } else if (g_world == NAPPING) {
        run_to = MIN(t, g_busy_until + 5000000);
    }
    if (run_to > g_counted_to) {
        g_ticks += (double)(run_to - g_counted_to) / TICK_NS;
    }
    g_counted_to = t;
}

static int64_t get_clock(void) { g_now += 200; return g_now; }
static void g_usleep(unsigned us) { g_now += (int64_t)us * 1000 + 60000; }
static int vkCreateQueryPool(int d, void *ci, void *a, VkQueryPool *p)
{ (void)d; (void)ci; (void)a; *p = 1; return VK_SUCCESS; }
static void vkDestroyQueryPool(int d, VkQueryPool p, void *a)
{ (void)d; (void)p; (void)a; }
static void vkCmdResetQueryPool(int c, VkQueryPool p, int a, int b)
{ (void)c; (void)p; (void)a; (void)b; }
static void vkCmdWriteTimestamp(int c, int s, VkQueryPool p, int q)
{ (void)c; (void)s; (void)p; (void)q; }
static VkCommandBuffer pgraph_vk_begin_single_time_commands(PGRAPHState *pg)
{ (void)pg; g_now += 20000; return 1; }

/* Submit, the GPU wakes and works, the fence is seen. */
static void pgraph_vk_end_single_time_commands(PGRAPHState *pg, int cmd)
{
    (void)pg; (void)cmd;
    int64_t submit = g_now;
    int64_t work = 60000 + rnd() % 40000;
    int64_t lat = 20000 + rnd() % 30000;
    if (g_world == PREEMPT && (++g_nsample % 9) == 0) {
        lat += 3000000;
    }
    int64_t at = submit + lat / 2 + rnd() % (work / 2);
    count_to(submit + lat / 2);           /* idle until the GPU starts */
    g_busy_until = submit + lat / 2 + work;
    count_to(at);                         /* the timestamp is written */
    if (g_world == RESET && !g_reset_done && g_ticks > 1.1e6) {
        g_ticks = 100.0;
        g_reset_done = true;
    }
    g_last_tick = (uint64_t)g_ticks;
    count_to(g_busy_until);
    g_now = submit + lat + work;
}

static int vkGetQueryPoolResults(int d, VkQueryPool p, int a, int b,
                                 size_t sz, void *out, size_t st, int fl)
{
    (void)d; (void)p; (void)a; (void)b; (void)sz; (void)st; (void)fl;
    memcpy(out, &g_last_tick, sizeof(g_last_tick));
    return VK_SUCCESS;
}
'''

MAIN = r'''
int main(int argc, char **argv)
{
    PGRAPHVkState r = {0};
    PGRAPHState pg = { &r };
    g_world = atoi(argv[1]);
    r.device_props.limits.timestampPeriod = (float)atof(argv[2]);
    (void)argc;
    g_counted_to = g_now;
    gpu_ts_calibrate(&pg);
    printf("%.3f|%s\n", r.gpu_ts_period_ns, g_line);
    return 0;
}
'''

# world, reported, the period that must be used, a phrase the line must carry
CASES = [
    ('free-running', 0, 33.113, 52.083, '(measured)'),
    ('honest driver', 0, 52.083, 52.083, '(reported)'),
    ('gated', 1, 33.113, 33.113, 'idle gaps'),
    ('napping', 2, 33.113, 52.083, '(measured)'),
    ('reset', 3, 33.113, 33.113, 'went back'),
    ('preempted', 4, 33.113, 52.083, '(measured)'),
]


def cut(src):
    a = src.index('#define GPU_TS_CAL_SPAN_NS')
    m = re.search(r'^static void gpu_ts_calibrate\(', src, re.M)
    b = src.index('\n}\n', m.start()) + 3
    return src[a:b]


def first_cut(body):
    """The mutant: no sample between the first and the last 8, one sleep."""
    loop = re.search(r'    while \(n < GPU_TS_CAL_MAX_SAMPLES\) \{\n.*?\n    \}\n',
                     body, re.S)
    assert loop, 'sampling loop not found'
    old = loop.group(0)
    new = old.replace(
        '        if (elapsed >= GPU_TS_CAL_SPAN_NS) {\n            break;\n        }\n',
        '        if (n >= 16) {\n            break;\n        }\n'
        '        if (n == 8) {\n            g_usleep(100000);\n        }\n')
    new = new.replace('bool gapped = elapsed >= GPU_TS_CAL_SPAN_NS / 2;',
                      'bool gapped = false; if (n == 8) { split = 8; } '
                      '(void)elapsed;')
    assert new != old
    return body.replace(old, new)


def build(body, d, name):
    c = os.path.join(d, name + '.c')
    exe = os.path.join(d, name)
    open(c, 'w').write(STUBS + body + MAIN)
    r = subprocess.run(['gcc', '-O1', '-Wall', '-Wno-unused-function', '-o',
                        exe, c, '-lm'], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr)
        sys.exit('caltest: the cut-out function did not compile')
    return exe


def run(exe, world, reported):
    out = subprocess.run([exe, str(world), str(reported)], capture_output=True,
                         text=True).stdout.strip()
    used, line = out.split('|', 1)
    return float(used), line


def main():
    keep = '--keep' in sys.argv
    body = cut(open(SRC).read())
    d = tempfile.mkdtemp(prefix='caltest-')
    exe = build(body, d, 'cal')
    bad = 0
    for name, world, reported, want, phrase in CASES:
        used, line = run(exe, world, reported)
        ok = abs(used / want - 1.0) < 0.01 and phrase in line
        bad += not ok
        print('%-14s %s using=%.3f want=%.3f | %s'
              % (name, 'ok  ' if ok else 'FAIL', used, want,
                 line[line.index('measured='):]))
    mut = build(first_cut(body), d, 'firstcut')
    for name, world in (('gated', 1), ('napping', 2)):
        used, line = run(mut, world, 33.113)
        slope = float(re.search(r'measured=([0-9.]+)', line).group(1))
        ok = slope > 500.0 and abs(used - 33.113) < 0.01 and \
            'not measured' in line
        bad += not ok
        print('first cut, %-8s %s slope=%.0f using=%.3f | %s'
              % (name, 'ok  ' if ok else 'FAIL', slope, used,
                 line[line.index('(+-'):]))
    # The second mutant: the idle gap taken out of the second half. The gated
    # world must then be ACCEPTED with a wrong period, which shows the gap is
    # the check that refuses it and not the scatter or the ticks' order.
    nogap = body.replace('        if (gapped) {\n            g_usleep('
                         'GPU_TS_CAL_GAP_US);\n        }\n', '')
    assert nogap != body, 'the gap was not found'
    used, line = run(build(nogap, d, 'nogap'), 1, 33.113)
    ok = '(measured)' in line and abs(used / 52.083 - 1.0) > 0.02
    bad += not ok
    print('no gap, gated      %s using=%.3f | %s'
          % ('ok  ' if ok else 'FAIL', used, line[line.index('(+-'):]))
    if not keep:
        subprocess.run(['rm', '-rf', d])
    print('caltest %s' % ('FAIL' if bad else 'ok: 6 worlds, 2 mutants'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
