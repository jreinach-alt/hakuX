#!/usr/bin/env python3
"""Score the #10 axis follow-up (y16axis-run.md) on one captures root.

    y16axis_score.py <captures root> [--goldens /home/justin/goldens/results] [--hakux]

<captures root> is a console run's `console/` (Bump_map/Test.png) or a
dispatcher result's `captures1/` (Bump_map::Test.png). Pixel counts compare
RGB outside the printed label rows 20..44. Writes nothing.

Gates (as in PR #359), then per axis ("h": only m00 = 0.3 live; "v": only
m11 = 0.5 live):
  C1  BumpMap_Y16 and BumpMap_Y8 equal their goldens (not checked with --hakux)
  C0  BumpMap_Y16_patchSame equals this run's BumpMap_Y16
  Z   BumpMap_Y16_zero differs from BumpMap_Y16 by >= 10,000 px
  S   Y8_h's quads vary along x (<= 10% single-colour rows); Y8_v's vary
      along y (<= 10% single-colour columns). An axis whose image cannot move
      along it is not read.
  M   Y16_<axis>_lo00 against Y8_<axis>: LOW >= 10,000 px (the axis reads
      the low byte), HIGH <= 2,000, else X
  N   Y16_<axis> against Y8_<axis> (the native byte-replicated seam): SWEEP
      >= 5,000 px, NONE <= 1,000, else X
The registered prediction is the split: exactly one axis LOW, and on each
axis N agrees with M (LOW with SWEEP, HIGH with NONE).
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

QUADS = [(66, 146), (66, 326), (246, 146), (246, 326)]
LABEL = (20, 45)


def find(root, name):
    for p in (os.path.join(root, "Bump_map", name + ".png"), os.path.join(root, "Bump_map::%s.png" % name)):
        if os.path.exists(p):
            return p
    return None


def rgb(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def px(a, b):
    d = np.abs(a - b).max(axis=2) > 0
    d[LABEL[0]:LABEL[1], :] = False
    return int(d.sum())


def uniform_fraction(a, along):
    """Fraction of rows (along='x') or columns (along='y') in the quads that are one colour."""
    n = tot = 0
    for top, left in QUADS:
        q = a[top:top + 168, left:left + 168]
        lines = q if along == "x" else q.transpose(1, 0, 2)
        for ln in lines:
            tot += 1
            n += len({tuple(p) for p in ln.tolist()}) == 1
    return n / float(tot)


def grade(n, lo, hi, names):
    return names[0] if n >= hi else (names[1] if n <= lo else "X")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--hakux", action="store_true")
    a = ap.parse_args()
    names = ["BumpMap_Y16", "BumpMap_Y8", "BumpMap_Y16_patchSame", "BumpMap_Y16_zero"]
    for ax in ("h", "v"):
        names += ["BumpMap_Y16_%s" % ax, "BumpMap_Y16_%s_lo00" % ax, "BumpMap_Y8_%s" % ax]
    missing = [n for n in names if not find(a.root, n)]
    if missing:
        print("MISSING: %s" % ", ".join(missing))
        return 2
    cap = {n: rgb(find(a.root, n)) for n in names}
    gold = lambda n: rgb(os.path.join(a.goldens, "Bump_map", n + ".png"))
    c1 = a.hakux or all(np.array_equal(cap[n], gold(n)) for n in ("BumpMap_Y16", "BumpMap_Y8"))
    c0 = np.array_equal(cap["BumpMap_Y16_patchSame"], cap["BumpMap_Y16"])
    z = px(cap["BumpMap_Y16_zero"], cap["BumpMap_Y16"])
    print("C1 %s; C0 %s; Z %d px %s" % ("holds" if c1 else "FAILS", "holds" if c0 else "FAILS", z, "holds" if z >= 10000 else "FAILS"))
    gates = c1 and c0 and z >= 10000
    res = {}
    for ax, along in (("h", "x"), ("v", "y")):
        u = uniform_fraction(cap["BumpMap_Y8_%s" % ax], along)
        s_ok = u <= 0.10
        m = px(cap["BumpMap_Y16_%s_lo00" % ax], cap["BumpMap_Y8_%s" % ax])
        n = px(cap["BumpMap_Y16_%s" % ax], cap["BumpMap_Y8_%s" % ax])
        res[ax] = (s_ok, grade(m, 2000, 10000, ("LOW", "HIGH")), grade(n, 1000, 5000, ("SWEEP", "NONE")))
        print("axis %s: S %.3f uniform %s -> %s; M lo00 vs Y8 %d px -> %s; N Y16 vs Y8 %d px -> %s" % (
            ax, u, "rows" if along == "x" else "columns", "holds" if s_ok else "FAILS", m, res[ax][1], n, res[ax][2]))
    if not gates or not all(r[0] for r in res.values()):
        print("verdict: not scored -- a gate or a sensitivity check failed")
        return 1
    lows = [ax for ax, r in res.items() if r[1] == "LOW"]
    agree = all((r[1], r[2]) in (("LOW", "SWEEP"), ("HIGH", "NONE")) for r in res.values())
    split = len(lows) == 1 and agree
    print("verdict: %s" % ("SPLIT -- the %s offset reads the low byte (%s), the other the high byte"
                          % ({"h": "horizontal", "v": "vertical"}[lows[0]], "m00" if lows[0] == "h" else "m11")
                          if split else "X -- %s" % res))
    return 0 if split else 1


if __name__ == "__main__":
    sys.exit(main())
