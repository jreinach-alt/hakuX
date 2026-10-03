#!/usr/bin/env python3
"""Tabulate hakuX-pace lines against offset from the route mark.

usage: pacetab.py <result-copy> [bucket_s]
Prints one row per pace line (60 flips): offset s, ms, fps, vblank histogram.
Then a per-bucket summary: share of 60-flip windows >= 30 fps (ms <= 2000+tol).
"""
import re, sys, os, datetime

d = sys.argv[1]
bucket = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
m = re.search(r'ROUTE (\d+:\d+:\d+\.\d+) mark gameplay', runlog)
end = re.search(r'ROUTE (\d+:\d+:\d+\.\d+) end', runlog)


def t(s):
    h, mi, se = s.split(':')
    return int(h) * 3600 + int(mi) * 60 + float(se)


mark = t(m.group(1))
tend = t(end.group(1)) if end else None
rows = []
pat = re.compile(r'^\d+-\d+ (\d+:\d+:\d+\.\d+) I/hakuX-pace\(\d+\): f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) max=([\d.]+) ms=([\d.]+)')
for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
    mm = pat.match(line)
    if not mm:
        continue
    ts = t(mm.group(1))
    if ts < mark - 120:
        continue
    f, v0, v1, v2, v3, v4, vb = map(int, mm.groups()[1:8])
    mx, ms = float(mm.group(9)), float(mm.group(10))
    rows.append((ts - mark, f, v0, v1, v2, v3, v4, vb, mx, ms))

if '-v' in sys.argv:
    for r in rows:
        print('off=%7.1f f=%6d fps=%5.1f v0-4=%2d %2d %2d %2d %2d vb=%4d max=%7.1f' % (
            r[0], r[1], 60000.0 / r[9], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
b = {}
for r in rows:
    if r[0] < 0:
        continue
    k = int(r[0] // bucket)
    b.setdefault(k, []).append(r)
print('bucket_s=%g  (fps = 60 flips / window ms; ok = fps >= 29.5)' % bucket)
for k in sorted(b):
    rs = b[k]
    fps = [60000.0 / r[9] for r in rs]
    ok = sum(1 for x in fps if x >= 29.5)
    v3p = sum(r[5] + r[6] for r in rs)
    v1 = sum(r[3] for r in rs)
    print('%5d-%5ds n=%2d fps min/med/max=%5.1f %5.1f %5.1f ok=%2d/%2d v1=%4d v3+=%4d maxms=%6.1f' % (
        k * bucket, (k + 1) * bucket, len(rs), min(fps), sorted(fps)[len(fps) // 2], max(fps), ok, len(rs), v1, v3p, max(r[8] for r in rs)))
