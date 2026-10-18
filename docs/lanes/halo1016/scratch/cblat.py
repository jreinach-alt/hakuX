#!/usr/bin/env python3
"""The PFIFO callback-latency lines (cblat, perflog builds) around the plateau, per arm.

usage: cblat.py <result dir> [lo hi]   (seconds after `mark cinematic`, default 100 220)

Prints each cblat window inside [mark+lo, mark+hi]: flips, callbacks n, latency mean/p50/p90/max (ms),
the split's pnop/pidle/pflip/mdraw/mclear/mother/rest (ms over the window) and the callback params.
Then the totals over [mark+131, mark+191] per flip. Read-only; prints, writes nothing.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from cineread import ts  # noqa: E402

d = sys.argv[1]
lo, hi = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (100.0, 220.0)
mark = None
rows = []
with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
    for line in f:
        if mark is None and 'mark cinematic' in line:
            mark = ts(line)
        elif mark is not None and 'cblat win=' in line:
            t = ts(line) - mark
            r = {'t': t}
            for k in ('win', 'flips', 'n'):
                r[k] = float(re.search(r'\b%s=([\d.]+)' % k, line).group(1))
            m = re.search(r'lat\(mean=([\d.]+) p50=([\d.]+) p90=([\d.]+) max=([\d.]+)\)', line)
            r['mean'], r['p50'], r['p90'], r['max'] = map(float, m.groups())
            sp = re.search(r'split\(([^)]*)\)', line).group(1)
            for kv in sp.split():
                k, v = kv.split('=')
                r[k] = float(v)
            r['params'] = re.search(r'params=(\S+)', line).group(1)
            rows.append(r)

print('arm', os.path.basename(d.rstrip('/')), 'mark', mark)
print('| t-mark | win ms | flips | n | lat mean | p50 | p90 | max | pnop | pidle | pflip | mdraw | mclear | mother | rest | fin | params |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for r in rows:
    if lo <= r['t'] <= hi:
        print('| %.0f | %.0f | %.0f | %.0f | %.2f | %.2f | %.2f | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %s |' % (
            r['t'], r['win'], r['flips'], r['n'], r['mean'], r['p50'], r['p90'], r['max'], r['pnop'], r['pidle'],
            r['pflip'], r['mdraw'], r['mclear'], r['mother'], r['rest'], r['fin'], r['params']))
sel = [r for r in rows if 131 <= r['t'] <= 191]
fl = sum(r['flips'] for r in sel) or 1
print('\nover [mark+131, mark+191]: %d windows, %.0f flips, %.0f callbacks (%.2f a flip)' % (
    len(sel), fl, sum(r['n'] for r in sel), sum(r['n'] for r in sel) / fl))
for k in ('span', 'pnop', 'pidle', 'pflip', 'mdraw', 'mclear', 'mother', 'rest', 'fin', 'dl'):
    print('  %s per flip: %.2f ms' % (k, sum(r.get(k, 0) for r in sel) / fl))
print('  lat mean (n-weighted): %.2f ms' % (sum(r['mean'] * r['n'] for r in sel) / max(1, sum(r['n'] for r in sel))))
