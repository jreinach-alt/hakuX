#!/usr/bin/env python3
"""The #425 return split from a soak's [rr425] / [rr425pc] lines.

    python3 rr425.py [--from S] [--to S] <result-id | logcat path> [...]

Windows are seconds since the logcat's first line (the aufire412b windows:
AUF mission play is 299-483 on the survey route). For every [rr425] window
whose line falls inside [from, to] it sums the counters, and it takes the
frame rate from the hakuX-perf gfps lines in the same span. It prints:

  - returns per second and per frame by cause, and each cause's share;
  - the checks the counter owes before any number is read:
      d <= x          a return none of the causes booked is a longjmp
      m ~= hm         the loop's miss count agrees with the helper's own
      gs+gi+ga <= g   the goto_tb split does not exceed its parent
  - the loop cost: gapus (sampled loop time, scaled to all dispatches) in ms
    per frame, beside the 37 ms/frame bound from the #412 profile;
  - the top 16 (cause, pc) pairs summed over the span, with guest bytes.

--selftest runs it on a built-in two-window logcat.
"""
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
KV = re.compile(r'(\w+)=(-?\d+)')
PC = re.compile(r' ([a-z]):([0-9a-f]{8}):([0-9a-f]{6}):(\d+)')
CAUSES = [('e', 'gen_eob plain exit_tb'), ('m', 'lookup_tb_ptr miss'),
          ('r', 'TB_EXIT_REQUESTED'), ('g', 'goto_tb not patched'),
          ('o', 'other NULL exit')]
SUB = [('en', 'e: EOB_NEXT'), ('es', 'e: EOB_INHIBIT_IRQ (STI, MOV SS)'),
       ('eo', 'e: EOB_ONLY (IRET, far jump)'), ('et', 'e: RECHECK_TF'),
       ('ej', 'e: DISAS_JUMP in a shadow'), ('esh', 'e: TB began in a shadow'),
       ('gs', 'g: target spans pages'), ('gi', 'g: CF_INVALID'),
       ('ga', 'g: tb_add_jump called')]


def ts(line):
    return datetime.strptime('2026-' + line[:18], '%Y-%m-%d %H:%M:%S.%f')


def read(lines, lo, hi):
    t0 = None
    tot = Counter()
    nwin = 0
    pcs = Counter()
    gfps = []
    for line in lines:
        try:
            t = ts(line)
        except ValueError:
            continue
        if t0 is None:
            t0 = t
        s = (t - t0).total_seconds()
        if not lo <= s <= hi:
            continue
        if '[rr425] ' in line:
            kv = {k: int(v) for k, v in KV.findall(line.split('[rr425]', 1)[1])}
            tot.update(kv)
            nwin += 1
        elif '[rr425pc] ' in line:
            for c, pc, b, n in PC.findall(line):
                pcs[(c, pc, b)] += int(n)
        elif 'hakuX-perf' in line:
            # G:<mean ms per guest frame>; gfps is an integer and too coarse.
            m = re.search(r' G:([\d.]+)', line)
            if m and float(m.group(1)) > 0:
                gfps.append(float(m.group(1)))
    return tot, nwin, pcs, gfps


def report(name, tot, nwin, pcs, gfps, bound_ms=37.0):
    print('== %s: %d [rr425] windows, %.1f s' % (name, nwin, tot['dt'] / 1000))
    if not nwin:
        print('   VOID: no [rr425] line in the span')
        return False
    secs = tot['dt'] / 1000
    fps = 1000.0 / mean(gfps) if gfps else None
    frames = fps * secs if fps else None
    print('   fps (1000 / mean G) %s over %d perf lines' %
          ('%.2f' % fps if fps else 'n/a', len(gfps)))
    ret = sum(tot[c] for c, _ in CAUSES)
    print('   %-34s %12s %10s %10s %7s' % ('cause', 'count', '/s', '/frame', 'share'))
    for c, label in CAUSES + SUB + [('it', 'dispatches (it)'), ('x', 'longjmps'),
                                    ('hc', 'lookup_tb_ptr calls'),
                                    ('hm', 'lookup_tb_ptr misses'),
                                    ('ip', 'irq pending at dispatch'),
                                    ('iq', 'irq taken'), ('xr', 'exit_request'),
                                    ('ih', 'idle halts (HAKUX_IDLE_HLT)')]:
        n = tot[c]
        print('   %-34s %12d %10.0f %10s %6.1f%%' % (
            '%s  %s' % (c, label), n, n / secs,
            '%.0f' % (n / frames) if frames else 'n/a',
            100.0 * n / ret if ret else 0))
    ok = True
    print('   checks:')
    chk = [('d <= x', tot['d'] <= tot['x'], 'd=%d x=%d' % (tot['d'], tot['x'])),
           ('m ~= hm', abs(tot['m'] - tot['hm']) <= max(2 * nwin, tot['hm'] // 100),
            'm=%d hm=%d' % (tot['m'], tot['hm'])),
           ('gs+gi+ga <= g', tot['gs'] + tot['gi'] + tot['ga'] <= tot['g'],
            'sum=%d g=%d' % (tot['gs'] + tot['gi'] + tot['ga'], tot['g'])),
           ('pcdrop == 0', tot['pcdrop'] == 0, 'pcdrop=%d' % tot['pcdrop'])]
    for label, good, detail in chk:
        print('     %-16s %s  %s' % (label, 'ok' if good else 'FAIL', detail))
        ok &= good
    # The 1-in-64 timer charges its own get_clock() cost to the sample and
    # scales it by 64: on the Nova's idle loop (~35 ns a dispatch) the timed
    # total came to 4x the wall clock. Say so rather than print it as a cost.
    timed_ok = tot['gapus'] + tot['tbus'] <= 1.05 * tot['dt'] * 1000
    print('     %-16s %s  timed=%.0f s wall=%.0f s' % (
        'timed <= wall', 'ok' if timed_ok else 'INVALID (timing only)',
        (tot['gapus'] + tot['tbus']) / 1e6, secs))
    if frames:
        loop_ms = tot['gapus'] / 1000 / frames
        tb_ms = tot['tbus'] / 1000 / frames
        print('   loop time %.1f ms/frame (sampled gap), TB time %.1f ms/frame;'
              ' profile bound %.1f ms/frame; per return %.2f us' % (
                  loop_ms, tb_ms, bound_ms,
                  tot['gapus'] / ret if ret else 0))
    print('   top (cause, pc, guest bytes at pc): count, share of returns')
    for (c, pc, b), n in pcs.most_common(16):
        print('     %s %s %s %10d %6.2f%%' % (c, pc, b, n, 100.0 * n / ret if ret else 0))
    return ok


SELFTEST = """\
09-27 03:00:00.000  1  2 W hakuX   : start
09-27 03:00:02.000  1  2 W hakuX   : [rr425] w=0 dt=2000 it=100 e=60 en=10 es=20 eo=30 et=0 ej=0 esh=5 m=10 o=5 r=5 g=19 gs=4 gi=0 ga=15 x=2 d=1 hc=500 hm=10 ip=7 iq=6 xr=1 gapus=40000 tbus=60000 sn=2 tbn=2 pcdrop=0
09-27 03:00:02.000  1  2 W hakuX   : [rr425pc] w=0 e:80010000:fbc3cc:40 m:80020000:8bff55:10
09-27 03:00:02.500 I/hakuX-perf(1): gfps=20 G:50.0(3.3-340.2) D:16.7
09-27 03:00:04.000  1  2 W hakuX   : [rr425] w=1 dt=2000 it=100 e=60 en=10 es=20 eo=30 et=0 ej=0 esh=5 m=10 o=5 r=5 g=20 gs=4 gi=0 ga=16 x=0 d=0 hc=500 hm=10 ip=7 iq=6 xr=1 gapus=40000 tbus=60000 sn=2 tbn=2 pcdrop=0
09-27 03:00:04.000  1  2 W hakuX   : [rr425pc] w=1 e:80010000:fbc3cc:20 e:80030000:cf0000:20
"""


def selftest():
    tot, nwin, pcs, gfps = read(SELFTEST.splitlines(), 0, 1e9)
    assert nwin == 2 and tot['it'] == 200 and tot['e'] == 120, tot
    assert pcs[('e', '80010000', 'fbc3cc')] == 60, pcs
    assert gfps == [50.0]
    ok = report('selftest', tot, nwin, pcs, gfps)
    assert ok
    # 4 s at 20 fps = 80 frames; e = 120 returns -> 1.5 per frame
    bad = Counter(tot)
    bad['d'] = 5
    assert not report('selftest-bad', bad, nwin, pcs, gfps)
    print('selftest ok')


def main(argv):
    lo, hi = 0.0, 1e9
    args = list(argv)
    if args == ['--selftest']:
        return selftest()
    while args and args[0].startswith('--'):
        k, v = args.pop(0), float(args.pop(0))
        if k == '--from':
            lo = v
        elif k == '--to':
            hi = v
    for run in args:
        path = run if os.path.exists(run) else R + run + '/logcat.txt'
        lines = open(path, errors='replace').read().splitlines()
        report(run, *read(lines, lo, hi))


if __name__ == '__main__':
    main(sys.argv[1:])
