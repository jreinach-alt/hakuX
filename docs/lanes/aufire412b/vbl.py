#!/usr/bin/env python3
"""Guest-visible VBLANK over a soak window, from the `vbl`/`vblphase` lines.

    python3 vbl.py <lo> <hi> <result-id> [...]

lo/hi are seconds since the logcat's first line. Both lines print every ~2 s
from nv2a.c's vbh_dump_and_reset (always on, not perflog-gated):

  vbl       n asserted VBLANKs, win ms, got = mean interval ns, rate Hz,
            def = deferred assertions, coal = coalesced (guest had not acked)
  vblphase  lateness against the fixed grid: mean/p90/max ns, split by
            deferred and not; clamp = grid re-based because a callback ran
            more than a whole period late (each clamp loses guest time)

Summed over the window: VBLANKs per wall second (n / win), the deferral and
clamp counts, and the mean lateness of undeferred assertions (the timer's own
delivery latency: main-loop / BQL delay, not policy).
"""
import os
import re
import sys
from datetime import datetime

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def ts(line):
    return datetime.strptime('2026-' + line[:18], '%Y-%m-%d %H:%M:%S.%f')


def one(run, lo, hi):
    L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
    L = [x for x in L if len(x) > 18 and x[2] == '-' and x[5] == ' ']
    t0 = ts(L[0])
    o = dict(lines=0, n=0, win=0, deff=0, coal=0, clamp=0, pn=0, nd_n=0,
             nd_sum=0, nd_max=0, d_n=0, d_sum=0, d_max=0, gmax=0)
    for x in L:
        s = (ts(x) - t0).total_seconds()
        if s < lo or s > hi:
            continue
        m = re.search(r'vbl n=(\d+) win=(\d+)ms .* max=(\d+) src.* coal=(\d+) def=(\d+)', x)
        if m:
            o['lines'] += 1
            o['n'] += int(m.group(1))
            o['win'] += int(m.group(2))
            o['gmax'] = max(o['gmax'], int(m.group(3)))
            o['coal'] += int(m.group(4))
            o['deff'] += int(m.group(5))
            continue
        m = re.search(r'vblphase n=(\d+) .*nodef\(n=(\d+) mean=(-?\d+) max=(-?\d+)\) '
                      r'def\(n=(\d+) mean=(-?\d+) max=(-?\d+)\).* clamp=(\d+)', x)
        if m:
            g = [int(v) for v in m.groups()]
            o['pn'] += g[0]
            o['nd_n'] += g[1]
            o['nd_sum'] += g[1] * g[2]
            o['nd_max'] = max(o['nd_max'], g[3])
            o['d_n'] += g[4]
            o['d_sum'] += g[4] * g[5]
            o['d_max'] = max(o['d_max'], g[6])
            o['clamp'] += g[7]
    if not o['lines']:
        return None
    return {
        'lines': o['lines'],
        'Hz': 1000.0 * o['n'] / o['win'],
        'def%': 100.0 * o['deff'] / o['n'],
        'coal': o['coal'],
        'clamp': o['clamp'],
        'late_nodef_ms': o['nd_sum'] / o['nd_n'] / 1e6 if o['nd_n'] else 0.0,
        'late_def_ms': o['d_sum'] / o['d_n'] / 1e6 if o['d_n'] else 0.0,
        'late_max_ms': max(o['nd_max'], o['d_max']) / 1e6,
        'ivl_max_ms': o['gmax'] / 1e6,
    }


def main():
    lo, hi = float(sys.argv[1]), float(sys.argv[2])
    cols = ['lines', 'Hz', 'def%', 'coal', 'clamp', 'late_nodef_ms',
            'late_def_ms', 'late_max_ms', 'ivl_max_ms']
    print('run | ' + ' | '.join(cols))
    for r in sys.argv[3:]:
        o = one(r, lo, hi)
        if o is None:
            print(r, '| VOID: no vbl line in the window')
            continue
        print(r + ' | ' + ' | '.join(
            ('%.2f' % o[c]) if isinstance(o[c], float) else str(o[c])
            for c in cols))


if __name__ == '__main__':
    main()
