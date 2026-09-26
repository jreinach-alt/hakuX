#!/usr/bin/env python3
"""Offline pricing for lane.wparamff223 (#223): the ff W_param families.

Question: if the fixed-function path carried each vertex homogeneously to the
rasteriser, instead of dividing x/w in float32 and snapping to the 1/16 grid
(vsh-ff.c:879-887), would ff bitri and ff quad match the goldens?

Model S (homogeneous silicon), per vertex, in float32:
    w  = clampAwayZeroInf(w)
    X  = x + 320 w,  Y = y + 240 w          (viewport offset, homogeneous)
Then each triangle is rasterised exactly (Fractions) with 2D homogeneous
edge functions at pixel centres: a centre p is covered iff M^-1 p >= 0,
where M's columns are the three (X, Y, w).  That is the projection of the
triangle's w > 0 part: the host clipper's answer with no divide and no
overflow.  One negative w gives the external wedge; two give the cone at the
positive vertex spanned by (P - N1), (P - N2); three give nothing.

The prog family is run through the same rasteriser as a control, with
(X, Y, w) = (sx * w, sy * w, w) for its already-screen-space oPos.

Scores coverage only (clear 0x251135, label pixels excluded), as
wparamclip223/wedge_price.py does, against the golden and optionally
against a Thor capture (C) of today's build.

Usage: homog_price.py [--golden-dir D] [--capture-dir D] [--family ff|prog|all]
                      [--png-dir D]   (write model masks for inspection)
"""
import argparse
import math
import os
import sys
from fractions import Fraction

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "wparamclip223"))
from wedge_price import (MULTIPLIERS, K_MIN_W, K_MAX_W, W, H,  # noqa: E402
                         clamp_away_zero_inf, f32, mul32, load_mask)


def add32(a, b):
    with np.errstate(all="ignore"):
        return f32(f32(a) + f32(b))


NEGZERO_POSITIVE = False


def clamp_w(w):
    """clampAwayZeroInf, or with --negzero-positive silicon's reading of
    -0 as +0 (so it clamps to +2^-64, not -2^-64)."""
    if NEGZERO_POSITIVE and float(w) == 0.0:
        return K_MIN_W
    return clamp_away_zero_inf(w)


def ff_hvertex(x, y, w):
    wc = clamp_w(w)
    return (add32(x, mul32(320.0, wc)), add32(y, mul32(240.0, wc)), wc)


def prog_hvertex(x, y, w):
    wc = clamp_w(w)
    return (mul32(x, wc), mul32(y, wc), wc)


def triangles(family, quad, m):
    m = f32(m)
    with np.errstate(all="ignore"):
        tl_w = f32(K_MIN_W / m) if m != 0 else f32(math.copysign(math.inf, float(m)))
        br_w = f32(K_MAX_W * m)
    neg = lambda v: math.copysign(1.0, float(v)) < 0
    if family == "prog":
        L, T, R, B = 160.0, 70.0, 480.0, 390.0
        v = prog_hvertex
        v0 = v(R, B, tl_w) if neg(tl_w) else v(L, T, tl_w)
        if quad:
            v1 = v(R, T, 1.0)
            v2 = v(L, T, br_w) if neg(br_w) else v(R, B, br_w)
            v3 = v(L, B, 1.0)
            return [(v0, v1, v2), (v0, v2, v3)]
        t1 = (v0, v(R, T, K_MIN_W), v(L, B, K_MIN_W))
        v3 = v(L, T, br_w) if neg(br_w) else v(R, B, br_w)
        t2 = (v3, v(L, B, K_MAX_W), v(R, T, K_MAX_W))
        return [t1, t2]
    L, T, R, B = -80.0, -80.0, 80.0, 80.0
    v = ff_hvertex
    v0 = v(mul32(L, K_MIN_W), mul32(T, K_MIN_W), tl_w)
    v1 = v(R, T, 1.0)
    v2 = v(L, B, 1.0)
    vb = v(mul32(R, K_MAX_W), mul32(B, K_MAX_W), br_w)
    if quad:
        return [(v0, v1, vb), (v0, vb, v2)]
    return [(v0, v1, v2), (vb, v2, v1)]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def homog_mask(tri):
    """Pixel centres p with M^-1 p >= 0 (closed).  Exact."""
    V = [tuple(Fraction(float(c)) for c in vt) for vt in tri]
    e = [cross(V[1], V[2]), cross(V[2], V[0]), cross(V[0], V[1])]
    det = sum(V[0][i] * e[0][i] for i in range(3))
    if det == 0:
        return np.zeros((H, W), dtype=bool), 0
    s = 1 if det > 0 else -1
    yy, xx = np.mgrid[0:H, 0:W]
    cx = xx + 0.5
    cy = yy + 0.5
    m = np.ones((H, W), dtype=bool)
    for a, b, c in e:
        # Scale to float64 safely: only the sign matters, and the three
        # coefficients of one edge are rescaled together.
        big = max(abs(a), abs(b), abs(c))
        a, b, c = (float(t / big) for t in (a, b, c))
        m &= s * (a * cx + b * cy + c) >= -1e-12
    return m, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden-dir",
                    default=os.path.expanduser("~/goldens/results/W_param"))
    ap.add_argument("--capture-dir", default=None)
    ap.add_argument("--family", default="all")
    ap.add_argument("--png-dir", default=None)
    ap.add_argument("--negzero-positive", action="store_true")
    args = ap.parse_args()
    global NEGZERO_POSITIVE
    NEGZERO_POSITIVE = args.negzero_positive
    fams = ["ff", "prog"] if args.family == "all" else [args.family]
    print("capture\tnneg\tG\tC_xor_G\tS_xor_G\tS_minus_G\tG_minus_S")
    tot = {}
    for fam in fams:
        for quad in (False, True):
            for label, mult in MULTIPLIERS:
                name = "%s_w_zero_inf__%s_w%s" % (fam, "quad" if quad else "bitri", label)
                gpath = os.path.join(args.golden_dir, name + ".png")
                if not os.path.exists(gpath):
                    continue
                tris = triangles(fam, quad, mult)
                g, glab = load_mask(gpath)
                excl = glab.copy()
                c = None
                if args.capture_dir:
                    cpath = os.path.join(args.capture_dir, "W_param::" + name + ".png")
                    if os.path.exists(cpath):
                        c, clab = load_mask(cpath)
                        excl |= clab
                keep = ~excl
                model = np.zeros((H, W), dtype=bool)
                for t in tris:
                    model |= homog_mask(t)[0]
                nneg = ",".join(str(sum(1 for vt in t if float(vt[2]) < 0)) for t in tris)
                cx = int(((c ^ g) & keep).sum()) if c is not None else -1
                sx = int(((model ^ g) & keep).sum())
                print("%s\t%s\t%d\t%d\t%d\t%d\t%d" % (
                    name, nneg, int((g & keep).sum()), cx, sx,
                    int((model & ~g & keep).sum()), int((g & ~model & keep).sum())))
                k = (fam, quad)
                tc, ts = tot.get(k, (0, 0))
                tot[k] = (tc + max(cx, 0), ts + sx)
                if args.png_dir:
                    os.makedirs(args.png_dir, exist_ok=True)
                    img = np.zeros((H, W, 3), dtype=np.uint8)
                    img[..., 0] = (model & keep) * 255
                    img[..., 1] = (g & keep) * 255
                    Image.fromarray(img).save(os.path.join(args.png_dir, name + ".png"))
    for (fam, quad), (tc, ts) in tot.items():
        print("TOTAL %s %s\tC_xor_G %d\tS_xor_G %d" % (fam, "quad" if quad else "bitri", tc, ts))


if __name__ == "__main__":
    main()
