#!/usr/bin/env python3
"""Tabulate the sampled per-frame xemu-work fields (Fin:*, S2T, RP, QS) of a
perflog soak, split into a menu window and a demo window by seconds since the
first xemu-work line.

xemu-work is printed once per 60 guest frames and carries ONE frame's counts
(the frame it was printed on), so each line is a sample, not a 60-frame sum.

Usage: python3 workread.py <logcat.txt> [demo_start_s=130] [demo_end_s=270]
"""
import collections
import re
import sys
from datetime import datetime

path = sys.argv[1]
d0 = float(sys.argv[2]) if len(sys.argv) > 2 else 130.0
d1 = float(sys.argv[3]) if len(sys.argv) > 3 else 270.0
T = re.compile(r'^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+) I/xemu-work\(\s*\d+\): (.*)$')
t0 = None
win = {'menu': [], 'demo': []}
for ln in open(path, errors='replace'):
    m = T.match(ln)
    if not m:
        continue
    t = datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S.%f')
    if t0 is None:
        t0 = t
    s = (t - t0).total_seconds()
    f = dict(re.findall(r'(\w+):?([\d/]+)', m.group(2).replace('Fin:', '')))
    key = 'demo' if d0 <= s < d1 else ('menu' if s < d0 else None)
    if key:
        win[key].append((s, m.group(2)))
for key, rows in win.items():
    print('== %s: %d samples' % (key, len(rows)))
    fins = collections.Counter()
    for s, body in rows:
        fin = body.split('Fin:', 1)[1]
        nz = ' '.join(x for x in fin.split() if not x.endswith('0') or x[-2:].isdigit() and int(re.sub(r'\D', '', x) or 0))
        fins[nz] += 1
    for k, n in fins.most_common(12):
        print('  %4d  %s' % (n, k))
    s2t = collections.Counter(re.search(r'S2T:(\S+)', b).group(1) for _, b in rows)
    print('  S2T', dict(s2t.most_common(8)))
