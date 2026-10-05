#!/usr/bin/env python3
"""GPU time outside render passes, per title, over every perflog soak in the
dispatch results (lane.belowbar1005).

    xfrsurvey.py [--days 12] [--min-tot 8]

From each run's `xemu-gpu` lines (`GPU: Tot:T Rnd:R Xfr:X RP:n`, ms per guest
frame, perflog builds only): the median Tot, Rnd, Xfr and RP (render passes per frame) over lines with
Tot >= --min-tot (drops menus and loads), and the share of Xfr in Tot. Per
title: medians over its runs. Whole logcats, so this ranks titles; it judges
none of them.
"""
import argparse
import glob
import json
import os
import re
import statistics
import time

D = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch')
ap = argparse.ArgumentParser()
ap.add_argument('--days', type=float, default=12)
ap.add_argument('--min-tot', type=float, default=8)
a = ap.parse_args()

GPU = re.compile(r'xemu-gpu.*GPU: Tot:([\d.]+) Rnd:([\d.]+) Xfr:([\d.]+) RP:(\d+)')
since = time.time() - a.days * 86400
per_title = {}
for rdir in glob.glob(os.path.join(D, 'results', '*')):
    lc = os.path.join(rdir, 'logcat.txt')
    try:
        if os.path.getmtime(rdir) < since or not os.path.exists(lc):
            continue
        req = json.load(open(os.path.join(rdir, 'request.json')))
    except Exception:
        continue
    if not req.get('title'):
        continue
    tot, rnd, xfr, rp = [], [], [], []
    for line in open(lc, errors='replace'):
        m = GPU.search(line)
        if m and float(m.group(1)) >= a.min_tot:
            tot.append(float(m.group(1)))
            rnd.append(float(m.group(2)))
            xfr.append(float(m.group(3)))
            rp.append(float(m.group(4)))
    if len(tot) < 10:
        continue
    med = statistics.median
    per_title.setdefault(req['title'][:40], []).append(
        (med(tot), med(rnd), med(xfr), med(rp), len(tot), os.path.basename(rdir)))

rows = []
for t, runs in per_title.items():
    med = statistics.median
    T, R, X, P = (med(r[i] for r in runs) for i in range(4))
    rows.append((X, T, R, P, t, len(runs), runs[0][5]))
print('%-40s %5s %6s %6s %6s %6s %5s  %s' % ('title', 'runs', 'Tot', 'Rnd', 'Xfr', 'Xfr/T', 'RP', 'a run'))
for X, T, R, P, t, n, rid in sorted(rows, reverse=True):
    print('%-40s %5d %6.1f %6.1f %6.1f %6.2f %5.0f  %s' % (t, n, T, R, X, X / T if T else 0, P, rid))
