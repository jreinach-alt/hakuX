#!/usr/bin/env python3
"""Classify each capture's difference from its golden by shape, not size.

A count of differing pixels says how far a capture is from the hardware; it
does not say what kind of wrong it is.  This splits the differences into
classes that call for different fixes, and the useful signal turns out to be
the *sign* distribution of the one-step differences:

  exact         no channel differs.
  one-step-hi   every differing channel is +-1 and at least 4/5 are +1.
                Ours reads one high: a quantisation or rounding difference,
                where the hardware truncates a value we round.
  one-step-lo   the mirror of that, ours reads one low.
  one-step-sym  every differing channel is +-1 and neither sign dominates.
                Not a rounding rule -- a rounding rule is one-directional.
                Our computed value sits a fraction of a step either side of
                the hardware's, so this is arithmetic or filter precision.
  structural    some channel differs by more than one step.

The distinction matters because the two one-step classes want opposite
corrections: truncating the shader output moves one-step-hi toward the
hardware and one-step-sym away from it (issue #38).

Usage:
  classify_residuals.py RESULTS_DIR [RESULTS_DIR ...] --goldens DIR [--tsv OUT]

Each RESULTS_DIR holds "<Suite>::<Test>.png" as written by run_disc.sh.  A
capture seen in more than one directory is counted once, from the first.
"""
import argparse
import os
import sys
from collections import defaultdict

CLASSES = ["exact", "one-step-hi", "one-step-lo", "one-step-sym", "structural"]


def classify(ours, gold):
    import numpy as np
    d = ours.astype(np.int16) - gold.astype(np.int16)
    nz = d != 0
    n = int(nz.sum())
    if n == 0:
        return "exact", 0, 0, 0
    v = d[nz]
    pos = int((v == 1).sum())
    neg = int((v == -1).sum())
    if pos + neg != n:
        return "structural", n, pos, neg
    share = pos / n
    if share >= 0.8:
        return "one-step-hi", n, pos, neg
    if share <= 0.2:
        return "one-step-lo", n, pos, neg
    return "one-step-sym", n, pos, neg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--goldens", required=True)
    ap.add_argument("--tsv")
    args = ap.parse_args(argv)

    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        sys.exit(f"needs numpy and pillow: {e}")

    seen = set()
    rows = []
    for d in args.results:
        for name in sorted(os.listdir(d)):
            if not name.endswith(".png") or "::" not in name:
                continue
            suite, test = name[:-4].split("::", 1)
            if (suite, test) in seen:
                continue
            gold_path = os.path.join(args.goldens, suite, test + ".png")
            if not os.path.exists(gold_path):
                continue
            a = np.asarray(Image.open(os.path.join(d, name)).convert("RGB"))
            b = np.asarray(Image.open(gold_path).convert("RGB"))
            if a.shape != b.shape:
                continue
            seen.add((suite, test))
            kind, n, pos, neg = classify(a, b)
            rows.append((suite, test, kind, n, pos, neg))

    per_suite = defaultdict(lambda: defaultdict(int))
    for suite, _, kind, _, _, _ in rows:
        per_suite[suite][kind] += 1

    width = max([len(s) for s in per_suite] + [5])
    print(f"{'suite':{width}} " + " ".join(f"{c:>12}" for c in CLASSES))
    for suite in sorted(per_suite):
        counts = per_suite[suite]
        print(f"{suite:{width}} " + " ".join(f"{counts[c]:>12}" for c in CLASSES))
    totals = defaultdict(int)
    for counts in per_suite.values():
        for c in CLASSES:
            totals[c] += counts[c]
    print(f"{'TOTAL':{width}} " + " ".join(f"{totals[c]:>12}" for c in CLASSES))

    if args.tsv:
        with open(args.tsv, "w") as f:
            f.write("suite\ttest\tclass\tdiffering_channels\tplus_one\tminus_one\n")
            for r in rows:
                f.write("\t".join(str(x) for x in r) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
