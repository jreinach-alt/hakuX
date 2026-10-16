#!/usr/bin/env python3
"""perflog1016 selftest (#433): the run-time perflog switch in debug.h.

    python3 docs/lanes/perflog1016/selftest.py [--cc cc] [--keep]

Builds rt_selftest.c against hw/xbox/nv2a/debug.h on the host and runs it
three ways: the marker switch (off by default, books nothing off, one line
per flip, the ON path reaching the timers and the counter), the env pin
(XEMU_PERFLOG_RT=1), and a perflog build (-DNV2A_PERF_LOG=1, unaffected).

Then it builds the same harness against MUTATED copies of the header, each
removing one mechanism, and requires the check named for that mechanism to
FAIL. A mutant that passes means the check cannot see the thing it is named
for, and the selftest fails.

Exit 0 only if every check passes on the real header and every mutant is
caught. Needs a C compiler; no QEMU tree build, no device.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
HDR = 'hw/xbox/nv2a/debug.h'

# debug.h takes qemu/timer.h off ARM64 only, for nv2a_clock_ns(); a host
# build gets this stand-in instead of the QEMU tree.
TIMER_STUB = r'''
#include <stdint.h>
#include <time.h>
#define QEMU_CLOCK_REALTIME 0
static inline int64_t qemu_clock_get_ns(int type)
{
    struct timespec t;
    (void)type;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000LL + t.tv_nsec;
}
'''

# (name, old, new, mode, the check that must FAIL)
MUTANTS = [
    ('switch reads as on by default',
     '__atomic_load_n(&g_nv2a_stats.perflog_rt, __ATOMIC_RELAXED) != 0, 0);',
     '__atomic_load_n(&g_nv2a_stats.perflog_rt, __ATOMIC_RELAXED) >= 0, 0);',
     'marker', 'off.default_off'),
    ('BEGIN reads the clock whatever the switch',
     'int64_t _phase_t0_##phase = nv2a_perflog_on() ? nv2a_clock_ns() : 0',
     'int64_t _phase_t0_##phase = nv2a_clock_ns()',
     'marker', 'off.books_nothing'),
    ('counter counts whatever the switch',
     '    if (nv2a_perflog_on()) {\n        g_nv2a_stats.frame_working',
     '    if (1) {\n        g_nv2a_stats.frame_working',
     'marker', 'off.counts_nothing'),
    ('a poll logs whether or not the state changed',
     '    if ((was != 0) == on) {\n        return;',
     '    if (0) {\n        return;',
     'marker', 'flip.no_line_without_a_flip'),
    ('the marker is not read',
     'want = n > 0 && (size_t)n < sizeof(path) && access(path, F_OK) == 0;',
     'want = false;',
     'marker', 'flip.marker_turns_on'),
    ('a vanished marker does not turn it off',
     '    nv2a_perflog_set(want, "marker");',
     '    if (want) {\n        nv2a_perflog_set(want, "marker");\n    }',
     'marker', 'flip.no_marker_turns_off'),
    ('END reads the switch instead of the phase t0',
     '#define NV2A_PHASE_TIMER_END(phase) do { \\\n'
     '    if (__builtin_expect(_phase_t0_##phase != 0, 0)) { \\',
     '#define NV2A_PHASE_TIMER_END(phase) do { \\\n'
     '    if (nv2a_perflog_on()) { \\',
     'marker', 'edge.begun_off_books_nothing'),
    ('EXCL keeps the nested finish',
     '        g_nv2a_stats.phase_working.phase##_ns += \\\n'
     '            nv2a_clock_ns() - _phase_t0_##phase - _nested; \\\n'
     '    } \\\n} while (0)\n\n#define NV2A_PHASE_TIMER_BEGIN_EXCL_CHILD',
     '        g_nv2a_stats.phase_working.phase##_ns += \\\n'
     '            nv2a_clock_ns() - _phase_t0_##phase - 0*_nested; \\\n'
     '    } \\\n} while (0)\n\n#define NV2A_PHASE_TIMER_BEGIN_EXCL_CHILD',
     'marker', 'on.excl_takes_out_nested_finish'),
    ('EXCL_CHILD keeps the child',
     '            - (g_nv2a_stats.phase_working.child##_ns - _phase_csnap_##phase); \\',
     '            - 0; \\',
     'marker', 'on.excl_child_takes_out_child'),
    ('the env does not pin it on',
     '    if (nv2a_perflog_rt.env_on) {\n        return;\n    }',
     '    if (0) {\n        return;\n    }',
     'env', 'env.pins_on_without_marker'),
    ('the env is not read',
     'nv2a_perflog_rt.env_on = env && env[0] && strcmp(env, "0");',
     'nv2a_perflog_rt.env_on = false;',
     'env', 'env.first_poll_turns_on'),
]


def build(cc, tmp, hdr_text, tag, perf_log, werror=True):
    """Compile the harness against `hdr_text` as hw/xbox/nv2a/debug.h.
    The real header builds with -Werror; a mutant leaves variables unused by
    construction, so it builds without."""
    inc = os.path.join(tmp, 'inc-' + tag)
    os.makedirs(os.path.join(inc, 'hw', 'xbox', 'nv2a'), exist_ok=True)
    os.makedirs(os.path.join(inc, 'qemu'), exist_ok=True)
    with open(os.path.join(inc, HDR), 'w') as f:
        f.write(hdr_text)
    with open(os.path.join(inc, 'qemu', 'timer.h'), 'w') as f:
        f.write(TIMER_STUB)
    exe = os.path.join(tmp, 'rt_selftest-' + tag)
    cmd = [cc, '-std=gnu11', '-O1', '-Wall'] + (['-Werror'] if werror else []) + [
           '-Wno-unused-function', '-I', inc,
           '-DNV2A_PERF_LOG=%d' % perf_log,
           os.path.join(HERE, 'rt_selftest.c'), '-o', exe]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        return None, r.stderr
    return exe, ''


def run(exe, tmp, mode):
    d = tempfile.mkdtemp(prefix='marker-', dir=tmp)
    env = dict(os.environ)
    env.pop('XEMU_PERFLOG_RT', None)
    if mode == 'env':
        env['XEMU_PERFLOG_RT'] = '1'
    r = subprocess.run([exe, d, mode], capture_output=True, text=True,
                       env=env, timeout=60)
    return r.returncode, r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    ap.add_argument('--keep', action='store_true')
    a = ap.parse_args()

    real = open(os.path.join(ROOT, HDR)).read()
    tmp = tempfile.mkdtemp(prefix='perflog1016-selftest-')
    ok = True
    try:
        for mode, perf_log in (('marker', 0), ('env', 0), ('build', 1)):
            exe, err = build(a.cc, tmp, real, 'real%d' % perf_log, perf_log)
            if not exe:
                print('FAIL build (NV2A_PERF_LOG=%d):\n%s' % (perf_log, err))
                return 1
            rc, out = run(exe, tmp, mode)
            sys.stdout.write(out)
            if rc or 'RESULT' not in out:
                ok = False

        caught = 0
        for name, old, new, mode, must_fail in MUTANTS:
            n = real.count(old)
            if n != 1:
                print('MUTANT %r: pattern found %d times, not once' % (name, n))
                ok = False
                continue
            exe, err = build(a.cc, tmp, real.replace(old, new), 'mut', 0,
                             werror=False)
            if not exe:
                print('MUTANT %r: did not build:\n%s' % (name, err))
                ok = False
                continue
            rc, out = run(exe, tmp, mode)
            if ('FAIL %s:' % must_fail) in out:
                caught += 1
                print('CAUGHT %s -> FAIL %s' % (name, must_fail))
            else:
                ok = False
                print('MISSED %s: %s did not fail\n%s' % (name, must_fail, out))
        print('MUTANTS caught=%d of %d' % (caught, len(MUTANTS)))
    finally:
        if a.keep:
            print('kept', tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print('SELFTEST', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
