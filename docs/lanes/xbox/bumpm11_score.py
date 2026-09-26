#!/usr/bin/env python3
"""Score the #10 m11 run (bumpm11-run.md) on one captures root.

    bumpm11_score.py <captures root> [--goldens /home/justin/goldens/results] [--hakux]

<captures root> is a console run's `console/` directory (Bump_map/Test.png)
or a dispatcher result's `captures1/` (Bump_map::Test.png). Pixel counts
exclude the printed label rows (20..44) and compare RGB. Writes nothing.

Silicon (default):
  C1  BumpMap_{Y16,Y16_L,Y8,Y8_L} bit-identical to their goldens
  M   Y16_m11x10 vs Y8_m11x10 and Y16_L_m11x10 vs Y8_L_m11x10:
      COLLAPSE if both <= 2,000 px, SURVIVES if both >= 10,000 px, else X
--hakux: the same pair counts, reported with hakuX's own prediction (both
<= 2,000: it renders Y16 as Y8), and BumpMap_Y16's px against its golden.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

CONTROLS = ["BumpMap_Y16", "BumpMap_Y16_L", "BumpMap_Y8", "BumpMap_Y8_L"]
PAIRS = [("BumpMap_Y16_m11x10", "BumpMap_Y8_m11x10"), ("BumpMap_Y16_L_m11x10", "BumpMap_Y8_L_m11x10")]
BASE_PAIRS = [("BumpMap_Y16", "BumpMap_Y8"), ("BumpMap_Y16_L", "BumpMap_Y8_L")]
LABEL = (20, 45)
COLLAPSE, SURVIVES = 2000, 10000


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--hakux", action="store_true")
    a = ap.parse_args()
    gold = lambda n: os.path.join(a.goldens, "Bump_map", n + ".png")
    missing = [n for n in CONTROLS + [x for p in PAIRS for x in p] if not find(a.root, n)]
    if missing:
        print("MISSING captures: %s" % ", ".join(missing))
        return 2
    for x, y in BASE_PAIRS:
        print("m11 0.5:  %-20s vs %-19s %6d px" % (x, y, px(rgb(find(a.root, x)), rgb(find(a.root, y)))))
    counts = []
    for x, y in PAIRS:
        n = px(rgb(find(a.root, x)), rgb(find(a.root, y)))
        counts.append(n)
        print("m11 5.0:  %-20s vs %-19s %6d px" % (x, y, n))
    if all(n <= COLLAPSE for n in counts):
        m = "COLLAPSE"
    elif all(n >= SURVIVES for n in counts):
        m = "SURVIVES"
    else:
        m = "X"
    if a.hakux:
        n = px(rgb(find(a.root, "BumpMap_Y16")), rgb(gold("BumpMap_Y16")))
        print("hakuX BumpMap_Y16 vs its golden: %d px (22,374 at 84a67b9cf8 against the console)" % n)
        print("hakuX pairs at m11 5.0: %s (predicted COLLAPSE: hakuX renders Y16 as Y8)" % m)
        return 0 if m == "COLLAPSE" else 1
    c1 = True
    for n in CONTROLS:
        same = np.array_equal(rgb(find(a.root, n)), rgb(gold(n)))
        c1 = c1 and same
        print("C1 %-14s == golden: %s" % (n, same))
    print("C1 controls equal their goldens: %s" % ("holds" if c1 else "FAILS -- the run is void"))
    if c1:
        print("M  silicon Y16 vs Y8 at m11 5.0: %s" % m)
    else:
        print("M  not scored: C1 failed, so the run is void")
    return 0 if c1 else 1


if __name__ == "__main__":
    sys.exit(main())
