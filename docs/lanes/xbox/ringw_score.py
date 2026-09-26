#!/usr/bin/env python3
"""Score the #53 ring-weights run (ringw-run.md) on one captures root.

    ringw_score.py <captures root> [--cases M0,M1,...] [--baseline M0]

--cases picks which cases to read (default: the original run's 15); the
baseline case must step exactly 4 (leg C0). ringw-boundary-run.md uses
--cases N0,...,N7 --baseline N0.

<captures root> is a console run's `console/` (Ring_weights/Test.png) or a
dispatcher result's `captures1/` (Ring_weights::Test.png). Values are the red
channel at each quad corner, from a plane fit per triangle (UL-LR diagonal),
exactly as litprime_score.py (PR #355). Writes nothing.

Every case K is a priming test K a_FF (two lit FF quads, vertices 0..7) and a
shader test K b_* (six single-quad draws). Each draw's corners name four
consecutive entries of the ring cycle 2,3,4,5,6,7, and its window start is
read. The step between draws is the difference of starts (mod 6), and the
method's weight is step - 4 (mod 6).

  S   per case: the eight priming values are pairwise >= 10 apart
  R   per case: every draw names a window (all four corners map to priming
      vertices 2..7, consecutive, ascending)
  C0  M0 (no extra method) steps exactly 4 on all five gaps: the baseline the
      weights are measured against (PR #355's L0 measured it)
  P1  each M case steps by one constant (the weight is a property of the method)
  P2  the fill weight read from C0/C1/C2's first-draw starts equals M6's
"""
import os
import sys

import numpy as np
from PIL import Image

SUITE = "Ring_weights"
PRIME_QUADS = [(80.0, 180.0, 160.0, 120.0), (400.0, 180.0, 160.0, 120.0)]
LIT_QUADS = [(16.0 + 104.0 * q, 192.0, 96.0, 96.0) for q in range(6)]
CYCLE = [2, 3, 4, 5, 6, 7]
TOL, SEP, OWN = 6.0, 10.0, 255.0
CASES = ["B1", "B2", "B3", "C0", "C1", "C2", "M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]


def find(root, prefix):
    for base in (os.path.join(root, SUITE), root):
        if not os.path.isdir(base):
            continue
        for f in sorted(os.listdir(base)):
            name = f[len(SUITE) + 2:] if f.startswith(SUITE + "::") else f
            if name.startswith(prefix) and name.endswith(".png"):
                return os.path.join(base, f), name[:-4]
    return None, None


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


def window_start(vals, prime):
    srcs = []
    for v in vals:
        if abs(v - OWN) <= TOL:
            return None, "own"
        d = [abs(v - p) for p in prime]
        i = int(np.argmin(d))
        if d[i] > TOL:
            return None, "none"
        srcs.append(i)
    if not all(s in CYCLE for s in srcs):
        return None, srcs
    p = CYCLE.index(srcs[0])
    return (p, srcs) if [CYCLE[(p + k) % 6] for k in range(4)] == srcs else (None, srcs)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--cases", default=",".join(CASES))
    ap.add_argument("--baseline", default="M0")
    a = ap.parse_args()
    root, cases, base = a.root, a.cases.split(","), a.baseline
    res = {}
    for k in cases:
        pp, _ = find(root, k + "a_FF")
        sp, sname = find(root, k + "b_")
        if not pp or not sp:
            print("%s: MISSING" % k)
            res[k] = None
            continue
        pa = rgb(pp)
        prime = [v for quad in PRIME_QUADS for v in corners(pa, *quad)]
        sep = min(abs(x - y) for i, x in enumerate(prime) for y in prime[i + 1:])
        sa = rgb(sp)
        starts, notes = [], []
        for quad in LIT_QUADS:
            s, info = window_start(corners(sa, *quad), prime)
            starts.append(s)
            notes.append(info)
        steps = None if None in starts else [(b - a) % 6 for a, b in zip(starts, starts[1:])]
        res[k] = (sep >= SEP, starts, steps, sname)
        print("%-3s %-14s S %s  starts %s  steps %s%s" % (
            k, sname, "ok" if sep >= SEP else "FAIL(%.1f)" % sep, starts, steps,
            "" if steps is not None else "  unreadable: %s" % notes))
    ok = lambda k: res.get(k) and res[k][0] and res[k][2] is not None
    c0 = ok(base) and set(res[base][2]) == {4}
    print("C0 %s steps all 4: %s" % (base, "holds" if c0 else "FAILS -- the weights have no baseline"))
    p1 = True
    for k in [c for c in cases if c != base and c[0] in "MN"]:
        if ok(k):
            st = set(res[k][2])
            const = len(st) == 1
            p1 = p1 and const
            print("   %s %-11s weight %s%s" % (k, res[k][3].split("_", 1)[1], sorted((s - 4) % 6 for s in st),
                                              "" if const else "  <- not constant"))
        else:
            p1 = False
            print("   %s unreadable" % k)
    print("P1 each method's step is constant: %s" % ("holds" if p1 else "FAILS"))
    if not any(c in cases for c in ("C0", "C1", "C2")):
        p2 = True
        print("P2 not part of this run")
    elif all(ok(k) for k in ("C0", "C1", "C2", "M6")):
        f1 = (res["C1"][1][0] - res["C0"][1][0]) % 6
        f2 = (res["C2"][1][0] - res["C1"][1][0]) % 6
        m6 = sorted({(s - 4) % 6 for s in res["M6"][2]})
        p2 = f1 == f2 and [f1] == m6
        print("P2 fill weight: C1-C0 %d, C2-C1 %d, M6 %s -> %s" % (f1, f2, m6, "holds" if p2 else "FAILS"))
    else:
        p2 = False
        print("P2 not read: a C case or M6 unreadable")
    for k in ("B1", "B2", "B3"):
        if k in cases and res.get(k):
            print("   %s (recorded) starts %s steps %s" % (k, res[k][1], res[k][2]))
    return 0 if (c0 and p1 and p2) else 1


if __name__ == "__main__":
    sys.exit(main())
