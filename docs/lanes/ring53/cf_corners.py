#!/usr/bin/env python3
"""Dump per-corner values (UL, UR, LR, LL) of all 16 ControlFlags quads.

    cf_corners.py [--root DIR] [--suite Specular] [--test ControlFlags_VS]

Plane fit per triangle split on the UL-LR diagonal, as cf53_slots.py does,
for every channel. Writes nothing.
"""
import argparse

import numpy as np
from PIL import Image

QW, QH = 640 / 6.0, 80.0
LEFTS = [QW + i * (QW + 15) for i in range(4)]
TOPS = [QH + 15.0 + r * (QH + 15.0) for r in range(4)]


def corner_values(a, left, top, ch):
    x0, y0 = int(np.ceil(left)), int(np.ceil(top))
    q = a[y0:int(np.ceil(top + QH)), x0:int(np.ceil(left + QW)), ch].astype(float)
    h, w = q.shape
    yy, xx = np.mgrid[0:h, 0:w]
    X, Y = (xx + 0.5) / w, (yy + 0.5) / h
    fits, res = [], 0.0
    for m in (X > Y + 0.02, Y > X + 0.02):
        A = np.stack([np.ones(m.sum()), X[m], Y[m]], 1)
        c = np.linalg.lstsq(A, q[m], rcond=None)[0]
        res = max(res, float(np.abs(A @ c - q[m]).max()))
        fits.append(c)
    P = lambda c, x, y: c[0] + c[1] * x + c[2] * y
    up, lo = fits
    return [0.5 * (P(up, 0, 0) + P(lo, 0, 0)), P(up, 1, 0),
            0.5 * (P(up, 1, 1) + P(lo, 1, 1)), P(lo, 0, 1)], res


def load(root, suite, test):
    return np.asarray(Image.open("%s/%s/%s.png" % (root, suite, test)).convert("RGBA"))


def quads(root, suite, test):
    a = load(root, suite, test)
    out = {}
    for r in range(4):
        for c in range(4):
            out[r * 4 + c] = [corner_values(a, LEFTS[c], TOPS[r], ch) for ch in range(4)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/home/justin/goldens/results")
    ap.add_argument("--suite", default="Specular")
    ap.add_argument("--test", default="ControlFlags_VS")
    a = ap.parse_args()
    for d, chans in quads(a.root, a.suite, a.test).items():
        s = "  ".join("%s[%s] r%.0f" % ("RGBA"[i], " ".join("%6.1f" % v for v in vals), res)
                      for i, (vals, res) in enumerate(chans))
        print("d%02d %s" % (d, s))


if __name__ == "__main__":
    main()
