#!/usr/bin/env python3
"""The [rtrace] lines of one arm inside the plateau span, raw w windows and the r samples summarised.

usage: rtspan.py <result dir> [lo hi]   (seconds after `mark cinematic`, default 131 191)
Prints every `[rtrace] w` line in the span (time-stamped from the mark), then over the span's `[rtrace] r`
samples: count, report offsets by count, q2e/q2f/q2w quartiles (us), the frame lag fe-fq and fw-fq, and the
status word at queue/write. Read-only.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from cineread import ts  # noqa: E402

d = sys.argv[1]
lo, hi = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (131.0, 191.0)
mark = None
ws, rs = [], []
with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
    for line in f:
        if mark is None and 'mark cinematic' in line:
            mark = ts(line)
            continue
        if mark is None or '[rtrace]' not in line and '[rcatch1018]' not in line:
            continue
        t = ts(line) - mark
        if not lo <= t <= hi:
            continue
        if '[rtrace] w ' in line or '[rcatch1018]' in line:
            ws.append('%6.1f %s' % (t, line.split('): ', 1)[1].strip()))
        elif '[rtrace] r ' in line:
            rs.append(dict(re.findall(r'(\w+)=(\w+)', line.split('[rtrace] r ', 1)[1])))
print('mark', mark, '| w lines', len(ws), '| r samples', len(rs))
for w in ws:
    print(w)


def q(vals):
    v = sorted(vals)
    if not v:
        return '-'
    return 'p25 %d p50 %d p75 %d max %d' % (v[len(v) // 4], v[len(v) // 2], v[3 * len(v) // 4], v[-1])


print('\nr samples over the span:')
print('  offsets:', collections.Counter(r['off'] for r in rs).most_common(8))
for k in ('q2e', 'q2f', 'q2w'):
    print('  %s us: %s' % (k, q([int(r[k]) for r in rs if k in r])))
print('  fe-fq:', collections.Counter(int(r['fe']) - int(r['fq']) for r in rs).most_common(6))
print('  fw-fq:', collections.Counter(int(r['fw']) - int(r['fq']) for r in rs).most_common(6))
print('  stq/stw:', collections.Counter((r.get('stq'), r.get('stw')) for r in rs).most_common(6))
