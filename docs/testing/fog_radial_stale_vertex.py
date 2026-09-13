#!/usr/bin/env python3
"""#41: which stale vertex the program-mode RADIAL fog coordinate comes from.

    fog_radial_stale_vertex.py [--goldens DIR]            # the derivation
    fog_radial_stale_vertex.py --results DIR [--goldens DIR]   # judge an arm

`fog_radial_band.py` established that silicon's program-mode RADIAL fog
coordinate is in **(204.06, 221.81)** and is the same on all 374 quads, by
inverting the two `Fog_gen` VS radial goldens that are not clipped. That
recovery says what the coordinate *is*; it does not say where it comes from,
and the entry was refused twice on the reading that the answer is a property
of the test scene and therefore not computable.

This script closes that. Three measurements, in order:

1. **The scene is reconstructed, and the reconstruction is checked against
   silicon rather than asserted.** `FogGen_FF-linear-radial` is the fixed
   function radial cell in linear mode, where `f = 1 - d/200` inverts to a
   distance per quad at 0.78 units of resolution. The model below agrees with
   it to +0.38 +/- 0.23 over 360 unclipped quads, worst 0.82 -- one
   quantisation step. So `length(modelview . v)` *is* what silicon's radial
   generator computes, and the geometry is good enough to evaluate at a named
   vertex.

2. **The last vertex the fixed function scene draws is in the band.** Quad
   373's fourth vertex sits at 215.93, and every vertex of the final four
   quads is between 210.35 and 219.67. The mechanism does not have to name
   the exact register slot to predict the window, which is the difference
   between this and fitting a constant.

3. **The text overlay is excluded.** Each test draws its label last, so "the
   last fixed function vertex" could have been a text vertex. The two
   captures that pin the coordinate are preceded by labels 40 px apart in
   their right edge. For a text vertex to be in the band at all, its position
   vector has to be ~210 long with x dominating, so 40 px of x is ~40 units
   of coordinate against a band 17.74 wide: no text-derived model puts both
   pinning captures in one window. The quad grid's tail does, because all six
   VS tests draw the identical grid.

With `--results`, the same geometry judges an arm: per capture it reports the
drawn region's colour, the coordinate that colour inverts to, and the
differing-pixel count against the golden. A fix that carries the stale
coordinate should land every capture on the golden's single colour; a fix that
merely saturates leaves the two interior captures at (255, 0, 0) against a
golden of (254, 0, 1), which is the 724,064 channels `fog_radial_band.py`
prices.
"""

import argparse
import collections
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as captures_mod  # noqa: E402

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("needs numpy and pillow")

DEFAULT_GOLDENS = "/mnt/wslg/distro/home/justin/goldens/results"

# ---------------------------------------------------------------------------
# fog_gen_tests.cpp, and the shaders it drives.
#
# The grid: 22px quads, 2px spacing, 48/70 padding. Each quad is unprojected
# at world z = -6 + 0.5*i, and its two right-hand vertices one unit further
# (kQuadZRightInc). Both paths use fov pi/4, near 1, far 200 and a camera at
# (0, 0, -7) looking at the origin -- the vertex shader through
# PerspectiveVertexShaderNoLighting and LookAt, the fixed function path
# through SetXDKDefaultViewportAndFixedFunctionMatrices, whose
# BuildDefaultXDKModelViewMatrix is the same LookAtLH. So one geometry serves
# both, which is what makes a distance recovered from an FF capture usable at
# a VS capture's vertex.
FB_W, FB_H = 640.0, 480.0
QW = 22.0
SIDE_PAD, TOP_PAD, SPACE_H, SPACE_V = 48.0, 70.0, 2.0, 2.0
QUAD_Z, Z_INC, Z_RIGHT_INC = -6.0, 0.5, 1.0
FOV_Y = math.pi * 0.25
ASPECT = FB_W / FB_H
Y_SCALE = 1.0 / math.tan(FOV_Y * 0.5)
CAMERA_Z = -7.0

FOG_END = 200.0
LN_256 = 5.5452
M_EXP = -0.025 / (2.0 * LN_256)

# fog_radial_band.py's result, which this script's job is to explain.
BAND = (204.06, 221.81)
DRAWN_PX = 181016

MODES = ["linear", "exp", "exp2", "exp_abs", "exp2_abs", "linear_abs"]


def quads():
    """The quad list a Fog gen test draws, in draw order."""
    right = FB_W - (SIDE_PAD + QW)
    bottom = FB_H - QW
    out = []
    left, top, z, i = SIDE_PAD, TOP_PAD, QUAD_Z, 0
    while top < bottom:
        out.append((i, left, top, z))
        left += QW + SPACE_H
        if left >= right:
            left, top = SIDE_PAD, top + QW + SPACE_V
        z += Z_INC
        i += 1
    return out


def quad_vertices(left, top, z):
    """The four vertices in draw order: UL, UR, LR, LL."""
    right, bottom = left + QW, top + QW
    return [("UL", left, top, z),
            ("UR", right, top, z + Z_RIGHT_INC),
            ("LR", right, bottom, z + Z_RIGHT_INC),
            ("LL", left, bottom, z)]


def radial(screen_x, screen_y, world_z):
    """|modelview . v| for the world point that unprojects from this screen
    point at this world z -- what vsh-ff.c computes as
    length(tPosition.xyz)."""
    z_eye = world_z - CAMERA_Z
    x_eye = (screen_x - FB_W / 2) / (FB_W / 2) * (ASPECT / Y_SCALE) * z_eye
    y_eye = -(screen_y - FB_H / 2) / (FB_H / 2) * (1.0 / Y_SCALE) * z_eye
    return math.sqrt(x_eye * x_eye + y_eye * y_eye + z_eye * z_eye)


# ---------------------------------------------------------------------------


def load(path):
    return np.array(Image.open(path).convert("RGB"))


def golden(root, name):
    p = os.path.join(root, "Fog_gen", name + ".png")
    if not os.path.exists(p):
        sys.exit("missing golden: %s" % p)
    return load(p)


def factor_at(img, left, top, inset=3):
    """The 8-bit fog factor at a quad's centre, or None where the pixel is
    not the f*(0,0,1) + (1-f)*(1,0,0) mix -- background or printed label."""
    x, y = int(left + QW / 2), int(top + QW / 2)
    blk = img[y - inset:y + inset, x - inset:x + inset]
    r, b = blk[..., 0].astype(int), blk[..., 2].astype(int)
    if r.min() != r.max() or b.min() != b.max():
        return None
    if int(r[0, 0]) + int(b[0, 0]) != 255:
        return None
    return int(b[0, 0])


def drawn_colour(img):
    """(colour, count) of the single mix colour in a VS radial capture."""
    flat = img.reshape(-1, 3)
    cnt = collections.Counter(map(tuple, flat))
    mix = [(c, n) for c, n in cnt.items()
           if c[1] == 0 and int(c[0]) + int(c[2]) == 255]
    return [(tuple(int(v) for v in c), n) for c, n in
            sorted(mix, key=lambda t: -t[1])]


def label_right_edge(img):
    """Rightmost column of the white printed label."""
    ys, xs = np.where((img[:, :, 0] > 200) & (img[:, :, 1] > 200) &
                      (img[:, :, 2] > 200))
    if not len(xs):
        return None
    return int(xs.max()), int(ys.max())


def coord_from_f8(f8):
    """Invert an exp-mode 8-bit factor to a coordinate window.

    Only the exp modes are invertible here; the others clip. Bias is 1.5 in
    fog_gen_tests.cpp so it cancels and fogX = coord * M_EXP. The window edges
    come from fog_radial_band.py's calibration of silicon's own exp unit:
    f8 = 1 iff fogX in (-0.5000, -0.4600).
    """
    if f8 == 1:
        return BAND
    if f8 == 0:
        return (-0.4600 / M_EXP, math.inf)
    lo = math.log2(max(f8 + 0.5, 0.5) / 255.0) / 16.0 / M_EXP
    hi = math.log2(max(f8 - 0.5, 0.5) / 255.0) / 16.0 / M_EXP
    return (min(lo, hi), max(lo, hi))


# ---------------------------------------------------------------------------


def derive(root):
    rc = 0
    grid = quads()
    print("== 1. the reconstruction, against silicon's own FF radial cell ==")
    lin = golden(root, "FogGen_FF-linear-radial")
    diffs = []
    for (i, left, top, z) in grid:
        f8 = factor_at(lin, left, top)
        if f8 is None or f8 == 0:
            continue  # clipped: d >= 200 carries no information in linear
        model = radial(left + QW / 2, top + QW / 2, z + Z_RIGHT_INC * 0.5)
        diffs.append(FOG_END * (1.0 - f8 / 255.0) - model)
    d = np.array(diffs)
    print("   %d unclipped quads: silicon - model = %+.3f +/- %.3f, "
          "range %+.3f .. %+.3f" % (len(d), d.mean(), d.std(), d.min(),
                                    d.max()))
    step = FOG_END / 255.0
    print("   one quantisation step is %.3f, so the worst disagreement is "
          "%.2f steps" % (step, abs(d).max() / step))
    if abs(d).max() > 1.5 * step:
        print("   FAIL: the geometry does not reproduce silicon's own "
              "distances")
        rc = 1

    print("\n== 2. the last vertex the fixed-function scene draws ==")
    last_i, last_l, last_t, last_z = grid[-1]
    for (i, left, top, z) in grid[-4:]:
        print("   quad %3d: %s" % (i, "  ".join(
            "%s %7.2f" % (n, radial(sx, sy, wz))
            for (n, sx, sy, wz) in quad_vertices(left, top, z))))
    last = radial(last_l, last_t + QW, last_z)
    tail = [radial(sx, sy, wz) for (_, l, t, z) in grid[-4:]
            for (_, sx, sy, wz) in quad_vertices(l, t, z)]
    print("   last vertex drawn (quad %d, LL) = %.2f" % (last_i, last))
    print("   goldens require the coordinate in (%.2f, %.2f)" % BAND)
    inside = BAND[0] < last < BAND[1]
    print("   => %s" % ("IN the band" if inside else "OUT of the band"))
    if not inside:
        print("   FAIL: the stale-last-vertex model does not predict the band")
        rc = 1
    print("   the final four quads' 16 vertices span %.2f .. %.2f, and %d of "
          "them are in the band" % (min(tail), max(tail),
                                    sum(1 for v in tail
                                        if BAND[0] < v < BAND[1])))

    print("\n== 3. the text overlay, which the same band excludes ==")
    print("   each test draws its label last, so the stale vertex could have")
    print("   been a text one. The two captures that pin the coordinate:")
    pinned = []
    for mode in MODES:
        cap = golden(root, "FogGen_VS-%s-radial" % mode)
        mix = drawn_colour(cap)
        f8 = mix[0][0][2] if mix else None
        prev = golden(root, "FogGen_VS-%s-planar" % mode)  # runs just before
        edge = label_right_edge(prev)
        pinned.append((mode, f8, edge))
    for (mode, f8, edge) in pinned:
        marker = "  <- pins the coordinate" if f8 == 1 else ""
        print("   %-11s f8=%-3s preceding label right edge col %s%s"
              % (mode, f8, edge[0] if edge else "?", marker))
    edges = [e[0] for (m, f8, e) in pinned if f8 == 1 and e]
    if len(edges) >= 2:
        spread = max(edges) - min(edges)
        print("   the two pinning captures' labels are %d px apart in x." %
              spread)
        print("   A text vertex in the band has |v| ~ 210 with x dominating, "
              "so that is")
        print("   ~%d units of coordinate against a band %.2f wide: "
              "excluded." % (spread, BAND[1] - BAND[0]))
        if spread < BAND[1] - BAND[0]:
            print("   FAIL: the label spread is inside the band, so this "
                  "does not exclude the overlay")
            rc = 1
    else:
        print("   FAIL: could not find two pinning captures")
        rc = 1
    return rc


def judge(root, results):
    rc = 0
    cap_dir = captures_mod.resolve(results, "Fog_gen::*.png")
    print("== arm: FogGen_VS-*-radial against the goldens ==")
    print("   captures resolved to %s" % cap_dir)
    print(" mode        ours                gold              differing  "
          "our coord")
    for mode in MODES:
        name = "FogGen_VS-%s-radial" % mode
        p = captures_mod.find(results, "Fog_gen", name)
        if p is None:
            print("   %-11s MISSING" % mode)
            rc = 1
            continue
        ours, gold = load(p), golden(root, name)
        if ours.shape != gold.shape:
            print("   %-11s shape %s vs %s" % (mode, ours.shape, gold.shape))
            rc = 1
            continue
        differing = int((ours != gold).any(axis=2).sum())
        omix, gmix = drawn_colour(ours), drawn_colour(gold)
        oc = "%s x%d" % (omix[0][0], omix[0][1]) if omix else "none"
        gc = "%s x%d" % (gmix[0][0], gmix[0][1]) if gmix else "none"
        coord = ""
        if omix and mode in ("exp", "exp_abs"):
            lo, hi = coord_from_f8(omix[0][0][2])
            coord = "(%.1f, %.1f)" % (lo, hi)
        print("   %-11s %-19s %-17s %9d  %s"
              % (mode, oc, gc, differing, coord))
        if differing:
            rc = 1
        if omix and len(omix) > 1:
            print("       note: %d distinct mix colours, so the coordinate "
                  "varies across the scene -- a per-vertex model, not a "
                  "carried one" % len(omix))
    print("\n   expected drawn region is %d px in every capture" % DRAWN_PX)
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldens", default=DEFAULT_GOLDENS)
    ap.add_argument("--results", help="a dispatcher result or captures dir")
    args = ap.parse_args()
    if args.results:
        rc = judge(args.goldens, args.results)
    else:
        rc = derive(args.goldens)
    print("\n%s" % ("PASS" if rc == 0 else "FAIL"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
