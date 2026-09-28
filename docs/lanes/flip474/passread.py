#!/usr/bin/env python3
"""DOA's GPU time per render pass, from the O4 pilot's [o4] lines.

    python3 passread.py [--from 151 --to 288] [--period 52.083] <result id>
    python3 passread.py --selftest

[o4] is one line per waited flip (o4read.py has the field list). Its `o=`
list is each render pass's first and last GPU timestamp, as an offset from
the command buffer's first, computed by the build with the period in `per=`.
--period restates every figure with another period (the Nova's fitted 52.083
ns, NOTES.md section 15); without it the build's own period is kept.

Per pass index, over the flips that have the modal pass count:

  start   the pass's first timestamp, from the command buffer's first
  dur     last - first timestamp of the pass
  before  this pass's start - the previous pass's end (for pass 0: start)

and for the command buffer: span, the passes' sum, the gaps' sum, and the
tail after the last pass. Every column is a median over flips, so a row's
columns need not add up exactly; `sum check` prints how far they are off.

Both timestamps of a pass are written INSIDE it (draw.c begin_render_pass /
end_render_pass), so on a tiler a pass's `dur` and the `before` that precedes
it are one pass's work split by where the driver executes the timestamp; read
`before + dur` as the pass's cost and neither half alone.
"""
import argparse
import os
import sys
from collections import Counter
from datetime import datetime
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from o4read import LONG_WAIT_MS, R, parse_o4, pct  # noqa: E402


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


def per_of(l):
    i = l.find(' per=')
    return float(l[i + 5:].split()[0])


def table(flips, scale):
    """flips: parse_o4 dicts. Returns (n used, n all, modal count, rows, cb)."""
    flips = [f for f in flips if f['wait'] >= LONG_WAIT_MS and f['passes']]
    if not flips:
        return None
    modal = Counter(len(f['passes']) for f in flips).most_common(1)[0][0]
    use = [f for f in flips if len(f['passes']) == modal]
    rows = []
    for i in range(modal):
        start = [f['passes'][i][0] * scale for f in use]
        dur = [(f['passes'][i][1] - f['passes'][i][0]) * scale for f in use]
        before = [(f['passes'][i][0] -
                   (f['passes'][i - 1][1] if i else 0.0)) * scale for f in use]
        rows.append({'i': i, 'start': median(start), 'dur': median(dur),
                     'dur10': pct(dur, 0.1), 'dur90': pct(dur, 0.9),
                     'before': median(before), 'before10': pct(before, 0.1),
                     'before90': pct(before, 0.9)})
    span = [f['span'] * scale for f in use]
    rsum = [sum(e - b for b, e in f['passes']) * scale for f in use]
    gsum = [(f['passes'][-1][1] - f['passes'][0][0]) * scale - r
            for f, r in zip(use, rsum)]
    tail = [s - f['passes'][-1][1] * scale for f, s in zip(use, span)]
    cb = {'span': median(span), 'R': median(rsum), 'gaps': median(gsum),
          'head': median([f['passes'][0][0] * scale for f in use]),
          'tail': median(tail), 'wait': median([f['wait'] for f in use])}
    return len(use), len(flips), modal, rows, cb


def show(t, scale, per):
    n, n_all, modal, rows, cb = t
    print('   period: build %.4f ns, x%.4f -> %.4f ns' % (per, scale, per * scale))
    print('   flips: %d of %d long-wait flips have %d passes (the modal count)'
          % (n, n_all, modal))
    print('   pass   start    before (p10-p90)        dur (p10-p90)     before+dur')
    for r in rows:
        print('   %4d %7.2f  %7.2f (%6.2f-%6.2f)  %7.2f (%6.2f-%6.2f)  %7.2f'
              % (r['i'], r['start'], r['before'], r['before10'], r['before90'],
                 r['dur'], r['dur10'], r['dur90'], r['before'] + r['dur']))
    print('   command buffer: span=%.2f  passes=%.2f  gaps=%.2f  head=%.2f  '
          'tail=%.2f | the flip\'s fence wait (CPU clock)=%.2f'
          % (cb['span'], cb['R'], cb['gaps'], cb['head'], cb['tail'], cb['wait']))
    print('   sum check: passes+gaps+head+tail - span = %.2f'
          % (cb['R'] + cb['gaps'] + cb['head'] + cb['tail'] - cb['span']))


def selftest():
    """Three passes of different sizes and gaps, and a period correction that
    doubles every figure; a 2-pass flip is outvoted and a short wait dropped."""
    lines = []
    for i in range(30):
        o = [100, 4100, 4200 + i % 3 * 10, 9200 + i % 3 * 10, 25700, 32200]
        lines.append('[o4] fi=0 sc=%d pre=0 post=1 w0=2 w1=40000002 '
                     'per=10.0000 cs=1000 ce=3301000 rp=3 o=%s'
                     % (i, ','.join(str(x) for x in o)))
    lines.append('[o4] fi=0 sc=1 pre=0 post=1 w0=2 w1=40000002 per=10.0000 '
                 'cs=1000 ce=3301000 rp=2 o=1,2,3,4')
    lines.append('[o4] fi=0 sc=1 pre=0 post=1 w0=2 w1=1000002 per=10.0000 '
                 'cs=1000 ce=3301000 rp=3 o=1,2,3,4,5,6')
    t = table([f for f in map(parse_o4, lines) if f], 2.0)
    n, n_all, modal, rows, cb = t
    want = [(n, 30), (n_all, 31), (modal, 3),
            (rows[0]['before'], 0.2), (rows[0]['dur'], 8.0),
            (rows[1]['before'], 0.22), (rows[1]['dur'], 10.0),
            (rows[2]['dur'], 13.0), (rows[2]['before'], 32.98),
            (cb['span'], 66.0), (cb['R'], 31.0), (cb['tail'], 1.6)]
    bad = [(i, g, w) for i, (g, w) in enumerate(want) if abs(g - w) > 0.011]
    for i, g, w in bad:
        print('selftest FAIL field %d: got %r, want %r' % (i, g, w))
    print('selftest %s' % ('FAIL' if bad else 'ok: %d fields' % len(want)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='lo', type=float, default=151)
    ap.add_argument('--to', dest='hi', type=float, default=288)
    ap.add_argument('--period', type=float, default=None,
                    help='the true tick period in ns; default: the build\'s')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('runs', nargs='*')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    for run in a.runs:
        L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
        t0 = ts(L[1])
        o4 = []
        for l in L:
            if '[o4] ' not in l:
                continue
            try:
                s = (ts(l) - t0).total_seconds()
            except ValueError:
                continue
            if a.lo <= s <= a.hi:
                o4.append(l)
        print(run, '[o4] lines in %g-%g s: %d' % (a.lo, a.hi, len(o4)))
        if not o4:
            continue
        per = per_of(o4[0])
        scale = (a.period / per) if a.period else 1.0
        t = table([f for f in map(parse_o4, o4) if f], scale)
        if t is None:
            print('   no long-wait flip with a pass')
            continue
        show(t, scale, per)


if __name__ == '__main__':
    main()
