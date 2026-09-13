#!/usr/bin/env python3
"""Recover hardware's slope-offset ANCHOR for every triangle in `W buffering`.

    docs/testing/wbuf_anchor_recover.py --goldens /home/justin/goldens/results

Why this exists.  #31's residual was recorded as "a 4-pixel anchoring regime
the available goldens cannot select between", and a blocker is a claim that
needs the same evidence as a fix (AGENTS.md).  This is that evidence, and it
needs no device: every `ZS1` capture has a `ZS0` sibling of identical geometry,
the offset is one constant per triangle, and the depth stored is
``floor(w + offset)``.  So for each triangle

    offset in [ max(z - w), min(z + 1 - w) ]     over its pixels

is an EXACT interval, typically 0.002 wide on a value of 10^5 -- which pins
the anchor to a fraction of a pixel, because moving the anchor one pixel moves
the offset by 0.5% to 5%.

Read that way the corpus is far more informative than "cannot select":

  * All 24 `TriH` triangles anchor their ROW on an absolute 4-pixel grid at
    phase 2 -- `4*floor(y_top/4)+2` -- reproduced inside hardware's own
    interval for every one of them.
  * Every triangle the window clip CUT anchors at the first covered pixel
    snapped to the 2x2 quad, which is what the shipped code does: Wall both
    triangles, Roof both, Floor both, all three `ClipW`, and `ClipF`s first
    triangle.  Eleven for eleven.
  * `TriV` fits NEITHER.  No integer column reproduces its offsets: the best
    is 164, off by -122, +658, +1547 and +2555 units on the four residues,
    where this model is inside hardware's interval everywhere else.  So the
    "4-pixel grid" recorded for `TriV` is a fit, not a measurement, and 105,600
    of the 619,349 residual pixels are a third unmodelled thing.
  * `ClipF`s second triangle anchors at ``clip_top + 2``.  It is the one
    exception, and it is the one the corpus cannot resolve: see the module
    docstring of `--pairs`.

The oracle validates against itself in two ways, both printed:

  1. ``floor(w)`` from the recovered plane equals hardware's own `ZS0` depth on
     100% of the pixels of Floor, Roof, Wall and TriH (0.55% on TriV, 6 px per
     triangle at exact edges).  An instrument that could not reproduce the
     unbiased capture would not be allowed to arbitrate the biased one.
  2. `--simulate` emulates `wbufSlopeStep` in float32 and reproduces the
     DEVICE's exact/+-1/wrong split for `bdc26fa5c8` to the pixel on six of
     eight `WBuf24D` rows of `run-2026-09-10-wbuffer-adreno.tsv`.

This file writes nothing (AGENTS.md: a checker writes nothing).
"""

import argparse
import math
import os
import sys

W, H = 640, 480
CLEAR24 = 16777215
FACTOR_W = 65536.0

# ---------------------------------------------------------------- geometry
# From nxdk_pgraph_tests/src/tests/wbuf_tests.cpp.  V1 is the passthrough
# vertex shader, so these are screen coordinates and w is as pushed.


def _quad(v):
    """Hardware splits a QUAD on the v0-v2 diagonal; measured, see #31."""
    return [(v[0], v[1], v[2]), (v[0], v[2], v[3])]


FLOOR = _quad([(53.1875, -34.3125, 325.8057861328125),
               (586.75, -34.3125, 325.8057861328125),
               (1808.6875, 453.0, 58.379993438720703),
               (-1168.6875, 453.0, 58.379993438720703)])
ROOF = _quad([(-1168.6875, 0.0, 58.379993438720703),
              (1808.6875, 0.0, 58.379993438720703),
              (586.75, 487.3125, 325.8057861328125),
              (53.1875, 487.3125, 325.8057861328125)])
WALL = _quad([(637.3125, -26.8125, 325.8057861328125),
              (637.3125, 506.75, 325.8057861328125),
              (150.0, 1728.6875, 58.379993438720703),
              (150.0, -1248.6875, 58.379993438720703)])
_MD = 16777046.0
LARGEZ = _quad([(0.0, 0.0, _MD), (640.0, 0.0, _MD),
                (640.0, 480.0, _MD + 1.0), (0.0, 480.0, _MD + 1.0)])


def _trih():
    out, shift = [], 0.0
    for x in range(160, 640, 20):
        out.append(((x + 0.5, shift + 0.5, 325.0),
                    (x + 10.5, shift + 0.5, 325.0),
                    (x + 0.5, shift + 200.0, 58.0)))
        shift += 1.0
    return out


def _triv():
    out, shift = [], 0.0
    for y in range(0, 480, 20):
        out.append(((160.5 + shift, y + 0.5, 325.0),
                    (360.0 + shift, y + 0.5, 58.0),
                    (160.5 + shift, y + 10.5, 325.0)))
        shift += 1.0
    return out


PRIMS = {
    "FloorQuad": (FLOOR, 150, 0, "FloorQuad"),
    "RoofQuad": (ROOF, 150, 0, "RoofQuad"),
    "WallQuad": (WALL, 150, 0, "WallQuad"),
    "LargeZ": (LARGEZ, 150, 0, "LargeZ"),
    "TriH": (_trih(), 150, 0, "TriH"),
    "TriV": (_triv(), 150, 0, "TriV"),
}
for _ct in (32, 128, 224):
    # ClipF/ClipW exist only with zslope set, so their ZS0 baseline is the
    # unclipped quad: identical geometry, and floor(w) does not see the clip.
    PRIMS["ClipF-150-%03d" % _ct] = (FLOOR, 150, _ct, "FloorQuad")
for _cl in (159, 261, 363):
    PRIMS["ClipW-%03d-000" % _cl] = (WALL, _cl, 0, "WallQuad")


def inv_w_plane(tri):
    """(1/w at v0, d(1/w)/dx, d(1/w)/dy), spelled as psh.c spells it: the
    1/w differences as (w0-wk)/(w0*wk), which is what keeps LargeZ's
    w ~ 1.7e7 from cancelling to nothing."""
    (x0, y0, w0), (x1, y1, w1), (x2, y2, w2) = tri
    d1 = (x1 - x0, y1 - y0)
    d2 = (x2 - x0, y2 - y0)
    det = d1[0] * d2[1] - d2[0] * d1[1]
    b = ((w0 - w1) / (w0 * w1), (w0 - w2) / (w0 * w2))
    return (1.0 / w0,
            (b[0] * d2[1] - b[1] * d1[1]) / det,
            (d1[0] * b[1] - d2[0] * b[0]) / det)


def dominant_axis(tri):
    _, pa, pb = inv_w_plane(tri)
    return "x" if abs(pa) >= abs(pb) else "y"


def offset_at(tri, factor, cx, cy):
    """The offset if the pair anchors at pixel (cx, cy) and steps one pixel
    along the larger |d(1/w)| axis."""
    i0, pa, pb = inv_w_plane(tri)
    x0, y0, _ = tri[0]
    step = pa if abs(pa) >= abs(pb) else pb
    i1 = i0 + pa * (cx + 0.5 - x0) + pb * (cy + 0.5 - y0)
    i2 = i1 + step
    if i1 <= 0.0 or i2 <= 0.0:
        return 0.0
    return factor * abs(step) / (i1 * i2)


# ---------------------------------------------------------- shipped rule
# A Python transcription of wbufSlopeStep() from psh.c, so the two anchoring
# rules can be compared without a build.  `mode` selects which.


def _clip(tri, clip):
    poly = [v[:2] for v in tri]
    cut = False
    for side in range(4):
        kept = []
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            if side == 0:
                da, db = a[0] - clip[0], b[0] - clip[0]
            elif side == 1:
                da, db = clip[2] - a[0], clip[2] - b[0]
            elif side == 2:
                da, db = a[1] - clip[1], b[1] - clip[1]
            else:
                da, db = clip[3] - a[1], clip[3] - b[1]
            if da >= 0.0:
                kept.append(a)
            else:
                cut = True
            if (da >= 0.0) != (db >= 0.0):
                t = da / (da - db)
                kept.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
                cut = True
        poly = kept
        if not poly:
            return None, cut
    return poly, cut


def anchor(tri, clip, mode="shipped"):
    """(col, row) anchor.  mode 'shipped' is bdc26fa5c8's 2x2-quad snap;
    'row4' snaps the ROW to the absolute 4-grid at phase 2 when the clip did
    not cut the triangle."""
    poly, cut = _clip(tri, clip)
    if poly is None:
        return None, cut
    p0, p1, p2 = tri
    xtop = p0[0] if (p0[1] <= p1[1] and p0[1] <= p2[1]) else (
        p1[0] if p1[1] <= p2[1] else p2[0])
    r = math.ceil(min(v[1] for v in poly) - 0.5)
    c, found = 0.0, False
    for _ in range(4):
        yc, lo, hi = r + 0.5, 1e30, -1e30
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            if (a[1] <= yc) != (b[1] <= yc):
                x = a[0] + (b[0] - a[0]) * (yc - a[1]) / (b[1] - a[1])
                lo, hi = min(lo, x), max(hi, x)
            elif a[1] == yc and b[1] == yc:
                lo, hi = min(lo, a[0], b[0]), max(hi, a[0], b[0])
        first, last = math.ceil(lo - 0.5), math.ceil(hi - 0.5) - 1.0
        if hi > lo and last >= first:
            c = min(max(math.floor(xtop), first), last)
            found = True
            break
        r += 1
    if not found:
        return None, cut
    c = 2.0 * math.floor(c / 2.0)
    r = (4.0 * math.floor(r / 4.0) + 2.0) if (mode == "row4" and not cut) \
        else 2.0 * math.floor(r / 2.0)
    return (c, r), cut


# ------------------------------------------------------------------ raster


def _mesh(np):
    return np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)


def coverage(np, tri, clip_left, clip_top):
    px, py = _mesh(np)
    (x0, y0, _), (x1, y1, _), (x2, y2, _) = tri

    def edge(ax, ay, bx, by):
        return (bx - ax) * (py - ay) - (by - ay) * (px - ax)

    e0, e1, e2 = (edge(x0, y0, x1, y1), edge(x1, y1, x2, y2),
                  edge(x2, y2, x0, y0))
    m = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))
    m[:clip_top, :] = False
    m[:, :clip_left] = False
    return m


def plane_w(np, tri):
    i0, pa, pb = inv_w_plane(tri)
    x0, y0, _ = tri[0]
    px, py = _mesh(np)
    return 1.0 / (i0 + pa * (px - x0) + pb * (py - y0))


def decode24(np, Image, path):
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.int64)
    return (a[..., 3] << 16) | (a[..., 0] << 8) | a[..., 1]


# -------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default="/home/justin/goldens/results",
                    help="golden results root (holds W_buffering/)")
    ap.add_argument("--ours", metavar="RESULTDIR", action="append",
                    help="also bound the offset from OUR capture in this "
                         "dispatcher result directory, and print it beside "
                         "hardware's.  This is how #31's mechanism leg is "
                         "checked on an arm: the recovered offset is a "
                         "property of the arm's own render, so it needs no "
                         "baseline and no golden arithmetic.")
    ap.add_argument("--simulate", action="store_true",
                    help="also emulate the shader in float32 and print the "
                         "exact/+-1/wrong split each anchoring rule predicts")
    ap.add_argument("--pairs", action="store_true",
                    help="print the two capture pairs that refute a selector "
                         "over (plane, clip, first covered pixel, top vertex)")
    args = ap.parse_args(argv)

    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        print("needs numpy and pillow: %s" % e, file=sys.stderr)
        return 2

    root = os.path.join(args.goldens, "W_buffering")
    if not os.path.isdir(root):
        print("no W_buffering under %s" % args.goldens, file=sys.stderr)
        return 2

    print("=" * 78)
    print("CONTROL: floor(w) from the recovered plane vs hardware's own ZS0")
    print("=" * 78)
    for name in ("FloorQuad", "RoofQuad", "WallQuad", "TriH", "TriV"):
        tris, cl, ct, _ = PRIMS[name]
        p = os.path.join(root, "WBuf24D_%s_V1_ZB0_ZS0_ZB.png" % name)
        if not os.path.exists(p):
            continue
        z0 = decode24(np, Image, p)
        tot = bad = 0
        for tri in tris:
            m = coverage(np, tri, cl, ct) & (z0 != CLEAR24)
            if m.sum() < 40:
                continue
            d = z0[m] - np.floor(plane_w(np, tri)[m]).astype(np.int64)
            tot += int(m.sum())
            bad += int((d != 0).sum())
        print("  %-12s %7d px, %6d mismatch (%.2f%%)"
              % (name, tot, bad, 100.0 * bad / max(tot, 1)))

    print()
    print("=" * 78)
    print("RECOVERED ANCHORS (WBuf24D, ZB0).  hw offset is an EXACT interval.")
    print("=" * 78)
    print("%-16s %2s %2s %7s %-33s %8s %8s %8s"
          % ("capture", "t", "ax", "n", "hw offset interval", "A_hw",
             "shipped", "row4"))
    rows = []
    for cap in PRIMS:
        tris, cl, ct, base = PRIMS[cap]
        p1 = os.path.join(root, "WBuf24D_%s_V1_ZB0_ZS1_ZB.png" % cap)
        p0 = os.path.join(root, "WBuf24D_%s_V1_ZB0_ZS0_ZB.png" % base)
        if not (os.path.exists(p0) and os.path.exists(p1)):
            continue
        z1 = decode24(np, Image, p1)
        clip = (float(cl), float(ct), float(W), float(H))
        for ti, tri in enumerate(tris):
            m = coverage(np, tri, cl, ct) & (z1 != CLEAR24)
            if m.sum() < 40:
                continue
            w = plane_w(np, tri)
            lo = float(np.max(z1[m] - w[m]))
            hi = float(np.min(z1[m] + 1 - w[m]))
            ax = dominant_axis(tri)
            a_hw = _invert(tri, 0.5 * (lo + hi), ax)
            a_s, _ = anchor(tri, clip, "shipped")
            a_4, _ = anchor(tri, clip, "row4")
            sel = 0 if ax == "x" else 1
            rows.append((cap, ti, ax, int(m.sum()), lo, hi, a_hw,
                         a_s[sel], a_4[sel]))
            print("%-16s %2d %2s %7d [%15.4f,%15.4f] %8.3f %8.0f %8.0f"
                  % (cap, ti, ax, m.sum(), lo, hi, a_hw, a_s[sel], a_4[sel]))

    # LargeZ is NOT discriminating and must be excluded before any rule is
    # scored on it: w ~ 1.7e7 changing by 1 over the whole surface, so the
    # offset is 136 at every anchor and the inversion runs off the bracket.
    # Counting it as agreement or as disagreement would both be wrong.
    disc = [r for r in rows if not r[0].startswith("LargeZ")]
    if args.ours:
        print()
        print("=" * 78)
        print("RECOVERED OFFSET FROM OUR OWN CAPTURES (the mechanism leg)")
        print("=" * 78)
        for rd in args.ours:
            print(rd)
            for cap in PRIMS:
                tris, cl, ct, _ = PRIMS[cap]
                p1 = _ours_path(rd, "WBuf24D_%s_V1_ZB0_ZS1_ZB" % cap)
                if p1 is None:
                    continue
                z1 = decode24(np, Image, p1)
                for ti, tri in enumerate(tris):
                    m = coverage(np, tri, cl, ct) & (z1 != CLEAR24)
                    if m.sum() < 40:
                        continue
                    w = plane_w(np, tri)
                    lo = float(np.max(z1[m] - w[m]))
                    hi = float(np.min(z1[m] + 1 - w[m]))
                    if hi < lo:
                        print("  %-16s t%-2d NO SINGLE CONSTANT fits this "
                              "triangle (interval empty): the offset is not "
                              "one value per primitive here" % (cap, ti))
                        continue
                    print("  %-16s t%-2d ours in [%15.4f,%15.4f]"
                          % (cap, ti, lo, hi))

    agree_s = [r for r in disc if abs(r[6] - r[7]) < 0.01]
    agree_4 = [r for r in disc if abs(r[6] - r[8]) < 0.01]
    noint = [r for r in disc if abs(r[6] - round(r[6])) > 0.05]
    print()
    print("%d anchors recovered, %d of them discriminating (LargeZ excluded: "
          "its offset is 136 at every anchor)." % (len(rows), len(disc)))
    print("  shipped 2x2-quad snap reproduces %d/%d" % (len(agree_s), len(disc)))
    print("  row4 (4-grid row when the clip did not cut) reproduces %d/%d"
          % (len(agree_4), len(disc)))
    print("  unexplained by either: %s"
          % ", ".join(sorted({r[0] for r in disc
                              if r not in agree_4 and r not in agree_s})))
    print("  anchor is NOT an integer pixel under any rule (%d): %s"
          % (len(noint),
             ", ".join("%s/t%d=%.3f" % (r[0], r[1], r[6]) for r in noint[:6])
             + (" ..." if len(noint) > 6 else "") or "none"))

    if args.pairs:
        print()
        print("=" * 78)
        print("WHY NO SELECTOR OVER THE MEASURABLE INPUTS CAN WORK")
        print("=" * 78)
        print("""\
PAIR A -- ClipF-150-032 t0 vs t1.  Same 1/w plane (it is one planar quad), the
same window clip, the same top vertex (both triangles are cut from the v0-v2
diagonal so both have v0 as their topmost vertex), and the same first covered
ROW: hardware's own coverage is byte-identical to the geometric prediction on
all 206,290 pixels.  Measured anchors: row 32 and row 34.  So no function of
(plane, clip rect, first covered pixel, top vertex) reproduces the table -- if
one existed these two would be equal, and they differ by exactly 2 rows.

PAIR B -- FloorQuad t1 vs ClipF-150-032 t1.  IDENTICAL vertices, identical
plane, identical shape and orientation; the clip_top differs, 0 against 32.
Measured anchors: row 0 and row 34, i.e. clip_top+0 against clip_top+2.  So the
selector cannot be a function of the triangle alone either.

Together the four cells are (shape0,ct=0)->2snap, (shape1,ct=0)->2snap,
(shape0,ct=32)->2snap, (shape1,ct=32)->4grid.  That is a single interaction
term pinned by exactly one data point, so any rule reproducing it is fitted to
that one cell.  THE MEASUREMENT THAT WOULD REFUTE THIS: a capture the suite
does not contain -- one triangle translated in y across the 4-grid phase with
the clip fixed, or a quad at clip_top>0 whose BOTH triangles are truncated at
the top.  Either gives a second data point in the (shape, clip) table and the
interaction stops being free.""")

    if args.simulate:
        print()
        print("=" * 78)
        print("SIMULATED exact/+-1/wrong per capture (float32, WBuf24D ZB0)")
        print("=" * 78)
        f32 = np.float32
        for cap in PRIMS:
            tris, cl, ct, base = PRIMS[cap]
            p1 = os.path.join(root, "WBuf24D_%s_V1_ZB0_ZS1_ZB.png" % cap)
            if not os.path.exists(p1):
                continue
            z1 = decode24(np, Image, p1)
            clip = (float(cl), float(ct), float(W), float(H))
            acc = {"shipped": [0, 0, 0], "row4": [0, 0, 0]}
            for tri in tris:
                m = coverage(np, tri, cl, ct) & (z1 != CLEAR24)
                if m.sum() < 40:
                    continue
                for mode in acc:
                    a, _ = anchor(tri, clip, mode)
                    i0, pa, pb = (f32(v) for v in inv_w_plane(tri))
                    step = pa if abs(pa) >= abs(pb) else pb
                    i1 = i0 + pa * (f32(a[0] + 0.5) - f32(tri[0][0])) \
                            + pb * (f32(a[1] + 0.5) - f32(tri[0][1]))
                    off = f32(0.0) if (i1 <= 0 or i1 + step <= 0) else \
                        f32(FACTOR_W) * (abs(step) / (i1 * (i1 + step)))
                    zhi = f32(math.floor(tri[0][2]))
                    zlo = (plane_w(np, tri).astype(np.float32) - zhi) + off
                    d = (zhi + np.floor(zlo)).astype(np.int64)[m] - z1[m]
                    e = int((d == 0).sum())
                    p = int((np.abs(d) == 1).sum())
                    acc[mode][0] += e
                    acc[mode][1] += p
                    acc[mode][2] += int(m.sum()) - e - p
            print("  %-16s shipped %8d/%6d/%8d   row4 %8d/%6d/%8d"
                  % (cap, *acc["shipped"], *acc["row4"]))
        print("  (compare against run-2026-09-10-wbuffer-adreno.tsv, which is"
              " bdc26fa5c8 on the Nova)")
    return 0


def _ours_path(rd, test):
    """Our capture for one test inside a dispatcher result directory.

    captures.find() owns the two directory shapes the dispatcher produces, and
    it is called WITHOUT a fallback on purpose.  A fallback that walks the tree
    by hand is how a wrong call to this API goes unnoticed: the first version of
    this function passed resolve() three arguments, the TypeError was swallowed,
    the hand-rolled walk answered, and the guard AGENTS.md asks for was dead
    code that looked live.  Let it raise.
    """
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import captures as capmod
    return capmod.find(rd, "W_buffering", test)


def _invert(tri, target, axis):
    """The anchor coordinate that produces `target`; the offset is monotone in
    it, so bisect.  Returns a float on purpose: a value that is not an integer
    is the finding, not a rounding error."""
    lo, hi = -4000.0, 4000.0

    def f(t):
        return offset_at(tri, FACTOR_W, t, 0.0) if axis == "x" \
            else offset_at(tri, FACTOR_W, 0.0, t)

    best, ba = None, lo
    t = lo
    while t < hi:
        v = f(t)
        if v > 0 and (best is None or abs(v - target) < best):
            best, ba = abs(v - target), t
        t += 0.5
    a, b = ba - 0.5, ba + 0.5
    for _ in range(60):
        m = 0.5 * (a + b)
        if (f(a) - target) * (f(m) - target) <= 0:
            b = m
        else:
            a = m
    return 0.5 * (a + b)


if __name__ == "__main__":
    sys.exit(main())
