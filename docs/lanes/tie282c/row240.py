#!/usr/bin/env python3
"""Texture_render_target row 240: silicon's v-tie direction per column, against
cloud-282b's binade rule and its rivals (#282). See NOTES.md for the geometry.

Usage: row240.py DIR [DIR ...]   (each DIR holds TexFmt_*.png, e.g. a golden suite dir)
"""
import glob
import math
import os
import sys

import numpy as np
from PIL import Image

ROW, X0, X1 = 240, 178, 462          # tie row, first and last quad column
R, WQ = 463.3125, 285.625            # snapped right edge and width (NOTES)
COLS = np.arange(X0, X1 + 1)
XC = COLS + 0.5
L0 = (R - XC) / WQ                   # UL weight in T1 on this row; l2 = 1/2
T1 = XC > 320.5

RULES = {
    "binade rule (cloud-282b)": T1 & (L0 <= 0.25),
    "always up (today)": np.zeros_like(T1),
    "#314 diag: T1 down": T1.copy(),
    "screen x >= 481 (checkerboard split)": COLS >= 481,
    "edge-function binade l0 <= 2^14/2A": T1 & (L0 <= 2.0 ** 14 / (WQ * WQ)),
}


def directions(path):
    g = np.asarray(Image.open(path).convert("RGBA")).astype(int)[:, X0:X1 + 1]
    a, b, c = g[ROW - 1], g[ROW], g[ROW + 1]
    eq_a, eq_c = (b == a).all(1), (b == c).all(1)
    d = np.full(len(COLS), -1)       # -1 unobservable, 0 up, 1 down
    d[eq_a & ~eq_c] = 1
    d[eq_c & ~eq_a] = 0
    return d


def binade(l):
    return "%d" % math.floor(math.log2(l))


def main():
    files = sorted(f for d in sys.argv[1:] for f in glob.glob(os.path.join(d, "TexFmt_*.png")))
    D = np.array([directions(f) for f in files])
    obs = D >= 0
    print("captures: %d, observable px: %d of %d" % (len(files), obs.sum(), D.size))

    # per-capture transition: first down column in T1, and whether it is one clean step
    for f, d in zip(files, D):
        o = d >= 0
        down = COLS[(d == 1)]
        up_t1 = COLS[(d == 0) & T1]
        print("  %-28s obs %3d  down %3d [%s]  up-in-T1 max %s" % (
            os.path.basename(f)[:-4], o.sum(), len(down),
            "%d-%d" % (down.min(), down.max()) if len(down) else "-",
            up_t1.max() if len(up_t1) else "-"))

    print("\ntable by triangle and weight binade (l2 = 1/2 on the whole row):")
    print("tri  b(l0) b(l1) columns      down/observable")
    keys = {}
    for i, x in enumerate(COLS):
        if not T1[i]:
            k = ("T2/edge", "-", "-")
        else:
            l0 = L0[i]
            k = ("T1", binade(l0), binade(0.5 - l0))
        keys.setdefault(k, []).append(i)
    for k, idx in keys.items():
        sub = D[:, idx]
        print("%-7s %5s %5s %3d-%3d  %6d/%-6d" % (k + (COLS[idx[0]], COLS[idx[-1]], (sub == 1).sum(), (sub >= 0).sum())))

    print("\nscore over observable pixels:")
    for name, pred in RULES.items():
        P = np.broadcast_to(pred.astype(int), D.shape)
        hit = ((P == D) & obs).sum()
        print("  %-40s %6d/%-6d %7.2f%%" % (name, hit, obs.sum(), 100.0 * hit / obs.sum()))


if __name__ == "__main__":
    main()
