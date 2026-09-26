#!/usr/bin/env python3
"""Per-window timeline of lane.tcgchurn's [tlb68] counter line next to the
nearest hakuX-perf gfps. Fields (docs/lanes/tcgchurn/NOTES.md): ff full
flushes, rd/rde tlb_reset_dirty calls / entries walked from the code re-arm,
rdo/rdoe the same from other callers, sd tlb_set_dirty (a notdirty write
re-enabling a page), pf page faults, tn current TLB entries, rs resizes.

    python3 tlb68.py <result-id-or-suffix> [every_n_windows]
"""
import os
import re
import sys
from datetime import datetime

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


r = sys.argv[1]
every = int(sys.argv[2]) if len(sys.argv) > 2 else 5
run = sorted(d for d in os.listdir(R) if d == r or d.endswith(r) or r in d)[0]
L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
t0 = ts(L[1])
gf = []
for l in L:
    if 'hakuX-perf' in l and 'gfps=' in l:
        gf.append(((ts(l) - t0).total_seconds(), int(re.search(r'gfps=(\d+)', l).group(1))))


def gfps_at(s):
    best = min(gf, key=lambda x: abs(x[0] - s)) if gf else (0, -1)
    return best[1]


print(run)
print('     t gfps    ff     rd      rde   rdo   rdoe      sd     pf     tn  rs')
n = 0
for l in L:
    if '[tlb68]' not in l:
        continue
    d = dict(re.findall(r'(\w+)=(\d+)', l))
    s = (ts(l) - t0).total_seconds()
    if n % every == 0:
        print('%6.1f %4d %5s %6s %8s %5s %8s %7s %6s %6s %3s' % (
            s, gfps_at(s), d.get('ff'), d.get('rd'), d.get('rde'), d.get('rdo'),
            d.get('rdoe'), d.get('sd'), d.get('pf'), d.get('tn'), d.get('rs')))
    n += 1
