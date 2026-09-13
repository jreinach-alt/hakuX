#!/usr/bin/env python3
"""#67: the `Blend_tests` swatch over-extent is the guest's `floorf`, not our fill rule.

What this measures
------------------

#67 was filed as a rasterisation defect: "the 24x24 swatch quads rasterise
25x25". The quads do come out 25x25, and the boundaries do land at 25/50/75/100
instead of 24/48/72/96. But the geometry is not ours to get wrong -- the guest
computes it:

    blend_tests.cpp:186  test_width         = floorf((512 - 16) / 5)  = floorf(99.2)     = 99
    blend_tests.cpp:189  test_height        = floorf((480 - 72) / 3)  = floorf(136.0)    = 136
    blend_tests.cpp:190  color_swatch_size  = floorf(test_width / 4)  = floorf(24.75)    = 24

Every measured edge of every cell -- the two colour stacks, the four nested
alpha rings, in all fifteen cells of the 5x3 grid -- is reproduced by exactly
one parameter change: `color_swatch_size` is **25** in our render and **24** in
silicon's. Nothing else moves. `test_width` stays 99 (the cell pitch is 103 in
both) and `test_height` stays 136 (the cell rows are at 136 and 272 in both).

floor(24.75) = 24. **rint(24.75) = 25.** And the other two calls are the ones
where floor and round-to-nearest agree: floor(99.2) = rint(99.2) = 99,
floor(136.0) = rint(136.0) = 136. One rule, three call sites, three matching
outcomes -- and the two that do not move are what makes it a rule rather than a
fit.

So this is not a fill convention. It is x87 `FRNDINT` ignoring the guest's
rounding-control field, in `target/i386/tcg/fpu_helper.c`:

    #define floatx80_round_to_int(a, s)    ((void)(s), rint(a))

`rint()` rounds per the *host* FP environment, which QEMU leaves at
nearest-even; `(void)(s)` throws the guest `float_status` away. nxdk's `floorf`
is the textbook x87 sequence -- save the control word, set RC=round-down,
`FRNDINT`, restore -- so with RC discarded `floorf` becomes `rint`. That block
is `#if defined(XBOX) && defined(__aarch64__)` under `USE_HARD_FPU`, so it is
the Android FP JIT path only (`g_config.perf.fp_jit`, default on); the x86_64
hard path leaves `floatx80_round_to_int` as softfloat and is unaffected.

Why the confirmation does not come from Blend_tests
---------------------------------------------------

A single capture's geometry can be curve-fitted by a single parameter, so the
rule is confirmed on a suite that has nothing to do with blending:

    point_size_tests.cpp:387  increment = floorf((640 - 32 - 8) / 7) = floorf(85.714...)
    point_size_tests.cpp:323  cy        = floorf((480 - 64) / 3)     = floorf(138.666...)

`Point_size::SmallestPointSize_*` draws nine 1-px points at `16 + increment*k`.
Silicon puts them at 85-px spacing, we put them at 86 -- and the whole residual
of those two captures is the 14 pixels that displaces (seven points move, two
pixels each). `Point_size::LargestPointSize_*` places a ruler quad at
`cy - 36` and a second row at `2*cy`; silicon is at 102 and 307, we are at 103
and 309, which is cy = 138 against cy = 139.

Three call sites, three different fractional parts, three independent suites,
all decided the same way, and no free parameter anywhere.

What it checks
--------------

1. `geometry` -- reconstructs one Blend_tests cell's primitive-ownership map
   from `blend_tests.cpp` under `color_swatch_size` = 24 and = 25, and checks
   that **every** differing pixel of every unsigned `#spot_*` capture lies
   inside the set where ownership changes. A second, unrelated defect in the
   swatch area would land outside it. Ownership is not colour: two primitives
   can agree on a pixel, so the prediction is one-directional -- zero outside,
   not equality.
2. `points` -- recovers the point spacing and the ruler edges from the
   `Point_size` captures and reports which of floor / rint each side matches.

Neither leg reads a constant out of a capture; both come from the test sources.

    guest_frndint_rounding.py <result-dir> [--goldens DIR]

Takes a dispatcher result directory or a captures directory; `captures.resolve`
handles both shapes.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as captures_mod

#: `TestSpot` prints the test name into rows 0..63; the 512x512 render target is
#: blitted at +64, so nothing below this row can be label.
LABEL_ROWS = 64
BLIT_X, BLIT_Y = 64, 64

#: blend_tests.cpp TestSpot: 5 cells across, 3 down, test_width 99 + 4 spacing,
#: test_height 136. These two are NOT in question -- both are floorf calls whose
#: argument rounds the same way under floor and under nearest.
TEST_W, TEST_H, SPACING = 99, 136, 4
GRID_COLS, GRID_ROWS = 5, 3

EQUATIONS_UNSIGNED = ["ADD", "SUB", "REVSUB", "MIN", "MAX"]
FACTORS = ["0", "1", "srcRGB", "1-srcRGB", "srcA", "1-srcA", "dstA", "1-dstA",
           "dstRGB", "1-dstRGB", "srcAsat", "cRGB", "1-cRGB", "cA", "1-cA"]

#: `0_ADD_1` and friends: sfactor ZERO with dfactor ONE writes the destination
#: back unchanged, so that cell carries no information under any mechanism. It
#: is left in -- it simply contributes no differing pixels -- but named here so
#: nobody reads its zero as a passing check.
NO_INFORMATION_CELL = ("0", "1")


def ownership(swatch):
    """Which primitive owns each pixel of one cell, for a given swatch size.

    Derived from `blend_tests.cpp`, not from any capture. Draw order is
    DrawColorStack 0..3, DrawColorAndAlphaStack 0..3, DrawAlphaStack ring 0..3,
    and later wins -- so this is just the rectangles painted in order.

    Returns an int map: 0 = render-target background, 1..4 = colour stack,
    5..8 = colour-and-alpha stack, 9..12 = alpha rings.
    """
    s = swatch
    m = np.zeros((TEST_H, TEST_W), dtype=np.int8)

    for k in range(4):                                   # DrawColorStack
        m[s * k:s * (k + 1), 0:s] = 1 + k
    for k in range(4):                                   # DrawColorAndAlphaStack
        m[s * k:s * (k + 1), s:2 * s] = 5 + k

    quad_size = TEST_W - 2 * s                           # DrawAlphaStack
    for k in range(4):
        inc = 4 * k
        left, top = 2 * s + inc, inc
        right, bottom = 2 * s + quad_size - inc, quad_size - inc
        m[top:bottom, left:right] = 9 + k
    return m


def cell_slices():
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            y = BLIT_Y + r * TEST_H
            x = BLIT_X + c * (TEST_W + SPACING)
            yield r, c, (slice(y, y + TEST_H), slice(x, x + TEST_W))


def leg_geometry(get_pair, verbose):
    """Every differing pixel of every unsigned #spot_ capture lies where the
    24-swatch and 25-swatch ownership maps disagree."""
    change = ownership(24) != ownership(25)
    print(f"  ownership changes on {int(change.sum())} px of the "
          f"{TEST_H}x{TEST_W} cell under swatch 24 -> 25")

    seen = outside = inside = 0
    missing = []
    per_cell_counts = set()
    union = np.zeros_like(change)
    for eqn in EQUATIONS_UNSIGNED:
        for f in FACTORS:
            name = f"#spot_{f}_{eqn}"
            gold, ours = get_pair(name)
            if gold is None or ours is None:
                missing.append(name)
                continue
            seen += 1
            differ = (gold != ours).any(axis=2)
            differ[:LABEL_ROWS, :] = False
            total_in = 0
            for r, c, sl in cell_slices():
                d = differ[sl]
                total_in += int((d & change).sum())
                per_cell_counts.add(int(d.sum()))
                union |= d
            out = int(differ.sum()) - total_in
            outside += out
            inside += total_in
            if out and verbose:
                print(f"    {name}: {out} px outside the ownership-change set")

    print(f"  {seen} unsigned captures: {inside} differing px inside the "
          f"change set, {outside} outside")
    print(f"  per-cell differing counts observed: "
          f"min {min(per_cell_counts) if per_cell_counts else '-'}, "
          f"max {max(per_cell_counts) if per_cell_counts else '-'}, "
          f"{len(per_cell_counts)} distinct")
    # Two masks of equal cardinality can be disjoint, so compare the sets.
    u, ch = int(union.sum()), int(change.sum())
    inter = int((union & change).sum())
    print(f"  union of every differing pixel over all cells and captures: {u} px; "
          f"ownership-change set: {ch} px; intersection {inter}")
    exact = (u == ch == inter)
    print(f"  union == ownership-change set, to the pixel: "
          f"{'YES' if exact else 'NO'}")
    if missing:
        print(f"  MISSING {len(missing)}: {', '.join(missing[:6])}"
              f"{' ...' if len(missing) > 6 else ''}")
    ok = seen > 0 and outside == 0 and exact
    print(f"  geometry leg: {'PASS' if ok else 'FAIL'} "
          f"(needs >0 captures, 0 px outside, and union == change set)")
    return ok


def _white_columns(img, y0, y1):
    band = img[y0:y1]
    m = (band[:, :, 0] > 200) & (band[:, :, 1] > 200) & (band[:, :, 2] > 200)
    cols = sorted(set(np.nonzero(m)[1].tolist()))
    runs, start, prev = [], None, None
    for c in cols:
        if prev is None or c != prev + 1:
            if prev is not None:
                runs.append((start, prev))
            start = c
        prev = c
    if prev is not None:
        runs.append((start, prev))
    return [a for a, _ in runs]


def leg_points(get_pair, verbose):
    """Point_size recovers two more floorf arguments, in a suite that draws no
    swatches and no blends."""
    ok = True

    # point_size_tests.cpp:387  increment = floorf((640 - 2*16 - 8) / 7)
    arg = (640.0 - 32.0 - 8.0) / 7.0
    import math
    expect = {"floor": int(math.floor(arg)), "rint": int(round(arg))}
    print(f"  SmallestPointSize increment = floorf({arg:.6f}): "
          f"floor {expect['floor']}, rint {expect['rint']}")
    for t in ("SmallestPointSize_FF", "SmallestPointSize_VS"):
        gold, ours = get_pair(t, suite="Point_size")
        if gold is None or ours is None:
            print(f"    {t}: MISSING")
            ok = False
            continue
        verdict = {}
        for img, label in ((gold, "silicon"), (ours, "ours")):
            xs = _white_columns(img, 225, 255)
            if len(xs) < 3:
                verdict[label] = None
                continue
            steps = {xs[i + 1] - xs[i] for i in range(len(xs) - 1)}
            verdict[label] = steps
        differing = int((gold != ours).any(axis=2).sum())
        print(f"    {t}: silicon spacing {verdict['silicon']}, "
              f"ours {verdict['ours']}, differing {differing} px")
        if verdict["silicon"] != {expect["floor"]} or \
           verdict["ours"] != {expect["rint"]}:
            ok = False

    # point_size_tests.cpp:323  cy = floorf((480 - 64) / 3). The green geometry
    # is a 64-square at top = cy - 32 plus a ruler bar 4 px above it, and the
    # whole lambda runs a second time at 2*cy -- so the topmost green row is
    # cy - 36 and the bottom-most is 2*cy - 32 + 63 = 2*cy + 31.
    arg = (480.0 - 64.0) / 3.0
    cy_floor, cy_rint = int(math.floor(arg)), int(round(arg))
    print(f"  LargestPointSize cy = floorf({arg:.6f}): "
          f"floor {cy_floor} (top {cy_floor - 36}, bottom {2 * cy_floor + 31}), "
          f"rint {cy_rint} (top {cy_rint - 36}, bottom {2 * cy_rint + 31})")
    for t in ("LargestPointSize_FF", "LargestPointSize_VS"):
        gold, ours = get_pair(t, suite="Point_size")
        if gold is None or ours is None:
            print(f"    {t}: MISSING")
            ok = False
            continue
        box = {}
        for img, label in ((gold, "silicon"), (ours, "ours")):
            m = (img[:, :, 1].astype(int) > 150) & (img[:, :, 0] < 60) & \
                (img[:, :, 2] < 60)
            ys = np.nonzero(m)[0]
            box[label] = (int(ys.min()), int(ys.max())) if len(ys) else None
        print(f"    {t}: silicon green rows {box['silicon']}, "
              f"ours {box['ours']}")
        if box["silicon"] != (cy_floor - 36, 2 * cy_floor + 31) or \
           box["ours"] != (cy_rint - 36, 2 * cy_rint + 31):
            ok = False

    print(f"  points leg: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("results",
                    help="result or captures directory holding Blend_tests")
    ap.add_argument("--point-results",
                    help="result directory holding Point_size, if it is a "
                         "different arm; the two suites are rarely on one disc")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cap_dir = args.results
    point_dir = args.point_results or args.results

    def get_pair(test, suite="Blend_tests"):
        root = point_dir if suite == "Point_size" else cap_dir
        ours_path = captures_mod.find(root, suite, test)
        gold_path = os.path.join(args.goldens, suite, f"{test}.png")
        ours = np.array(Image.open(ours_path).convert("RGBA"), dtype=np.uint8) \
            if ours_path and os.path.exists(ours_path) else None
        gold = np.array(Image.open(gold_path).convert("RGBA"), dtype=np.uint8) \
            if os.path.exists(gold_path) else None
        return gold, ours

    print(f"captures: {captures_mod.resolve(cap_dir)}")
    if point_dir != cap_dir:
        print(f"Point_size: {captures_mod.resolve(point_dir)}")
    print(f"goldens:  {args.goldens}")
    print("geometry leg -- Blend_tests #spot_* ownership under swatch 24 vs 25")
    a = leg_geometry(get_pair, args.verbose)
    print("points leg -- Point_size recovers two more floorf arguments")
    b = leg_points(get_pair, args.verbose)
    print(f"VERDICT: {'PASS' if (a and b) else 'FAIL'}")
    return 0 if (a and b) else 1


if __name__ == "__main__":
    sys.exit(main())
