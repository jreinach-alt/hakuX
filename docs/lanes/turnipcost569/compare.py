#!/usr/bin/env python3
"""Report an interleaved A|B vkharness run.

    compare.py <tag.tsv>

Per pipeline: median CPU ms of A and B, the A/B factor, and the per-stage
medians. Factors use thread CPU time (preemption excluded); wall medians are
printed beside them. Summary lines give the geometric mean of the per-pipeline
factors over the fixed set (+gtri) and over all rows.
"""
import csv
import math
import statistics
import sys
from collections import OrderedDict, defaultdict

rows = defaultdict(list)
order = OrderedDict()
with open(sys.argv[1]) as f:
    for r in csv.DictReader(f, delimiter="\t"):
        side, name = r["name"].split("|", 1)
        rows[(side, name)].append(r)
        order[name] = 1


def med(side, name, k):
    rs = rows.get((side, name), [])
    return statistics.median(float(r[k]) for r in rs) if rs else float("nan")


print("| pipeline | A cpu ms | B cpu ms | A/B | A wall | B wall | A VS/GS/FS | B VS/GS/FS |")
print("|---|---|---|---|---|---|---|---|")
facs, fixed = [], []
for n in order:
    a, b = med("A", n, "cpu_ms"), med("B", n, "cpu_ms")
    fac = a / b
    facs.append(fac)
    if n.endswith("+gtri"):
        fixed.append((n, a, b, fac))
    st = lambda s: "/".join(f"{med(s, n, k):.0f}" for k in ("fb_vs_ms", "fb_gs_ms", "fb_fs_ms"))
    print(f"| {n} | {a:.1f} | {b:.1f} | {fac:.2f}x | {med('A', n, 'wall_ms'):.1f} | "
          f"{med('B', n, 'wall_ms'):.1f} | {st('A')} | {st('B')} |")
gm = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
if fixed:
    print(f"\nfixed set (+gtri, n={len(fixed)}): A median {statistics.median(x[1] for x in fixed):.1f} ms, "
          f"B median {statistics.median(x[2] for x in fixed):.1f} ms, "
          f"geomean A/B {gm([x[3] for x in fixed]):.2f}x, "
          f"sum A/B {sum(x[1] for x in fixed) / sum(x[2] for x in fixed):.2f}x")
print(f"all rows (n={len(facs)}): geomean A/B {gm(facs):.2f}x")
