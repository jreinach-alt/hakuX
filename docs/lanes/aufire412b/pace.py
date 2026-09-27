#!/usr/bin/env python3
"""Vblanks per flip over a soak window, from the always-on hakuX-pace line.

    python3 pace.py <lo> <hi> <result-id> [...]

lo/hi are seconds since the logcat's first line (the convention of
lane.aufire412's splitread.py windows and tbchurn424's churn.py with no
route mark). hakuX-pace (profile.c:628) prints, every 60 flips, how many of
those flips consumed 0, 1, 2, 3 and 4+ VBLANKs (v0..v4), the VBLANK total, the
longest flip interval and the window's wall time.

A title that flips on VBLANK is quantized: its frame is n x 16.7 ms. A saving
that does not take a frame under the next lower multiple cannot move fps, and
the time it frees shows up as waiting for the VBLANK. The histogram is the
direct reading of that: all mass at v4 means every frame took 4+ VBLANKs.

Also from [tlb68] (cpu= vCPU-thread CPU ms, dt= wall ms): the vCPU thread's
busy share over the same window.
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
    v = [0] * 5
    vb = f = 0
    span = 0.0
    mx = 0.0
    cpu = dt = 0
    for x in L:
        s = (ts(x) - t0).total_seconds()
        if s < lo or s > hi:
            continue
        if 'hakuX-pace' in x:
            d = dict(re.findall(r'(\w+)=([\d.]+)', x))
            for i in range(5):
                v[i] += int(d['v%d' % i])
            vb += int(d['vb'])
            span += float(d['ms'])
            mx = max(mx, float(d['max']))
        elif '[tlb68]' in x:
            d = dict(re.findall(r'(\w+)=(\d+)', x))
            cpu += int(d.get('cpu', 0))
            dt += int(d.get('dt', 0))
    f = sum(v)
    if not f:
        return None
    return {
        'flips': f,
        'fps': 1000.0 * f / span if span else 0,
        'v0..v4 %': ' '.join('%.0f' % (100.0 * n / f) for n in v),
        'vb/flip': vb / f,
        'ms/flip': span / f,
        'max': mx,
        'vcpu%': 100.0 * cpu / dt if dt else -1,
    }


def main():
    lo, hi = float(sys.argv[1]), float(sys.argv[2])
    cols = ['flips', 'fps', 'v0..v4 %', 'vb/flip', 'ms/flip', 'max', 'vcpu%']
    print('run | ' + ' | '.join(cols))
    for r in sys.argv[3:]:
        o = one(r, lo, hi)
        if o is None:
            print(r, '| VOID: no hakuX-pace line in the window')
            continue
        print(r + ' | ' + ' | '.join(
            ('%.2f' % o[c]) if isinstance(o[c], float) else str(o[c])
            for c in cols))


if __name__ == '__main__':
    main()
