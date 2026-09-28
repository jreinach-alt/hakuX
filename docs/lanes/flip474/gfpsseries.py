#!/usr/bin/env python3
"""The gfps and hakuX-phase series of a run, line by line, over a window.

    python3 gfpsseries.py [--from 151 --to 288] <result id> ...

A median hides a window that is part fight and part something else (a KO
replay, a loading screen, a menu). This prints each hakuX-perf gfps line and
each hakuX-phase line's Tot and GPU with its second from logcat line 1, so
the window can be cut where the scene changes and the cut can be stated.
"""
import argparse
import os
import re
from datetime import datetime

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


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
        print(run, 'line 1 at', L[1][:18])
        for l in L:
            try:
                s = (ts(l) - t0).total_seconds()
            except ValueError:
                continue
            if not a.lo <= s <= a.hi:
                continue
            m = re.search(r'hakuX-perf\(\s*\d+\): (gfps=\S+ G:\S+)', l)
            if m:
                print('  %6.1f %s  %s' % (s, l[6:14], m.group(1)))
            elif 'hakuX-phase' in l:
                m = re.search(r'(Tot:\S+) (GPU:[0-9.]+\(R:\S+ X:\S+ RP:\d+)', l)
                if m:
                    print('  %6.1f %s      %s %s)' % (s, l[6:14], m.group(1),
                                                       m.group(2)))


if __name__ == '__main__':
    main()
