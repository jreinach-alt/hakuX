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

Every row also carries `golden_colours`: how many distinct colours the
*golden* holds over the pixels where we differ.  That is the capture's
discriminating power, and it is a different question from how wrong we are.
When it is **one**, the golden is flat everywhere the disagreement is, so
every wrong model scores identically and the only thing the capture can say
is pass or fail.  Such a capture is safe to verify against and unsafe to fit
to, and its channel count must never drive a ranking -- the number is the
size of a region, not the size of a defect (`Fog_gen`'s six `VS radial`
captures are 2.17M channels of one flat colour; the fog distance fitted to
them scored 94.9% and was wrong).  Two colours is already a partition with a
boundary in it and discriminates perfectly well, so the threshold is one and
not "few": `DotSTR3D_0to1`'s golden holds two colours where we differ and
pins the texel rule to exact per-corner counts.

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


def golden_colours(gold, differing):
    """Distinct colours the golden holds over the pixels where we differ.

    One means the golden is flat across the whole disagreement: it can say
    pass or fail and nothing else.
    """
    import numpy as np
    px = gold[differing]
    if px.size == 0:
        return 0
    key = ((px[:, 0].astype(np.int64) << 16)
           | (px[:, 1].astype(np.int64) << 8)
           | px[:, 2].astype(np.int64))
    return int(np.unique(key).size)


def classify(ours, gold):
    import numpy as np
    d = ours.astype(np.int16) - gold.astype(np.int16)
    nz = d != 0
    n = int(nz.sum())
    if n == 0:
        return "exact", 0, 0, 0, 0, 0
    cols = golden_colours(gold, nz.any(axis=2))
    band = int(nz[boundary_shift_mask(ours, gold)].sum())
    if band == n:
        return "boundary-shift", n, 0, 0, band, cols
    v = d[nz]
    pos = int((v == 1).sum())
    neg = int((v == -1).sum())
    if pos + neg != n:
        return "structural", n, pos, neg, band, cols
    share = pos / n
    if share >= 0.8:
        return "one-step-hi", n, pos, neg, band, cols
    if share <= 0.2:
        return "one-step-lo", n, pos, neg, band, cols
    return "one-step-sym", n, pos, neg, band, cols


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
            # RGBA, not RGB. A *_ZB capture stores the zeta word as
            # A<<16 | R<<8 | G with stencil in B, so dropping alpha drops the
            # TOP BYTE of every depth value -- the classes below would then be
            # computed on two thirds of the number they claim to describe.
            # That is not hypothetical: the same omission in an earlier
            # analysis is what put a "28 captures, 270,650 channels
            # unfalsifiable" row into unfalsifiable-goldens.md for a cell whose
            # goldens actually hold 57 to 168 distinct depth words.
            #
            # score_sweep.py has always used RGBA, so this also makes the two
            # tools agree about what a differing pixel is.
            #
            # MEASURED IMPACT: none on the classification. Rerunning both the
            # 144-capture current-disc set and the full 784-capture oracle with
            # and without alpha gives byte-identical class counts -- 34/24/86
            # and 108/148/528 respectively -- and moves the differing-pixel
            # total by 96 of 2,608,760. A capture that differs in alpha
            # essentially always differs in RGB too, so the class was already
            # decided by the RGB difference. The change is right on the
            # semantics and does not invalidate any classification taken
            # before it; recorded so nobody re-derives that conclusion from
            # the reasoning alone.
            a = np.asarray(Image.open(os.path.join(d, name)).convert("RGBA"))
            b = np.asarray(Image.open(gold_path).convert("RGBA"))
            if a.shape != b.shape:
                continue
            seen.add((suite, test))
            kind, n, pos, neg, band, cols = classify(a, b)
            rows.append((suite, test, kind, n, pos, neg, band, cols))

    per_suite = defaultdict(lambda: defaultdict(int))
    band_px = defaultdict(lambda: [0, 0])
    for suite, _, kind, n, _, _, band, _ in rows:
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

    flat = defaultdict(lambda: [0, 0, 0, 0])
    for suite, _, _, n, _, _, _, cols in rows:
        if not n:
            continue
        flat[suite][0] += n
        flat[suite][2] += 1
        if cols == 1:
            flat[suite][1] += n
            flat[suite][3] += 1
    ranked = sorted(flat.items(), key=lambda kv: -kv[1][1])
    ranked = [r for r in ranked if r[1][1]]
    if ranked:
        print()
        print("channels whose golden holds ONE colour where we differ -- pass/fail")
        print("only, never a ranking weight:")
        print(f"{'suite':{width}} {'channels':>12} {'flat':>12} {'share':>7} {'caps':>6}")
        tot = sum(v[0] for v in flat.values())
        tflat = sum(v[1] for v in flat.values())
        for suite, (n, fl, caps, fcaps) in ranked:
            print(f"{suite:{width}} {n:>12} {fl:>12} "
                  f"{100.0 * fl / n:6.1f}% {fcaps:>3}/{caps:<3}")
        print(f"{'TOTAL':{width}} {tot:>12} {tflat:>12} "
              f"{100.0 * tflat / tot if tot else 0:6.1f}%")

    if args.tsv:
        with open(args.tsv, "w") as f:
            f.write("suite\ttest\tclass\tdiffering_channels\tplus_one\tminus_one"
                    "\tboundary_shift_channels\tgolden_colours\n")
            for r in rows:
                f.write("\t".join(str(x) for x in r) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
