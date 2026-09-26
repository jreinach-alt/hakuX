#!/usr/bin/env python3
"""Barycentric evaluation with guard-bit-free adders (#282).

model_p.py rounds the exact result of every operation. A hardware adder with
no guard bits instead truncates the smaller operand to the larger operand's
ulp before adding, so what is lost depends on the exponent difference of the
two addends -- a loss keyed on binades, which is the shape binades.py reads
off the goldens. This module evaluates the barycentric families with that
adder ('a'), p-bit mantissas, lambdas by E * rcp(area) or E / area, the
reciprocal truncated or rounded.

Usage: align_model.py GOLD.npz [--scan] [--show FAM:P:RCP:ORDER1ORDER2]
"""
import argparse
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import plane_model as pm  # noqa: E402
import model_p  # noqa: E402


def trunc_to(a, p):
    return model_p.R(a, p, "z")


def ulp(a, p):
    m, e = np.frexp(np.abs(a))
    return np.ldexp(1.0, e - p)


def add(a, b, p):
    """a + b with the smaller operand truncated to the larger's ulp first."""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    big = np.where(np.abs(a) >= np.abs(b), a, b)
    small = np.where(np.abs(a) >= np.abs(b), b, a)
    q = np.where(big == 0, 1.0, ulp(big, p))
    small = np.trunc(small / q) * q
    return trunc_to(big + small, p)


def mul(a, b, p):
    return trunc_to(np.asarray(a, np.float64) * b, p)


def evaluate(fam, p, rcp, tri, comp, x, y, order):
    V = [pm.CORNERS[i] for i in tri]
    T = [float(pm.UV[i][comp]) for i in tri]
    x = x.astype(np.float64)
    y = y.astype(np.float64)
    area = float((V[1][0] - V[0][0]) * (V[2][1] - V[0][1]) - (V[2][0] - V[0][0]) * (V[1][1] - V[0][1]))

    def edge(a, b):
        (xa, ya), (xb, yb) = V[a], V[b]
        return (xb - xa) * (y - ya) - (yb - ya) * (x - xa)  # exact: small integers

    E = [edge(1, 2), edge(2, 0), edge(0, 1)]
    if rcp == "t":
        lam = [mul(e, trunc_to(1.0 / area, p), p) for e in E]
    elif rcp == "n":
        lam = [mul(e, model_p.R(1.0 / area, p, "n"), p) for e in E]
    else:
        lam = [trunc_to(e / area, p) for e in E]
    if fam == "bary":
        o = list(itertools.permutations(range(3)))[order]
        num = mul(T[o[0]], lam[o[0]], p)
        den = lam[o[0]]
        for i in o[1:]:
            num = add(num, mul(T[i], lam[i], p), p)
            den = add(den, lam[i], p)
        return trunc_to(num / den, p)
    ref, sw = divmod(order, 2)
    b, c = [i for i in range(3) if i != ref]
    if sw:
        b, c = c, b
    t = add(T[ref], mul(T[b] - T[ref], lam[b], p), p)
    return add(t, mul(T[c] - T[ref], lam[c], p), p)


def predict(u, fam, p, rcp, orders):
    x, y = u["x"], u["y"]
    comp = u["axis"].astype(int)
    tie = u["tex"].astype(np.float64)
    t1 = 3 * x >= 4 * y
    down = np.zeros(len(x), bool)
    for k, tri in enumerate((pm.TRIS["T1"], pm.TRIS["T2"])):
        for c in (0, 1):
            m = (t1 if k == 0 else ~t1) & (comp == c)
            t = evaluate(fam, p, rcp, tri, c, x[m], y[m], orders[k])
            down[m] = t * 256.0 < tie[m]
    down[u["vs"]] = False
    return down


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--show", action="append", default=[])
    ap.add_argument("--map")
    a = ap.parse_args()
    d, u, inv = pm.load(a.gold)
    fit, held = model_p.region_masks(u)
    if a.scan:
        rows = []
        for fam, p, rcp in itertools.product(("bary", "rb"), range(10, 25), "tnd"):
            for o1, o2 in itertools.product(range(6), range(6)):
                down = predict(u, fam, p, rcp, (o1, o2))
                hit = np.where(down, u["dn"], u["n"] - u["dn"])
                rows.append((hit[fit].sum() / u["n"][fit].sum(), hit[held].sum() / u["n"][held].sum(),
                             "%s:%d:%s:%d%d" % (fam, p, rcp, o1, o2), down))
        rows.sort(key=lambda r: -r[0])
        for r in rows[:25]:
            print("fit %.4f held %.4f %-16s %s" % (r[0], r[1], r[2], pm.fmt(pm.score(u, r[3]))))
    for s in a.show + ([a.map] if a.map else []):
        fam, p, rcp, o = s.split(":")
        down = predict(u, fam, int(p), rcp, (int(o[0]), int(o[1])))
        print(s, pm.fmt(pm.score(u, down)))
        if s == a.map:
            pm.sign_map(u, down)


if __name__ == "__main__":
    main()
