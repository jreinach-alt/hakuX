#!/usr/bin/env python3
"""Per-capture pixel price of desktop runs against the goldens, the way the
dispatcher scores (score_sweep.py: any channel differing), plus the count off
by more than one step (the floor a correct ring leaves).

    pxprice.py <run tag> [<run tag> ...]    tags under build-linux/ring53runs/

Every Specular / Specular_back capture in each run's out/ is priced; the
columns are one per tag. Writes nothing.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "..", "..", "..", "build-linux", "ring53runs")
GOLD = "/home/justin/goldens/results"


def price(png, gold):
    a = np.asarray(Image.open(png).convert("RGBA")).astype(int)
    g = np.asarray(Image.open(gold).convert("RGBA")).astype(int)
    if a.shape != g.shape:
        return None
    d = np.abs(a - g).max(axis=2)
    return int((d > 0).sum()), int((d > 1).sum())


def main():
    tags = sys.argv[1:]
    rows = {}
    for t in tags:
        out = os.path.join(RUNS, t, "out")
        for f in sorted(os.listdir(out)) if os.path.isdir(out) else []:
            if "::" not in f or not f.endswith(".png"):
                continue
            suite, test = f[:-4].split("::", 1)
            gold = os.path.join(GOLD, suite, test + ".png")
            if os.path.exists(gold):
                rows.setdefault("%s/%s" % (suite, test), {})[t] = price(os.path.join(out, f), gold)
    print("%-48s %s" % ("capture", "".join("%22s" % t for t in tags)))
    for k in sorted(rows):
        cells = []
        for t in tags:
            v = rows[k].get(t)
            cells.append("%22s" % ("-" if v is None else "%d (>1: %d)" % v))
        print("%-48s %s" % (k, "".join(cells)))


if __name__ == "__main__":
    sys.exit(main())
