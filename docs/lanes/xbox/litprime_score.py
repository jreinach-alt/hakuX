#!/usr/bin/env python3
"""Score the #53 lighting-priming run (litprime-run.md) on one captures root.

    litprime_score.py <captures root> [--hakux]

<captures root> is a console run's `console/` (Lighting_priming/Test.png)
or a dispatcher result's `captures1/` (Lighting_priming::Test.png). Values
are the red channel at each quad corner, from a plane fit per triangle split
on the UL-LR diagonal. Writes nothing.

Priming vertices are indexed 0..7 in draw order: P1 UL, UR, LR, LL, then P2
UL, UR, LR, LL. The model says a lit vertex-program corner reads one of six
ring slots holding vertices 2..7, in the cycle 2,3,4,5,6,7.

  S   the eight priming values of each *_FF capture are pairwise >= 10 apart
      (else no corner can name its source, and nothing below is read)
  M1  every lit corner is within 6 of a priming vertex, and none sits at the
      quads' own-normal value
  M2  every source is one of vertices 2..7
  M3  L0_VSdraws: each quad reads four consecutive entries of the cycle,
      ascending UL->LL, and the start advances by a constant 4 per quad
  R   L1_VSsingle: the sources and per-quad step, recorded

--hakux: prints the corner values only. hakuX emits the constant lighting
term under a vertex program (#53), so no corner is expected to name a source.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

SUITE = "Lighting_priming"
PRIME_QUADS = [(80.0, 180.0, 160.0, 120.0), (400.0, 180.0, 160.0, 120.0)]   # left, top, w, h
LIT_QUADS = [(16.0 + 104.0 * q, 192.0, 96.0, 96.0) for q in range(6)]
CYCLE = [2, 3, 4, 5, 6, 7]
TOL, SEP = 6.0, 10.0


def find(root, name):
    for p in (os.path.join(root, SUITE, name + ".png"), os.path.join(root, "%s::%s.png" % (SUITE, name))):
        if os.path.exists(p):
            return p
    return None


def corners(a, left, top, w, h):
    x0, y0 = int(np.ceil(left)), int(np.ceil(top))
    q = a[y0:int(np.ceil(top + h)), x0:int(np.ceil(left + w)), 0].astype(float)
    hh, ww = q.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    X, Y = (xx + 0.5) / ww, (yy + 0.5) / hh
    fits = []
    for m in (X > Y + 0.02, Y > X + 0.02):
        A = np.stack([np.ones(m.sum()), X[m], Y[m]], 1)
        fits.append(np.linalg.lstsq(A, q[m], rcond=None)[0])
    P = lambda c, x, y: c[0] + c[1] * x + c[2] * y
    up, lo = fits
    return [0.5 * (P(up, 0, 0) + P(lo, 0, 0)), P(up, 1, 0), 0.5 * (P(up, 1, 1) + P(lo, 1, 1)), P(lo, 0, 1)]


def rgb(p):
    return np.asarray(Image.open(p).convert("RGB"))


def priming_values(root, name):
    a = rgb(find(root, name))
    return [v for quad in PRIME_QUADS for v in corners(a, *quad)]


def sources(values, prime, own):
    out = []
    for v in values:
        if abs(v - own) <= TOL:
            out.append("own")
            continue
        d = [abs(v - p) for p in prime]
        i = int(np.argmin(d))
        out.append(i if d[i] <= TOL else "none")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--hakux", action="store_true")
    ap.add_argument("--own", type=float, default=255.0, help="red of the quads' own normal (N.L = 1)")
    a = ap.parse_args()
    for n in ("L0_FF", "L0_VSdraws", "L1_FF", "L1_VSsingle"):
        if not find(a.root, n):
            print("MISSING %s" % n)
            return 2
    ok = True
    runs = {}
    for prime_name, lit_name in (("L0_FF", "L0_VSdraws"), ("L1_FF", "L1_VSsingle")):
        prime = priming_values(a.root, prime_name)
        seps = min(abs(x - y) for i, x in enumerate(prime) for y in prime[i + 1:])
        s_ok = seps >= SEP
        print("%s priming values (vertices 0..7): %s; minimum separation %.1f -> S %s"
              % (prime_name, " ".join("%.1f" % v for v in prime), seps, "holds" if s_ok else "FAILS (void)"))
        lit = rgb(find(a.root, lit_name))
        vals = [corners(lit, *quad) for quad in LIT_QUADS]
        if a.hakux:
            print("%s corner values: %s" % (lit_name, [[round(v, 1) for v in q] for q in vals]))
            continue
        ok = ok and s_ok
        if not s_ok:
            continue
        srcs = [sources(q, prime, a.own) for q in vals]
        runs[lit_name] = srcs
        print("%s sources per quad (UL UR LR LL): %s" % (lit_name, srcs))
    if a.hakux:
        return 0
    if not ok:
        print("S fails: no leg below is read")
        return 1
    flat = [s for srcs in runs.values() for q in srcs for s in q]
    m1 = all(isinstance(s, int) for s in flat)
    m2 = m1 and all(s in CYCLE for s in flat)
    print("M1 every corner names a priming vertex, none at its own value: %s" % ("holds" if m1 else "FAILS"))
    print("M2 every source is one of vertices 2..7: %s" % ("holds" if m2 else "FAILS"))

    def starts(srcs):
        out = []
        for q in srcs:
            if not all(s in CYCLE for s in q):
                out.append(None)
                continue
            p = CYCLE.index(q[0])
            out.append(p if [CYCLE[(p + k) % 6] for k in range(4)] == list(q) else None)
        return out

    st = starts(runs["L0_VSdraws"])
    steps = sorted({(b - a_) % 6 for a_, b in zip(st, st[1:])}) if None not in st else None
    m3 = steps == [4]
    print("M3 L0_VSdraws: consecutive ascending windows, starts %s, steps %s: %s" % (st, steps, "holds" if m3 else "FAILS"))
    st1 = starts(runs["L1_VSsingle"])
    steps1 = sorted({(b - a_) % 6 for a_, b in zip(st1, st1[1:])}) if None not in st1 else None
    print("R  L1_VSsingle (recorded): starts %s, steps %s" % (st1, steps1))
    return 0 if (m1 and m2 and m3) else 1


if __name__ == "__main__":
    sys.exit(main())
