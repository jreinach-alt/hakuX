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
  boundary-shift
                every differing pixel lies in an isolated one-pixel band (the
                rows or columns either side agree with the golden) and equals
                the golden's neighbour across the band.  A quantisation
                boundary that landed one pixel over: a texel edge on an exact
                tie, a colour step, a depth compare, a snapped vertex.  These
                are the same shape whatever produced them, and they are the
                precision floor of interpolation, not a rule to derive
                (docs/investigations/edge-defect.md).  Checked before the
                one-step classes because shape says more than magnitude: a
                texel tie on a smooth gradient is a one-step difference too.
  structural    some channel differs by more than one step.

The distinction matters because the two one-step classes want opposite
corrections: truncating the shader output moves one-step-hi toward the
hardware and one-step-sym away from it (issue #38).  The TSV also carries
the boundary-shift channel count for every capture, so a sweep can report
how much of a structural capture is the band and how much is the residual.

Usage:
  classify_residuals.py RESULTS_DIR [RESULTS_DIR ...] --goldens DIR [--tsv OUT]

Each RESULTS_DIR holds "<Suite>::<Test>.png" as written by run_disc.sh.  A
capture seen in more than one directory is counted once, from the first.
"""
import argparse
import os
import sys
from collections import defaultdict

CLASSES = ["exact", "boundary-shift", "one-step-hi", "one-step-lo",
           "one-step-sym", "structural"]


def _shifted_eq(a, b, dy, dx):
    """a[y, x] == b[y + dy, x + dx] wherever both are in range."""
    import numpy as np
    h, w = a.shape[:2]
    out = np.zeros((h, w), bool)
    ys = slice(max(0, -dy), h - max(0, dy))
    xs = slice(max(0, -dx), w - max(0, dx))
    ys2 = slice(max(0, dy), h - max(0, -dy))
    xs2 = slice(max(0, dx), w - max(0, -dx))
    out[ys, xs] = (a[ys, xs] == b[ys2, xs2]).all(axis=2)
    return out


def boundary_shift_mask(ours, gold):
    """Differing pixels that are a one-pixel displacement of a boundary.

    A pixel qualifies when it differs, the rows (or columns) on either side
    of it agree with the golden at that x (or y), and our value equals the
    golden's value one pixel above or below (or left or right).  Requiring
    the band to be isolated is what separates a displaced boundary from a
    one-step error inside a gradient, which would also match a neighbour.
    """
    import numpy as np
    d = (ours != gold).any(axis=2)
    iso_r = np.zeros_like(d)
    iso_r[1:-1] = ~d[:-2] & ~d[2:]
    iso_c = np.zeros_like(d)
    iso_c[:, 1:-1] = ~d[:, :-2] & ~d[:, 2:]
    vert = (_shifted_eq(ours, gold, 1, 0) | _shifted_eq(ours, gold, -1, 0)) & iso_r
    horiz = (_shifted_eq(ours, gold, 0, 1) | _shifted_eq(ours, gold, 0, -1)) & iso_c
    return d & (vert | horiz)


def classify(ours, gold):
    import numpy as np
    d = ours.astype(np.int16) - gold.astype(np.int16)
    nz = d != 0
    n = int(nz.sum())
    if n == 0:
        return "exact", 0, 0, 0, 0
    band = int(nz[boundary_shift_mask(ours, gold)].sum())
    if band == n:
        return "boundary-shift", n, 0, 0, band
    v = d[nz]
    pos = int((v == 1).sum())
    neg = int((v == -1).sum())
    if pos + neg != n:
        return "structural", n, pos, neg, band
    share = pos / n
    if share >= 0.8:
        return "one-step-hi", n, pos, neg, band
    if share <= 0.2:
        return "one-step-lo", n, pos, neg, band
    return "one-step-sym", n, pos, neg, band


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
            kind, n, pos, neg, band = classify(a, b)
            rows.append((suite, test, kind, n, pos, neg, band))

    per_suite = defaultdict(lambda: defaultdict(int))
    band_px = defaultdict(lambda: [0, 0])
    for suite, _, kind, n, _, _, band in rows:
        per_suite[suite][kind] += 1
        band_px[suite][0] += n
        band_px[suite][1] += band

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

    print()
    print(f"{'suite':{width}} {'differing':>12} {'boundary':>12} {'share':>7}")
    for suite in sorted(band_px):
        n, band = band_px[suite]
        share = f"{100.0 * band / n:6.1f}%" if n else "      -"
        print(f"{suite:{width}} {n:>12} {band:>12} {share:>7}")

    if args.tsv:
        with open(args.tsv, "w") as f:
            f.write("suite\ttest\tclass\tdiffering_channels\tplus_one\tminus_one"
                    "\tboundary_shift_channels\n")
            for r in rows:
                f.write("\t".join(str(x) for x in r) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
