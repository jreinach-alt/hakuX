#!/usr/bin/env python3
"""#57 is #38 mechanism 2: the misplaced alpha boundary IS the pair sample position.

Issue #57 is filed as "the `Alpha_func` enabled comparison boundary is
misplaced".  Issue #38 mechanism 2 is "silicon holds the interpolated colour
constant across the even-aligned pixel pair `{2m, 2m+1}` and evaluates it at
the pair's right-hand edge, `s = 2*floor(x/2) + 2`" (measured in
`docs/testing/interpolator_phase.py`, written up in
`docs/investigations/interpolator-sample-position.md`).

This script asks whether those are two defects or one, and answers it the only
way the project accepts: by predicting the *mask* rather than the count, and
checking `intersection == union` against the measured mask.  Two masks of equal
cardinality can be disjoint -- measured on #38's own `Bump_map` nine, where
byte-identical 1,576-px masks sat 19 pixels from a capture that "went below the
floor" -- so cardinality is not evidence and is not reported as if it were.

WHAT IS FITTED AND WHAT IS NOT, stated because the conclusion depends on it:

  FITTED (elsewhere, not here).  The sample rule `2*floor(x/2)+2` was fixed on
  `Alpha_func`'s red and blue bands, whose diffuse alpha ramps 0->255 and
  255->0 over x 64..576.  Those bands are blended SRC_ALPHA/ONE_MINUS_SRC_ALPHA
  over a known clear colour, so the blend inverts uniquely and the integer
  fragment alpha is readable per pixel: 512 of 512 on both bands, for hardware
  and for us.  Section 1 re-derives that here so the claim is not taken on
  trust.

  NOT FITTED.  The green band is `0.495f -> 0.505f` -- *three* byte units over
  the same 512 px against red/blue's 255 -- and it is where the `Equal` and
  `NotEqual` boundaries live, which are the two largest structural residuals in
  the suite.  Nothing about green enters the fit.  Neither does the alpha test:
  the rule is a statement about the fragment's alpha, and the coverage mask is
  a second, independent instrument reading the same quantity with the blend
  taken out of the question.

  MEASURED vs ASSUMED, per "an inference can be valid and still wrong".  The
  byte-quantised endpoints (126 and 129 for green) are MEASURED -- that is #38
  mechanism 1, `colorPrecision()` in `glsl/vsh.c`, confirmed by slope in #57
  (2.5369 -> 3.0118 against hardware 3.0000).  The linear interpolation between
  them is ASSUMED, and it is the only assumption in section 2.

THE RESULT.  Over the eight `_Enabled` captures the pair rule predicts the
structural mask exactly: 1,792 of 1,792 pixels, `intersection == union` on
every capture, with the per-capture counts falling out as the three
complementary pairs #57 recorded (448/448, 192/192, 256/256).  Six rival sample
positions and two "our comparison boundary is wrong" rivals all fail, and three
of the rivals produce a mask that is *disjoint* from the measured one while
having non-zero cardinality -- which is the same trap stated above, showing up
inside this script's own rival table.

So there is nothing separate to fix in #57.  Our alpha comparison is correct;
the alpha arriving at it is sampled at the pixel centre where silicon samples
at the pair's right edge.  #57 should be closed into #38 mechanism 2 rather
than carried as its own defect, and a fix for mechanism 2 closes both by
construction.

WHAT THIS DOES NOT ESTABLISH.  Which draws the pair rule applies to.  That is
#38 mechanism 2's open item and this script says nothing about it; see
`docs/investigations/issue57-is-issue38-mech2.md` for the class enumeration and
why the corpus cannot settle it.  Do not read a pass here as licence to apply
the rule unconditionally -- it would displace every Gouraud gradient in the
corpus to fix two draws.

Run:  python3 docs/testing/alpha_func_pair_boundary.py [CAPTUREDIR]

CAPTUREDIR is a dispatcher result directory or a captures directory holding
`Alpha_func` captures; it defaults to the `z-tip-003-Alpha_func` sweep arm.
Exits non-zero if the identity stops holding.
"""

import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as captures_mod  # noqa: E402

GOLDENS = os.environ.get("PGRAPH_GOLDENS", "/home/justin/goldens/results")
DEFAULT_ARM = "/home/justin/hakux-work/dispatch/results/z-tip-003-Alpha_func"

FB_W, FB_H = 640, 480
# alpha_func_tests.cpp: kTop = (kFBHeight - 256) / 3 * 2, bands 64 px tall,
# quad x from (kFBWidth - 512)/2 to + 512, clear 0xFF222322, alpha ref 0x7F.
K_TOP = (FB_H - 256.0) / 3.0 * 2.0
X0, X1 = (FB_W - 512) // 2, (FB_W - 512) // 2 + 512
CLEAR = np.array([0x22, 0x23, 0x22], float)
REF = 127

# name, source rgb, y top, y bottom, byte endpoint left, right.
# 0.0f/1.0f are exactly 0 and 255; 0.495f/0.505f quantise to 126 and 129, which
# is #38 mechanism 1 as landed and is what #57's slope measurement confirmed.
BANDS = [
    ("red", [255, 0, 0], K_TOP, K_TOP + 64, 0.0, 255.0),
    ("blue", [0, 0, 255], K_TOP + 64, K_TOP + 128, 255.0, 0.0),
    ("green", [0, 255, 0], K_TOP + 128, K_TOP + 192, 126.0, 129.0),
]

FUNCS = [
    ("Never", lambda a: np.zeros_like(a, bool)),
    ("LessThan", lambda a: a < REF),
    ("Equal", lambda a: a == REF),
    ("LessThanOrEqual", lambda a: a <= REF),
    ("GreaterThan", lambda a: a > REF),
    ("NotEqual", lambda a: a != REF),
    ("GreaterThanOrEqual", lambda a: a >= REF),
    ("Always", lambda a: np.ones_like(a, bool)),
]

X = np.arange(FB_W, dtype=float)
S_PAIR_RIGHT = 2 * np.floor(X / 2) + 2       # hardware, per #38 mechanism 2
S_CENTRE = X + 0.5                           # ours

RIVALS = [
    ("pixel centre    x + 0.5   (= ours, i.e. no defect)", S_CENTRE),
    ("pixel corner    x", X),
    ("pair left       2*floor(x/2)", 2 * np.floor(X / 2)),
    ("pair centre     2*floor(x/2) + 1", 2 * np.floor(X / 2) + 1),
    ("pair right-half 2*floor(x/2) + 1.5", 2 * np.floor(X / 2) + 1.5),
    ("centre + 1      x + 1.5", X + 1.5),
    ("PAIR RIGHT      2*floor(x/2) + 2", S_PAIR_RIGHT),
]

FAILURES = []


def check(cond, msg):
    print("   %s   %s" % ("ok  " if cond else "FAIL", msg))
    if not cond:
        FAILURES.append(msg)


def load(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.int16)


def rnd(v):
    """UNORM8 round-half-up, which is what the colour attachment does."""
    return np.floor(np.asarray(v, float) + 0.5)


def rows_of(top, bottom):
    return [y for y in range(FB_H) if top <= y + 0.5 < bottom]


def ramp(vL, vR, s):
    return rnd(vL + (vR - vL) * (s - X0) / 512.0)


def recover_a8(img, src_rgb, y):
    """The unique integer source alpha reproducing the blend at (x, y), else -1.

    SRC_ALPHA/ONE_MINUS_SRC_ALPHA over a known clear colour from a known source
    colour, so this is a direct read of the integer fragment alpha the pipeline
    used -- no fit, no model of the interpolator.
    """
    src = np.array(src_rgb, float)
    t = np.arange(256) / 255.0
    tbl = np.rint(src[None, :] * t[:, None] + CLEAR[None, :] * (1 - t[:, None]))
    tbl = tbl.astype(np.int16)
    out = np.full(FB_W, -1, int)
    for x in range(X0, X1):
        m = np.nonzero((tbl == img[y, x, :3][None, :]).all(axis=1))[0]
        if len(m) == 1:
            out[x] = m[0]
    return out


def gold(test):
    return load(os.path.join(GOLDENS, "Alpha_func", test + ".png"))


def find_ours(arm, test):
    p = captures_mod.find(arm, "Alpha_func", test)
    if p is None:
        raise SystemExit(
            "MISSING capture Alpha_func::%s under %s -- resolve with captures.py, "
            "never by globbing; a missing capture reads exactly like a failed "
            "render and has twice been taken as a refutation." % (test, arm))
    return load(p)


def section1(arm):
    print("1. The sample rule, read straight out of the blend (no fit)")
    print("   Alpha_func's bands invert uniquely, so the integer fragment alpha")
    print("   is readable per pixel on both sides.\n")
    base = "AlphaFuncAlways_Disabled"
    go, ou = gold(base), find_ours(arm, base)
    for name, src, yt, yb, vL, vR in BANDS:
        rows = rows_of(yt, yb)
        y = rows[len(rows) // 2]
        hw, us = recover_a8(go, src, y), recover_a8(ou, src, y)
        mh, mu = hw[X0:X1] >= 0, us[X0:X1] >= 0
        ph, pu = ramp(vL, vR, S_PAIR_RIGHT), ramp(vL, vR, S_CENTRE)
        wh = int((hw[X0:X1][mh] != ph[X0:X1][mh]).sum())
        wu = int((us[X0:X1][mu] != pu[X0:X1][mu]).sum())
        print("   %-6s row y=%3d  invertible hw %3d/512 ours %3d/512"
              % (name, y, mh.sum(), mu.sum()))
        if name == "green":
            print("          (green inverts on few columns because two adjacent a8 round")
            print("           to one output triple; it is NOT used to fit anything)")
        check(wh == 0, "%s: hardware == exact ramp at 2*floor(x/2)+2 (%d wrong of %d)"
              % (name, wh, int(mh.sum())))
        check(wu == 0, "%s: ours == exact ramp at the pixel centre (%d wrong of %d)"
              % (name, wu, int(mu.sum())))
    print()


def predicted_mask(sample, func):
    """Columns where hardware's coverage differs from ours, over the band rows."""
    mask = np.zeros((FB_H, FB_W), bool)
    for _name, _src, yt, yb, vL, vR in BANDS:
        ph = func(ramp(vL, vR, sample))
        pu = func(ramp(vL, vR, S_CENTRE))
        cols = np.nonzero(ph != pu)[0]
        cols = cols[(cols >= X0) & (cols < X1)]
        for y in rows_of(yt, yb):
            mask[y, cols] = True
    return mask


def measured_structural(arm, test):
    d = np.abs(gold(test).astype(int) - find_ours(arm, test).astype(int))
    return (d[:, :, :3].max(axis=2) > 1) | (d[:, :, 3] > 1)


def section2(arm):
    print("2. Does the pair rule predict #57's structural mask?")
    print("   Structural = some channel more than one step out, which is the")
    print("   split #57 filed on (9,216 of 435,032 then; the rest is #38's floor).")
    print("   The green band carries Equal/NotEqual and is out of sample.\n")
    print("   %-38s %7s %7s %7s %7s  %s"
          % ("capture", "struct", "pred", "inter", "union", "verdict"))
    tot = dict(s=0, p=0, i=0, u=0)
    per_capture = {}
    for fn, f in FUNCS:
        test = "AlphaFunc%s_Enabled" % fn
        struct = measured_structural(arm, test)
        pred = predicted_mask(S_PAIR_RIGHT, f)
        i, u = int((pred & struct).sum()), int((pred | struct).sum())
        per_capture[fn] = int(struct.sum())
        print("   %-38s %7d %7d %7d %7d  %s"
              % (test, struct.sum(), pred.sum(), i, u,
                 "IDENTICAL" if i == u else "MASKS DIFFER"))
        check(i == u, "%s: predicted mask == measured structural mask" % test)
        for k, v in (("s", struct.sum()), ("p", pred.sum()), ("i", i), ("u", u)):
            tot[k] += int(v)
    print("   %-38s %7d %7d %7d %7d" % ("TOTAL", tot["s"], tot["p"], tot["i"], tot["u"]))
    check(tot["i"] == tot["u"] and tot["u"] > 0,
          "whole suite: intersection == union (%d == %d)" % (tot["i"], tot["u"]))
    print()
    print("   The three complementary pairs #57 identified, which is what a")
    print("   misplaced boundary looks like -- each pair partitions the alpha")
    print("   domain, so a pixel that wrongly passes one wrongly fails its")
    print("   complement, and a displaced sample position produces exactly that:")
    for a, b in (("Equal", "NotEqual"), ("GreaterThanOrEqual", "LessThan"),
                 ("GreaterThan", "LessThanOrEqual")):
        print("      %-22s %5d   %-22s %5d" % (a, per_capture[a], b, per_capture[b]))
        check(per_capture[a] == per_capture[b],
              "complementary pair %s/%s carries equal structural counts" % (a, b))
    print()
    return tot


def section3(arm):
    print("3. The rivals, scored on the same masks")
    print("   Note the cardinality column is NOT the verdict: three rivals below")
    print("   produce a non-empty mask that is DISJOINT from the measured one.\n")
    meas = {fn: measured_structural(arm, "AlphaFunc%s_Enabled" % fn) for fn, _ in FUNCS}
    print("   %-52s %7s %7s %7s  %s" % ("hardware sample position", "pred", "inter",
                                        "union", "verdict"))
    winners = []
    for name, sample in RIVALS:
        p = i = u = 0
        for fn, f in FUNCS:
            pred = predicted_mask(sample, f)
            p += int(pred.sum())
            i += int((pred & meas[fn]).sum())
            u += int((pred | meas[fn]).sum())
        if p == 0:
            verdict = "explains nothing"
        elif i == u:
            verdict = "IDENTICAL MASK"
            winners.append(name)
        elif i == 0:
            verdict = "disjoint from the measured mask"
        else:
            verdict = "mask differs"
        print("   %-52s %7d %7d %7d  %s" % (name, p, i, u, verdict))
    check(len(winners) == 1 and "PAIR RIGHT" in winners[0],
          "exactly one sample position reproduces the mask, and it is the pair right edge")

    print("\n   And the rival family #57's own filing proposed -- that our")
    print("   comparison is wrong rather than our sample position:\n")
    for dref, label in ((-1, "ours compares against ref 126, not 127"),
                        (1, "ours compares against ref 128, not 127")):
        p = i = u = 0
        for fn, f in FUNCS:
            mask = np.zeros((FB_H, FB_W), bool)
            for _n, _s, yt, yb, vL, vR in BANDS:
                a = ramp(vL, vR, S_CENTRE)
                cols = np.nonzero(f(a) != f(a - dref))[0]
                cols = cols[(cols >= X0) & (cols < X1)]
                for y in rows_of(yt, yb):
                    mask[y, cols] = True
            p += int(mask.sum())
            i += int((mask & meas[fn]).sum())
            u += int((mask | meas[fn]).sum())
        print("   %-52s %7d %7d %7d  %s" % (label, p, i, u,
                                            "IDENTICAL MASK" if i == u else "mask differs"))
        check(i != u, "'%s' does NOT reproduce the mask" % label)
    print()


def main():
    arm = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ARM
    if not os.path.isdir(GOLDENS):
        raise SystemExit("no goldens at %s (set PGRAPH_GOLDENS)" % GOLDENS)
    if not os.path.isdir(arm):
        raise SystemExit("no capture directory at %s" % arm)
    print(__doc__.split("Run:")[0].rstrip())
    print("\ngoldens: %s\narm:     %s\n" % (GOLDENS, captures_mod.resolve(arm)))
    section1(arm)
    section2(arm)
    section3(arm)
    if FAILURES:
        print("FALSIFIED: %d check(s) failed\n" % len(FAILURES))
        for f in FAILURES:
            print("   - %s" % f)
        print("\nEither the goldens changed, the arm is not the pixel-centre ramp")
        print("(i.e. a pair-sample fix has landed in glsl/psh.c -- in which case")
        print("this script's framing is what needs re-pointing, not the fix), or")
        print("the identity between #57 and #38 mechanism 2 does not hold.")
        return 1
    print("OK: #57's structural residual IS #38 mechanism 2, mask for mask.")
    print("    Our alpha comparison is correct; the alpha reaching it is sampled")
    print("    at the pixel centre where silicon samples at 2*floor(x/2)+2.")
    print("    There is no separate defect in #57 to fix.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
