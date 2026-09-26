#!/usr/bin/env python3
"""Per-quad ink map of a ZMinMaxControl capture against its golden (#276).

Every block in the test is 5 x 8 quads of 16 px on a 20 px pitch
(z_min_max_control_tests.cpp: kSmallSize 16, kStep 20, quads_per_row 5,
quads_per_col 8 at 640x480). For each quad this prints the fraction of its
16x16 body that is not the background 0xFF222228, golden and ours, so a
primitive the silicon culls whole reads 0.00 against our 1.00 and a
per-pixel depth clip reads as a partial fraction.

    zmm_quads.py <captures dir> <test> [<test> ...]
"""
import sys

import numpy as np
from PIL import Image

GOLD = "/home/justin/goldens/results/ZMinMaxControl/"
BG = np.array([0x22, 0x22, 0x28])

# Block origins as they land in the captures (measured from the ink profile of
# Ctrl_ZCLAMP, where every quad is drawn): x 90 / 307 / 523, y 60 / 252. The
# source's arithmetic says y 70; the 10 px is the test host's own offset and is
# identical in golden and ours, so it is taken from the image, not derived.
COLS = [90, 307, 523]
ROWS = [60, 252]
BLOCKS = {
    (0, 0): "Z=Inc W=1", (0, 1): "Z=NF W=Inc",
    (1, 0): "Z=Inc W=Frac", (1, 1): "Z=NF W=NF",
    (2, 0): "Z=Inc W=Inc", (2, 1): "Z=Inc W=10",
}


def ink(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    return np.any(np.abs(a - BG) > 2, axis=2)


def quad_fracs(m):
    out = {}
    for (c, r), name in BLOCKS.items():
        fr = np.zeros((8, 5))
        for j in range(8):
            for i in range(5):
                x = COLS[c] + 20 * i
                y = ROWS[r] + 20 * j
                # inset one px so a neighbour's edge rounding cannot count
                fr[j, i] = m[y + 1:y + 15, x + 1:x + 15].mean()
        out[name] = fr
    return out


def main():
    cap = sys.argv[1]
    for t in sys.argv[2:]:
        g = quad_fracs(ink(Image.open(GOLD + t + ".png")))
        o = quad_fracs(ink(Image.open(f"{cap}/ZMinMaxControl::{t}.png")))
        print(f"== {t}")
        for name in BLOCKS.values():
            gi = g[name].flatten()
            oi = o[name].flatten()
            diff = [k for k in range(40) if abs(gi[k] - oi[k]) > 0.05]
            print(f"  {name:13s} gold_kept={int((gi > 0.5).sum()):2d} "
                  f"ours_kept={int((oi > 0.5).sum()):2d} "
                  f"partial_gold={int(((gi > 0.05) & (gi < 0.95)).sum())} "
                  f"differ_idx={diff}")
            if "-v" in sys.argv[0:1] or len(sys.argv) == 3:
                for j in range(8):
                    print("     ", " ".join(f"{gi[j*5+i]:.2f}" for i in range(5)),
                          "  |  ", " ".join(f"{oi[j*5+i]:.2f}" for i in range(5)))


if __name__ == "__main__":
    main()
