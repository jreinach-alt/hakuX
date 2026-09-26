#!/usr/bin/env python3
"""Attribute setup/evaluation at a p-bit mantissa (#282).

plane_model.py fixes the arithmetic at IEEE float32. This module repeats the
three evaluation families with every operation rounded to a p-bit mantissa
(implicit bit included; p = 24 is float32), round-to-nearest-even ('n') or
toward zero ('z'), so the precision is a parameter the sign map can choose:

  plane  t = t_r + A (x - x_r) + B (y - y_r), A and B from edge vectors
  bary   t = sum(t_i l_i) / sum(l_i), l_i = E_i * (1/area) or E_i / area
  rb     t = t_r + (t_b - t_r) l_b + (t_c - t_r) l_c

Vertices are exact (every snap offset 0: plane_model.py's scan found no snap
that helps), pixel centres at integer (x, y), w = 8 everywhere (exact).

Usage: model_p.py GOLD.npz --scan | --show FAMILY:P:RND:REF1REF2:VAR | --map ...
"""
import argparse
import itertools
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import plane_model as pm  # noqa: E402


def R(a, p, mode):
    a = np.asarray(a, np.float64)
    m, e = np.frexp(a)  # a = m 2^e, |m| in [0.5, 1)
    s = m * 2.0 ** p
    s = np.rint(s) if mode == "n" else np.trunc(s)
    return np.ldexp(s, e - p)


def evaluate(fam, p, mode, tri, comp, x, y, ref, var):
    V = [pm.CORNERS[i] for i in tri]
    T = [float(pm.UV[i][comp]) for i in tri]
    r = lambda a: R(a, p, mode)
    x = x.astype(np.float64)
    y = y.astype(np.float64)
    e1x, e1y = V[1][0] - V[0][0], V[1][1] - V[0][1]
    e2x, e2y = V[2][0] - V[0][0], V[2][1] - V[0][1]
    area = r(r(e1x * e2y) - r(e2x * e1y))
    if fam == "plane":
        d1, d2 = T[1] - T[0], T[2] - T[0]
        if var & 1:  # multiply by a rounded reciprocal of the area
            ra = r(1.0 / area)
            A = r(r(r(d1 * e2y) - r(d2 * e1y)) * ra)
            B = r(r(r(d2 * e1x) - r(d1 * e2x)) * ra)
        else:
            A = r(r(r(d1 * e2y) - r(d2 * e1y)) / area)
            B = r(r(r(d2 * e1x) - r(d1 * e2x)) / area)
        xr, yr = V[ref]
        dx, dy = r(x - xr), r(y - yr)
        if var & 2:
            t = r(r(T[ref] + r(B * dy)) + r(A * dx))
        else:
            t = r(r(T[ref] + r(A * dx)) + r(B * dy))
    else:
        def edge(a, b):
            (xa, ya), (xb, yb) = V[a], V[b]
            return r(r((xb - xa) * r(y - ya)) - r((yb - ya) * r(x - xa)))
        E = [edge(1, 2), edge(2, 0), edge(0, 1)]
        if var & 1:
            ra = r(1.0 / area)
            lam = [r(e * ra) for e in E]
        else:
            lam = [r(e / area) for e in E]
        if fam == "bary":
            order = list(itertools.permutations(range(3)))[ref]
            num = np.zeros_like(x)
            den = np.zeros_like(x)
            for i in order:
                num = r(num + r(T[i] * lam[i]))
                den = r(den + lam[i])
            t = r(num * r(1.0 / den)) if var & 2 else r(num / den)
        else:  # rb
            b, c = [i for i in range(3) if i != ref]
            if var & 2:
                b, c = c, b
            t = r(r(T[ref] + r((T[b] - T[ref]) * lam[b])) + r((T[c] - T[ref]) * lam[c]))
    return t


def predict(u, fam, p, mode, refs, var):
    x, y = u["x"], u["y"]
    comp = u["axis"].astype(int)
    tie = u["tex"].astype(np.float64)
    t1 = 3 * x >= 4 * y
    down = np.zeros(len(x), bool)
    for k, (tri, ref) in enumerate(((pm.TRIS["T1"], refs[0]), (pm.TRIS["T2"], refs[1]))):
        for c in (0, 1):
            m = (t1 if k == 0 else ~t1) & (comp == c)
            t = evaluate(fam, p, mode, tri, c, x[m], y[m], ref, var)
            down[m] = t * 256.0 < tie[m]
    down[u["vs"]] = False
    return down


def region_masks(u):
    """Fit region (outside the discriminating region) and the held-out region."""
    ff = ~u["vs"] & u["axis"]
    t1 = 3 * u["x"] >= 4 * u["y"]
    held = ff & t1 & (((u["y"] >= 135) & (u["y"] <= 240) & (u["x"] >= 320) & (u["x"] <= 479)) |
                      ((u["y"] >= 241) & (u["y"] <= 270)))
    return ~held, held


def scan(u, fams=("plane", "bary", "rb"), ps=range(8, 25)):
    fit, held = region_masks(u)
    rows = []
    for fam, p, mode, var in itertools.product(fams, ps, "nz", range(4)):
        nref = 6 if fam == "bary" else 3
        for r1, r2 in itertools.product(range(nref), range(nref)):
            down = predict(u, fam, p, mode, (r1, r2), var)
            hit = np.where(down, u["dn"], u["n"] - u["dn"])
            fs = hit[fit].sum() / u["n"][fit].sum()
            rows.append((fs, fam, p, mode, r1, r2, var, down))
    rows.sort(key=lambda r: -r[0])
    return rows


def cfg(r):
    return "%s:%d:%s:%d%d:%d" % r[1:7]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--show", action="append", default=[])
    ap.add_argument("--map")
    a = ap.parse_args()
    d, u, inv = pm.load(a.gold)
    if a.scan:
        fit, held = region_masks(u)
        rows = scan(u)
        print("fit-region score | config | held-out region | overall")
        for r in rows[:30]:
            hit = np.where(r[7], u["dn"], u["n"] - u["dn"])
            print("%.4f %-18s held %.4f (%d px) | %s" % (r[0], cfg(r), hit[held].sum() / u["n"][held].sum(),
                                                       u["n"][held].sum(), pm.fmt(pm.score(u, r[7]))))
    for s in a.show:
        fam, p, mode, refs, var = s.split(":")
        down = predict(u, fam, int(p), mode, (int(refs[0]), int(refs[1])), int(var))
        print(s, pm.fmt(pm.score(u, down)))
    if a.map:
        fam, p, mode, refs, var = a.map.split(":")
        pm.sign_map(u, predict(u, fam, int(p), mode, (int(refs[0]), int(refs[1])), int(var)))


if __name__ == "__main__":
    main()
