#!/usr/bin/env python3
"""Reproduce every number in docs/investigations/image-blit-residual-is-not-the-blit.md.

    python3 docs/testing/blit_residual_anatomy.py [captures_dir] [goldens_dir]

Defaults to /tmp/pgraph-run/score_blit84/blit84 and /tmp/goldens/results/Image_blit.
Captures are named "Image_blit::<test>.png"; goldens are "<test>.png".

The point of the script is that the conclusion -- the Image_blit residual is in
interpolated vertex colour, not in gl/blit.c -- rests on measurements anyone can
re-run, not on a reading of the code.
"""
import os
import sys
import glob

import numpy as np
from PIL import Image

CAPS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pgraph-run/score_blit84/blit84"
GOLD = sys.argv[2] if len(sys.argv) > 2 else "/tmp/goldens/results/Image_blit"

# From nxdk_pgraph_tests src/tests/image_blit_tests.cpp:654 TestOverlapBarelyInclusive.
# A render-to-surface 128x128 Gouraud quad at (64,64), a 4x4 quad at (320,240) to
# force the 3D unit to wait on the 2D blit, and a blit of width 1, height 1.
SURF_X, SURF_Y, SURF_W, SURF_H = 64, 64, 128, 128
SMALL = (238, 248, 318, 328)          # generous box around the 4x4 quad
BLIT_DEST = {                         # (x, y) of the single blitted pixel
    "Overlap_TL_Inside": (64, 64),   "Overlap_TL_Outside": (63, 64),
    "Overlap_TR_Inside": (191, 64),  "Overlap_TR_Outside": (192, 64),
    "Overlap_BL_Inside": (64, 191),  "Overlap_BL_Outside": (63, 191),
    "Overlap_BR_Inside": (191, 191), "Overlap_BR_Outside": (192, 191),
}


def pair(test):
    a = Image.open(os.path.join(CAPS, "Image_blit::%s.png" % test)).convert("RGBA")
    b = Image.open(os.path.join(GOLD, "%s.png" % test)).convert("RGBA")
    a = np.asarray(a, dtype=np.int16)
    b = np.asarray(b, dtype=np.int16)
    return a, b, a - b


def rule(title):
    print("\n== %s ==" % title)


def main():
    tests = sorted(os.path.basename(p)[:-4].split("::", 1)[1]
                   for p in glob.glob(os.path.join(CAPS, "Image_blit::*.png")))
    if not tests:
        sys.exit("no captures under %s" % CAPS)

    rule("whole suite")
    total = 0
    nonzero = []
    for t in tests:
        if not os.path.exists(os.path.join(GOLD, "%s.png" % t)):
            print("  %-44s NO GOLDEN" % t)
            continue
        _, _, d = pair(t)
        n = int(np.count_nonzero(d))
        total += n
        if n:
            nonzero.append((n, int(np.abs(d).max()), t))
    for n, mx, t in sorted(nonzero, reverse=True):
        print("  %-44s %7d  max|d|=%d" % (t, n, mx))
    print("  %-44s %7d over %d captures, %d byte-exact"
          % ("TOTAL", total, len(tests), len(tests) - len(nonzero)))

    rule("the blit itself: width 1, height 1 -- is that pixel right?")
    bad = 0
    for t, (bx, by) in sorted(BLIT_DEST.items()):
        a, b, d = pair(t)
        delta = tuple(int(v) for v in d[by, bx])
        bad += any(delta)
        print("  %-20s dest=(%3d,%3d)  ours=%-18s golden=%-18s delta=%s"
              % (t, bx, by, tuple(int(v) for v in a[by, bx]),
                 tuple(int(v) for v in b[by, bx]), delta))
    print("  -> %d of %d blitted pixels differ" % (bad, len(BLIT_DEST)))

    rule("where the differing pixels are")
    for t in sorted(BLIT_DEST):
        _, _, d = pair(t)
        m = np.any(d != 0, axis=2)
        big = m[SURF_Y:SURF_Y + SURF_H, SURF_X:SURF_X + SURF_W].sum()
        small = m[SMALL[0]:SMALL[1], SMALL[2]:SMALL[3]].sum()
        rest = m.copy()
        rest[SURF_Y:SURF_Y + SURF_H, SURF_X:SURF_X + SURF_W] = False
        rest[SMALL[0]:SMALL[1], SMALL[2]:SMALL[3]] = False
        print("  %-20s total=%5d  big_quad=%5d  small_quad=%3d  ELSEWHERE=%d"
              % (t, m.sum(), big, small, rest.sum()))

    rule("the quad, split by its diagonals")
    _, _, d = pair("Overlap_TL_Inside")
    q = d[SURF_Y:SURF_Y + SURF_H, SURF_X:SURF_X + SURF_W]
    m = np.any(q != 0, axis=2)
    Y, X = np.mgrid[0:SURF_H, 0:SURF_W]
    for name, s1, s2 in (("main diag (TL-BR)", X > Y, X < Y),
                         ("anti diag (TR-BL)", X + Y > SURF_W - 1, X + Y < SURF_W - 1)):
        a1, n1 = int((m & s1).sum()), int(s1.sum())
        a2, n2 = int((m & s2).sum()), int(s2.sum())
        print("  %-18s  side1 %4d/%d (%4.1f%%)   side2 %4d/%d (%4.1f%%)"
              % (name, a1, n1, 100.0 * a1 / n1, a2, n2, 100.0 * a2 / n2))

    print("  per channel on the lower (X<Y) triangle -- one-sided means a scale error:")
    for c, nm in enumerate("RGBA"):
        dc = q[:, :, c]
        lo = int(((dc == -1) & (X < Y)).sum())
        hi = int(((dc == 1) & (X < Y)).sum())
        print("    %s: ours_low=%4d  ours_high=%4d" % (nm, lo, hi))

    edge = np.zeros((SURF_H, SURF_W), bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    print("  interior=%d  border=%d of %d (base rate %.1f%%) -- not a coverage rule"
          % (int((m & ~edge).sum()), int((m & edge).sum()), int(edge.sum()),
             100.0 * m.sum() / m.size))

    rule("the midpoint tie: hardware rounds half UP, we round half down")
    for t in sorted(BLIT_DEST):
        a, b, _ = pair(t)
        qa = a[SURF_Y:SURF_Y + SURF_H, SURF_X:SURF_X + SURF_W]
        qb = b[SURF_Y:SURF_Y + SURF_H, SURF_X:SURF_X + SURF_W]
        # R ramps 255 -> 0 across the quad, so x = w/2 is an exact .5 tie.
        ours = qa[0:SURF_H // 2, SURF_W // 2, 0]
        gold = qb[0:SURF_H // 2, SURF_W // 2, 0]
        print("  %-20s x=%d  ours=%s golden=%s  all delta==1: %s"
              % (t, SURF_W // 2, sorted(set(ours.tolist())),
                 sorted(set(gold.tolist())), bool(((gold - ours) == 1).all())))
    print("  exact value at x=w/2 on a 255->0 ramp is 127.5; hardware gives 128.")


if __name__ == "__main__":
    main()
