#!/usr/bin/env python3
"""Pacing-field timeline (gfps, G, Ri, Vpf, Df, J, Tq) from a soak's
hakuX-perf lines. Tq is the per-frame count of texture dirty-bitmap queries
(profile.c, tex_dirty_queries, an EMA over frames).

    python3 pacing.py <result-id-or-suffix> [...]
"""
import os
import re
import sys
from datetime import datetime

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


for r in sys.argv[1:]:
    cands = [d for d in os.listdir(R) if d == r or d.endswith(r)]
    if not cands:
        print('==', r, 'MISSING')
        continue
    run = sorted(cands)[0]
    L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
    t0 = ts(L[1])
    print('==', run)
    print('     t gfps      G     Ri   Vpf   Df     J    Tq')
    for l in L:
        if 'hakuX-perf' not in l or ' G:' not in l:
            continue
        d = dict(re.findall(r'(\w+)[:=]([\d.]+)', l))
        s = (ts(l) - t0).total_seconds()
        g = d.get('gfps', '?')
        print('%6.1f %4s %6.1f %6.1f %5.2f %4s %5s %5s' % (
            s, g, float(d['G']), float(d['Ri']), float(d['Vpf']),
            d['Df'], d['J'], d['Tq']))
