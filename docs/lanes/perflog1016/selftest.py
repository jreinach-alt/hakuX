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

Last, PauseMenuOverlay.kt, which has no host build: its contract with the
emulator and with the readers is a set of names that must agree across files
(the marker, the env pin, the log tags and the logcat spec that keeps them,
the mark line the route driver and hitch_report read, the literal labels, the
launch-time clear). Each static check reads both sides from source, and each
has a mutant of one side, applied in memory, that it must catch. The toggle's
own logic (createNewFile/delete) needs a device; these checks do not reach it.

Exit 0 only if every check passes on the real sources and every mutant is
caught. Needs a C compiler; no QEMU tree build, no device.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
HDR = 'hw/xbox/nv2a/debug.h'

# The static checks' sources, by side. Read only; mutants edit the text in
# memory.
SIDES = {
    'kt': 'android/app/src/main/java/com/rfandango/haku_x/PauseMenuOverlay.kt',
    'main': 'android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt',
    'hdr': HDR,
    'renderer': 'hw/xbox/nv2a/pgraph/vk/renderer.c',
    'spec': 'docs/testing/dispatcher.sh',
    'hitch': 'docs/testing/hitch_report.py',
    'route': 'docs/testing/titles/route.sh',
    'gradle': 'android/app/build.gradle.kts',
    'stamp': 'docs/testing/version_stamp.sh',
}

LABELS = ('Perflog: OFF', 'Perflog: ON', 'Mark this moment',
          'Frame dump (30 frames)')

# logcat priorities, lowest first; a line passes a filter tag:L if its own
# priority is L or above.
PRIO = 'VDIWEFS'

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


def one(pat, text):
    """The single match of `pat` (its first group), or None if it matches
    zero times or more than once: an ambiguous source is a failed check."""
    m = re.findall(pat, text)
    return m[0] if len(m) == 1 else None


def span(text, start, end_pat):
    """`text` from the first `start` to the next match of `end_pat`."""
    i = text.find(start)
    if i < 0:
        return ''
    m = re.compile(end_pat).search(text, i + len(start))
    return text[i:m.start() if m else len(text)]


def logcat_spec(spec_sh):
    """dispatcher.sh's default LOGCAT_SPEC as {tag: priority}."""
    s = one(r'LOGCAT_SPEC="\$\{LOGCAT_SPEC_OVERRIDE:-([^}]*)\}"', spec_sh)
    if s is None:
        return {}
    return dict(t.rsplit(':', 1) for t in s.split() if ':' in t)


def kept(spec, tag, prio):
    """Whether a line on `tag` at `prio` survives the dispatcher's filter."""
    want = spec.get(tag, spec.get('*'))
    return want is not None and PRIO.index(prio) >= PRIO.index(want)


def kt_checks(src):
    """[(name, ok, detail)] for the pause menu's cross-file contract."""
    kt, hdr = src['kt'], src['hdr']
    out = []

    def check(name, ok, detail):
        out.append((name, bool(ok), detail))

    a = one(r'perflogMarker\(\): java\.io\.File\? = markerFile\("([^"]+)"\)', kt)
    b = one(r'#define NV2A_PERFLOG_MARKER "([^"]+)"', hdr)
    check('kt.marker_matches_header', a and a == b,
          'kt %r, debug.h NV2A_PERFLOG_MARKER %r' % (a, b))

    a = one(r'val env = System\.getenv\("([^"]+)"\)', kt)
    b = one(r'getenv\("(XEMU_PERFLOG[A-Z_]*)"\)', hdr)
    check('kt.env_pin_matches_header', a and a == b,
          'kt %r, debug.h %r' % (a, b))

    a = one(r'const val PERF_TAG = "([^"]+)"', kt)
    b = one(r'#define NV2A_PERFLOG_RT_LOG\(\.\.\.\) \\\n\s*'
            r'__android_log_print\(ANDROID_LOG_INFO, "([^"]+)"', hdr)
    check('kt.perf_tag_matches_header', a and a == b,
          'kt PERF_TAG %r, debug.h NV2A_PERFLOG_RT_LOG %r' % (a, b))

    # Every [perflog] line either side writes, and the mark, must survive the
    # dispatcher's logcat filter, or the capture the switch exists for is cut.
    spec = logcat_spec(src['spec'])
    tags = {'PERF_TAG': a}
    lines = []
    for lv, tag, msg in re.findall(
            r'Log\.([vdiwe])\((PERF_TAG|"[^"]+"), "(\[perflog\][^"]*|mark [^"]*)"', kt):
        lines.append((tags.get(tag, tag.strip('"')), lv.upper(), msg))
    if b:
        lines.append((b, 'I', '[perflog] runtime tier (debug.h)'))
    lost = [l for l in lines if not l[0] or not kept(spec, l[0], l[1])]
    check('kt.lines_kept_by_logcat_spec', spec and len(lines) >= 4 and not lost,
          '%d lines, lost %s' % (len(lines), lost))

    m = re.findall(r'Log\.([vdiwe])\("([^"]+)", "(mark [^"]*)"\)', kt)
    m = m[0] if len(m) == 1 else None
    drv = one(r'log -t (\S+) "\'mark \$1\'"', src['route'])
    rdr = one(r'tag == "([^"]+)" and msg\.startswith\("mark "\)', src['hitch'])
    label = m[2][len('mark '):] if m else ''
    check('kt.mark_line_shape',
          m and m[0] == 'i' and m[1] == drv == rdr
          and re.match(r'owner-\$\w+$', label)
          and label not in ('gameplay', 'play'),
          'kt %r, route driver tag %r, hitch_report tag %r' % (m, drv, rdr))

    body = span(kt, 'private fun createPerflogButton', r'\n    private fun createMenuButton')
    missing = [l for l in LABELS if '"%s"' % l not in kt]
    check('kt.labels_literal', body and not missing and 'R.string' not in body
          and 'getString(' not in body,
          'missing %s; resource lookups in the buttons: %s'
          % (missing, 'R.string' in body or 'getString(' in body))

    init = span(kt, '\n    init {', r'\n    fun ')
    clr = re.search(r'val (\w+) = perflogMarker\(\)\n\s*'
                    r'if \(\1 != null && \1\.exists\(\) && \1\.delete\(\)\)', init)
    on_create = span(src['main'], 'override fun onCreate(', r'\n  (private |override )?fun ')
    setup = span(src['main'], 'private fun setupPauseMenu()', r'\n  (private |override )?fun ')
    check('kt.launch_clears_marker',
          clr and 'setupPauseMenu()' in on_create and 'PauseMenuOverlay(' in setup,
          'clear in init: %s; built from onCreate: %s'
          % (bool(clr), 'setupPauseMenu()' in on_create and 'PauseMenuOverlay(' in setup))

    a = one(r'markerFile\("(frame_dump[^"]*)"\)', kt)
    b = one(r'#define FDUMP_MARKER_NAME\s+"([^"]+)"', src['renderer'])
    check('kt.frame_dump_marker_matches_renderer', a and a == b,
          'kt %r, renderer.c FDUMP_MARKER_NAME %r' % (a, b))

    a = one(r'version\.contains\("([^"]+)"\)', kt)
    v = one(r'hasProperty\("perflog"\)\) "(\w+)"', src['gradle'])
    s = one(r'\*\) VER="\$VER(-)\$VARIANT" ;;', src['stamp'])
    check('kt.perflog_build_suffix_matches_stamp', a and v and s and a == s + v,
          'kt %r, gradle variant %r, version_stamp.sh joins with %r' % (a, v, s))
    return out


# (name, side, old, new, the check that must FAIL)
KT_MUTANTS = [
    ('kt names another marker', 'kt',
     'markerFile("perflog.on")', 'markerFile("perflog_on")',
     'kt.marker_matches_header'),
    ('debug.h names another marker', 'hdr',
     '#define NV2A_PERFLOG_MARKER "perflog.on"', '#define NV2A_PERFLOG_MARKER "perflog"',
     'kt.marker_matches_header'),
    ('kt reads another env', 'kt',
     'System.getenv("XEMU_PERFLOG_RT")', 'System.getenv("XEMU_PERFLOG")',
     'kt.env_pin_matches_header'),
    ('kt logs on another tag', 'kt',
     'const val PERF_TAG = "hakuX-perf"', 'const val PERF_TAG = "hakuX-perflog"',
     'kt.perf_tag_matches_header'),
    ('the logcat spec drops hakuX-perf', 'spec',
     ' hakuX-perf:I ', ' hakuX-perf:W ',
     'kt.lines_kept_by_logcat_spec'),
    ('the mark logs at debug', 'kt',
     'Log.i("hakuX-route", "mark owner-$marks")', 'Log.d("hakuX-route", "mark owner-$marks")',
     'kt.mark_line_shape'),
    ('the mark logs on another tag', 'kt',
     'Log.i("hakuX-route", "mark owner-$marks")', 'Log.i("hakuX-mark", "mark owner-$marks")',
     'kt.mark_line_shape'),
    ('the mark takes a scored label', 'kt',
     'Log.i("hakuX-route", "mark owner-$marks")', 'Log.i("hakuX-route", "mark gameplay")',
     'kt.mark_line_shape'),
    ('a label changes', 'kt',
     '"Perflog: OFF"', '"Perflog off"',
     'kt.labels_literal'),
    ('a label comes from a resource', 'kt',
     'createMenuButton(context, "Mark this moment")',
     'createMenuButton(context, context.getString(R.string.mark_moment))',
     'kt.labels_literal'),
    ('launch keeps the marker', 'kt',
     'stale.exists() && stale.delete()', 'stale.exists() && false',
     'kt.launch_clears_marker'),
    ('the overlay is built after onCreate', 'main',
     '    setupPauseMenu()\n', '\n',
     'kt.launch_clears_marker'),
    ('kt arms another frame-dump marker', 'kt',
     'markerFile("frame_dump.on")', 'markerFile("framedump.on")',
     'kt.frame_dump_marker_matches_renderer'),
    ('kt looks for another build suffix', 'kt',
     'version.contains("-perflog")', 'version.contains("perflog-")',
     'kt.perflog_build_suffix_matches_stamp'),
]


def run_kt(src):
    """Run the static checks on `src`; print each; True if all pass."""
    ok = True
    for name, good, detail in kt_checks(src):
        print('%s %s: %s' % ('ok  ' if good else 'FAIL', name, detail))
        ok = ok and good
    return ok


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

        src = {k: open(os.path.join(ROOT, p)).read() for k, p in SIDES.items()}
        if not run_kt(src):
            ok = False
        caught = 0
        for name, side, old, new, must_fail in KT_MUTANTS:
            n = src[side].count(old)
            if n != 1:
                print('KT MUTANT %r: pattern found %d times in %s, not once'
                      % (name, n, SIDES[side]))
                ok = False
                continue
            mut = dict(src)
            mut[side] = src[side].replace(old, new)
            res = {c: good for c, good, _ in kt_checks(mut)}
            if res.get(must_fail) is False:
                caught += 1
                print('CAUGHT %s -> FAIL %s' % (name, must_fail))
            else:
                ok = False
                print('MISSED %s: %s did not fail' % (name, must_fail))
        print('KT MUTANTS caught=%d of %d' % (caught, len(KT_MUTANTS)))
    finally:
        if a.keep:
            print('kept', tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print('SELFTEST', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
