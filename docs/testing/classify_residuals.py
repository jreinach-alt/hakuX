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


# The depth decode and the z16/z24 test-name rule live in score_sweep.py and
# are IMPORTED rather than copied. Two copies of a packed-format decode is how
# the two tools came to disagree about what a differing pixel is in the first
# place: score_sweep has always decoded, this file never did. A copy would fix
# today's disagreement and re-create the mechanism that produced it.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from score_sweep import decode_depth as _decode_depth, \
        depth_bits as _depth_bits
except ImportError:      # pragma: no cover - score_sweep is a sibling file
    _decode_depth = _depth_bits = None


def _is_zb(test):
    """Is this capture a zeta surface? Same test score_sweep.py:143 uses."""
    return test.endswith("_ZB")


def golden_colours(gold, differing, zb_bits=None):
    """Distinct VALUES the golden holds over the pixels where we differ.

    One means the golden is flat across the whole disagreement: it can say
    pass or fail and nothing else.

    For a ``_ZB`` capture the value is the decoded depth word, not the RGB
    triple. Keying on ``R<<16 | G<<8 | B`` is wrong there in a way that is
    worse than a truncation: for z24 the zeta word is ``A<<16 | R<<8 | G``
    with the stencil in B, so that key hashes the middle byte, the low byte
    and the STENCIL while dropping the depth's top byte entirely. Two pixels
    a whole megabyte apart in depth collide if their stencils match. For z16
    the word is packed 5/6/5 across all three channels, so the RGB key is a
    bijection there and the count is unaffected -- but decoding is still the
    honest thing, and it makes the two branches say the same kind of thing.
    """
    import numpy as np
    if zb_bits:
        word, _ = _decode_depth(gold, zb_bits)
        px = word[differing]
        return 0 if px.size == 0 else int(np.unique(px).size)
    px = gold[differing]
    if px.size == 0:
        return 0
    key = ((px[:, 0].astype(np.int64) << 16)
           | (px[:, 1].astype(np.int64) << 8)
           | px[:, 2].astype(np.int64))
    return int(np.unique(key).size)


def classify(ours, gold, zb_bits=None):
    """Classify one capture. ``zb_bits`` is 16 or 24 for a ``_ZB`` capture.

    WHY THE ``_ZB`` BRANCH EXISTS, and it is the reason two issues carried a
    wrong label for a day. Without it this function differences CHANNELS, and
    a one-step class is then unreachable for a packed depth word:

      - z16 is RGB565, so one unit of depth moves B by a lattice STEP of 8
        (9 where it rounds), and on the pixels where B wraps 31 -> 0 the carry
        appears as +4 in G and -255 in B. Measured on #52's z16 float cell:
        1,436 differing pixels, every one of them EXACTLY ONE ULP of depth,
        and **zero** channels at |delta| == 1. The histogram is
        {+8: 1084, +9: 304, +4: 48, -255: 48}.
      - z24 is A<<16 | R<<8 | G, so +1 in depth reads as an ordinary +1 in G
        until G wraps, where it reads as -255 with a carry into R. That exact
        symptom is already recorded on #52's z24 cell.

    So "float Z is structural -- not one of F16's 469,927 channels is one
    step" was an artefact of this function, not a property of the renderer.
    Both cells are sub-ULP precision floors. An oracle that mislabels a floor
    as a rule sends agents to look for a rule.

    ``int64`` rather than ``int16``: a 24-bit word does not fit, and the
    difference of two of them needs 25 bits plus a sign.
    """
    import numpy as np
    if zb_bits:
        ours_w, ours_s = _decode_depth(ours, zb_bits)
        gold_w, gold_s = _decode_depth(gold, zb_bits)
        # Depth and stencil are two quantities; stack them so a stencil-only
        # disagreement is still counted, and neither is averaged into the
        # other.
        ours = np.stack([ours_w, ours_s], axis=-1)
        gold = np.stack([gold_w, gold_s], axis=-1)
    d = ours.astype(np.int64) - gold.astype(np.int64)
    nz = d != 0
    n = int(nz.sum())
    if n == 0:
        return "exact", 0, 0, 0, 0, 0
    # For a _ZB capture `gold` is already the decoded (word, stencil) stack,
    # so count distinct depth words directly; otherwise count golden colours.
    if zb_bits:
        cols = int(np.unique(gold_w[nz.any(axis=2)]).size)
    else:
        cols = golden_colours(gold, nz.any(axis=2))
    # boundary_shift_mask compares neighbouring PIXELS of an image and is
    # shape-agnostic, but its meaning is "the golden's value one pixel over",
    # which is exactly as valid on a decoded depth word as on a colour.
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
            # A *_ZB capture is a zeta surface, not a colour image, and must
            # be differenced as a decoded depth word. score_sweep.py has
            # always done this; this tool never did, which is why #16 and #52
            # both carried a "structural" label for a residual that is one ULP.
            zb = _depth_bits(test) if _is_zb(test) else None
            kind, n, pos, neg, band, cols = classify(a, b, zb)
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
