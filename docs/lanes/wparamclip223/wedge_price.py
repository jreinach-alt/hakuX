#!/usr/bin/env python3
"""Offline pricing for lane.wparamclip223 (#223): the external wedge.

For every W_param `*_w_zero_inf_*` capture this regenerates the vertices from
the test source (nxdk_pgraph_tests/src/tests/w_param_tests.cpp:485-740), runs
them through the same float32 arithmetic vsh-prog.c / vsh-ff.c apply
(clampAwayZeroInf, the ff divide and viewport offset, roundScreenCoords), and
decides per triangle what the geometry-shader change does with it:

  WEDGE     exactly one w < 0 and a non-degenerate screen triangle: the new
            path emits silicon's external wedge -- the region across the edge
            P1-P2 from N, between the rays N->P1 and N->P2 continued past P1
            and P2 -- clipped to the surface.
  HOST      anything else (no negative w, two or three, or a screen triangle
            whose area is 0 in float32): today's path, the host clipper.

It then scores COVERAGE only, never colour:

  G  golden pixels that are not the clear colour 0x251135
  C  the same mask on a Thor capture of today's build (--capture-dir)
  M  the model: C outside every WEDGE triangle's screen bounding region is
     not knowable offline, so M is scored only on captures where every
     triangle is WEDGE or where the HOST triangles are all-positive (whose
     coverage we already match), else the row says `partial`.

Pixels that are near-white in the golden or the capture are the guest's
printed label and are excluded from both masks.

Usage: wedge_price.py [--golden-dir D] [--capture-dir D] [--family prog|ff|all]
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

W, H = 640, 480
CLEAR = np.array([0x25, 0x11, 0x35])
K_MIN_W = np.float32(2.0 ** -64)
K_MAX_W = np.float32(2.0 ** 64)

# w_param_tests.cpp:104-123.  The six tiny ones are -kMinW * (2^k * kMinW),
# i.e. -2^(k - 128), exact in float32.
MULTIPLIERS = [
    ("-0.00", -0.0), ("-0.25", -0.25), ("-0.50", -0.5), ("-0.96e-34", -2.0 ** -113),
    ("-1.00", -1.0), ("-1.50e-36", -2.0 ** -119), ("-1.88e-37", -2.0 ** -122),
    ("-2.00", -2.0), ("-3.08e-33", -2.0 ** -108), ("-3.76e-37", -2.0 ** -121),
    ("-4.00", -4.0), ("-7.52e-37", -2.0 ** -120), ("-inf", -math.inf),
    ("0.00", 0.0), ("0.25", 0.25), ("0.50", 0.5), ("1.00", 1.0), ("2.00", 2.0),
    ("4.00", 4.0), ("inf", math.inf),
]


def f32(x):
    return np.float32(x)


def clamp_away_zero_inf(t):
    """vsh.c clampAwayZeroInf(): +0 and positives to [2^-64, 2^64], the rest
    (negatives and -0) to [-2^64, -2^-64]."""
    t = f32(t)
    if t > 0 or (t == 0 and not math.copysign(1.0, float(t)) < 0):
        return f32(min(max(t, K_MIN_W), K_MAX_W))
    return f32(min(max(t, -K_MAX_W), -K_MIN_W))


def round_screen(v):
    with np.errstate(all="ignore"):
        s = float(f32(v) * f32(16.0))
    if not math.isfinite(s):
        return f32(s)
    return f32(math.trunc(s) / 16.0)


def div32(a, b):
    with np.errstate(all="ignore"):
        return f32(f32(a) / f32(b))


def mul32(a, b):
    with np.errstate(all="ignore"):
        return f32(f32(a) * f32(b))


def prog_vertex(x, y, w):
    """vsh-prog.c: oPos is already screen space; only w is clamped."""
    return (float(round_screen(x)), float(round_screen(y)),
            float(clamp_away_zero_inf(w)))


def ff_vertex(x, y, w):
    """vsh-ff.c with identity composite and viewport offset (320, 240)."""
    wc = clamp_away_zero_inf(w)
    sx = f32(div32(x, wc) + f32(320.0))
    sy = f32(div32(y, wc) + f32(240.0))
    return (float(round_screen(sx)), float(round_screen(sy)), float(wc))


def triangles(family, quad, m):
    m = f32(m)
    with np.errstate(all="ignore"):
        tl_w = f32(K_MIN_W / m) if m != 0 else f32(math.copysign(math.inf, float(m)))
        br_w = f32(K_MAX_W * m)
    neg = lambda v: math.copysign(1.0, float(v)) < 0
    if family == "prog":
        L, T, R, B = 160.0, 70.0, 480.0, 390.0
        v0 = prog_vertex(R, B, tl_w) if neg(tl_w) else prog_vertex(L, T, tl_w)
        if quad:
            v1 = prog_vertex(R, T, 1.0)
            v2 = prog_vertex(L, T, br_w) if neg(br_w) else prog_vertex(R, B, br_w)
            v3 = prog_vertex(L, B, 1.0)
            # rewrite_quads(), smooth: v0-v2 diagonal
            return [(v0, v1, v2), (v0, v2, v3)]
        t1 = (v0, prog_vertex(R, T, K_MIN_W), prog_vertex(L, B, K_MIN_W))
        v3 = prog_vertex(L, T, br_w) if neg(br_w) else prog_vertex(R, B, br_w)
        t2 = (v3, prog_vertex(L, B, K_MAX_W), prog_vertex(R, T, K_MAX_W))
        return [t1, t2]
    # ff
    L, T, R, B = -80.0, -80.0, 80.0, 80.0
    v0 = ff_vertex(mul32(L, K_MIN_W), mul32(T, K_MIN_W), tl_w)
    v1 = ff_vertex(R, T, 1.0)
    v2 = ff_vertex(L, B, 1.0)
    vb = ff_vertex(mul32(R, K_MAX_W), mul32(B, K_MAX_W), br_w)
    if quad:
        return [(v0, v1, vb), (v0, vb, v2)]
    return [(v0, v1, v2), (vb, v2, v1)]


def classify(tri):
    ws = [v[2] for v in tri]
    if any(not math.isfinite(c) for v in tri for c in v):
        return "HOST"
    nneg = sum(1 for w in ws if w < 0)
    if nneg != 1:
        return "HOST" if nneg else "POS"
    (x0, y0, _), (x1, y1, _), (x2, y2, _) = tri
    with np.errstate(all="ignore"):
        area = f32(f32(f32(x1 - x0) * f32(y2 - y0)) - f32(f32(x2 - x0) * f32(y1 - y0)))
    # emit_wedge() falls back on a zero OR a non-finite area; ff's w-0.96e-34
    # and w-3.08e-33 tri2 overflow float32 here (a vertex at ~8e35 px).
    return "WEDGE" if area != 0 and math.isfinite(float(area)) else "HOST"


def wedge_mask(tri):
    """Pixel centres in the external wedge (closed, so a centre on a shared
    edge counts as covered -- this scores the union's coverage, not ties)."""
    ws = [v[2] for v in tri]
    n = next(i for i, w in enumerate(ws) if w < 0)
    p = [np.array(v[:2], dtype=np.float64) for v in tri]
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = xx + 0.5, yy + 0.5

    def edge(a, b):  # signed area of (a, b, centre)
        return (b[0] - a[0]) * (cy - a[1]) - (b[1] - a[1]) * (cx - a[0])

    area = (p[1][0] - p[0][0]) * (p[2][1] - p[0][1]) - \
           (p[2][0] - p[0][0]) * (p[1][1] - p[0][1])
    lam = [edge(p[1], p[2]) / area, edge(p[2], p[0]) / area,
           edge(p[0], p[1]) / area]
    eps = 1e-9
    m = np.ones((H, W), dtype=bool)
    for i in range(3):
        if i == n:
            m &= lam[i] <= eps
        else:
            m &= lam[i] >= -eps
    return m


def load_mask(path):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.int32)
    drawn = np.abs(im - CLEAR).max(axis=2) > 2
    label = im.min(axis=2) >= 200
    return drawn, label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden-dir",
                    default=os.path.expanduser("~/goldens/results/W_param"))
    ap.add_argument("--capture-dir", default=None)
    ap.add_argument("--family", default="all")
    args = ap.parse_args()

    fams = ["prog", "ff"] if args.family == "all" else [args.family]
    print("capture\ttri_paths\tG\tC_xor_G\tM_xor_G\tM_minus_G\tG_minus_M")
    for fam in fams:
        for quad in (False, True):
            for label, m in MULTIPLIERS:
                name = "%s_w_zero_inf__%s_w%s" % (fam, "quad" if quad else "bitri", label)
                gpath = os.path.join(args.golden_dir, name + ".png")
                if not os.path.exists(gpath):
                    print(name, "\tno golden", file=sys.stderr)
                    continue
                tris = triangles(fam, quad, m)
                paths = [classify(t) for t in tris]
                g, glab = load_mask(gpath)
                excl = glab.copy()
                c = None
                if args.capture_dir:
                    cpath = os.path.join(args.capture_dir, "W_param::" + name + ".png")
                    if os.path.exists(cpath):
                        c, clab = load_mask(cpath)
                        excl |= clab
                keep = ~excl
                cx = int(((c ^ g) & keep).sum()) if c is not None else -1
                if "WEDGE" not in paths:
                    mx, mm, gm = cx, -1, -1
                    mcol = "unchanged"
                else:
                    mm_ = np.zeros((H, W), dtype=bool)
                    for t, pth in zip(tris, paths):
                        if pth == "WEDGE":
                            mm_ |= wedge_mask(t)
                    if all(pth in ("WEDGE",) for pth in paths):
                        model = mm_
                        mcol = None
                    elif c is not None:
                        # HOST triangles keep whatever the host draws today.
                        model = mm_ | c
                        mcol = None
                    else:
                        model = None
                        mcol = "partial"
                    if model is not None:
                        mx = int(((model ^ g) & keep).sum())
                        mm = int(((model & ~g) & keep).sum())
                        gm = int(((g & ~model) & keep).sum())
                print("%s\t%s\t%d\t%d\t%s\t%s\t%s" % (
                    name, ",".join(paths), int((g & keep).sum()), cx,
                    mcol or mx, mm, gm))


if __name__ == "__main__":
    main()
