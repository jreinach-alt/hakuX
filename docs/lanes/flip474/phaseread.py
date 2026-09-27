#!/usr/bin/env python3
"""Median hakuX-phase per-frame times (ms) over a window of each run.

    python3 phaseread.py [--from 151 --to 288] <result id> ...

GPU is the frame's command-buffer span from GPU timestamps (R: inside render
passes, X: outside); Tot is the PFIFO thread's per-frame wall time.
"""
import argparse
import os
import re
from datetime import datetime
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
KEYS = ['Surf', 'Draw', 'Fin', 'Tot', 'GPU', 'R', 'X']


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='lo', type=float, default=151)
    ap.add_argument('--to', dest='hi', type=float, default=288)
    ap.add_argument('runs', nargs='+')
    a = ap.parse_args()
    for run in a.runs:
        L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
        t0 = ts(L[1])
        v = {k: [] for k in KEYS}
        n = 0
        for l in L:
            if 'hakuX-phase' not in l:
                continue
            try:
                s = (ts(l) - t0).total_seconds()
            except ValueError:
                continue
            if not a.lo <= s <= a.hi:
                continue
            n += 1
            for k in KEYS:
                m = re.search(r'(?<![A-Za-z])' + k + r':([0-9.]+)', l)
                if m:
                    v[k].append(float(m.group(1)))
        print(run, 'n=%d' % n,
              ' '.join('%s=%.1f' % (k, median(v[k])) for k in KEYS if v[k]))


if __name__ == '__main__':
    main()
