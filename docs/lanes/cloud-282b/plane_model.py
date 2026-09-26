#!/usr/bin/env python3
"""A desktop model of NV2A attribute-plane setup on DrawCheckerboardUnproject (#282).

The helper's quad is split on v0-v2 into T1 = (v0 v1 v2) and T2 = (v0 v2 v3).
Vertices are the four framebuffer corners plus a per-coordinate snap offset
delta in {0, +1/16} (a round-to-nearest snap of corner + 0.53125 + eps goes
to +1/16 when eps > 0; a truncating snap always gives 0). Pixel centres are at
integer (x, y) in this frame, so with every delta = 0 the ties are exact:
u = 256 x / 640 and v = 256 y / 480, in texels.

Per triangle the model computes the plane of the texcoord from its three
snapped vertices and evaluates it at the pixel centre, in one of:

  exact   rational arithmetic (fractions) -- the error is only the snap
  f32     float32 setup (edge vectors from the first vertex, det, gradients
          by division) and float32 evaluation relative to a reference vertex
          r: t_r + A*(x - x_r) + B*(y - y_r), summed left to right
  f32fma  as f32, evaluated as fma(B, dy, fma(A, dx, t_r)) in float64 then
          rounded once (a fused evaluator)

A tie pixel goes DOWN (copies the lower texel) iff the evaluated coordinate is
below the tie. The model's score is the fraction of golden tie pixels whose
direction it predicts, over the pixels extract.py wrote.

Usage: plane_model.py GOLD.npz [--scan] [--show CONFIG] [--map CONFIG]
"""
import argparse
import itertools
from fractions import Fraction as F

import numpy as np

W, H = 640, 480
CORNERS = [(0, 0), (W, 0), (W, H), (0, H)]
UV = [(0, 0), (1, 0), (1, 1), (0, 1)]  # normalised texcoords per vertex
TRIS = {"T1": (0, 1, 2), "T2": (0, 2, 3)}
f32 = np.float32


def load(path):
    z = np.load(path)
    d = {k: z[k] for k in z.files}
    # unique (vs, axis, line, pos) with golden down/total counts
    key = (d["vs"].astype(np.int64) << 40) | (d["axis"].astype(np.int64) << 32) | \
          (d["line"].astype(np.int64) << 16) | d["pos"].astype(np.int64)
    uk, inv = np.unique(key, return_inverse=True)
    n = np.bincount(inv)
    dn = np.bincount(inv, weights=d["down"].astype(float)).astype(int)
    u = dict(vs=(uk >> 40).astype(bool), axis=((uk >> 32) & 1).astype(bool),
             line=((uk >> 16) & 0xFFFF).astype(int), pos=(uk & 0xFFFF).astype(int), n=n, dn=dn)
    tex = np.where(u["axis"], u["line"] * 8 // 15, u["line"] * 2 // 5)
    u["tex"] = tex
    u["x"] = np.where(u["axis"], u["pos"], u["line"])
    u["y"] = np.where(u["axis"], u["line"], u["pos"])
    return d, u, inv


def verts(delta):
    """delta: 8 values (dx0, dy0, dx1, dy1, ...) in 1/16 px units."""
    return [(F(cx) + F(delta[2 * i], 16), F(cy) + F(delta[2 * i + 1], 16)) for i, (cx, cy) in enumerate(CORNERS)]


def which_tri(vv, x, y):
    """T1 iff the pixel is on v1's side of the v0-v2 diagonal (on the line: T1)."""
    (x0, y0), (x2, y2), (x1, y1) = vv[0], vv[2], vv[1]
    side = lambda px, py: (x2 - x0) * (py - y0) - (y2 - y0) * (px - x0)
    s1 = side(x1, y1)
    s = (float(x2 - x0) * (y - float(y0)) - float(y2 - y0) * (x - float(x0)))
    return np.where(s == 0, True, np.sign(s) == np.sign(float(s1)))


def plane_exact(vv, tri, comp):
    a, b, c = (vv[i] for i in tri)
    ta, tb, tc = (F(UV[i][comp] * 256) for i in tri)
    e1x, e1y, e2x, e2y = b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]
    det = e1x * e2y - e2x * e1y
    A = ((tb - ta) * e2y - (tc - ta) * e1y) / det
    B = ((tc - ta) * e1x - (tb - ta) * e2x) / det
    return A, B, ta - A * a[0] - B * a[1]


def eval_exact(vv, tri, comp, x, y, tie):
    A, B, C = plane_exact(vv, tri, comp)
    # down iff A x + B y + C < tie; all rationals -> compare with a common denominator
    den = A.denominator * B.denominator * C.denominator
    Ai, Bi, Ci = int(A * den), int(B * den), int(C * den)
    return (Ai * x.astype(object) + Bi * y.astype(object) + Ci < tie.astype(object) * den).astype(bool)


def eval_f32(vv, tri, comp, x, y, tie, ref, fused, norm):
    """Float32 setup and evaluation. norm: evaluate in normalised [0,1] texcoords
    (then x256), else in texels -- identical unless something is not a power of two."""
    P = [(f32(float(vv[i][0])), f32(float(vv[i][1]))) for i in tri]
    scale = f32(1.0) if norm else f32(256.0)
    T = [f32(UV[i][comp]) * scale for i in tri]
    e1x, e1y = f32(P[1][0] - P[0][0]), f32(P[1][1] - P[0][1])
    e2x, e2y = f32(P[2][0] - P[0][0]), f32(P[2][1] - P[0][1])
    d1, d2 = f32(T[1] - T[0]), f32(T[2] - T[0])
    det = f32(f32(e1x * e2y) - f32(e2x * e1y))
    A = f32(f32(f32(d1 * e2y) - f32(d2 * e1y)) / det)
    B = f32(f32(f32(d2 * e1x) - f32(d1 * e2x)) / det)
    xr, yr = P[ref]
    tr = T[ref]
    dx = (x.astype(f32) - xr).astype(f32)
    dy = (y.astype(f32) - yr).astype(f32)
    if fused:
        v = (np.float64(tr) + np.float64(A) * dx.astype(np.float64) + np.float64(B) * dy.astype(np.float64)).astype(f32)
    else:
        v = ((tr + (A * dx).astype(f32)).astype(f32) + (B * dy).astype(f32)).astype(f32)
    if norm:
        v = (v * f32(256.0)).astype(f32)
    return v < tie


def eval_bary(vv, tri, comp, x, y, tie, recip_area, recip_den, order):
    """Perspective-correct barycentric evaluation in float32.

    lambda_i = E_i / area (edge function of the edge opposite vertex i, over the
    doubled area), then t = sum(t_i lambda_i / w_i) / sum(lambda_i / w_i). With
    w = 8 at every vertex the 1/w factors are exact powers of two, so what is
    left is the float rounding of the lambdas and of the two sums. The
    denominator is 1 in exact arithmetic; in float32 it can round to 1 - 2^-24,
    1 or 1 + 2^-23 depending on the binades of the three lambdas, which is
    where an x dependence can come from on a plane whose dv/dx is 0.
    recip_area: lambda by multiplying with fl(1/area) instead of dividing.
    recip_den: t = num * fl(1/den) instead of num / den.
    order: permutation of (0, 1, 2) giving the summation order.
    """
    P = [(f32(float(vv[i][0])), f32(float(vv[i][1]))) for i in tri]
    T = [f32(UV[i][comp]) for i in tri]
    xf, yf = x.astype(f32), y.astype(f32)

    def edge(a, b):  # E(x, y) for edge a->b, positive on the triangle's side for vertex opposite
        (xa, ya), (xb, yb) = P[a], P[b]
        return (f32(xb - xa) * (yf - ya).astype(f32)).astype(f32) - (f32(yb - ya) * (xf - xa).astype(f32)).astype(f32)

    area = f32(f32(f32(P[1][0] - P[0][0]) * f32(P[2][1] - P[0][1])) - f32(f32(P[2][0] - P[0][0]) * f32(P[1][1] - P[0][1])))
    E = [edge(1, 2), edge(2, 0), edge(0, 1)]  # opposite v0, v1, v2
    if recip_area:
        ra = f32(f32(1.0) / area)
        lam = [(e * ra).astype(f32) for e in E]
    else:
        lam = [(e / area).astype(f32) for e in E]
    num = np.zeros(len(x), f32)
    den = np.zeros(len(x), f32)
    for i in order:
        num = (num + (T[i] * lam[i]).astype(f32)).astype(f32)
        den = (den + lam[i]).astype(f32)
    if recip_den:
        t = (num * (f32(1.0) / den).astype(f32)).astype(f32)
    else:
        t = (num / den).astype(f32)
    return (t * f32(256.0)).astype(f32) < tie


def eval_refbary(vv, tri, comp, x, y, tie, ref, recip_area, order, rnd):
    """Barycentric evaluation relative to a reference vertex, in float32:

        t = t_r + (t_b - t_r) * lambda_b + (t_c - t_r) * lambda_c

    where b, c are the other two vertices and lambda_i = E_i * fl(1/area)
    (recip_area) or E_i / area. order 0 adds the b term first, 1 the c term.
    rnd: 'n' round to nearest (numpy), 'z' round toward zero on the lambdas.
    """
    P = [(f32(float(vv[i][0])), f32(float(vv[i][1]))) for i in tri]
    T = [f32(UV[i][comp]) for i in tri]
    xf, yf = x.astype(f32), y.astype(f32)

    def edge(a, b):
        (xa, ya), (xb, yb) = P[a], P[b]
        return ((f32(xb - xa) * (yf - ya).astype(f32)).astype(f32)
                - (f32(yb - ya) * (xf - xa).astype(f32)).astype(f32)).astype(f32)

    area = f32(f32(f32(P[1][0] - P[0][0]) * f32(P[2][1] - P[0][1])) - f32(f32(P[2][0] - P[0][0]) * f32(P[1][1] - P[0][1])))
    E = [edge(1, 2), edge(2, 0), edge(0, 1)]
    if recip_area:
        lam64 = [e.astype(np.float64) * np.float64(f32(f32(1.0) / area)) for e in E]
    else:
        lam64 = [e.astype(np.float64) / np.float64(area) for e in E]
    if rnd == "z":
        lam = [to_f32_rz(l) for l in lam64]
    else:
        lam = [l.astype(f32) for l in lam64]
    b, c = [i for i in range(3) if i != ref]
    if order:
        b, c = c, b
    t = (T[ref] + (f32(T[b] - T[ref]) * lam[b]).astype(f32)).astype(f32)
    t = (t + (f32(T[c] - T[ref]) * lam[c]).astype(f32)).astype(f32)
    return (t * f32(256.0)).astype(f32) < tie


def to_f32_rz(a):
    """float64 -> float32 rounding toward zero."""
    r = a.astype(f32)
    over = np.abs(r.astype(np.float64)) > np.abs(a)
    r[over] = np.nextafter(r[over], f32(0))
    return r


def predict(u, delta, mode, refs=(0, 0), fused=False, norm=True, vs_up=True):
    vv = verts(delta)
    x, y = u["x"], u["y"]
    comp = u["axis"].astype(int)  # 0 = u (x axis), 1 = v
    tie = u["tex"]
    t1 = which_tri(vv, x, y)
    down = np.zeros(len(x), bool)
    for name, tri, ref in (("T1", TRIS["T1"], refs[0]), ("T2", TRIS["T2"], refs[1])):
        for c in (0, 1):
            m = (t1 if name == "T1" else ~t1) & (comp == c)
            if not m.any():
                continue
            if mode == "exact":
                down[m] = eval_exact(vv, tri, c, x[m], y[m], tie[m])
            elif mode.startswith("rb"):
                # rb<recip><order><rnd>  e.g. rb10n
                down[m] = eval_refbary(vv, tri, c, x[m], y[m], tie[m], ref, mode[2] == "1", int(mode[3]), mode[4])
            elif mode.startswith("bary"):
                # bary<ra><rd>  e.g. bary00: divide by area, divide by den
                order = ORDERS[ref]
                down[m] = eval_bary(vv, tri, c, x[m], y[m], tie[m], mode[4] == "1", mode[5] == "1", order)
            else:
                down[m] = eval_f32(vv, tri, c, x[m], y[m], tie[m], ref, fused, norm)
    if vs_up:
        down[u["vs"]] = False
    return down


def score(u, down):
    hit = np.where(down, u["dn"], u["n"] - u["dn"])
    v128 = u["axis"] & (u["tex"] <= 128)
    out = {"all": (hit.sum(), u["n"].sum()), "v<=128": (hit[v128].sum(), u["n"][v128].sum()),
           "u": (hit[~u["axis"]].sum(), u["n"][~u["axis"]].sum()),
           "v>=136": (hit[u["axis"] & ~v128].sum(), u["n"][u["axis"] & ~v128].sum())}
    band = v128 & (u["x"] >= 320) & (u["x"] <= 479) & (u["y"] >= 135) & (u["y"] <= 240) & ~u["vs"]
    out["band"] = (hit[band].sum(), u["n"][band].sum())
    ff = v128 & ~u["vs"]
    out["FF v<=128"] = (hit[ff].sum(), u["n"][ff].sum())
    return out


def fmt(s):
    return "  ".join("%s %.2f%%" % (k, 100.0 * h / max(n, 1)) for k, (h, n) in s.items())


ORDERS = list(itertools.permutations(range(3)))  # for bary modes, refs index a summation order

CONFIGS = [("exact", (0, 0), False)] + [("f32", r, fu) for r in itertools.product(range(3), range(3))
                                        for fu in (False, True)]


def scan(u):
    best = []
    for delta in itertools.product((0, 1), repeat=8):
        for mode, refs, fused in CONFIGS:
            s = score(u, predict(u, delta, mode, refs, fused))
            best.append((s["v<=128"][0] / s["v<=128"][1], delta, mode, refs, fused, s))
    best.sort(key=lambda r: -r[0])
    for r in best[:25]:
        print("%.4f delta=%s %s refs=%s fused=%d | %s" % (r[0], "".join(map(str, r[1])), r[2], r[3], r[4], fmt(r[5])))
    return best


def sign_map(u, down=None):
    """Runs of D/U per v-tie row over FF pixels: the golden (majority) or a model."""
    m = u["axis"] & ~u["vs"]
    for row in sorted(set(u["line"][m])):
        r = m & (u["line"] == row)
        xs = u["x"][r]
        o = np.argsort(xs)
        xs = xs[o]
        s = (down[r][o] if down is not None else (2 * u["dn"][r][o] > u["n"][r][o]))
        runs, start = [], 0
        for i in range(1, len(xs) + 1):
            if i == len(xs) or s[i] != s[start]:
                runs.append("%s%d-%d" % ("D" if s[start] else "U", xs[start], xs[i - 1]))
                start = i
        print("row %3d v=%3d  %s" % (row, row * 8 // 15, " ".join(runs)))


def parse_config(s):
    # e.g. 00000000:f32:01:0  (delta bits : mode : refs : fused)
    d, mode, refs, fused = s.split(":")
    return tuple(int(c) for c in d), mode, (int(refs[0]), int(refs[1])), bool(int(fused))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--show", help="score one config DELTA8:MODE:REFS:FUSED")
    ap.add_argument("--map", help="print a config's v-tie sign map (or 'golden')")
    a = ap.parse_args()
    d, u, inv = load(a.gold)
    if a.scan:
        scan(u)
    if a.show:
        delta, mode, refs, fused = parse_config(a.show)
        print(fmt(score(u, predict(u, delta, mode, refs, fused))))
    if a.map:
        if a.map == "golden":
            sign_map(u)
        else:
            delta, mode, refs, fused = parse_config(a.map)
            sign_map(u, predict(u, delta, mode, refs, fused))


if __name__ == "__main__":
    main()
