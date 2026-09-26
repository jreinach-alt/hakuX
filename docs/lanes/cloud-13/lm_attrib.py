#!/usr/bin/env python3
"""Attribute every STRUCTURAL pixel (max channel delta > 8, the inventory's
measure) of the #13 line-mode families to one cause.  No mask: the pb_print
labels are identical in golden and capture, so they contribute 0 anyway.

  colour     ink in both, delta > 8                      (shading/provoking)
  tie        a pixel of a TIE STROKE: a chain of thin cuts (lm_strokes) on
             which our run has the golden's length and sits one pixel over
             on at least half the cuts -- the whole stroke displaced
  primitive  ink in one image only, farther than 2 px from any ink of the
             other: a whole primitive one side drew and the other did not
             (Front_face: culling)
  extent     the remaining ink-in-one-image pixels: within 2 px of the other
             side's ink, so a stroke both drew with a different run length
             or phase
"""
import argparse
import collections
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lm_cuts as lc


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def tie_pixels(gi, oi, min_len=10):
    """Mask of pixels on tie strokes (both images' runs), either axis."""
    mask = np.zeros(gi.shape, bool)
    for axis in (0, 1):
        G, O, M = (gi, oi, mask) if axis == 0 else (gi.T, oi.T, mask.T)
        cuts = []
        for x in range(G.shape[1]):
            oruns = lc.thin_runs(O[:, x])
            for a, b in lc.thin_runs(G[:, x]):
                m = [r for r in oruns if r[1] >= a - 2 and r[0] <= b + 2]
                r = m[0] if m else None
                shifted = (r is not None and r[1] - r[0] == b - a
                           and abs(r[0] - a) == 1)
                cuts.append((x, a, b, r, shifted))
        parent = list(range(len(cuts)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        byx = collections.defaultdict(list)
        for i, c in enumerate(cuts):
            byx[c[0]].append(i)
        for i, c in enumerate(cuts):
            for j in byx.get(c[0] + 1, []):
                if cuts[j][1] <= c[2] + 1 and cuts[j][2] >= c[1] - 1:
                    parent[find(i)] = find(j)
        groups = collections.defaultdict(list)
        for i in range(len(cuts)):
            groups[find(i)].append(cuts[i])
        for g in groups.values():
            if len(g) < min_len:
                continue
            if sum(c[4] for c in g) * 2 < len(g):
                continue
            for x, a, b, r, s in g:
                if s:
                    M[a:b + 1, x] = True
                    M[r[0]:r[1] + 1, x] = True
    return mask


def attribute(g, o):
    gi, oi = lc.ink(g), lc.ink(o)
    d = np.abs(g - o).max(2)
    st = d > 8
    out = collections.Counter()
    out["structural"] = int(st.sum())
    colour = st & gi & oi
    out["colour"] = int(colour.sum())
    rest = st & ~colour
    tie = tie_pixels(gi, oi) & rest
    out["tie"] = int(tie.sum())
    rest &= ~tie
    near_o, near_g = dilate(oi, 2), dilate(gi, 2)
    prim = rest & ((oi & ~near_g) | (gi & ~near_o))
    out["primitive"] = int(prim.sum())
    out["primitive_ours_only"] = int((prim & oi).sum())
    rest &= ~prim
    out["extent"] = int(rest.sum())
    out["extent_ours_only"] = int((rest & oi).sum())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", action="append", required=True)
    ap.add_argument("--family", action="append", choices=list(lc.FAMS))
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--per-capture", action="store_true")
    args = ap.parse_args()
    for fam in args.family or list(lc.FAMS):
        tot = collections.Counter()
        n = 0
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
                print("  MISSING", test)
                continue
            a = attribute(lc.load(gp), o)
            n += 1
            tot.update(a)
            if args.per_capture:
                print("  %-34s %s" % (test, dict(a)))
        print("%-13s %2d captures  structural %6d = colour %6d + tie %5d + "
              "primitive %6d (ours-only %6d) + extent %5d (ours-only %5d)"
              % (fam, n, tot["structural"], tot["colour"], tot["tie"],
                 tot["primitive"], tot["primitive_ours_only"], tot["extent"],
                 tot["extent_ours_only"]))


if __name__ == "__main__":
    main()
