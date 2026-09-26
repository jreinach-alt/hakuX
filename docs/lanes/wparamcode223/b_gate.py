#!/usr/bin/env python3
"""Where does hunk (B) fire?  geom.c emit_wedge() with the zero-area rule:
exactly one w < 0, every q = gl.xy / w finite (and z/w, which is 0 here),
and kahan_det on v_vtxPos.xy (pz, the 1/16 px grid) exactly 0 -> emit
nothing.  Before (B) that triangle went to the host clipper.

Runs every triangle of every W_param test that can have a negative w:

  - ff_w_zero_inf  (bitri, quad) through ff_port.ff_tail, --model today|carry
  - prog_w_zero_inf (bitri, quad) through wedge_price.triangles("prog")
  - w_gaps (strip and translated tris) through wedge_port.gaps_triangles
  - w_neg_strip (CreateGeometryNegativeWTriangleStrip, passthrough program)

w_pos_strip, ff_w_zero and rcc_w_zero_inf have no negative w: w_pos_strip's
w are 0, inf, 0.1 .. 10.5 (0 clamps to +2^-64); ff_w_zero's are 0 and 1;
rcc's are all 1.  So (B) cannot fire there.

Prints one row per triangle on which (B) fires, then the per-capture set.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "wparamclip223"))
sys.path.insert(0, os.path.join(HERE, "..", "wparamff223"))
import wedge_price as wp  # noqa: E402
import wedge_port  # noqa: E402
import ff_port  # noqa: E402

f = np.float32


def to_clip(v):
    """vsh-prog.c: gl = ((2 * pz - size) / size * w, w)."""
    x, y, w = (f(c) for c in v)
    with np.errstate(all="ignore"):
        gx = f(f(f(f(2) * x - f(640)) / f(640)) * w)
        gy = f(f(f(f(2) * y - f(480)) / f(480)) * w)
    return (gx, gy, w)


def grid_area(pz):
    """kahan_det on pz differences.  pz are 1/16 px grid values, so the
    float64 determinant is exact and 0 exactly when kahan_det is 0."""
    g = [np.array([float(c) for c in p[:2]], dtype=np.float64) for p in pz]
    with np.errstate(all="ignore"):
        return float((g[1][0] - g[0][0]) * (g[2][1] - g[0][1])
                     - (g[2][0] - g[0][0]) * (g[1][1] - g[0][1]))


SNAP_ID = 2.0 ** 19
RANGE = True


def fires(gls, pzs):
    """(B)'s precondition, in geom.c's order.  With RANGE, every |pz| must
    also be < 2^19: only there is pz on the 1/16 grid (roundScreenCoords is
    the identity above it) and are its float32 differences exact.  Without
    it a vertex at 8e35 px swallows the others' offsets and a triangle
    silicon draws reads as zero area (ff bitri w-0.96e-34 / w-3.08e-33
    tri2, which is the golden's strip)."""
    ws = [float(g[2]) for g in gls]
    if sum(1 for w in ws if w < 0) != 1:
        return False, "nneg=%d" % sum(1 for w in ws if w < 0)
    with np.errstate(all="ignore"):
        q = [(f(g[0]) / f(g[2]), f(g[1]) / f(g[2])) for g in gls]
    if not all(math.isfinite(float(c)) for qq in q for c in qq):
        return False, "q"
    if RANGE and not all(abs(float(c)) < SNAP_ID for p in pzs for c in p[:2]):
        return False, "range"
    ga = grid_area(pzs)
    if ga == 0:
        return True, "zero"
    return False, "garea=%g" % ga


def ff_rows(model):
    for quad in (False, True):
        for label, m in wp.MULTIPLIERS:
            name = "ff_w_zero_inf__%s_w%s" % ("quad" if quad else "bitri", label)
            for ti, tri in enumerate(ff_port.ff_vertices(quad, m)):
                outs = [ff_port.ff_tail(v, model) for v in tri]
                yield name, "tri%d" % (ti + 1), [o[0] for o in outs], \
                    [o[1] for o in outs]


def prog_rows():
    for quad in (False, True):
        for label, m in wp.MULTIPLIERS:
            name = "prog_w_zero_inf__%s_w%s" % ("quad" if quad else "bitri", label)
            for ti, tri in enumerate(wp.triangles("prog", quad, m)):
                yield name, "tri%d" % (ti + 1), [to_clip(v) for v in tri], \
                    [v[:2] for v in tri]


def gaps_rows():
    for label, tri in wedge_port.gaps_triangles():
        for cap in ("w_gaps", "w_gaps_tex_persp"):
            yield cap, label, [to_clip(v) for v in tri], [v[:2] for v in tri]


def neg_strip_rows():
    left, top = math.floor(640 / 5.0), math.floor(480 / 6.0)
    bottom = top + (480 - top * 2.0)
    right = left + (640 - left * 2.0)
    mid = left + (right - left) * 0.5
    v = [(left, bottom, 1.0), (left, top, 1.0), (mid, bottom, 1.0),
         (mid, top, 1.0), (mid, top, -0.1), (right, bottom, 1.0)]
    v = [wp.prog_vertex(*p) for p in v]
    for i in range(len(v) - 2):
        tri = v[i:i + 3]
        for cap in ("w_neg_strip", "w_neg_strip_tex_persp"):
            yield cap, "strip%d" % i, [to_clip(p) for p in tri], \
                [p[:2] for p in tri]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ff-model", choices=("today", "carry"), default="carry")
    ap.add_argument("--no-range", action="store_true",
                    help="(B) as #304 wrote it, without the |pz| < 2^19 bound")
    args = ap.parse_args()
    global RANGE
    RANGE = not args.no_range
    hit = {}
    print("capture\ttri\tB")
    for gen in (ff_rows(args.ff_model), prog_rows(), gaps_rows(),
                neg_strip_rows()):
        for name, tri, gls, pzs in gen:
            ok, why = fires(gls, pzs)
            if ok:
                print("%s\t%s\tDROP" % (name, tri))
                hit.setdefault(name, []).append(tri)
    print("\n%d captures:" % len(hit))
    for k in sorted(hit):
        print("  %s: %s" % (k, ",".join(hit[k])))


if __name__ == "__main__":
    main()
