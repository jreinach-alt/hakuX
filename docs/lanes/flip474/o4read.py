#!/usr/bin/env python3
"""The PFIFO thread's deferred-download wait, split, over a window of each run.

    python3 o4read.py [--from 151 --to 288] [--show] [--lines] <result id> ...
    python3 o4read.py --selftest

Per frame (ms), from lines already in a perflog build's logcat:

  cdef       [surf413] the completion call in pgraph_vk_surface_update
  dfF, dfR   [surf413] xemu-surf: the completion's wait (fence or finish) and
             what follows it (the staged copies into VRAM and the flags)
  Tot, GPU   hakuX-phase: the PFIFO thread's frame and the GPU's span for its
             command buffers (R inside render passes, X outside; Pre/Post the
             span before the first and after the last pass; MxG the longest
             gap between two passes; RP the pass count)
  [sdcall]   when the build has it (lane.forza414): surface_update's
             completions by branch and the updates that deferred

xemu-surf's times are per frame already (profile.c divides by the flips in
the line); the #counts are per line. --show prints one raw line of each kind
from the middle of the window, so the field list above can be checked against
the build that wrote it.

[o4] (the O4 pilot's build only) is one line per waited flip, and is read per
flip, not per line of averages:

  finish     pre -> post: the flip's pre-record and finish on the PFIFO thread.
             vkQueueSubmit returned inside it.
  to_wait    post -> w0: from the finish to the start of the fence wait
  wait       w0 -> w1: the fence wait
  span       the command buffer's first to last GPU timestamp
  start      pre -> the first GPU timestamp: the flip's submit to the GPU
             starting this command buffer. An UPPER bound, by `finish` at most
             on the submit side and by the smallest signal latency in the
             window on the clock side (see below).
  end        the last GPU timestamp -> w1. A LOWER bound, by the same amount.
  R, gap     the sum of the render passes' spans, and the longest gap between
             two passes, with the pass it follows; gap/R is per flip

The GPU's clock is placed on the PFIFO thread's by the smallest (w1 - ce) in
the window: a command buffer cannot end after its fence was seen signalled, so
that minimum is the clocks' offset plus the smallest signal latency. `off
drift` is that minimum over each third of the window; a spread of more than
about a millisecond means the clocks drift and `start`/`end` are only good to
that spread.
"""
import argparse
import os
import re
import sys
from datetime import datetime
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
LONG_WAIT_MS = 4.0


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


def field(l, k, sep):
    m = re.search(r'(?<![A-Za-z#_])' + re.escape(k) + sep + r'(-?[0-9.]+)', l)
    return float(m.group(1)) if m else None


def med(rows, k, sep):
    v = [x for x in (field(l, k, sep) for l in rows) if x is not None]
    return median(v) if v else None


def fmt(name, x):
    return '%s=%s' % (name, 'n/a' if x is None else '%.1f' % x)


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]


def parse_o4(l):
    m = re.search(r'\[o4\] fi=(\d+) sc=(\d+) pre=(-?\d+) post=(-?\d+) '
                  r'w0=(-?\d+) w1=(-?\d+) per=([0-9.]+) cs=(\d+) ce=(\d+) '
                  r'rp=(\d+) o=(\S*)', l)
    if not m:
        return None
    per = float(m.group(7))
    o = [int(x) / 1000.0 for x in m.group(11).split(',') if x]
    rp = int(m.group(10))
    if len(o) != rp * 2 or int(m.group(9)) < int(m.group(8)):
        return None
    f = {'fi': int(m.group(1)), 'sc': int(m.group(2)),
         'pre': int(m.group(3)), 'post': int(m.group(4)),
         'w0': int(m.group(5)), 'w1': int(m.group(6)),
         'cs': int(m.group(8)) * per, 'ce': int(m.group(9)) * per,
         'passes': list(zip(o[0::2], o[1::2]))}
    f['wait'] = (f['w1'] - f['w0']) / 1e6
    f['span'] = (f['ce'] - f['cs']) / 1e6
    return f


def split_o4(flips):
    """Medians over the long-wait flips; None when there are none."""
    flips = [f for f in flips if f['wait'] >= LONG_WAIT_MS]
    if not flips:
        return None
    d = [f['w1'] - f['ce'] for f in flips]
    off = min(d)
    n = len(flips)
    thirds = [min(d[i * n // 3:(i + 1) * n // 3] or [off]) for i in range(3)]
    out = {'n': n, 'drift_ms': [(t - off) / 1e6 for t in thirds]}
    cols = {k: [] for k in ('finish', 'to_wait', 'wait', 'span', 'start',
                            'end', 'R', 'gap', 'gap_over_R', 'gap_after',
                            'first_pass', 'passes')}
    for f in flips:
        cols['finish'].append((f['post'] - f['pre']) / 1e6)
        cols['to_wait'].append((f['w0'] - f['post']) / 1e6)
        cols['wait'].append(f['wait'])
        cols['span'].append(f['span'])
        cols['start'].append((f['cs'] + off - f['pre']) / 1e6)
        cols['end'].append((f['w1'] - f['ce'] - off) / 1e6)
        p = f['passes']
        cols['passes'].append(len(p))
        if p:
            r_sum = sum(e - b for b, e in p)
            cols['R'].append(r_sum)
            cols['first_pass'].append(p[0][0])
            gaps = [(p[i + 1][0] - p[i][1], i) for i in range(len(p) - 1)]
            if gaps:
                g, i = max(gaps)
                cols['gap'].append(g)
                cols['gap_after'].append(i)
                if r_sum > 0:
                    cols['gap_over_R'].append(g / r_sum)
    out['med'] = {k: median(v) for k, v in cols.items() if v}
    out['p10'] = {k: pct(v, 0.1) for k, v in cols.items() if v}
    out['p90'] = {k: pct(v, 0.9) for k, v in cols.items() if v}
    g = cols['gap_over_R']
    out['gap_eq_R'] = (sum(1 for x in g if 0.95 <= x <= 1.05) / len(g)
                       if g else None)
    sc = [b['sc'] - a['sc'] for a, b in zip(flips, flips[1:])]
    out['submits_per_flip'] = median(sc) if sc else None
    return out


def print_o4(s):
    m, lo, hi = s['med'], s['p10'], s['p90']
    print('   [o4] long-wait flips=%d submits/flip=%s off drift (ms, by third)='
          '%s' % (s['n'], s['submits_per_flip'],
                  '/'.join('%.2f' % x for x in s['drift_ms'])))
    for k in ('finish', 'to_wait', 'wait', 'span', 'start', 'end'):
        print('     %-8s med=%6.1f  p10=%6.1f  p90=%6.1f' % (k, m[k], lo[k], hi[k]))
    if 'R' in m and 'gap' in m:
        print('     passes=%d R=%.1f first pass at %.1f | longest gap=%.1f after '
              'pass %d | gap/R med=%.2f p10=%.2f p90=%.2f, within 5%% of 1 on '
              '%.0f%% of flips'
              % (m['passes'], m['R'], m['first_pass'], m['gap'],
                 m['gap_after'], m['gap_over_R'], lo['gap_over_R'],
                 hi['gap_over_R'], 100 * s['gap_eq_R']))


def selftest():
    """A GPU clock 7 s ahead of the CPU's and 3 s into its own count; every
    part of the split has a different size, so a swapped pair shows."""
    lines = []
    for i in range(40):
        pre = 1000000000 + i * 70000000
        post = pre + 1800000
        w0 = post + 2500000
        start, span = 18000000, 33000000
        end = 200000 + (i % 5) * 100000       # the smallest, 0.2 ms, is lost
        cs_cpu = pre + start
        ce_cpu = cs_cpu + span
        w1 = ce_cpu + end
        gpu = lambda t: t + 7000000000
        o = [100, 4100, 4200, 9200, 25700, 32200]   # R 15.5, gap 16.5 after 1
        lines.append('[o4] fi=%d sc=%d pre=%d post=%d w0=%d w1=%d per=1.0000 '
                     'cs=%d ce=%d rp=3 o=%s'
                     % (i % 3, 10 + 2 * i, pre, post, w0, w1, gpu(cs_cpu),
                        gpu(ce_cpu), ','.join(str(x) for x in o)))
    lines.append('[o4] fi=0 sc=1 pre=1 post=2 w0=3 w1=1000003 per=1.0000 '
                 'cs=5 ce=9 rp=1 o=1,2')            # a short wait: not counted
    lines.append('[o4] fi=0 sc=1 pre=1 post=2 w0=3 w1=9000003 per=1.0000 '
                 'cs=5 ce=9 rp=2 o=1,2')            # malformed: not parsed
    s = split_o4([f for f in map(parse_o4, lines) if f])
    m = s['med']
    want = {'finish': 1.8, 'to_wait': 2.5, 'span': 33.0, 'start': 18.2,
            'end': 0.2, 'R': 15.5, 'gap': 16.5, 'gap_after': 1,
            'first_pass': 0.1, 'passes': 3,
            'wait': 18.0 + 33.0 + 0.4 - 1.8 - 2.5}
    bad = [(k, m[k], v) for k, v in want.items() if abs(m[k] - v) > 0.01]
    if s['n'] != 40:
        bad.append(('n', s['n'], 40))
    if s['submits_per_flip'] != 2:
        bad.append(('submits_per_flip', s['submits_per_flip'], 2))
    if abs(s['gap_eq_R'] - 0.0) > 1e-9:          # 16.5 / 15.5 = 1.065
        bad.append(('gap_eq_R', s['gap_eq_R'], 0.0))
    for k, got, exp in bad:
        print('selftest FAIL %s: got %r, want %r' % (k, got, exp))
    print('selftest %s' % ('FAIL' if bad else 'ok: 11 fields, 40 flips, a '
                           'short and a malformed line dropped'))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='lo', type=float, default=151)
    ap.add_argument('--to', dest='hi', type=float, default=288)
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--lines', action='store_true',
                    help="every hakuX-phase line's frame and GPU fields")
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('runs', nargs='*')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    for run in a.runs:
        L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
        t0 = ts(L[1])
        rows = []
        for l in L:
            try:
                s = (ts(l) - t0).total_seconds()
            except ValueError:
                continue
            if a.lo <= s <= a.hi:
                rows.append(l)
        s413 = [l for l in rows if '[surf413] frames=' in l]
        xs = [l for l in rows if '[surf413] xemu-surf' in l]
        ph = [l for l in rows if 'hakuX-phase' in l]
        sd = [l for l in rows if '[sdcall]' in l]
        o4 = [l for l in rows if '[o4] ' in l]
        print(run, 'lines: surf413=%d xemu-surf=%d phase=%d sdcall=%d o4=%d'
              % (len(s413), len(xs), len(ph), len(sd), len(o4)))
        print('  ', fmt('cdef', med(s413, 'cdef', '=')),
              fmt('dfF', med(xs, 'dfF', ':')), fmt('dfR', med(xs, 'dfR', ':')),
              fmt('#dl', med(xs, '#dl', ':')))
        print('  ', ' '.join(fmt(k, med(ph, k, ':')) for k in
                             ['Tot', 'Surf', 'Draw', 'Fin', 'GPU', 'R', 'X',
                              'RP', 'Pre', 'Post', 'MxG']))
        rx = []
        for l in ph:
            r_, x_ = field(l, 'R', ':'), field(l, 'X', ':')
            if r_ and x_:
                rx.append(x_ / r_)
        if rx:
            print('   X/R per line: min=%.2f p10=%.2f med=%.2f p90=%.2f max=%.2f'
                  ' n=%d' % (min(rx), pct(rx, 0.1), median(rx), pct(rx, 0.9),
                             max(rx), len(rx)))
        if o4:
            flips = [f for f in map(parse_o4, o4) if f]
            s = split_o4(flips)
            if len(flips) != len(o4):
                print('   [o4] %d of %d lines did not parse'
                      % (len(o4) - len(flips), len(o4)))
            if s:
                print_o4(s)
            else:
                print('   [o4] no flip waited %.0f ms or more' % LONG_WAIT_MS)
        if a.lines:
            for l in ph:
                m = re.search(r'Tot:\S+ GPU:.*', l)
                print('   |', l[6:14], 'Surf:%s' % field(l, 'Surf', ':'),
                      m.group(0) if m else '')
        if a.show:
            for rows_ in (s413, xs, ph, sd, o4):
                if rows_:
                    print('   |', rows_[len(rows_) // 2][19:])
        elif sd:
            print('   |', sd[len(sd) // 2][19:])


if __name__ == '__main__':
    main()
