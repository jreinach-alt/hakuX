#!/usr/bin/env python3
"""DOA's lit share and B1's modelled saving, from a doa_manifest.py vkharness run.

    doa_share.py <run.tsv>

Medians per pipeline and side (thread CPU ms, and the creation-feedback VS
stage ms). Each distinct vertex module is weighted once: the keys file lists
modules, not how many pipelines used each, so this is a per-module share.
"""
import csv
import statistics
import sys
from collections import defaultdict

rows = defaultdict(list)
for r in csv.DictReader(open(sys.argv[1]), delimiter="\t"):
    side, name = r["name"].split("|", 1)
    rows[(side, name)].append(r)
names = sorted({n for _, n in rows})
med = lambda s, n, k: statistics.median(float(r[k]) for r in rows[(s, n)])
tot = defaultdict(float)
for n in names:
    grp = "lit" if n.startswith("lit-changed") else "other"
    for s in "AB":
        tot[(s, grp, "cpu")] += med(s, n, "cpu_ms")
        tot[(s, grp, "vs")] += med(s, n, "fb_vs_ms")
        tot[(s, grp, "gs")] += med(s, n, "fb_gs_ms")
nlit = sum(1 for n in names if n.startswith("lit-changed"))
for k in ("cpu", "vs", "gs"):
    a = tot[("A", "lit", k)] + tot[("A", "other", k)]
    b = tot[("B", "lit", k)] + tot[("B", "other", k)]
    print(f"{k:4s} A lit {tot[('A','lit',k)]:8.0f} other {tot[('A','other',k)]:7.0f} "
          f"| B lit {tot[('B','lit',k)]:7.0f} other {tot[('B','other',k)]:7.0f} "
          f"| lit share of A {tot[('A','lit',k)]/a:6.1%} | A/B all {a/b:5.2f}x "
          f"| A/B lit {tot[('A','lit',k)]/tot[('B','lit',k)]:5.2f}x")
print(f"pipelines: {len(names)}, lit-changed {nlit}")
