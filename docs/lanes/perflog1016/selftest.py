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

The wiring checks do the same for the three files the lend granted:
profile.c defines the implementation before its first include and prints its
block only while the switch is on; renderer.c polls once, after the
once-a-second limit and before the dump's early returns; pfifo.c reads the
switch once per puller call and per pusher pass and reads no clock outside
it. A link error or a clock read the switch does not gate would otherwise
show only on a device. Last, the A/B reader (abread.py) against synthetic
result dirs: each fixture must give its named verdict.

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
    'profile': 'hw/xbox/nv2a/pgraph/profile.c',
    'pfifo': 'hw/xbox/nv2a/pfifo.c',
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


def gated(body, pos, flag):
    """Whether offset `pos` in `body` sits inside an `if (<flag>) {` block:
    the last such opener before it has more `{` than `}` up to `pos`."""
    i = body.rfind('if (%s) {' % flag, 0, pos)
    if i < 0:
        return False
    seg = body[i:pos]
    return seg.count('{') > seg.count('}')


def clock_reads_ungated(body, flag):
    """The lines in `body` that read nv2a_clock_ns() neither as
    `<flag> ? nv2a_clock_ns()` nor inside an `if (<flag>) {` block."""
    bad = []
    for m in re.finditer(r'nv2a_clock_ns\(\)', body):
        ls = body.rfind('\n', 0, m.start()) + 1
        le = body.find('\n', m.start())
        line = body[ls:le]
        if '%s ? nv2a_clock_ns()' % flag in line or gated(body, m.start(), flag):
            continue
        bad.append(line.strip())
    return bad


def wire_checks(src):
    """[(name, ok, detail)] for the three files the lend granted: the
    implementation, the poll, the print block, and pfifo's timers."""
    prof, rend, pf = src['profile'], src['renderer'], src['pfifo']
    out = []

    def check(name, ok, detail):
        out.append((name, bool(ok), detail))

    # nv2a_perflog_set()/_poll() compile only where the define precedes the
    # first include that reaches debug.h: after it, the bodies are skipped
    # and the poll is an undefined symbol at link time, which a compile-only
    # NDK check does not see.
    d = prof.find('#define NV2A_PERFLOG_RT_IMPLEMENTATION\n')
    inc = prof.find('#include ')
    check('wire.profile_defines_impl_before_includes',
          prof.count('#define NV2A_PERFLOG_RT_IMPLEMENTATION') == 1
          and 0 <= d < inc,
          'define at %d, first #include at %d' % (d, inc))

    # The one poll: inside fdump_poll_marker, after its once-a-second limit
    # (access() is a syscall), before the dump's own early returns (a dump in
    # progress must not hold the switch), and the function called at the flip.
    body = span(rend, 'static void fdump_poll_marker(NV2AState *d)\n{', r'\n}\n')
    lim = body.find('fdump.next_poll_ns = now + FDUMP_POLL_NS;')
    pol = body.find('nv2a_perflog_poll(fdump_base_dir());')
    ret = body.find('if (fdump.fp) {')
    calls = len(re.findall(r'\n\s+fdump_poll_marker\(d\);', rend))
    check('wire.renderer_polls_once_after_the_limit',
          rend.count('nv2a_perflog_poll(') == 1 and 0 <= lim < pol < ret
          and calls == 1,
          'polls in renderer.c %d; in fdump_poll_marker: limit %d, poll %d, '
          'dump return %d; fdump_poll_marker(d) calls %d'
          % (rend.count('nv2a_perflog_poll('), lim, pol, ret, calls))

    # The print block: a plain build prints it only while the switch is on.
    i = prof.find('"hakuX-phase", "%s"')
    pre = prof[:i] if i >= 0 else ''
    hif = pre[pre.rfind('#if'):].split('\n', 1)[0] if '#if' in pre else ''
    cif = pre[pre.rfind('\n    if ('):].split('\n')[1] if '\n    if (' in pre else ''
    check('wire.profile_prints_only_while_on',
          i >= 0 and hif == '#if defined(__ANDROID__)'
          and 'nv2a_perflog_on() &&' in cif,
          'guard %r, condition %r' % (hif, cif.strip()))

    # The four accumulators the switch books into reach the printed stats,
    # and the line has the perflog build's shape for the same readers.
    snap = span(prof, 'static void snapshot_phase_timing(void)', r'\n}\n')
    check('wire.profile_smooths_and_prints_fast_fields',
          'SMOOTH(draw_sfp);' in snap and 'SMOOTH(tex_hash);' in snap
          and '#if NV2A_PERF_LOG' not in snap
          and prof.count('#define PHASE_FAST_FMT " Sfp:%.1f Mfp:%.1f FTx:%.1f"') == 1
          and prof.count('#define PHASE_TXH_FMT " TxH:%.1f"') == 1
          and '#define PHASE_FAST_FMT ""' not in prof,
          'smoothed: %s; build-gated in snapshot: %s; formats unconditional: %s'
          % ('SMOOTH(draw_sfp);' in snap, '#if NV2A_PERF_LOG' in snap,
             '#define PHASE_FAST_FMT ""' not in prof))

    # pfifo: the puller reads the switch once per call (one load beside
    # pfifo_puller_should_stall's atomics) and every clock read follows it;
    # the pusher pass likewise; no build flag left on either path.
    pull = span(pf, 'static ssize_t pfifo_run_puller(', r'\n}\n')
    bad = clock_reads_ungated(pull, 'pl')
    check('wire.pfifo_puller_times_only_while_on',
          pull.count('const bool pl = nv2a_perflog_on();') == 1
          and pull.count('nv2a_perflog_on()') == 1
          and 'NV2A_PERF_LOG' not in pull and not bad
          and pull.count('nv2a_clock_ns()') >= 8,
          'switch reads %d; build flag %s; clock reads %d, ungated %s'
          % (pull.count('nv2a_perflog_on()'), 'NV2A_PERF_LOG' in pull,
             pull.count('nv2a_clock_ns()'), bad))

    thr = span(pf, 'void *pfifo_thread(void *arg)', r'\n}\n')
    push = span(thr, 'const bool pl = nv2a_perflog_on();', r'pfifo_run_pusher\(d\);')
    idle = span(thr, 'if (nv2a_perflog_on()) {', r'\n            }\n')
    check('wire.pfifo_pusher_and_idle_follow_the_switch',
          thr.count('const bool pl = nv2a_perflog_on();') == 1
          and 'pl ? nv2a_clock_ns() : 0' in push
          and 'phase_working.fifo_idle_ns' in idle
          and 'NV2A_PERF_LOG' not in thr,
          'pusher read %d; push t0 gated %s; idle split gated %s; build flag %s'
          % (thr.count('const bool pl = nv2a_perflog_on();'),
             'pl ? nv2a_clock_ns() : 0' in push,
             'phase_working.fifo_idle_ns' in idle, 'NV2A_PERF_LOG' in thr))
    return out


# (name, side, [(old, new), ...], the check that must FAIL)
WIRE_MUTANTS = [
    ('the implementation is defined after the first include', 'profile',
     [('#define NV2A_PERFLOG_RT_IMPLEMENTATION\n#include "hw/xbox/nv2a/nv2a_int.h"\n',
       '#include "hw/xbox/nv2a/nv2a_int.h"\n#define NV2A_PERFLOG_RT_IMPLEMENTATION\n')],
     'wire.profile_defines_impl_before_includes'),
    ('nothing polls', 'renderer',
     [('    nv2a_perflog_poll(fdump_base_dir());\n', '')],
     'wire.renderer_polls_once_after_the_limit'),
    ('the poll runs before the once-a-second limit', 'renderer',
     [('    nv2a_perflog_poll(fdump_base_dir());\n', ''),
      ('    int64_t now = qemu_clock_get_ns(QEMU_CLOCK_REALTIME);\n'
       '    if (now < fdump.next_poll_ns) {',
       '    int64_t now = qemu_clock_get_ns(QEMU_CLOCK_REALTIME);\n'
       '    nv2a_perflog_poll(fdump_base_dir());\n'
       '    if (now < fdump.next_poll_ns) {')],
     'wire.renderer_polls_once_after_the_limit'),
    ('a dump in progress holds the switch', 'renderer',
     [('    nv2a_perflog_poll(fdump_base_dir());\n', ''),
      ('        return; /* a dump in progress does not consume a new arm */\n    }\n',
       '        return; /* a dump in progress does not consume a new arm */\n    }\n'
       '    nv2a_perflog_poll(fdump_base_dir());\n')],
     'wire.renderer_polls_once_after_the_limit'),
    ('the print block ignores the switch', 'profile',
     [('if (nv2a_perflog_on() && (g_nv2a_stats.frame_count % 60) == 0) {',
       'if ((g_nv2a_stats.frame_count % 60) == 0) {')],
     'wire.profile_prints_only_while_on'),
    ('the print block is back under the build flag', 'profile',
     [('#if defined(__ANDROID__)\n    /* A perflog build',
       '#if defined(__ANDROID__) && NV2A_PERF_LOG\n    /* A perflog build')],
     'wire.profile_prints_only_while_on'),
    ('the fast fields are smoothed only in a perflog build', 'profile',
     [('    SMOOTH(draw_sfp);\n', '#if NV2A_PERF_LOG\n    SMOOTH(draw_sfp);\n')],
     'wire.profile_smooths_and_prints_fast_fields'),
    ('the puller reads the clock whatever the switch', 'pfifo',
     [('int64_t _puller_t0 = pl ? nv2a_clock_ns() : 0;',
       'int64_t _puller_t0 = nv2a_clock_ns();')],
     'wire.pfifo_puller_times_only_while_on'),
    ('the puller total books whatever the switch', 'pfifo',
     [('    if (pl) {\n        g_nv2a_stats.cpu_working.puller_total_ns',
       '    {\n        g_nv2a_stats.cpu_working.puller_total_ns')],
     'wire.pfifo_puller_times_only_while_on'),
    ('the puller is back under the build flag', 'pfifo',
     [('const bool pl = nv2a_perflog_on();\n    int64_t _puller_t0',
       'const bool pl = NV2A_PERF_LOG;\n    int64_t _puller_t0')],
     'wire.pfifo_puller_times_only_while_on'),
    ('the idle split is back under the build flag', 'pfifo',
     [('if (nv2a_perflog_on()) {\n                int64_t idle_ns',
       'if (NV2A_PERF_LOG) {\n                int64_t idle_ns')],
     'wire.pfifo_pusher_and_idle_follow_the_switch'),
]


def apply_edits(text, edits):
    """`text` with each (old, new) replaced once; None if an old is not
    found exactly once (an ambiguous mutant is a failed selftest)."""
    for old, new in edits:
        if text.count(old) != 1:
            return None
        text = text.replace(old, new)
    return text


def run_kt(src):
    """Run the static checks on `src`; print each; True if all pass."""
    ok = True
    for name, good, detail in kt_checks(src) + wire_checks(src):
        print('%s %s: %s' % ('ok  ' if good else 'FAIL', name, detail))
        ok = ok and good
    return ok


def fixture(d, tcpu, gfps=29, ri=23.5, cache='cleared', extra=(), on=False,
            tier='env'):
    """A synthetic dispatcher result dir: [rdc] and hakuX-perf lines every
    2 s for 200 s after `mark gameplay` (80 in the 20..180 window), the
    render thread at `tcpu` ms/s. `on` adds the ON path's lines after a
    tier line by `tier` (None: no tier line). `extra` lines go in as-is."""
    os.makedirs(d)
    lines = []
    if on and tier:
        lines.append('10-18 12:00:01.000 I/hakuX-perf(1): [perflog] runtime '
                     'tier ON (frame 1, by %s)' % tier)
    for i in range(110):
        t = 10 + 2 * i
        st = '10-18 12:%02d:%02d.000' % (t // 60, t % 60)
        jit = (i % 3 - 1) * 0.5
        lines.append('%s I/hakuX-perf(1): [rdc] f=60 dt=2000 tid=2 tcpu=%.1f'
                     % (st, (tcpu + jit) * 2))
        lines.append('%s I/hakuX-perf(1): gfps=%d Tq:1.0 Df:0 Ri:%.2f'
                     % (st, gfps, ri + jit / 10))
        if on:
            lines.append('%s I/hakuX-phase(1): Surf:0.4 Tex:0.2 TxH:0.1 Shd:0.0 '
                         'Draw:3.2 [Vtx:0.3 Cmd:0.5 Sfp:0.2 Mfp:0.1 FTx:0.1] '
                         'Fin:0.4 | Tot:9.0 ms' % st)
            lines.append('%s I/hakuX-cpu(1): CPU: K:40 W:12.0K M:900 Push:1.1ms '
                         '[Pull:2.3(Lk:0.1 Mth:2.0 Fst:0.4)] Lw:0.0' % st)
            lines.append('%s W/hakuX(1): [tcg787] w=%d dt=2000 gc=10' % (st, i))
    lines.extend(extra)
    with open(os.path.join(d, 'logcat.txt'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    with open(os.path.join(d, 'run.log'), 'w') as f:
        f.write('ROUTE 12:00:10.000 mark gameplay\n')
    with open(os.path.join(d, 'result.json'), 'w') as f:
        f.write('{"shader_cache": "%s: fixture"}' % cache)


# (name, cold_runs_only, A runs, B runs, ON run or None, exit, must print).
# A run is fixture() kwargs. Each case names the rule it exercises; the last
# repeats the one before without cold_runs_only, so the VOID is the rule's.
PHASE_LINE = ('10-18 12:01:00.000 I/hakuX-phase(1): Surf:0.4 Tex:0.2 TxH:0.1 '
              'Draw:3.2 Sfp:0.2 Mfp:0.1 FTx:0.1')
AB_CASES = [
    ('cleared_and_on_hit', True,
     [dict(tcpu=300), dict(tcpu=301), dict(tcpu=299)],
     [dict(tcpu=302), dict(tcpu=300)], dict(tcpu=330, on=True), 0,
     ['CLEARED', 'ON HIT', 'ON-OFF +29']),
    ('b_slower_by_40', True,
     [dict(tcpu=300), dict(tcpu=301), dict(tcpu=299)],
     [dict(tcpu=340), dict(tcpu=341)], None, 1, ['SLOWDOWN: tcpu B-A +40']),
    ('b_ri_down_by_1', True,
     [dict(tcpu=300), dict(tcpu=300)],
     [dict(tcpu=300, ri=22.5), dict(tcpu=300, ri=22.4)], None, 1,
     ['SLOWDOWN: Ri B-A']),
    ('b_prints_a_phase_line', True,
     [dict(tcpu=300), dict(tcpu=300)],
     [dict(tcpu=300, extra=[PHASE_LINE]), dict(tcpu=300)], None, 2,
     ['hakuX-phase lines; B must be OFF']),
    ('on_run_without_a_tier_line', True,
     [dict(tcpu=300), dict(tcpu=300)], [dict(tcpu=300), dict(tcpu=300)],
     dict(tcpu=330, on=True, tier=None), 3, ['ON MISS: want exactly 1']),
    ('on_run_on_by_marker', True,
     [dict(tcpu=300), dict(tcpu=300)], [dict(tcpu=300), dict(tcpu=300)],
     dict(tcpu=330, on=True, tier='marker'), 3, ['ON MISS: want exactly 1']),
    ('on_run_with_no_timers', True,
     [dict(tcpu=300), dict(tcpu=300)], [dict(tcpu=300), dict(tcpu=300)],
     dict(tcpu=330, extra=['10-18 12:00:01.000 I/hakuX-perf(1): [perflog] '
                           'runtime tier ON (frame 1, by env)']), 3,
     ['ON MISS: 0 full hakuX-phase lines', 'ON MISS: 0 [tcg787] lines']),
    ('warm_run_left_out', True,
     [dict(tcpu=300), dict(tcpu=300), dict(tcpu=200, cache='kept')],
     [dict(tcpu=300), dict(tcpu=300)], None, 0,
     ['LEFT OUT (M1/cold_runs_only)', 'CLEARED']),
    ('one_cold_b_run', True,
     [dict(tcpu=300), dict(tcpu=300)],
     [dict(tcpu=300), dict(tcpu=300, cache='kept')], None, 2,
     ['arm B: 1 cold-cache runs, under 2']),
    ('one_cold_b_run_rule_off', False,
     [dict(tcpu=300), dict(tcpu=300)],
     [dict(tcpu=300), dict(tcpu=300, cache='kept')], None, 0, ['CLEARED']),
]


def abread_checks(tmp):
    """Run abread.py on each AB_CASES fixture; True if every exit and every
    expected line matches."""
    ok = True
    for name, cold_only, a_runs, b_runs, on_run, want, says in AB_CASES:
        base = os.path.join(tmp, 'ab-' + name)
        os.makedirs(base)
        pred = os.path.join(base, 'pred.json')
        with open(pred, 'w') as f:
            f.write('{"expect": {"P2/window_from_mark_s": [20, 180], '
                    '"P2/tcpu_b_minus_a_max_ms_per_s": 15.0, '
                    '"P2/ri_b_minus_a_min_ms": -0.3, '
                    '"P2/prior_band_tcpu_ms_per_s": 14.0, '
                    '"P2/prior_band_ri_ms": 0.2, '
                    '"P1/tcpu_b_minus_a_max_ms_per_s": 100.0, '
                    '"M1/rdc_lines_min": 60, '
                    '"M1/cold_runs_only": %s, "M1/cold_runs_min_per_arm": 2, '
                    '"M2/on_tier_lines": 1, "M2/on_phase_lines_min": 50, '
                    '"M2/on_tcg787_lines_min": 20}}'
                    % ('true' if cold_only else 'false'))
        args = [sys.executable, os.path.join(HERE, 'abread.py'), '--judge', pred]
        for arm, runs in (('a', a_runs), ('b', b_runs)):
            for i, kw in enumerate(runs):
                d = os.path.join(base, '%s%d' % (arm, i + 1))
                fixture(d, **kw)
                args += ['--' + arm, d]
        if on_run:
            d = os.path.join(base, 'on')
            fixture(d, **on_run)
            args += ['--on', d]
        r = subprocess.run(args, capture_output=True, text=True, timeout=60)
        miss = [s for s in says if s not in r.stdout]
        if r.returncode == want and not miss:
            print('PASS abread.%s: exit %d' % (name, want))
        else:
            ok = False
            print('FAIL abread.%s: exit %d (want %d), missing %s\n%s%s'
                  % (name, r.returncode, want, miss, r.stdout, r.stderr))
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

        caught = 0
        for name, side, edits, must_fail in WIRE_MUTANTS:
            text = apply_edits(src[side], edits)
            if text is None:
                print('WIRE MUTANT %r: a pattern is not found once in %s'
                      % (name, SIDES[side]))
                ok = False
                continue
            mut = dict(src)
            mut[side] = text
            res = {c: good for c, good, _ in wire_checks(mut)}
            if res.get(must_fail) is False:
                caught += 1
                print('CAUGHT %s -> FAIL %s' % (name, must_fail))
            else:
                ok = False
                print('MISSED %s: %s did not fail' % (name, must_fail))
        print('WIRE MUTANTS caught=%d of %d' % (caught, len(WIRE_MUTANTS)))

        if not abread_checks(tmp):
            ok = False
    finally:
        if a.keep:
            print('kept', tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print('SELFTEST', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
