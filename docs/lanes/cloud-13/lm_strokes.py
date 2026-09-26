#!/usr/bin/env python3
"""Per-STROKE scoring of the #13 line-mode families: the region unit the brief
asks for, rather than pixels.

A stroke is a chain of thin golden cuts (lm_cuts.thin_runs) on one axis whose
runs touch from one scan index to the next.  For each stroke:

  n       cuts on the stroke that ours also has a thin run for
  exact   cuts with the same run
  +1/-1   cuts whose run is the same length, moved by one (ours - golden)
  size    cuts with a different length
  f       (+1 count) / n -- the SHIFT FRACTION
  slope   least-squares minor-per-major slope of the golden run centres

A constant sub-pixel offset d between our stroke centre and silicon's moves
floor(c) on a fraction |d| of the cuts of every slanted stroke, whatever the
slope, and on 0 or all of the cuts of an axis-aligned one.  That is the
single-rule hypothesis this tool tests: f should be one number per family if
it is one offset, and the SAME number across families if it is one rule.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lm_cuts as lc


def strokes(gi, oi, axis, min_len):
    if axis == 1:
        gi, oi = gi.T, oi.T
    cuts = []
    for x in range(gi.shape[1]):
        oruns = lc.thin_runs(oi[:, x])
        for a, b in lc.thin_runs(gi[:, x]):
            m = [r for r in oruns if r[1] >= a - 2 and r[0] <= b + 2]
            if not m:
                kind = None
            elif m[0] == (a, b):
                kind = 0
            elif m[0][1] - m[0][0] == b - a:
                kind = m[0][0] - a
            else:
                kind = "size"
            cuts.append((x, a, b, kind))
    # chain cuts whose runs touch on adjacent scan indices
    parent = list(range(len(cuts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    byx = {}
    for i, c in enumerate(cuts):
        byx.setdefault(c[0], []).append(i)
    for i, (x, a, b, _) in enumerate(cuts):
        for j in byx.get(x + 1, []):
            _, a2, b2, _ = cuts[j]
            if a2 <= b + 1 and b2 >= a - 1:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(cuts)):
        groups.setdefault(find(i), []).append(cuts[i])
    out = []
    for g in groups.values():
        if len(g) < min_len:
            continue
        xs = np.array([c[0] for c in g], float)
        cs = np.array([(c[1] + c[2]) / 2.0 for c in g])
        slope = float(np.polyfit(xs, cs, 1)[0]) if len(g) > 1 else 0.0
        kinds = [c[3] for c in g if c[3] is not None]
        out.append({"x0": int(xs.min()), "x1": int(xs.max()),
                    "c0": float(cs[0]), "slope": slope,
                    "n": len(kinds),
                    "exact": sum(1 for k in kinds if k == 0),
                    "p1": sum(1 for k in kinds if k == 1),
                    "m1": sum(1 for k in kinds if k == -1),
                    "size": sum(1 for k in kinds if k == "size"),
                    "absent": len(g) - len(kinds)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", action="append", required=True)
    ap.add_argument("--family", required=True, choices=list(lc.FAMS))
    ap.add_argument("--test", action="append",
                    help="restrict to these tests (default: all in family)")
    ap.add_argument("--min-len", type=int, default=20)
    args = ap.parse_args()
    import glob
    tests = args.test or sorted(
        os.path.basename(p)[:-4] for p in
        glob.glob(os.path.join(lc.G, args.family, lc.FAMS[args.family] + ".png")))
    for test in tests:
        g = lc.load(os.path.join(lc.G, args.family, test + ".png"))
        o = None
        for cap in args.cap:
            p = os.path.join(cap, "%s::%s.png" % (args.family, test))
            if os.path.exists(p):
                o = lc.load(p)
                break
        if o is None:
            print(test, "MISSING")
            continue
        keep = lc.masked(args.family, g.shape[:2])
        gi, oi = lc.ink(g) & keep, lc.ink(o) & keep
        print(test)
        for axis, name in ((0, "x-major (col cuts, minor=y)"),
                           (1, "y-major (row cuts, minor=x)")):
            for s in sorted(strokes(gi, oi, axis, args.min_len),
                            key=lambda s: (s["x0"], s["c0"])):
                f = s["p1"] / max(1, s["n"])
                print("  %-28s major %3d-%3d minor@start %6.1f slope %+7.4f "
                      "n %4d exact %4d +1 %4d -1 %3d size %3d absent %3d  f %.3f"
                      % (name, s["x0"], s["x1"], s["c0"], s["slope"], s["n"],
                         s["exact"], s["p1"], s["m1"], s["size"],
                         s["absent"], f))


if __name__ == "__main__":
    main()
