#!/usr/bin/env python3
"""Synthetic captures for pairsel_score.py mutation tests.

    pairsel_synth.py <out root> <world>

world: width | register | and | or | never | k1_mismatch | missing. Each band
is Alpha func's (alpha ramp over a 0xFF222322 clear, SRC_ALPHA blend), with the
fragment colour either evaluated per pixel or held across an even-aligned pair
at the pair's right edge (s = 2*floor(x/2) + 2), per the world's selector.
"""
import math
import os
import sys

import numpy as np
from PIL import Image

BG = (34, 35, 34)
BANDS = [((255, 0, 0), 0.0, 1.0, 149, 213), ((0, 0, 255), 1.0, 0.0, 213, 277),
         ((0, 255, 0), 0.495, 0.505, 277, 341)]


def paired(world, w, v4f):
    return {"width": w >= 512, "register": v4f, "and": w >= 512 and v4f, "or": w >= 512 or v4f,
            "never": False, "k1_mismatch": w >= 512, "missing": w >= 512}[world]


def image(w, pair):
    a = np.zeros((480, 640, 4), np.uint8)
    a[...] = BG + (255,)
    left = (640 - w) // 2
    for src, la, ra, y0, y1 in BANDS:
        for x in range(left, left + w):
            s = (2 * math.floor(x / 2) + 2) if pair else (x + 0.5)
            t = min(max((s - left) / w, 0.0), 1.0)
            al = round(255 * (la + (ra - la) * t))
            col = tuple(int(round(c * al / 255 + b * (1 - al / 255))) for c, b in zip(src, BG))
            a[y0:y1, x] = col + (int(round(al * al / 255 + 255 * (1 - al / 255))),)
    a[341:373, :] = (144, 145, 144, 191)
    return a


def main():
    root, world = sys.argv[1], sys.argv[2]
    for sub in ("Pair_selector", "Alpha_func"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    for w in (512, 384, 256, 128):
        for v4f in (True, False):
            name = "PairSel_W%d_%s" % (w, "V4F" if v4f else "V3F")
            Image.fromarray(image(w, paired(world, w, v4f)), "RGBA").save(os.path.join(root, "Pair_selector", name + ".png"))
    ref = image(512, paired(world, 512, True))
    if world == "k1_mismatch":
        ref[250, 300] = (1, 2, 3, 255)
    Image.fromarray(ref, "RGBA").save(os.path.join(root, "Alpha_func", "AlphaFuncAlways_Disabled.png"))
    if world == "missing":
        os.remove(os.path.join(root, "Pair_selector", "PairSel_W256_V3F.png"))


if __name__ == "__main__":
    main()
