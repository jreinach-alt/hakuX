#!/usr/bin/env python3
"""Summarise ccost.tsv: per pipeline, spec vs uber cpu ms and FS-stage ms
(median over whatever reps completed).   ccost_summary.py ccost.tsv"""
import collections
import statistics
import sys

rows = collections.defaultdict(list)
for line in open(sys.argv[1]):
    f = line.split()
    if len(f) < 8 or f[0] == "name":
        continue
    rows[f[0]].append((float(f[3]), float(f[6])))


def med(k, i):
    return statistics.median(r[i] for r in rows[k])


print("| pipeline | reps | cpu ms spec | cpu ms uber | x | FS ms spec | FS ms uber | x |")
print("|---|---|---|---|---|---|---|---|")
for k in sorted({k.rsplit("+", 1)[0] for k in rows}):
    a, b = k + "+spec", k + "+uber"
    if a in rows and b in rows:
        cs, cu, fs, fu = med(a, 0), med(b, 0), med(a, 1), med(b, 1)
        print("| %s | %d | %.0f | %.0f | %.1f | %.1f | %.0f | %.0f |" % (
            k, min(len(rows[a]), len(rows[b])), cs, cu, cu / cs, fs, fu, fu / fs))
