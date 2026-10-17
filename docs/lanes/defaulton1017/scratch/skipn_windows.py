#!/usr/bin/env python3
"""Does the gap-1 gate's skipn explain HON's ms/f over EIF's? Per 10-s window from mark+100: each row's ms/f
(censusread) and HON's [rearly1018] w sums (early, skipn, cold, stale, vis) over the same seconds.
usage: skipn_windows.py <HON dir> <EIF dir> [<more rows>...]"""
import os
import re
import sys

LANES = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(LANES, 'halo1016'))
from cineread import ts  # noqa: E402
from vcpuread import VArm  # noqa: E402

K = ('early', 'skipn', 'skip0', 'cold', 'stale', 'vis')


def rwin(d):
    out = []
    for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        if '[rearly1018] w ' in line:
            out.append((ts(line), {k: int(v) for k, v in re.findall(r' (\w+)=(\d+)', line.split('] w', 1)[1])}))
    return out


arms = [VArm(d) for d in sys.argv[1:]]
wins = [rwin(d) for d in sys.argv[1:]]
print('| +s | ' + ' | '.join('%s ms/f' % a.name[-12:] for a in arms) + ' | ' +
      ' | '.join('%s %s' % (a.name[-7:], k) for a in arms[:1] for k in K) + ' | frames |')
print('|---' * (2 + len(arms) + len(K)) + '|')
for lo in range(60, 260, 10):
    row = []
    for a in arms:
        row.append('%.1f' % a.msf(a.mark + lo, a.mark + lo + 8.0))
    a, w = arms[0], wins[0]
    s = dict.fromkeys(K, 0)
    for t, kv in w:
        if t is not None and a.mark + lo < t <= a.mark + lo + 10:
            for k in K:
                s[k] += kv.get(k, 0)
    fr = (a.frame_at(a.mark + lo + 10) or 0) - (a.frame_at(a.mark + lo) or 0)
    print('| +%d | %s | %s | %d |' % (lo, ' | '.join(row), ' | '.join(str(s[k]) for k in K), fr))
