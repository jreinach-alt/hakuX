#!/usr/bin/env python3
"""float32 port of vsh-ff.c's position tail (vsh-ff.c:878-887), today's and
the proposed homogeneous-carry hunk, on the W_param ff_w_zero_inf vertices.

For every vertex it prints what reaches the geometry shader: gl_Position
(x, y, w) and v_vtxPos.xy, and whether each is finite.  Then per triangle it
says what geom.c's append_wedge() gate would do with it (one negative w,
q = xy/w finite, NDC area finite and non-zero, grid area finite and
non-zero), and prices the region an ideal host clipper would draw from that
gl_Position (homog_price.homog_mask, NDC mapped to pixels) against the
golden.

Composite is identity (w_param_tests.cpp:491-496), viewport offset (320, 240),
surface 640x480, clipRange irrelevant to coverage.

  --model today     GLSL as it is: vec4 * mat4 (0 * inf = NaN), divide,
                    snap, (2 * pos - size) / size * w
  --model carry     the proposed hunk: nv2a 0 * x = 0 in the transform, and
                    where |pos| >= 2^19 (roundScreenCoords is the identity
                    there) gl.xy is carried homogeneously as
                    2 * xy / size + (2 * vpoff / size - 1) * w
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "wparamclip223"))
sys.path.insert(0, HERE)
from wedge_price import (MULTIPLIERS, K_MIN_W, K_MAX_W, W, H,  # noqa: E402
                         clamp_away_zero_inf, f32, mul32, load_mask,
                         round_screen)
from homog_price import homog_mask  # noqa: E402

SW, SH = f32(640.0), f32(480.0)
VPX, VPY = f32(320.0), f32(240.0)
SNAP_ID = f32(2.0 ** 19)


def op(fn):
    def g(*a):
        with np.errstate(all="ignore"):
            return f32(fn(*[f32(t) for t in a]))
    return g


add = op(lambda a, b: a + b)
sub = op(lambda a, b: a - b)
mul = op(lambda a, b: a * b)
div = op(lambda a, b: a / b)


def nvmul(a, b):
    """nv2a multiply: 0 * anything (inf, NaN) is 0."""
    if f32(a) == 0 or f32(b) == 0:
        return f32(0.0)
    return mul(a, b)


def transform(v, nv):
    """position * identity, as a row-vector dot per column."""
    m = mul if not nv else nvmul
    out = []
    for col in range(4):
        acc = None
        for k in range(4):
            t = m(v[k], 1.0 if k == col else 0.0)
            acc = t if acc is None else add(acc, t)
        out.append(acc)
    return out


NO_NVMUL = False


def ff_tail(v, model):
    x, y, z, w = transform(v, nv=(model == "carry" and not NO_NVMUL))
    w = clamp_away_zero_inf(w)
    sx, sy = add(div(x, w), VPX), add(div(y, w), VPY)
    px, py = round_screen(sx), round_screen(sy)
    gx = mul(div(sub(mul(2.0, px), SW), SW), w)
    gy = mul(div(sub(mul(2.0, py), SH), SH), w)
    if model == "carry":
        # roundScreenCoords is the identity for |pos| >= 2^19; carry
        # homogeneously there (and where the divide overflowed).
        if not (abs(float(sx)) < float(SNAP_ID)) or not math.isfinite(float(sx)):
            gx = add(div(mul(2.0, x), SW), mul(sub(div(mul(2.0, VPX), SW), 1.0), w))
        if not (abs(float(sy)) < float(SNAP_ID)) or not math.isfinite(float(sy)):
            gy = add(div(mul(2.0, y), SH), mul(sub(div(mul(2.0, VPY), SH), 1.0), w))
    return (gx, gy, w), (px, py)


def ff_vertices(quad, m):
    m = f32(m)
    with np.errstate(all="ignore"):
        tl_w = f32(K_MIN_W / m) if m != 0 else f32(math.copysign(math.inf, float(m)))
        br_w = f32(K_MAX_W * m)
    L, T, R, B = -80.0, -80.0, 80.0, 80.0
    v0 = (mul32(L, K_MIN_W), mul32(T, K_MIN_W), 0.0, tl_w)
    v1 = (R, T, 0.0, 1.0)
    v2 = (L, B, 0.0, 1.0)
    vb = (mul32(R, K_MAX_W), mul32(B, K_MAX_W), 0.0, br_w)
    if quad:
        return [(v0, v1, vb), (v0, vb, v2)]
    return [(v0, v1, v2), (vb, v2, v1)]


def area(p):
    (x0, y0), (x1, y1), (x2, y2) = p
    return sub(mul(sub(x1, x0), sub(y2, y0)), mul(sub(x2, x0), sub(y1, y0)))


def gate(gls, pzs):
    """append_wedge()'s gate, float32 (geom.c): exactly one w < 0, q finite,
    NDC area finite non-zero, grid area finite non-zero."""
    nneg = sum(1 for g in gls if float(g[2]) < 0)
    if nneg != 1:
        return "host(%dneg)" % nneg
    q = [(div(g[0], g[2]), div(g[1], g[2])) for g in gls]
    if not all(math.isfinite(float(c)) for qq in q for c in qq):
        return "host(q)"
    a = area(q)
    if not math.isfinite(float(a)) or a == 0:
        return "host(area)"
    ga = area(pzs)
    if not math.isfinite(float(ga)) or ga == 0:
        return "host(grid)"
    return "WEDGE"


def ndc_to_px(g):
    """(ndc*w, w) -> homogeneous pixel coords (X, Y, w), exactly as the host
    maps NDC: px = (ndc + 1) * size / 2.  Done in float64 on the float32
    gl_Position so only our inputs carry float32 rounding."""
    gx, gy, w = (float(t) for t in g)
    return (
        np.float64(gx) * 320.0 + np.float64(w) * 320.0,
        np.float64(gy) * 240.0 + np.float64(w) * 240.0,
        np.float64(w))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=("today", "carry"), default="carry")
    ap.add_argument("--golden-dir",
                    default=os.path.expanduser("~/goldens/results/W_param"))
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-nvmul", action="store_true",
                    help="carry without the 0 * x = 0 transform")
    args = ap.parse_args()
    global NO_NVMUL
    NO_NVMUL = args.no_nvmul
    print("capture\tpaths\tgl_finite\tclipper_xor_G")
    tot = {False: 0, True: 0}
    for quad in (False, True):
        for label, m in MULTIPLIERS:
            name = "ff_w_zero_inf__%s_w%s" % ("quad" if quad else "bitri", label)
            gpath = os.path.join(args.golden_dir, name + ".png")
            if not os.path.exists(gpath):
                continue
            g, glab = load_mask(gpath)
            keep = ~glab
            model = np.zeros((H, W), dtype=bool)
            paths, fin = [], []
            for tri in ff_vertices(quad, m):
                outs = [ff_tail(v, args.model) for v in tri]
                gls = [o[0] for o in outs]
                pzs = [o[1] for o in outs]
                ok = all(math.isfinite(float(c)) for gg in gls for c in gg)
                fin.append("y" if ok else "n")
                paths.append(gate(gls, pzs))
                if args.verbose:
                    for o in outs:
                        print("   gl=(%.4g, %.4g, w=%.4g) pz=(%.6g, %.6g)" % (
                            *(float(c) for c in o[0]), *(float(c) for c in o[1])))
                if ok:
                    model |= homog_mask([ndc_to_px(gg) for gg in gls])[0]
            x = int(((model ^ g) & keep).sum())
            tot[quad] += x
            print("%s\t%s\t%s\t%d" % (name, ",".join(paths), ",".join(fin), x))
    print("TOTAL bitri %d  quad %d" % (tot[False], tot[True]))


if __name__ == "__main__":
    main()
