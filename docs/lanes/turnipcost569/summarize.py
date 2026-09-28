#!/usr/bin/env python3
"""Per-pipeline medians of a vkharness TSV.

    summarize.py <run.tsv> [<run.tsv> ...]   (one column block per run)
"""
import csv
import statistics
import sys
from collections import OrderedDict


def load(path):
    rows = OrderedDict()
    with open(path) as f:
        for r in csv.DictReader(f, delimiter="\t"):
            rows.setdefault(r["name"], []).append(r)
    out = OrderedDict()
    for name, rs in rows.items():
        med = lambda k: statistics.median(float(r[k]) for r in rs)
        out[name] = dict(n=len(rs), wall=med("wall_ms"), vs=med("fb_vs_ms"),
                         fs=med("fb_fs_ms"), gs=med("fb_gs_ms"),
                         lo=min(float(r["wall_ms"]) for r in rs),
                         hi=max(float(r["wall_ms"]) for r in rs))
    return out


runs = [load(p) for p in sys.argv[1:]]
print("| pipeline | " + " | ".join(
    f"wall ms (min-max) | VS | GS | FS" for _ in runs) + " |")
print("|---|" + "---|---|---|---|" * len(runs))
for name in runs[0]:
    cells = []
    for run in runs:
        d = run.get(name)
        if not d:
            cells.append("- | - | - | -")
            continue
        cells.append(f"{d['wall']:.1f} ({d['lo']:.1f}-{d['hi']:.1f}) | {d['vs']:.1f} | "
                     f"{d['gs']:.1f} | {d['fs']:.1f}")
    print(f"| {name} | " + " | ".join(cells) + " |")
for i, run in enumerate(runs):
    fixed = [d["wall"] for n, d in run.items() if n.endswith("+gtri")]
    if fixed:
        print(f"\nrun {i}: fixed set n={len(fixed)} median {statistics.median(fixed):.1f} ms, "
              f"mean {statistics.mean(fixed):.1f}, min {min(fixed):.1f}, max {max(fixed):.1f}")
