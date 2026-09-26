#!/usr/bin/env python3
"""Run-length table for thin cuts: (golden length, ours length) -> count, per
family, over every cut where ours has an overlapping run.  A stroke-EXTENT
difference shows up here as a one-sided excess: ours longer than silicon on
many cuts and shorter on few means our minor-axis extent is wider than
silicon's; a two-sided spread is phase, not extent.  The extent itself is
scored against the goldens alone by lm_extent.py.
"""
import argparse
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lm_cuts as lc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", action="append", required=True)
    ap.add_argument("--family", action="append", choices=list(lc.FAMS))
    ap.add_argument("--exclude", action="append", default=[],
                    help="skip tests whose name contains this")
    args = ap.parse_args()
    for fam in args.family or list(lc.FAMS):
        pairs = collections.Counter()
        for gp in sorted(glob.glob(os.path.join(lc.G, fam, lc.FAMS[fam] + ".png"))):
            test = os.path.basename(gp)[:-4]
            if any(e in test for e in args.exclude):
                continue
            o = None
            for cap in args.cap:
                p = os.path.join(cap, "%s::%s.png" % (fam, test))
                if os.path.exists(p):
                    o = lc.load(p)
                    break
            if o is None:
                continue
            g = lc.load(gp)
            keep = lc.masked(fam, g.shape[:2])
            gi, oi = lc.ink(g) & keep, lc.ink(o) & keep
            for G2, O2 in ((gi, oi), (gi.T, oi.T)):
                for x in range(G2.shape[1]):
                    oruns = lc.thin_runs(O2[:, x])
                    for a, b in lc.thin_runs(G2[:, x]):
                        m = [r for r in oruns if r[1] >= a - 2 and r[0] <= b + 2]
                        if m:
                            pairs[(b - a + 1, m[0][1] - m[0][0] + 1)] += 1
        print("%s" % fam)
        print("  (golden len, ours len): %s"
              % dict(sorted(pairs.items(), key=lambda kv: -kv[1])))
        tot = sum(pairs.values())
        same = sum(v for (a, b), v in pairs.items() if a == b)
        longer = sum(v for (a, b), v in pairs.items() if b > a)
        shorter = sum(v for (a, b), v in pairs.items() if b < a)
        print("  cuts %d: same length %d, ours longer %d, ours shorter %d"
              % (tot, same, longer, shorter))


if __name__ == "__main__":
    main()
