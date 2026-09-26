#!/usr/bin/env python3
"""gfps timeline from a soak's hakuX-perf lines, in 30 s bins, plus the
median over a window (default 90-240 s). Prints the raw perf line format once
so the reader can see which fields exist.

    python3 gfps.py [--from 90] [--to 240] <result-id> [...]
"""
import os
import re
import sys
from datetime import datetime
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


args = sys.argv[1:]
lo, hi = 90.0, 240.0
while args and args[0].startswith('--'):
    k = args.pop(0)
    v = float(args.pop(0))
    if k == '--from':
        lo = v
    elif k == '--to':
        hi = v

for run in args:
    L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
    t0 = ts(L[1])
    perf = []
    shown = False
    for l in L:
        if 'hakuX-perf' not in l:
            continue
        m = re.search(r'gfps[= ]([\d.]+)', l)
        if not m:
            m = re.search(r'\bG[= ]?([\d.]+)', l)
            if not m:
                continue
        if not shown:
            print('   perf line:', l[19:160])
            shown = True
        perf.append(((ts(l) - t0).total_seconds(), float(m.group(1)), l))
    print(run, f'({len(perf)} perf lines)')
    if not perf:
        continue
    bins = {}
    for s, g, _ in perf:
        bins.setdefault(int(s // 30), []).append(g)
    print('   30 s bins (median gfps):',
          ' -> '.join(f'{median(bins[b]):.0f}' for b in sorted(bins)))
    win = [g for s, g, _ in perf if lo <= s <= hi]
    if win:
        print(f'   median gfps {lo:.0f}-{hi:.0f} s: {median(win):.1f} '
              f'(min {min(win):.1f}, max {max(win):.1f}, n={len(win)})')
    last = perf[-1][2]
    print('   last perf line:', last[19:200])
