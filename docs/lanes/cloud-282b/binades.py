#!/usr/bin/env python3
"""Golden tie direction by the binades of the barycentric weights (#282).

For every FF v-tie pixel: which triangle, and floor(log2) of each barycentric
weight in that triangle, exact rationals from the unsnapped corners. Prints
golden down/total per (triangle, binade(l0), binade(l1), binade(l2)) cell,
so a reader can see which weights the direction is keyed on.

Usage: binades.py GOLD.npz [--axis u|v]
"""
import argparse
import collections
import math
import os
import sys
from fractions import Fraction as F

sys.path.insert(0, os.path.dirname(__file__))
import plane_model as pm  # noqa: E402


def lams(tri, x, y):
    (xa, ya), (xb, yb), (xc, yc) = (pm.CORNERS[i] for i in tri)
    area = (xb - xa) * (yc - ya) - (xc - xa) * (yb - ya)
    e = lambda p, q: (q[0] - p[0]) * (y - p[1]) - (q[1] - p[1]) * (x - p[0])
    P = [(xa, ya), (xb, yb), (xc, yc)]
    return [F(e(P[1], P[2]), area), F(e(P[2], P[0]), area), F(e(P[0], P[1]), area)]


def binade(l):
    return "0" if l == 0 else "%d" % math.floor(math.log2(l))


def binade_rule(u):
    """The rule the table reads as: in T1 (t = l2) a v tie goes down iff
    l2 <= 1/2, except where l0 and l2 are both in (1/4, 1/2]; T2 and u ties
    up; VS draws up. Intervals are half-open at the bottom: a weight that is
    exactly a power of two behaves as if computed a hair below it."""
    x, y = u["x"], u["y"]
    t1 = 3 * x >= 4 * y
    l0 = (W - x) / W
    l2 = y / H
    band = (l0 > 0.25) & (l0 <= 0.5) & (l2 > 0.25) & (l2 <= 0.5)
    return u["axis"] & ~u["vs"] & t1 & (l2 <= 0.5) & ~band


W, H = pm.W, pm.H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gold")
    ap.add_argument("--axis", default="v")
    ap.add_argument("--rule", action="store_true", help="score binade_rule")
    a = ap.parse_args()
    d, u, inv = pm.load(a.gold)
    if a.rule:
        print(pm.fmt(pm.score(u, binade_rule(u))))
        return
    m = ~u["vs"] & (u["axis"] == (a.axis == "v"))
    cells = collections.defaultdict(lambda: [0, 0])
    for x, y, n, dn in zip(u["x"][m], u["y"][m], u["n"][m], u["dn"][m]):
        name = "T1" if 3 * x >= 4 * y else "T2"
        L = lams(pm.TRIS[name], int(x), int(y))
        k = (name,) + tuple(binade(l) for l in L)
        cells[k][0] += int(dn)
        cells[k][1] += int(n)
    print("tri  b(l0) b(l1) b(l2)      down/total   down%")
    for k in sorted(cells):
        dn, n = cells[k]
        print("%-4s %5s %5s %5s  %8d/%-8d %6.1f%%" % (k + (dn, n, 100.0 * dn / n)))


if __name__ == "__main__":
    main()
