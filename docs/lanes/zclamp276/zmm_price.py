#!/usr/bin/env python3
"""Price the NEARFAR trivial-reject rule offline against all 32 ZMinMaxControl
captures (#276).

The rule (derived from the goldens by zmm_quads.py): with
NV097_SET_ZMIN_MAX_CONTROL_CULL_NEAR_FAR_EN set, a primitive whose vertices all
have screen-space z below NV097_SET_CLIP_MIN, or all above
NV097_SET_CLIP_MAX, is rejected whole -- whatever ZCLAMP_EN says and whether
the surface is z- or w-buffered (the test is on z, never w).

Each quad in the test has z_left = i * 150 / 41 and z_right = z_left +
0.75 * 150 / 41 (DrawBlock, num_quads 40), clip [10, 100] in both buffer
modes (kZNear/kZFar == kWNear/kWFar). The "Z=N->F" blocks straddle the range
and are never rejected. This script paints the rejected quads of our capture
with the background and rescores it against the golden with the scorer's
own definition (any RGB channel different), so the printed figure is what a
correct implementation would score if it changes nothing else.

    zmm_price.py <captures dir>
"""
import os
import sys

import numpy as np
from PIL import Image

from zmm_quads import BLOCKS, COLS, ROWS, GOLD

BG = np.array([0x22, 0x22, 0x28, 0xFF])
Z_NEAR, Z_FAR = 10.0, 100.0
Z_INC = 150.0 / 41.0


def rejected(i):
    lo = i * Z_INC
    hi = lo + 0.75 * Z_INC
    return hi < Z_NEAR or lo > Z_FAR


def score(a, b):
    d = np.abs(a[..., :3].astype(int) - b[..., :3].astype(int)).max(axis=2)
    return int((d > 0).sum()), int(d.max()), int((d == 1).sum())


def extra_ink(a, b):
    """Pixels we inked where the golden shows background, beyond one step."""
    d = np.abs(a[..., :3].astype(int) - b[..., :3].astype(int)).max(axis=2)
    gbg = np.all(b[..., :3] == BG[:3], axis=2)
    return int(((d > 1) & gbg).sum())


def main():
    cap = sys.argv[1]
    names = sorted(f[len("ZMinMaxControl::"):-4] for f in os.listdir(cap)
                   if f.startswith("ZMinMaxControl::"))
    tot_before = tot_after = 0
    print(f"{'test':34s} {'before':>7s} {'max':>4s}   {'after':>7s} {'max':>4s} {'1-step':>7s} {'>1':>6s} {'ink':>6s}")
    for t in names:
        ours = np.asarray(Image.open(f"{cap}/ZMinMaxControl::{t}.png").convert("RGBA")).copy()
        gold = np.asarray(Image.open(GOLD + t + ".png").convert("RGBA"))
        b = score(ours, gold)
        if "_NEARFAR" in t:
            for (c, r), name in BLOCKS.items():
                if name.startswith("Z=NF"):
                    continue
                for k in range(40):
                    if rejected(k):
                        x = COLS[c] + 20 * (k % 5)
                        y = ROWS[r] + 20 * (k // 5)
                        # one-px ring: the fixed-function W=10 quads land
                        # 17 px wide, and the pitch leaves a 4 px gap
                        ours[y - 1:y + 17, x - 1:x + 17] = BG
        a = score(ours, gold)
        tot_before += b[0]
        tot_after += a[0]
        mark = "  <-" if b != a else ""
        print(f"{t:34s} {b[0]:7d} {b[1]:4d}   {a[0]:7d} {a[1]:4d} {a[2]:7d} "
              f"{a[0] - a[2]:6d} {extra_ink(ours, gold):6d}{mark}")
    print(f"{'TOTAL':34s} {tot_before:7d}        {tot_after:7d}")


if __name__ == "__main__":
    main()
