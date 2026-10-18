#!/usr/bin/env python3
"""Two desktop suite arms against each other and against the goldens (#1049).

usage: arm_diff.py A_RESULTS B_RESULTS GOLDENS [--tsv OUT]

A_RESULTS and B_RESULTS are extract_results.py output dirs
(Suite::Test.png); GOLDENS is goldens/results (Suite/Test.png). Per test:
whether A and B are bit-identical over RGBA, and each arm's differing-pixel
count against the golden. The arm pair is the claim (R1 changes no pixel);
the golden counts say whether either arm is broken in a way the pair hides.
Prints the totals and every test where the arms differ or a golden is
missing; --tsv writes one row per test.
"""
import os
import sys

import numpy as np
from PIL import Image


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"))


def ndiff(x, y):
    if x.shape != y.shape:
        return -1
    return int(np.any(x != y, axis=2).sum())


def main():
    a = sys.argv[1:]
    tsv = None
    if "--tsv" in a:
        i = a.index("--tsv")
        tsv = a[i + 1]
        del a[i:i + 2]
    ra, rb, gold = a
    names = sorted(n for n in os.listdir(ra) if n.endswith(".png"))
    missing_b = [n for n in names if not os.path.exists(os.path.join(rb, n))]
    rows = []
    for n in names:
        if n in missing_b:
            continue
        suite, test = n.split("::", 1)
        ia, ib = load(os.path.join(ra, n)), load(os.path.join(rb, n))
        g = os.path.join(gold, suite, test)
        if os.path.exists(g):
            ig = load(g)
            ga, gb = ndiff(ia, ig), ndiff(ib, ig)
        else:
            ga = gb = None
        rows.append((suite, test, ndiff(ia, ib), ga, gb))
    same = sum(1 for r in rows if r[2] == 0)
    nogold = sum(1 for r in rows if r[3] is None)
    gexact_a = sum(1 for r in rows if r[3] == 0)
    gexact_b = sum(1 for r in rows if r[4] == 0)
    print(f"tests {len(rows)} (A {len(names)}, missing in B {len(missing_b)}); "
          f"A==B bit-identical {same}; no golden {nogold}; "
          f"golden-exact A {gexact_a} B {gexact_b}")
    for n in missing_b:
        print(f"  missing in B: {n}")
    for r in rows:
        if r[2] != 0:
            print(f"  A!=B {r[0]}::{r[1]} arm-diff {r[2]} px; "
                  f"vs golden A {r[3]} B {r[4]}")
    if tsv:
        with open(tsv, "w") as f:
            f.write("suite\ttest\tarm_diff\tgold_a\tgold_b\n")
            for r in rows:
                f.write("\t".join("" if v is None else str(v) for v in r) + "\n")


if __name__ == "__main__":
    main()
