#!/usr/bin/env python3
"""Measure where silicon's colour interpolator samples, per axis (#38 mechanism 2).

Issue #38's mechanism 2 is "the host rasteriser's colour interpolation differs
from the NV2A's", and the sharpest prior statement of it -- from the `Alpha_func`
work in #57 -- was "hardware's red ramp starts 0.8 high and its blue ramp starts
0.8 low on identical geometry ... a phase offset of about 1 px".  This script
recovers that offset as a *measured displacement in pixels, per axis*, on ramps
whose endpoints are known exactly, and then asks the whole corpus whether the
displacement is a property of the interpolator or of one suite.

The answer is the latter, and the four sections below are the evidence.

1. x, from `Alpha_func`'s red and blue bands.  A 512-px screen-space quad
   (x 64 -> 576, w = 1, passthrough shader) carrying diffuse alpha 0 -> 1 and
   1 -> 0, blended SRC_ALPHA/ONE_MINUS_SRC_ALPHA over a known clear colour.
   The blend inverts uniquely, so the *integer fragment alpha the pipeline
   used* is readable per pixel from a golden.  Both endpoints are exactly
   representable bytes (0 and 255) under every rule #38 considered, so nothing
   here depends on the vertex quantiser.

   Ours is the exact ramp at the pixel centre, 512/512.  Hardware is the exact
   ramp evaluated at `2*floor(x/2) + 2` -- constant across the even-aligned
   pixel *pair*, sampled at the pair's right-hand edge -- 512/512, on both
   bands, including the 127.5 tie.  Six other sample positions are tested and
   all of them miss by hundreds of pixels.

2. y, from `Attrib_float/0_1`.  A screen-space quad (y 144 -> 432, w = 1)
   carrying a grey diffuse ramp 0.0f -> 1.0f, written straight out with no
   blend.  Hardware's step positions sit +0.033 px from the pixel-centre
   prediction and show no parity structure at all.  **There is no y offset.**

3. The alpha test, not the blend.  `AlphaFuncEqual`/`LessThan`/... discard per
   fragment, before blending, so the coverage mask is a direct read of the
   fragment alpha.  Every hardware band boundary starts on an even x and ends
   on an odd x; ours are mixed.  The pair is in the fragment's alpha, not in
   the blend unit.

4. Which draws it applies to, tested per row.  `Context_switch/GRZero` is the
   second confirmation and the important one: a screen-space 7-vertex POLYGON
   with per-vertex diffuse RGBA, whose pair shows on **RGB** and on a gradient
   running in **both** axes.  So the rule is neither alpha-specific nor
   specific to a purely-x gradient -- both readings the `Alpha_func` evidence
   alone permits are wrong.  It is still not universal: 3D_primitive,
   Shade_model, Attrib_carryover, Lighting_*, Material_*, Fog and Specular all
   have hundreds of measurable rows and not one paired row among them.

So mechanism 2 is *not* a global sample-position difference -- a sample
position belongs to the rasteriser and would move every suite and both axes,
and a corpus-wide best-shift census puts 1,482 of 1,674 non-exact captures at
(0,0) with the non-zero winners scattered in every direction.  Our
interpolator's phase is correct on both axes almost everywhere.  What is left
is a subset of draws in which silicon holds the fragment colour constant
across an even-aligned 2-pixel group in x, and reproducing that needs
per-fragment `gl_FragCoord` parity and a screen-space derivative -- which
exist only in fragment-shader code.  What selects those draws is **not
established**; see the investigation note.

Run:  python3 docs/testing/interpolator_phase.py [CAPTUREDIR ...]

With no arguments it checks the goldens alone, which is the load-bearing half:
the claim about silicon does not depend on which of our binaries is on hand.
Any capture directories given are additionally checked to still be the
pixel-centre ramp.  Exits non-zero if any recorded number fails to reproduce.
"""

import os
import sys
from collections import Counter

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as captures_mod  # noqa: E402

GOLDENS = os.environ.get("PGRAPH_GOLDENS", "/home/justin/goldens/results")

FB_W, FB_H = 640, 480
K_TOP = (FB_H - 256.0) / 3.0 * 2.0          # alpha_func_tests.cpp
X0, X1 = (FB_W - 512) // 2, (FB_W - 512) // 2 + 512
CLEAR = np.array([0x22, 0x23, 0x22, 0xFF], float)   # PrepareDraw(0xFF222322)

# (name, source rgb, band top offset, endpoint bytes left/right)
BANDS = [("red", [255, 0, 0], 0, 0.0, 255.0),
         ("blue", [0, 0, 255], 64, 255.0, 0.0)]

# attribute_float_tests.cpp: inset 0.2, quad y = (0.2+0.1)*480 .. + (1-0.4)*480
AF_Y0, AF_Y1 = 0.3 * FB_H, 0.3 * FB_H + 0.6 * FB_H
AF_COLS = [int((0.2 + i * 0.1) * FB_W + (0.1 * 0.8 * FB_W) / 2)
           for i in range(7)]

FAILURES = []


def check(cond, msg):
    print("   %s %s" % ("ok  " if cond else "FAIL", msg))
    if not cond:
        FAILURES.append(msg)


def load(path):
    return np.array(Image.open(path)).astype(np.int16)


def rnd(v):
    """Round half away from zero, as the UNORM8 attachment does."""
    return int(np.floor(v + 0.5))


# ---------------------------------------------------------------- section 1

def blend_table(src_rgb):
    out = np.zeros((256, 4))
    for a8 in range(256):
        a = a8 / 255.0
        for ch in range(3):
            out[a8, ch] = round(src_rgb[ch] * a + CLEAR[ch] * (1 - a))
        out[a8, 3] = round(a8 * a + CLEAR[3] * (1 - a))
    return out


def recover_alpha(img, y, src_rgb):
    """The integer fragment alpha the pipeline used, per pixel across the band."""
    t = blend_table(src_rgb)
    a8 = np.zeros(X1 - X0, int)
    exact = np.zeros(X1 - X0, bool)
    for i, x in enumerate(range(X0, X1)):
        d = np.abs(t - img[y, x, :4].astype(float)).sum(axis=1)
        c = np.where(d == d.min())[0]
        a8[i] = c[0]
        exact[i] = d.min() == 0 and len(c) == 1
    return a8, exact


SAMPLE_POSITIONS = [
    ("pixel centre    x + 0.5", lambda x: x + 0.5),
    ("pixel corner    x", lambda x: float(x)),
    ("pair left       2*fl(x/2)", lambda x: float(2 * (x // 2))),
    ("pair centre     2*fl(x/2)+1", lambda x: float(2 * (x // 2) + 1)),
    ("PAIR RIGHT      2*fl(x/2)+2", lambda x: float(2 * (x // 2) + 2)),
    ("pair right-half 2*fl(x/2)+1.5", lambda x: 2 * (x // 2) + 1.5),
    ("centre + 1      x + 1.5", lambda x: x + 1.5),
]


def model_row(vL, vR, pos):
    return np.array([max(0, min(255, rnd(vL + (vR - vL) * ((pos(x) - X0) / 512.0))))
                     for x in range(X0, X1)])


def step_phase(a8, vL, vR):
    """Mean displacement, in px, of each unit step from its pixel-centre position."""
    phis = []
    for i in range(1, len(a8)):
        lo, hi = int(a8[i - 1]), int(a8[i])
        if abs(hi - lo) != 1:
            continue
        lvl = (lo + hi) / 2.0
        if not (8 <= lvl <= 247):
            continue
        t = (lvl - vL) / (vR - vL)
        phis.append((X0 + i - 0.5) - (X0 + 512.0 * t - 0.5))
    return np.array(phis)


def section1(caps):
    print("1. x axis -- Alpha_func red and blue bands, endpoints 0 and 255 bytes")
    print("   512-px screen-space quad, x 64 -> 576, w = 1, gradient purely in x.")
    print()
    gold = load(os.path.join(GOLDENS, "Alpha_func", "AlphaFuncAlways_Disabled.png"))
    ours = {}
    for c in caps:
        p = captures_mod.find(c, "Alpha_func", "AlphaFuncAlways_Disabled")
        if p:
            ours[c] = load(p)

    for name, src, dy, vL, vR in BANDS:
        y = int(K_TOP) + dy + 32
        a8, ok = recover_alpha(gold, y, src)
        print("   band %-4s row y=%d, blend inverts uniquely on %d/%d px"
              % (name, y, int(ok.sum()), len(a8)))
        for label, pos in SAMPLE_POSITIONS:
            pred = model_row(vL, vR, pos)
            wrong = int((pred != a8).sum())
            mark = "   <== hardware" if wrong == 0 else ""
            print("      %-32s wrong %4d / 512%s" % (label, wrong, mark))
        ph = step_phase(a8, vL, vR)
        print("      hardware step phase  %+.4f px  (sd %.3f, range %+.2f..%+.2f)"
              % (ph.mean(), ph.std(), ph.min(), ph.max()))
        check(int((model_row(vL, vR, SAMPLE_POSITIONS[4][1]) != a8).sum()) == 0,
              "hardware %s band == exact ramp at 2*floor(x/2)+2, 512/512" % name)
        check(abs(ph.mean() + 1.0) < 0.05,
              "hardware %s band phase is -1.00 px (measured %+.4f)" % (name, ph.mean()))

        for c, img in ours.items():
            oa, _ = recover_alpha(img, y, src)
            centre = model_row(vL, vR, SAMPLE_POSITIONS[0][1])
            oph = step_phase(oa, vL, vR)
            print("      ours (%s): pixel-centre model %d/512, phase %+.4f px"
                  % (os.path.basename(c.rstrip("/")), int((oa == centre).sum()),
                     oph.mean()))
            check(int((oa == centre).sum()) == 512,
                  "ours %s band == exact ramp at the pixel centre, 512/512" % name)
        print()

    # --- the out-of-sample check: predict the green band's coverage ---------
    #
    # The sample position was fixed on red and blue, whose endpoints are 0 and
    # 255 and whose ramp is 255 units wide.  The green band is a different
    # animal -- 0.495f -> 0.505f, three byte units across the same 512 px --
    # and the alpha test's own coverage mask reads it with no model of the
    # blend at all.  Nothing below was fitted to it.
    #
    # #57 landed the byte-quantised endpoints (126 -> 129) and got the slope
    # right, but left the coverage on x 149..319 where hardware has 148..317,
    # and recorded that 1-2 px displacement as #38 mechanism 2's to finish.
    # This is it: the pair-right sample position lands both bounds exactly.
    print("   out of sample: the green band, 0.495f -> 0.505f, read by the")
    print("   alpha test's own coverage mask (AlphaFuncEqual_Enabled).")
    vL, vR = 126.0, 129.0          # #38's landed byte-quantised endpoints
    for label, pos in (("ours       pixel centre", SAMPLE_POSITIONS[0][1]),
                       ("prediction pair right  ", SAMPLE_POSITIONS[4][1])):
        xs = [x for x in range(X0, X1)
              if rnd(vL + (vR - vL) * ((pos(x) - X0) / 512.0)) == 127]
        print("      %s  a8 == 127 on x %d..%d" % (label, xs[0], xs[-1]))
    eq = load(os.path.join(GOLDENS, "Alpha_func", "AlphaFuncEqual_Enabled.png"))
    sp = [s for s in band_spans(eq, 128) if s[1] - s[0] > 8]
    print("      hardware   measured   a8 == 127 on x %d..%d" % sp[0])
    pred = [x for x in range(X0, X1)
            if rnd(vL + (vR - vL) * ((SAMPLE_POSITIONS[4][1](x) - X0) / 512.0)) == 127]
    check(sp and (pred[0], pred[-1]) == sp[0],
          "pair-right predicts the green band's coverage out of sample "
          "(predicted %d..%d, hardware %d..%d)"
          % (pred[0], pred[-1], sp[0][0], sp[0][1]))

    # AlphaFuncLessThan_Enabled holds the low crossing alone -- one boundary,
    # no second edge to average against, no clamping.  It is the capture that
    # would expose a wrong sample position first, so it is asserted separately.
    lt = load(os.path.join(GOLDENS, "Alpha_func", "AlphaFuncLessThan_Enabled.png"))
    lsp = [s for s in band_spans(lt, 128) if s[1] - s[0] > 8]
    lpred = [x for x in range(X0, X1)
             if rnd(vL + (vR - vL) * ((SAMPLE_POSITIONS[4][1](x) - X0) / 512.0)) < 127]
    print("      LessThan_Enabled green: predicted x %d..%d, hardware x %d..%d"
          % (lpred[0], lpred[-1], lsp[0][0], lsp[0][1]))
    check(lsp and (lpred[0], lpred[-1]) == lsp[0],
          "pair-right predicts AlphaFuncLessThan_Enabled's low crossing "
          "(predicted %d..%d, hardware %d..%d)"
          % (lpred[0], lpred[-1], lsp[0][0], lsp[0][1]))
    print()


# ---------------------------------------------------------------- section 2

def section2(caps):
    print("2. y axis -- Attrib_float/0_1, grey diffuse ramp 0.0f -> 1.0f")
    print("   screen-space quad, y 144 -> 432, w = 1, gradient purely in y, no blend.")
    print()
    gold = load(os.path.join(GOLDENS, "Attrib_float", "0_1.png"))
    imgs = [("hardware", gold)]
    for c in caps:
        p = captures_mod.find(c, "Attrib_float", "0_1")
        if p:
            imgs.append(("ours (%s)" % os.path.basename(c.rstrip("/")), load(p)))

    for label, img in imgs:
        allph, allpar = [], Counter()
        for xc in AF_COLS:
            col = img[:, xc, 0]
            ys = np.arange(int(np.ceil(AF_Y0)) + 2, int(AF_Y1) - 2)
            seg = col[ys].astype(int)
            d = np.diff(seg)
            if not ((d >= 0).all() and len(np.flatnonzero(d)) > 32):
                continue
            for j in np.flatnonzero(d):
                lo, hi = int(seg[j]), int(seg[j + 1])
                if hi - lo != 1:
                    continue
                lvl = (lo + hi) / 2.0
                if not (8 <= lvl <= 247):
                    continue
                y_ideal = AF_Y0 + (AF_Y1 - AF_Y0) * (lvl / 255.0) - 0.5
                allph.append((ys[j + 1] - 0.5) - y_ideal)
                allpar[int(ys[j + 1]) % 2] += 1
        ph = np.array(allph)
        skew = max(allpar.values()) / sum(allpar.values())
        print("   %-22s %4d steps  phase %+.4f px (sd %.3f)  parity skew %.3f %s"
              % (label, len(ph), ph.mean(), ph.std(), skew, dict(allpar)))
        if label == "hardware":
            check(abs(ph.mean()) < 0.20,
                  "hardware y phase is zero within 0.2 px (measured %+.4f)" % ph.mean())
            check(skew < 0.60,
                  "hardware y steps show no even/odd preference (skew %.3f)" % skew)
        else:
            check(abs(ph.mean()) < 0.20,
                  "%s y phase is zero within 0.2 px (measured %+.4f)" % (label, ph.mean()))
    print()


# ---------------------------------------------------------------- section 3

def band_spans(img, dy):
    y0 = int(np.ceil(K_TOP + dy)) + 2
    y1 = int(np.ceil(K_TOP + dy + 64)) - 2
    cov = ~np.all(img[y0:y1, X0:X1, :3] == CLEAR[:3].astype(np.int16), axis=2)
    col = cov.any(axis=0)
    out, i = [], 0
    while i < len(col):
        if not col[i]:
            i += 1
            continue
        j = i
        while j < len(col) and col[j]:
            j += 1
        out.append((X0 + i, X0 + j - 1))
        i = j
    return out


def section3(caps):
    print("3. The alpha test, which discards before the blend")
    print()
    for label, d in ([("hardware", os.path.join(GOLDENS, "Alpha_func"))]
                     + [("ours (%s)" % os.path.basename(c.rstrip("/")),
                         captures_mod.resolve(c, "Alpha_func::*.png")) for c in caps]):
        if not os.path.isdir(d):
            continue
        par = Counter()
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".png") or "Alpha" not in fn:
                continue
            img = load(os.path.join(d, fn))
            for _, _, dy, _, _ in BANDS + [("green", None, 128, None, None)]:
                for (a, b) in band_spans(img, dy):
                    if b - a < 8 or (a == X0 and b == X1 - 1):
                        continue
                    if a != X0:
                        par["start even" if a % 2 == 0 else "start odd"] += 1
                    if b != X1 - 1:
                        par["end even" if b % 2 == 0 else "end odd"] += 1
        tot_s = par["start even"] + par["start odd"]
        tot_e = par["end even"] + par["end odd"]
        print("   %-22s starts %d even / %d odd,  ends %d even / %d odd"
              % (label, par["start even"], par["start odd"],
                 par["end even"], par["end odd"]))
        if label == "hardware":
            check(tot_s and par["start even"] == tot_s,
                  "every hardware band boundary starts on an even x (%d/%d)"
                  % (par["start even"], tot_s))
            check(tot_e and par["end odd"] == tot_e,
                  "every hardware band boundary ends on an odd x (%d/%d)"
                  % (par["end odd"], tot_e))
    print()


# ---------------------------------------------------------------- section 4

# (suite, capture, minimum paired rows expected, maximum allowed)
WITNESSES = [
    ("Alpha_func", "AlphaFuncAlways_Disabled", 120, None),
    ("Alpha_func", "AlphaFuncLessThan_Enabled", 120, None),
    # A second, independent confirmation, and the one that kills the two
    # readings this was first given.  Context_switch/GRZero is a screen-space
    # 7-vertex POLYGON with per-vertex diffuse RGBA: the pair shows on *RGB*,
    # not just alpha, and on a gradient that runs in BOTH axes, not just x.
    # It reads only E=0.787 over the whole frame because the paired polygon
    # shares the picture with a w=12 perspective triangle, a checkerboard and
    # the pb_print overlay -- which is why this test is per row.
    ("Context_switch", "GRZero", 40, None),
    ("3D_primitive", "Polygon-inlinearrays", None, 0),
    ("Shade_model", "Fixed_Quad_Smooth_First", None, 0),
    ("Attrib_carryover", "T-bd0.2_0.0_0.6_1.0-ie", None, 0),
    # Attrib_float/0_1 is deliberately absent: its gradient runs in y and its
    # rows are constant in x, so it has nothing for this test to measure.  It
    # is the y-axis instrument in section 2 instead.
    # Attrib_setter/Setters-alpha is absent for the opposite reason: only 3 of
    # its rows are measurable, which is too few to call either way.
    ("Lighting_accumulation", "Point-4", None, 0),
    ("Material_alpha", "MatA_SVDiffuse_A3F400000", None, 0),
    ("Fog", "AFF-linear-planar", None, 0),
    ("Specular", "ControlFlags_FF", None, 0),
    # Kept as a deliberate contrast: a render target sampled at 2x magnification
    # repeats every value in pairs, but it repeats them at BOTH parities, so O
    # is high too.  That is what a magnified texture looks like; it is not what
    # a pair-constant interpolant looks like.
    ("Blend_tests", "#spot_0_ADD", None, 0),
]


def row_pair_stats(a):
    """Per row: E = P(v[x]==v[x+1]) for even x, O for odd x, gradient px only.

    Two restrictions are load bearing.

    Gradient px only (neighbours within 4 per channel): the `pb_print` overlay
    puts 3-px white glyph stems on a flat ground, and without the bound the
    metric reads those as a pair -- E=1.00, O=0.03 on `Depth_Clamp`'s text
    alone, and E=0.82 on `Specular`'s.  Gradients step by 1, glyph edges by
    hundreds.

    Per row, not per capture: a paired primitive can share its frame with
    unpaired content.  `Context_switch/GRZero` averages to E=0.787 over the
    whole picture and reaches E=1.000, O=0.039 on individual rows inside the
    polygon.  A whole-capture average hides it.

    Blind spot, stated so it is not mistaken for a negative: a gradient
    steeper than ~4 bytes/px leaves too few qualifying positions and the row
    is dropped rather than judged.  So a row this returns nothing for is
    *unmeasured*, not unpaired.
    """
    w = a[:, :, :3].astype(np.int16)
    d = np.abs(w[:, 1:, :] - w[:, :-1, :]).max(axis=2)
    same = d == 0
    grad = d <= 4
    vary = np.zeros_like(same)
    for k in (1, 2, 3, 4):
        if w.shape[1] > k:
            e = np.abs(w[:, k:, :] - w[:, :-k, :]).max(axis=2)
            m = (e > 0) & (e <= 4 * k)
            vary[:, :m.shape[1]] |= m[:, :vary.shape[1]]
    use = grad & vary
    xs = np.arange(same.shape[1])
    evm = (xs % 2 == 0)[None, :]
    odm = (xs % 2 == 1)[None, :]
    ne, no = (use & evm).sum(axis=1), (use & odm).sum(axis=1)
    se, so = (same & use & evm).sum(axis=1), (same & use & odm).sum(axis=1)
    ok = (ne >= 50) & (no >= 50)
    if not ok.any():
        return 0, 0, 0.0, 1.0
    E, O = se[ok] / ne[ok], so[ok] / no[ok]
    return (int(ok.sum()), int(((E > 0.90) & (O < 0.25)).sum()),
            float(E.max()), float(O.min()))


def section4():
    print("4. Does the 2-pixel group belong to the interpolator, or to some draws?")
    print("   Per row: E = P(v[x]==v[x+1]) for even x, O for odd x, gradient px only.")
    print("   A row is paired when E > 0.90 and O < 0.25.")
    print()
    for suite, cap, lo, hi in WITNESSES:
        p = os.path.join(GOLDENS, suite, cap + ".png")
        if not os.path.exists(p):
            check(False, "witness %s/%s is missing from the goldens" % (suite, cap))
            continue
        n, paired, maxE, minO = row_pair_stats(np.array(Image.open(p)))
        if n == 0:
            check(False, "witness %s/%s has no measurable rows" % (suite, cap))
            continue
        print("   %-22s %-34s rows=%3d paired=%3d maxE=%.3f minO=%.3f"
              % (suite, cap[:34], n, paired, maxE, minO))
        if lo is not None:
            check(paired >= lo,
                  "%s/%s has at least %d paired rows (%d)" % (suite, cap, lo, paired))
        if hi is not None:
            check(paired <= hi,
                  "%s/%s has no paired rows (%d)" % (suite, cap, paired))
    print()


# ---------------------------------------------------------------- section 5

def section5(caps):
    """Is there a global displacement?  Then some non-zero shift must win."""
    if not caps:
        return
    print("5. Best whole-capture shift against the golden, over the suites supplied")
    print("   A sample-position error is a displacement: a non-zero (dx,dy) must win.")
    print()
    for c in caps:
        root = captures_mod.resolve(c)
        files = [f for f in sorted(os.listdir(root)) if f.endswith(".png")] \
            if os.path.isdir(root) else []
        tally = Counter()
        for fn in files:
            if "::" not in fn:
                continue
            suite, nm = fn[:-4].split("::", 1)
            gp = os.path.join(GOLDENS, suite, nm + ".png")
            if not os.path.exists(gp):
                continue
            g = load(gp)[:, :, :3].astype(int)
            o = load(os.path.join(root, fn))[:, :, :3].astype(int)
            if g.shape != o.shape:
                continue
            H, W, _ = g.shape

            def dc(dx, dy):
                xs = slice(max(0, dx), W + min(0, dx))
                xd = slice(max(0, -dx), W + min(0, -dx))
                ys = slice(max(0, dy), H + min(0, dy))
                yd = slice(max(0, -dy), H + min(0, -dy))
                return int(np.any(g[ys, xs] != o[yd, xd], axis=2).sum())

            base = dc(0, 0)
            if base == 0:
                tally["exact"] += 1
                continue
            best = (base, 0, 0)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = dc(dx, dy)
                    if n < best[0]:
                        best = (n, dx, dy)
            tally["(%+d,%+d)" % (best[1], best[2])] += 1
        if tally:
            print("   %-40s %s" % (os.path.basename(c.rstrip("/")), dict(tally)))
    print()


def main():
    caps = sys.argv[1:]
    print(__doc__.split("Run:")[0].strip().splitlines()[0])
    print("goldens: %s" % GOLDENS)
    print()
    section1(caps)
    section2(caps)
    section3(caps)
    section4()
    section5(caps)
    if FAILURES:
        print("FALSIFIED: %d recorded result(s) did not reproduce:" % len(FAILURES))
        for f in FAILURES:
            print("   - %s" % f)
        return 1
    print("OK: on the draws where it applies, silicon samples the colour at")
    print("    2*floor(x/2)+2 in x -- constant across the even-aligned pixel pair")
    print("    -- and at the pixel centre in y. Confirmed on Alpha_func (alpha,")
    print("    1-D gradient) and Context_switch (RGB, 2-D gradient); absent from")
    print("    every other witness. Our phase is correct where it is absent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
