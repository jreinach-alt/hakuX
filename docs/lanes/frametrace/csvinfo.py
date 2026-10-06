#!/usr/bin/env python3
"""One line per frametrace CSV: frames, span, period median, interval, classes.

    csvinfo.py <csv> [...]
"""
import collections
import csv
import statistics
import sys

for f in sys.argv[1:]:
    rows = list(csv.DictReader(open(f)))
    if not rows:
        print(f, 'empty')
        continue
    t0, t1 = int(rows[0]['t_ns']), int(rows[-1]['t_ns'])
    P = [int(r['P']) / 1000 for r in rows]
    cls = collections.Counter(r['cls'] for r in rows)
    print('%s frames=%d span=%.0fs t0_ms=%.1f P50=%.1f ireq=%s cls=%s' % (
        f, len(rows), (t1 - t0) / 1e9, t0 / 1e6, statistics.median(P),
        rows[-1]['ireq'], dict(cls)))
