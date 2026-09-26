#!/usr/bin/env python3
"""Held-out test of #13's width-1 extent on each family's GOLDENS alone.

#13's rule (derived on Line_width, drawn by geom.c) gives a stroke of slope t
(|minor/major|, 0 <= t <= 1) a minor-axis extent E = w * (1 + t/2).  At w = 1
a band of width E over a stroke whose centre phase sweeps uniformly lights 2
pixels on a fraction t/2 of its cuts and 1 on the rest.  So per stroke:

    expected mean run length  =  E  =  w * (1 + t/2)
    observed mean run length  =  (golden ink on the stroke's cuts) / (cuts)

scored per stroke, not per pixel.  No vertex data and no capture of ours is
read: this asks what silicon does, not what we do.  A stroke is only scored
when its phase sweeps at least 4 whole pixels (t * n >= 4); a stroke that
sweeps less has too few phases for its mean to mean anything, which is also
why axis-aligned strokes are excluded (their phase does not sweep at all).
Strokes at t > 0.99 are excluded for the same reason: an exact 45-degree
stroke steps one whole pixel per cut, so its phase is locked, not swept.

Positive control, before any family is read: Line_width/Line_0001.0 (w = 1,
the suite the rule was derived on) scores 26 of 30 strokes within tolerance.

The tolerance is 2 sigma of the mean over n cuts (a run is floor(E) or
ceil(E), so its variance is frac(E)(1 - frac(E))), plus 1/n for the ends.
"""
import argparse
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lm_cuts as lc


def golden_strokes(gi, axis, min_len):
    """Thin golden cuts chained into strokes: list of (xs, lens, centres)."""
    if axis == 1:
        gi = gi.T
    cuts = []
    for x in range(gi.shape[1]):
        for a, b in lc.thin_runs(gi[:, x]):
            cuts.append((x, a, b))
    parent = list(range(len(cuts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    byx = {}
    for i, c in enumerate(cuts):
        byx.setdefault(c[0], []).append(i)
    for i, (x, a, b) in enumerate(cuts):
        for j in byx.get(x + 1, []):
            _, a2, b2 = cuts[j]
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
        lens = np.array([c[2] - c[1] + 1 for c in g])
        out.append((xs, lens, cs))
    return out


def width_of(test):
    """Line_width names carry the width: Line_0001.7 is 1 + 7/8."""
    if test.startswith("Line_") and "." in test:
        whole, eighth = test[5:].split(".")
        return int(whole) + int(eighth) / 8.0
    return 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", action="append", choices=list(lc.FAMS))
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--min-len", type=int, default=20)
    ap.add_argument("--per-stroke", action="store_true")
    ap.add_argument("--width", type=float, default=None,
                    help="line width; default 1.0, or read from Line_NNNN.k")
    ap.add_argument("--suite-glob", nargs=2, metavar=("SUITE", "GLOB"),
                    help="score another suite, e.g. Line_width 'Line_0001.*'")
    args = ap.parse_args()
    jobs = []
    if args.suite_glob:
        jobs.append(tuple(args.suite_glob))
    for fam in args.family or ([] if args.suite_glob else list(lc.FAMS)):
        jobs.append((fam, lc.FAMS[fam]))
    for suite, pat in jobs:
        n_str = n_in = 0
        n_cut = 0
        obs2 = exp2 = 0.0
        seen = set()
        for gp in sorted(glob.glob(os.path.join(lc.G, suite, pat + ".png"))):
            test = os.path.basename(gp)[:-4]
            if any(e in test for e in args.exclude):
                continue
            g = lc.load(gp)
            gi = lc.ink(g) & lc.masked(suite, g.shape[:2])
            for axis in (0, 1):
                for xs, lens, cs in golden_strokes(gi, axis, args.min_len):
                    t = abs(float(np.polyfit(xs, cs, 1)[0]))
                    n = len(xs)
                    if t > 0.99 or t * n < 4:
                        continue
                    # identical goldens (e.g. four draw modes) are one stroke
                    key = (axis, int(xs[0]), int(cs[0]), n, int((lens >= 2).sum()))
                    if key in seen:
                        continue
                    seen.add(key)
                    w = args.width if args.width else width_of(test)
                    share = float(lens.mean())
                    exp = w * (1 + t / 2)
                    fe = exp - np.floor(exp)
                    tol = 2 * np.sqrt(max(fe * (1 - fe), 1e-4) / n) + 1.0 / n
                    ok = abs(share - exp) <= tol
                    n_str += 1
                    n_in += ok
                    n_cut += n
                    obs2 += lens.sum()
                    exp2 += exp * n
                    if args.per_stroke:
                        print("  %-36s %s major %3d-%3d t %.4f n %4d  "
                              "mean len obs %.3f exp %.3f tol %.3f %s"
                              % (test, "col" if axis == 0 else "row",
                                 xs[0], xs[-1], t, n, share, exp, tol,
                                 "ok" if ok else "OUT"))
        print("%-14s %-18s strokes %3d, within tolerance %3d | cuts %5d, "
              "ink observed %5d vs E=w(1+t/2) expects %7.1f"
              % (suite, pat, n_str, n_in, n_cut, obs2, exp2))


if __name__ == "__main__":
    main()
