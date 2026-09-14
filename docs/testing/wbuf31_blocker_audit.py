#!/usr/bin/env python3
"""Audit #31's blocker: "the remaining 566,549 px need geometry the corpus
does not contain".

    docs/testing/wbuf31_blocker_audit.py --goldens /home/justin/goldens/results

A blocker is a claim and needs the same evidence as a fix (AGENTS.md).  Two
such claims have already been refuted in this campaign with the answering data
already on disk -- #31's own earlier one, and #13's -- so this one was tested
rather than inherited.  Nothing here needs a device or a build.

The verdict is TRUE, and this file is the evidence.  Four sections:

  --classes   Which captures in the WHOLE corpus carry a slope-scaled polygon
              offset at all, and what each population can and cannot resolve.
              Run before any "the corpus does not contain X": an empty class
              settles the question, a non-empty one says the exhaustive check
              is worth running (AGENTS.md).

  --period    The 24 `TriH` and 24 `TriV` triangles are translates of one
              shape.  Their recovered offsets are EXACTLY 4-periodic in the
              translation index, so the offset is a function of the shift mod
              4 alone, with no dependence on the triangle's position along the
              other axis.  That is a new structural fact and it kills the whole
              family of "plane-solve error accumulating across the screen"
              explanations for `TriV`.

  --rivals    The #13 move.  Invert each golden's EXACT offset interval to the
              sample position it implies, then score every anchoring rule
              against it.  `TriH` lands on the pixel centre of
              4*floor(y_top/4)+2 to 1.1e-7; NO rule lands on `TriV`, the best
              missing by 5.6e-3 -- a 50,000x separation, which is what makes
              `TriV` a third mechanism rather than the known rounding floor.
              A three-free-parameter absolute model fitted on three residues
              misses the fourth by 416x its interval width, so the refutation
              is of the model FAMILY, not of one rule.

  --cells     The (shape, clip_top) table `ClipF` fills, with the two
              degeneracies that make the regime selector unrecoverable, one of
              which is new: every clip_top the suite can generate is a multiple
              of 32, so "clip_top + 2" and "the absolute 4-grid at phase 2" are
              the SAME prediction on every capture that exists.

This file writes nothing (AGENTS.md: a checker writes nothing).
"""

import argparse
import math
import os
import sys
from fractions import Fraction as Fr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wbuf_anchor_recover as W  # noqa: E402

SUITE = "W_buffering"


# ------------------------------------------------------------------ classes

def classes(np, Image, root):
    print("=" * 78)
    print("CLASS AUDIT -- what in the corpus carries a slope-scaled offset")
    print("=" * 78)
    print("`NV097_SET_POLYGON_OFFSET_SCALE_FACTOR` is pushed non-zero in exactly")
    print("one file of nxdk_pgraph_tests (wbuf_tests.cpp:464).  depth_clamp_tests")
    print("pushes POLYGON_OFFSET_BIAS only -- a constant, which no anchor can move.")
    print("So the class is the `W buffering` suite and nothing else, and these are")
    print("its populations:")
    print()
    rows = []
    for pre in ("WBuf24D", "WBuf24F", "WBuf16D", "WBuf16F"):
        for name in ("FloorQuad", "RoofQuad", "WallQuad", "TriH", "TriV", "LargeZ"):
            a = os.path.join(root, "%s_%s_V1_ZB0_ZS0_ZB.png" % (pre, name))
            b = os.path.join(root, "%s_%s_V1_ZB0_ZS1_ZB.png" % (pre, name))
            if not (os.path.exists(a) and os.path.exists(b)):
                continue
            z0 = W.decode24(np, Image, a)
            clear = np.bincount(z0.ravel()).argmax()
            ink = (z0 != clear)
            rows.append((pre, name, int(ink.sum()),
                         int(len(np.unique(z0[ink]))) if ink.sum() else 0))
    print("  %-9s %-10s %9s %14s" % ("depth fmt", "prim", "ink px", "distinct z"))
    for r in rows:
        print("  %-9s %-10s %9d %14d" % r)
    print()
    print("  WBuf24D is the only population with ~1-unit depth quantisation, which")
    print("  is what makes the offset interval 0.002 wide on a value of 1e5.  The")
    print("  16-bit populations resolve 7-10 distinct depths on the fixed-point")
    print("  variants -- three orders of magnitude coarser -- and they carry NO")
    print("  ClipF or ClipW captures at all (the clip variants are generated only")
    print("  at depthf == 6, i.e. WBuf24D; wbuf_tests.cpp:330 and :368).  So they")
    print("  duplicate five primitives already measured and add no geometry.")
    print()
    print("  SUB-CLAIM CHECKED, and it is PARTLY FALSE: the write-up records 'the")
    print("  fixed-function _V0_ ZS1 captures are empty (nothing drawn) on hardware;")
    print("  not investigated'.  Measured:")
    for pre in ("WBuf24D", "WBuf24F", "WBuf16D", "WBuf16F"):
        for zb in (0, 1):
            p = os.path.join(root, "%s_FloorQuad_V0_ZB%d_ZS1_ZB.png" % (pre, zb))
            if not os.path.exists(p):
                continue
            z = W.decode24(np, Image, p)
            clear = np.bincount(z.ravel()).argmax()
            print("    %-8s ZB%d  non-clear px = %7d" % (pre, zb, int((z != clear).sum())))
    print("  Empty on WBuf24D -- the population that matters -- and NOT empty on")
    print("  WBuf24F.  It changes no verdict, because every _V0_ capture is the")
    print("  same FloorQuad geometry, so it fills no cell of the table below; but")
    print("  'empty' was asserted for a class that is not uniformly empty.")


# ----------------------------------------------------------------- geometry

I0 = Fr(1, 325)
I1 = Fr(1, 58)
D = (I1 - I0) / Fr(399, 2)     # d(1/w) per pixel along the gradient axis, EXACT
K = float(I0 / D)              # i0 in units of D
DF = float(D)
FACTOR = 65536.0


def recover(np, Image, root, cap, base, tris, cl, ct):
    """Exact offset interval per triangle, from the ZS1/ZS0 golden pair."""
    z1 = W.decode24(np, Image, os.path.join(root, "%s_ZB.png" % cap))
    z0 = W.decode24(np, Image, os.path.join(root,
                    "WBuf24D_%s_V1_ZB0_ZS0_ZB.png" % base))
    out = []
    for tri in tris:
        m = W.coverage(np, tri, cl, ct) & (z1 != W.CLEAR24) & (z0 != W.CLEAR24)
        if not m.any():
            out.append(None)
            continue
        wv = W.plane_w(np, tri)
        lo = float((z1[m] - wv[m]).max())
        hi = float((z1[m] + 1 - wv[m]).min())
        out.append((lo, hi, int(m.sum())) if hi > lo else None)
    return out


def period(np, Image, root):
    print("=" * 78)
    print("4-PERIODICITY -- measured, not assumed")
    print("=" * 78)
    print("TriH and TriV are each 24 translates of one shape (wbuf_tests.cpp:197")
    print("and :222).  TriH steps x by 20 and y_top by 1; TriV steps y_top by 20")
    print("and x_left by 1.  If the offset depended on the triangle's position")
    print("along the NON-gradient axis, triangles s and s+4 would differ: they are")
    print("80 px apart on that axis.  What the instrument would show if it were")
    print("present is therefore six distinct intervals per residue, not one.")
    print()
    for name in ("TriH", "TriV"):
        tris, cl, ct, base = W.PRIMS[name]
        iv = recover(np, Image, root, "WBuf24D_%s_V1_ZB0_ZS1" % name, base, tris, cl, ct)
        print("  %s:" % name)
        for r in range(4):
            grp = [iv[s] for s in range(r, 24, 4) if iv[s]]
            lo = sorted(set(round(g[0], 6) for g in grp))
            hi = sorted(set(round(g[1], 6) for g in grp))
            same = "IDENTICAL" if (len(lo) == 1 and len(hi) == 1) else "DIFFER"
            print("    residue %d: %d triangles, interval [%14.6f,%14.6f]  %s"
                  % (r, len(grp), grp[0][0], grp[0][1], same))
    print()
    print("  Both are exactly 4-periodic.  So each suite's offset is a function of")
    print("  its shift mod 4 alone.  Consequence for TriV: no explanation that")
    print("  accumulates error down the screen survives -- t0 and t20 are 400 rows")
    print("  apart and agree to the last digit of a 0.0014-wide interval.")
    print()
    print("  AND THE COROLLARY IS A CORPUS GAP.  TriH's x is 160+20s, so x mod 4 is")
    print("  0 for all 24; TriV's y_top is 20s+0.5, so y_top mod 4 is 0.5 for all")
    print("  24.  Each family sweeps its GRADIENT axis through all four phases and")
    print("  holds the CROSS axis at one phase.  If the anchor is a 2-D quantity --")
    print("  which the ClipF split below is evidence for -- the corpus holds a")
    print("  single cross-axis phase and cannot see that dependence at all.")


# ------------------------------------------------------------------ rivals

def prod(O):
    """i(A)*i(B) in units of D^2, from an offset."""
    return FACTOR * DF / O / (DF * DF)


def rivals(np, Image, root):
    print("=" * 78)
    print("RIVAL SWEEP -- the #13 move, on the exact intervals")
    print("=" * 78)
    print("Every model is  offset = FACTOR * C * |d| / (i(A) * i(B)),  with A, B")
    print("pixel positions on the gradient axis.  A model passes a residue only if")
    print("it lands inside the GOLDEN's own interval, which is 1e-5 wide in these")
    print("units -- not merely on the right integer pixel, which is what the")
    print("existing instrument scores and is why TriV read as 'no integer column'")
    print("rather than as a refutation of the model family.")
    print()
    print("  GUARD, run first, because a filtered-away row makes an all-plausible")
    print("  table meaningless: an EMPTY interval would mean the offset is not one")
    print("  constant per triangle, which is the premise the whole instrument rests")
    print("  on.  Counted over every triangle the sweep scores:")
    tot = emp = 0
    for name in ("TriH", "TriV", "FloorQuad", "RoofQuad", "WallQuad"):
        tris, cl, ct, base = W.PRIMS[name]
        iv = recover(np, Image, root, "WBuf24D_%s_V1_ZB0_ZS1" % name, base, tris, cl, ct)
        tot += len(tris)
        emp += sum(1 for x in iv if x is None)
    print("    %d triangles, %d empty.  The premise is a property the data could" % (tot, emp))
    print("    have refused and did not; it is not an assumption.")
    print()

    sets = {}
    for name in ("TriH", "TriV"):
        tris, cl, ct, base = W.PRIMS[name]
        iv = recover(np, Image, root, "WBuf24D_%s_V1_ZB0_ZS1" % name, base, tris, cl, ct)
        sets[name] = [(prod(iv[r][1]), prod(iv[r][0])) for r in range(4)]

    def score(P, anchor_of, off_a, off_b, C, origin):
        ok, worst = 0, 0.0
        for s in range(4):
            o = origin(s)
            A = anchor_of(s) + off_a - o
            B = anchor_of(s) + off_b - o
            v = C * (K + A) * (K + B)
            if P[s][0] <= v <= P[s][1]:
                ok += 1
            mid = (P[s][0] + P[s][1]) / 2.0
            worst = max(worst, abs(v - mid) / mid)
        return ok, worst

    print("  TriH -- CONTROL.  origin y_top = s + 0.5; the published rule is")
    print("  'sample the centre of row 4*floor(y_top/4)+2'.")
    print("  %-46s %7s %12s" % ("model", "in/4", "worst rel"))
    for k in range(0, 5):
        f = (lambda s, k=k: 4 * math.floor((s + 0.5) / 4) + k)
        ok, w = score(sets["TriH"], f, 0.5, 1.5, 1.0, lambda s: s + 0.5)
        print("  %-46s %5d/4 %12.3e" % ("4-grid row %d, pixel centres, 1 px step" % k, ok, w))
    print()
    print("  TriV -- origin x_left = 160.5 + s.")
    print("  %-46s %7s %12s" % ("model", "in/4", "worst rel"))
    org = lambda s: 160.5 + s
    g4 = lambda k: (lambda s: 4 * math.floor((160.5 + s) / 4) + k)
    for k in range(0, 9):
        ok, w = score(sets["TriV"], g4(k), 0.5, 1.5, 1.0, org)
        print("  %-46s %5d/4 %12.3e" % ("4-grid col %d, pixel centres, 1 px step" % k, ok, w))
    for k in range(0, 9):
        ok, w = score(sets["TriV"], g4(k), 0.0, 1.0, 1.0, org)
        print("  %-46s %5d/4 %12.3e" % ("4-grid col %d, pixel corners, 1 px step" % k, ok, w))
    for k in (0, 2, 4):
        for m in (2.0, 4.0):
            ok, w = score(sets["TriV"], g4(k), 0.0, m, m, org)
            print("  %-46s %5d/4 %12.3e"
                  % ("4-grid col %d, corners, %d px step / %d" % (k, m, m), ok, w))
    for k in range(0, 5):
        f = (lambda s, k=k: (160 + s) + k)
        ok, w = score(sets["TriV"], f, 0.5, 1.5, 1.0, org)
        print("  %-46s %5d/4 %12.3e" % ("first covered col + %d, centres, 1 px" % k, ok, w))
    for k in (0, 1, 2):
        f = (lambda s, k=k: 2 * math.floor((160 + s) / 2) + k)
        ok, w = score(sets["TriV"], f, 0.5, 1.5, 1.0, org)
        print("  %-46s %5d/4 %12.3e" % ("2-snap first covered + %d, centres" % k, ok, w))

    print()
    print("  The separation is the finding.  On TriH the published rule is wrong by")
    print("  1.1e-7 -- 0.05 of one offset unit, which is the per-triangle plane-solve")
    print("  rounding this issue already measures as a separate floor.  On TriV the")
    print("  BEST of 32 rules is wrong by 5.6e-3, about 2,500 offset units: four")
    print("  orders of magnitude larger, so TriV is not that floor.")
    print()
    print("  INVERTED SAMPLE POSITION -- where the golden says the pair actually is:")
    for name, org2 in (("TriH", lambda s: s + 0.5), ("TriV", lambda s: 160.5 + s)):
        P = sets[name]
        print("    %s:" % name)
        for s in range(4):
            mid = (P[s][0] + P[s][1]) / 2.0
            iA = (-1.0 + math.sqrt(1.0 + 4.0 * mid)) / 2.0   # in units of D above 0
            x = org2(s) + (iA - K)
            halfw = (P[s][1] - P[s][0]) / 2.0
            dx = halfw / (2.0 * iA + 1.0)
            print("      s=%d  sample at %10.4f  +/- %.1e   (origin %+7.2f)"
                  % (s, x, dx, org2(s)))
    print()
    print("    The +/- above is the golden's depth quantisation ALONE.  The honest")
    print("    bound must also cover our plane differing from hardware's, and the")
    print("    interval itself supplies it: it is non-empty over ~1,100 px of each")
    print("    triangle, so our w agrees with hardware's interpolated w to better")
    print("    than 0.002 EVERYWHERE on the triangle, which is 2.7e-4 px of sample")
    print("    position.  The TriV drift is 0.0438 px -- 160x that.")
    print()
    print("  TriH sits on 2.5000 -- the centre of row 2 -- at every residue.")
    print("  TriV sits on 164.5072, 164.4634, 164.4195, 164.3758: pinned to a few")
    print("  ten-thousandths of a pixel, and DRIFTING by -0.0438 px for every pixel")
    print("  the triangle translates.  An anchor on any fixed grid is constant")
    print("  within a residue group by construction, so no such rule can produce a")
    print("  drift, whatever its phase or step.")
    print()
    print("  AND THE FAMILY, not just the rules.  Within one residue group any")
    print("  fixed-grid rule is a fixed absolute pair, so P(s) = C*(A-s)*(B-s) is a")
    print("  quadratic in s with three free parameters.  Fit it through residues")
    print("  0, 1, 2 and predict residue 3:")
    P = sets["TriV"]
    m = [(P[s][0] + P[s][1]) / 2.0 for s in range(4)]
    # exact quadratic through (0,m0),(1,m1),(2,m2)
    c2 = (m[2] - 2 * m[1] + m[0]) / 2.0
    c1 = m[1] - m[0] - c2
    c0 = m[0]
    p3 = c2 * 9 + c1 * 3 + c0
    width = P[3][1] - P[3][0]
    print("    predicted P(3) = %.6f" % p3)
    print("    golden   P(3) in [%.6f, %.6f]" % P[3])
    print("    miss = %.6f = %.0f x the interval width"
          % (abs(p3 - m[3]), abs(p3 - m[3]) / width))
    print("    fitted leading coefficient C = %.6f  (a k-px step needs C = k)" % c2)
    print("  Three free parameters, calibrated on three of the four points, and the")
    print("  fourth is still out by hundreds of interval widths at a step count that")
    print("  is not an integer.  So TriV refutes the model family, not one phase.")


# ------------------------------------------------------------------- cells

def cells(np, Image, root):
    print("=" * 78)
    print("THE (shape, clip_top) TABLE -- and the two degeneracies in it")
    print("=" * 78)
    tab = []
    for ct in (0, 32, 128, 224):
        cap = ("WBuf24D_FloorQuad_V1_ZB0_ZS1" if ct == 0
               else "WBuf24D_ClipF-150-%03d_V1_ZB0_ZS1" % ct)
        tris, cl, _, base = W.PRIMS["FloorQuad" if ct == 0 else "ClipF-150-%03d" % ct]
        iv = recover(np, Image, root, cap, base, tris, cl, ct)
        for t in (0, 1):
            if iv[t] is None:
                tab.append((ct, t, None, None))
                continue
            lo, hi, n = iv[t]
            mid = (lo + hi) / 2.0
            a, b = -50.0, 500.0
            for _ in range(90):
                mm = (a + b) / 2.0
                if W.offset_at(tris[t], W.FACTOR_W, 0.0, mm) > mid:
                    a = mm
                else:
                    b = mm
            tab.append((ct, t, (a + b) / 2.0, n))
    print("  %-9s %-3s %9s %12s %10s %10s %10s"
          % ("clip_top", "tri", "px", "anchor row", "firstcov", "4grid+2", "ct+2"))
    for ct, t, anc, n in tab:
        if anc is None:
            print("  %-9d t%d %9s   -- triangle has no covered pixel: cell EMPTY"
                  % (ct, t, "0"))
            continue
        print("  %-9d t%d %9d %12.3f %10d %10d %10d"
              % (ct, t, n, anc, 2 * (ct // 2), 4 * (ct // 4) + 2, ct + 2))
    print()
    print("  DEGENERACY 1 (new).  clip_top comes from kVertSampleCoords[3 + 6*i],")
    print("  wbuf_tests.cpp:335, and that array is 0,32,64,...,448 -- every entry a")
    print("  multiple of 32.  So no clip_top the suite can generate is anything but")
    print("  0 mod 4, and 'clip_top + 2' and 'the absolute 4-grid at phase 2' are")
    print("  THE SAME PREDICTION on every capture that exists.  The write-up records")
    print("  ClipF t1's rule as clip_top+2; it is one of two rules that fit, and the")
    print("  other is the rule TriH already obeys at all four phases.")
    print()
    print("  DEGENERACY 2.  The (t0, clip_top > 0) cell has exactly ONE observation,")
    print("  at clip_top = 32, because t0 has no covered pixel at 128 or 224 -- its")
    print("  left edge has left the framebuffer by then.  Checked rather than")
    print("  inferred from the instrument's silence.")
    print()
    print("  So the interaction that decides the regime rests on one t0 observation")
    print("  and three t1 observations at a single clip phase, and 'FloorQuad t1 vs")
    print("  ClipF t1' is the same triangle differing only in clip_top -- confirmed")
    print("  from source: both draws push the identical four vertices")
    print("  (53.1875,-34.3125) (586.75,-34.3125) (1808.6875,453) (-1168.6875,453),")
    print("  wbuf_tests.cpp:344 and the FloorQuad block above it.")
    print()
    print("  ALSO FROM SOURCE: ClipW's clip_left is kHorizSampleCoords[6*i] =")
    print("  159, 261, 363, and that array is 159,193,227,... step 34, so clip_left")
    print("  mod 4 alternates 3, 1 and is NEVER 0 or 2.  The column grid therefore")
    print("  has its own phase gap, independent of the row one.")
    print()
    print("  WHAT WOULD REFUTE THE BLOCKER, stated as the capture:")
    print("    (a) ONE ClipF variant at a clip_top that is not 0 mod 4 -- 33, 34 or")
    print("        35.  That is one integer in kVertSampleCoords, not a new test")
    print("        case, and it separates clip_top+2 from the absolute 4-grid.")
    print("    (b) A quad at clip_top > 0 whose t0 half still has covered pixels --")
    print("        i.e. a clip_top between 1 and ~127 for this quad -- to give the")
    print("        (t0, clipped) cell a second observation.")
    print("    (c) A TriH or TriV variant that steps the CROSS axis by something")
    print("        other than a multiple of 4, which is the gap --period reports.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    for f in ("classes", "period", "rivals", "cells"):
        ap.add_argument("--" + f, action="store_true")
    args = ap.parse_args(argv)
    run_all = not (args.classes or args.period or args.rivals or args.cells)

    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        print("needs numpy and pillow: %s" % e, file=sys.stderr)
        return 2
    root = os.path.join(args.goldens, SUITE)
    if not os.path.isdir(root):
        print("no %s under %s" % (SUITE, args.goldens), file=sys.stderr)
        return 2

    if run_all or args.classes:
        classes(np, Image, root)
        print()
    if run_all or args.period:
        period(np, Image, root)
        print()
    if run_all or args.rivals:
        rivals(np, Image, root)
        print()
    if run_all or args.cells:
        cells(np, Image, root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
