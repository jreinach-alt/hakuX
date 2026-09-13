#!/usr/bin/env python3
"""#43's factor-independent region in Blend tests' `#spot_` captures, measured
as a region.

Why this file exists, which is the whole point of it
----------------------------------------------------

The `ONE`/`ONE` fix for `FUNC_ADD_SIGNED` left all fifteen
`Blend_tests/#spot_*_SADD` captures disagreeing with their goldens over
**exactly 104,205 pixels**, where before the fix the counts varied per capture
from 91,310 to 111,381. Fifteen different blend factors collapsing to one
number reads as an input no longer being read, and that is how it was first
filed.

Two readings were then published and both were wrong, for the same reason:

1. "the factor is ignored on the SADD path, the fifteen captures must be
   byte-identical" -- checked by sha256 over the whole PNG, which came back
   *fifteen distinct images*, and the reading was withdrawn;
2. "the blend factor IS being applied, because fifteen distinct sha256s" --
   which is this file's reason to exist.

`TestSpot` ends with ``pb_printat(0, 0, name)``, so **every capture carries its
own test name rendered into the top rows of the framebuffer**. A sha256 over
the whole PNG therefore always reports fifteen distinct images, whatever the
renderer did, and so does the same sha over the fifteen goldens. Crop the label
away and the goldens collapse to **one** image under `SADD` -- silicon renders
one picture for all fifteen source factors, because the signed equations ignore
the factors.

So the collapse is the fix working. Measured with the label cropped, our
renderer's factor sensitivity now matches silicon's on all seven equations,
and `MIN`/`MAX` -- which ignore the factors by specification on both sides --
are the built-in control that says a 1 is a real 1.

Everything here compares REGIONS, and crops ``LABEL_ROWS`` before comparing
anything. Both of this suite's bad calls were a point measurement (a whole-file
hash, a whole-capture pixel total) standing in for a region.

What the 104,205 is
-------------------

Per cell of the 5x3 grid, exactly, with nothing left over::

    6,947 = 4,608  DrawColorStack + DrawColorAndAlphaStack, every pixel
          +        (their four diffuse colours have every non-zero component
          |         at 0xDD or 0xFF, so every pixel carries at least one
          |         channel whose source byte is >= 128: the sign fold)
          + 1,849  DrawAlphaStack's nested quads 1..3 (alpha sources 0xFF,
          |         0x80, 0x00 -- the third is exact in itself and inherits
          |         quad 2's wrong alpha as its blend destination)
          +   490  quad-edge seam, the part of it the sign fold does not
                   already cover

times fifteen cells: 96,855 sign fold + 7,350 seam-only = 104,205.

The seam is a separate, pre-existing defect and the decomposition is stated so
that neither of its two inputs is derived from the captures being judged:

* ``ink_mask()`` comes from `blend_tests.cpp` -- the quad rectangles and their
  diffuse colours -- and from the signed rule. No capture goes into it.
* ``seam_mask()`` is the union of the differing-pixel masks of the **75
  unsigned** ``#spot_*`` captures, and what makes it a rule rather than a fit
  is that the union is the *same* 1,276-pixel set in all fifteen cells whatever
  the equation and whatever the factor -- 1,276 x 15 = 19,140, which is the
  whole residual of ``#spot_srcA_ADD``. It is a 1-2 px band on quad edges
  (columns 24 and 48-49, the left columns of each nested alpha quad, and the
  rows below each swatch), so it is a rasterisation class and not an
  arithmetic one. Nothing about a signed capture chooses it.

So "differing == ink | seam, to the pixel" is a prediction and not a
description: a second defect anywhere in the swatch area lands outside both.

`DrawAlphaStack`'s outer ring is the control inside the picture. Its alpha
source is 0x7F = 127, the only blended source byte in the whole frame below
128, and it is bit-exact -- the same "below 128 is now exact" result the
`Texture_signed_component_tests` arm measured at the channel level, reproduced
here as a region in a suite that reaches the framebuffer by a different path.

Geometry is derived from `blend_tests.cpp`, not guessed: `test_width` 99 with
4 of spacing and `test_height` 136 put cell (r, c) at
(64 + 103c, 64 + 136r) once the 512x512 render target is blitted to +64,+64;
`color_swatch_size` is floor(99/4) = 24.

    signed_blend_spot_region.py <result-dir> [--goldens DIR] [--eqn SADD]

Takes a dispatcher result directory or a captures directory -- `captures.resolve`
handles both, because a falsifier that cannot find its own evidence answers
anyway, and that is worse than no falsifier.
"""
import argparse
import collections
import hashlib
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as captures_mod

#: `pb_printat(0, 0, ...)` writes the test name here, and the 512x512 render
#: target is blitted at +64, so nothing below this row can be label. Cropping
#: it is not cosmetic: it is what separates "fifteen pictures" from "fifteen
#: captions".
LABEL_ROWS = 64

#: blend_tests.cpp: 5 cells across, 3 down, test_width 99 + 4 spacing,
#: test_height 136, render target blitted to (64, 64).
CELL_DX, CELL_DY, CELL_W, CELL_H = 103, 136, 103, 136
BLIT_X, BLIT_Y = 64, 64
GRID_COLS, GRID_ROWS = 5, 3

#: The fifteen destination factors, in the order the cells are drawn, and the
#: fifteen source factors, which are the same list.
FACTORS = ["0", "1", "srcRGB", "1-srcRGB", "srcA", "1-srcA", "dstA", "1-dstA",
           "dstRGB", "1-dstRGB", "srcAsat", "cRGB", "1-cRGB", "cA", "1-cA"]

EQUATIONS = ["ADD", "SUB", "REVSUB", "MIN", "MAX", "SADD", "SREVSUB"]

#: Silicon's factor sensitivity, counted over the fifteen goldens of each
#: equation with the label cropped. Recomputed from the goldens on every run
#: and only *reported* against this table, so the table is a record of what was
#: measured rather than an input to the verdict.
#:
#: 13 rather than 15 for ADD/SUB because kBlendColorConstant is 0x55555555, so
#: CONSTANT_COLOR and CONSTANT_ALPHA are the same factor here, twice over
#: (cRGB==cA, 1-cRGB==1-cA). REVSUB collapses six pairs. MIN/MAX ignore the
#: factors by specification, and the signed equations ignore them in silicon --
#: which is the rule #43 rests on.
SILICON_DISTINCT = {"ADD": 13, "SUB": 13, "REVSUB": 9, "MIN": 1, "MAX": 1,
                    "SADD": 1, "SREVSUB": 1}

#: The signed equations under test, and the unsigned ones whose union is the
#: seam class. Using the union of all five unsigned equations over all fifteen
#: factors, rather than the same-factor ADD capture, matters: an individual
#: unsigned capture gets some seam pixels right by arithmetic accident, so
#: pairing SADD with one of them charges those accidents to the sign fold.
#: That first draft of this file reported six of the fifteen captures as
#: carrying "a second defect" for exactly that reason.
SIGNED = ["SADD", "SREVSUB"]
UNSIGNED = ["ADD", "SUB", "REVSUB", "MIN", "MAX"]


def ink_mask():
    """The pixels of one cell whose blended source byte is >= 128.

    Derived, not fitted. `DrawColorStack` (x 0..23) and
    `DrawColorAndAlphaStack` (x 24..47) both draw four 24-square quads down
    96 rows, and their diffuse colours -- 0xDD00DD00, 0xDDDD0000, 0xDD0000DD,
    0xDDFFFFFF -- have every non-zero component at 0xDD or 0xFF, with alpha
    0xDD. So every pixel of that 48x96 block carries at least one channel the
    sign fold gets wrong.

    `DrawAlphaStack` blends only alpha, over four nested quads inset by 4 at
    x 48..98, y 0..50, with alpha sources 0x7F, 0xFF, 0x80, 0x00. Only the
    outer one is below 128; quad 1 is the 43-square at x 52..94, y 4..46, and
    everything inside it is wrong -- quad 2 directly, quad 3 because its own
    exact blend reads quad 2's wrong alpha as its destination.
    """
    m = np.zeros((CELL_H, CELL_W), dtype=bool)
    m[0:96, 0:48] = True            # ColorStack + ColorAndAlphaStack
    m[4:47, 52:95] = True           # AlphaStack nested quads 1, 2, 3
    return m


def alpha_ring0_mask():
    """`DrawAlphaStack`'s outer ring: the only blended source byte below 128.

    The 51-square at x 48..98, y 0..50 minus quad 1's 43-square. Alpha source
    0x7F = 127, so `clamp(signed(127) + D)` and `clamp(127 + D)` agree and this
    ring must be bit-exact. It is the control that lives inside the picture.
    """
    m = np.zeros((CELL_H, CELL_W), dtype=bool)
    m[0:51, 48:99] = True
    m[4:47, 52:95] = False
    return m


def seam_mask(get, fails):
    """The equation-independent quad-edge residual, one cell.

    The union over the 75 unsigned ``#spot_*`` captures. Also checks that the
    union really is one set in all fifteen cells: if it is not, this is not a
    seam class and must not be used as one.
    """
    u = np.zeros((CELL_H, CELL_W), dtype=bool)
    per_cell = [np.zeros((CELL_H, CELL_W), dtype=bool)
                for _ in range(GRID_ROWS * GRID_COLS)]
    n = 0
    for eqn in UNSIGNED:
        for f in FACTORS:
            t = "#spot_%s_%s" % (f, eqn)
            o, g = get[0](t), get[1](t)
            if o is None or g is None:
                fails.append("SEAM %s: capture missing; absent is not zero "
                             "and a short union under-predicts" % t)
                continue
            d = (o != g).any(axis=2)
            d[:LABEL_ROWS, :] = False
            for i, c in enumerate(cells(d)):
                per_cell[i] |= c
            n += 1
    for c in per_cell:
        u |= c
    same = all((c == per_cell[0]).all() for c in per_cell)
    return u, n, same


def cells(a):
    """The 15 grid cells of a full-frame array, row-major as drawn."""
    return [a[BLIT_Y + CELL_DY * r: BLIT_Y + CELL_DY * r + CELL_H,
              BLIT_X + CELL_DX * c: BLIT_X + CELL_DX * c + CELL_W]
            for r in range(GRID_ROWS) for c in range(GRID_COLS)]


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16)


def sha_below_label(a):
    return hashlib.sha256(
        np.ascontiguousarray(a[LABEL_ROWS:, :]).tobytes()).hexdigest()


def fingerprint(get, label):
    """Distinct rendered images per equation, label cropped.

    Returns {eqn: (distinct, [groups of factors that collapsed]) } or None for
    an equation whose captures are not all present -- absent is not zero.
    """
    out = {}
    for eqn in EQUATIONS:
        groups = collections.defaultdict(list)
        missing = []
        for f in FACTORS:
            img = get("#spot_%s_%s" % (f, eqn))
            if img is None:
                missing.append(f)
                continue
            groups[sha_below_label(img)].append(f)
        if missing:
            print("  %-8s MISSING %d of 15 in %s: %s"
                  % (eqn, len(missing), label, ",".join(missing)))
            out[eqn] = None
            continue
        out[eqn] = (len(groups),
                    sorted(v for v in groups.values() if len(v) > 1))
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("result", help="dispatcher result dir, or a captures dir")
    ap.add_argument("--goldens", default="/home/justin/goldens/results/Blend_tests")
    ap.add_argument("--eqn", default="SADD", choices=SIGNED,
                    help="which signed equation to decompose (default SADD)")
    args = ap.parse_args()

    root = captures_mod.resolve(args.result, "Blend_tests::*.png")
    ours_cache, gold_cache = {}, {}

    def ours(test):
        if test not in ours_cache:
            p = captures_mod.find(args.result, "Blend_tests", test)
            ours_cache[test] = load(p) if p and os.path.exists(p) else None
        return ours_cache[test]

    def gold(test):
        if test not in gold_cache:
            p = os.path.join(args.goldens, test + ".png")
            gold_cache[test] = load(p) if os.path.exists(p) else None
        return gold_cache[test]

    print("captures: %s" % root)
    print("goldens : %s" % args.goldens)
    fails = []

    # ------------------------------------------------------------------
    # Leg 1. Factor sensitivity, which is what the 104,205 was mistaken for.
    # ------------------------------------------------------------------
    print("\n=== LEG 1  factor sensitivity: distinct rendered images of 15, "
          "label cropped ===")
    fg_g = fingerprint(gold, "goldens")
    fg_o = fingerprint(ours, "captures")
    print("  %-8s %8s %8s %8s" % ("eqn", "silicon", "ours", "recorded"))
    for eqn in EQUATIONS:
        g, o = fg_g.get(eqn), fg_o.get(eqn)
        if g is None or o is None:
            fails.append("LEG 1 %s: captures missing, absent is not zero" % eqn)
            continue
        rec = SILICON_DISTINCT[eqn]
        ok = (g[0] == o[0])
        print("  %-8s %8d %8d %8d   %s%s"
              % (eqn, g[0], o[0], rec, "ok" if ok else "FAIL",
                 "" if g[0] == rec else "  (silicon differs from the "
                                        "recorded table -- goldens changed)"))
        if not ok:
            fails.append("LEG 1 %s: silicon renders %d distinct images for the "
                         "15 source factors, we render %d" % (eqn, g[0], o[0]))
        if g[1]:
            print("           silicon collapses: %s"
                  % "; ".join("=".join(v) for v in g[1]))

    # ------------------------------------------------------------------
    # Leg 2. The region, decomposed. Sign fold + pre-existing seam, no more.
    # ------------------------------------------------------------------
    eqn = args.eqn
    ink = ink_mask()
    ring0 = alpha_ring0_mask()
    seam, n_seam, seam_same = seam_mask((ours, gold), fails)
    print("\n=== SEAM  the equation-independent quad-edge residual ===")
    print("  union of %d unsigned #spot_ captures: %d px per cell, "
          "identical in all 15 cells: %s"
          % (n_seam, int(seam.sum()), seam_same))
    if not seam_same:
        fails.append("SEAM: the unsigned residual is not the same set in every "
                     "cell, so it is not a geometric seam class and must not "
                     "be subtracted as one")
    print("\n=== LEG 2  %s region = sign fold (source byte >= 128) | seam, "
          "to the pixel ===" % eqn)
    print("  %-14s %8s %8s %8s %8s %8s %10s"
          % ("capture", "differ", "ink", "seam", "unexpl", "overpr", "mask_sha"))
    masks = {}
    pred = ink | seam
    for f in FACTORS:
        t = "#spot_%s_%s" % (f, eqn)
        o, g = ours(t), gold(t)
        if o is None or g is None:
            fails.append("LEG 2 %s: capture missing" % t)
            continue
        d = (o != g).any(axis=2)
        d[:LABEL_ROWS, :] = False
        masks[f] = d
        tot = ink_px = seam_px = unexpl = overpr = 0
        for dcell in cells(d):
            tot += int(dcell.sum())
            ink_px += int((dcell & ink).sum())
            seam_px += int((dcell & ~ink).sum())
            unexpl += int((dcell & ~pred).sum())
            overpr += int((pred & ~dcell).sum())
        outside = int(d.sum()) - tot
        print("  %-14s %8d %8d %8d %8d %8d   %s%s"
              % (f, int(d.sum()), ink_px, seam_px, unexpl, overpr,
                 hashlib.sha256(d.tobytes()).hexdigest()[:10],
                 "" if not outside else "  %d px OUTSIDE the grid" % outside))
        if unexpl:
            fails.append("LEG 2 %s: %d differing px are neither the sign fold "
                         "nor the seam class -- a second defect" % (t, unexpl))
        if overpr:
            fails.append("LEG 2 %s: %d px that the sign fold or the seam must "
                         "get wrong are exact -- the mechanism is not what is "
                         "described" % (t, overpr))
        if outside:
            fails.append("LEG 2 %s: %d differing px outside the 5x3 grid"
                         % (t, outside))
    if masks:
        shas = {hashlib.sha256(m.tobytes()).hexdigest() for m in masks.values()}
        print("  distinct differing-pixel MASKS across the %d captures: %d"
              % (len(masks), len(shas)))
        if len(shas) != 1:
            fails.append("LEG 2: the region is not one pixel set (%d distinct "
                         "masks) -- the 104,205 would be cardinality, not a "
                         "region, and the diagnosis changes completely"
                         % len(shas))

    # ------------------------------------------------------------------
    # Leg 3. The below-128 control, inside the same picture.
    # ------------------------------------------------------------------
    print("\n=== LEG 3  DrawAlphaStack's outer ring, alpha source 0x7F = 127, "
          "must be bit-exact ===")
    # The seam class is pre-existing and equation-independent, so it is
    # excluded here rather than charged to the sign fold.
    keep = ring0 & ~seam
    for e in SIGNED:
        worst = 0
        kept = 0
        for f in FACTORS:
            t = "#spot_%s_%s" % (f, e)
            o, g = ours(t), gold(t)
            if o is None or g is None:
                fails.append("LEG 3 %s: capture missing" % t)
                continue
            d = (o != g).any(axis=2)
            d[:LABEL_ROWS, :] = False
            for dcell in cells(d):
                kept += int(keep.sum())
                worst += int((dcell & keep).sum())
        print("  %-8s %7d px of ring 0 (seams excluded), %d differing   %s"
              % (e, kept, worst, "ok" if worst == 0 else "FAIL"))
        if worst:
            fails.append("LEG 3 %s: %d px with source byte 127 differ. The "
                         "factor half of the rule is not exact below 128."
                         % (e, worst))

    print("\n" + "=" * 68)
    if fails:
        print("FAIL -- %d leg(s):" % len(fails))
        for f in fails:
            print("  * %s" % f)
        return 1
    print("PASS -- the factor-independent region is the sign fold and the "
          "pre-existing seam class, and nothing else.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
