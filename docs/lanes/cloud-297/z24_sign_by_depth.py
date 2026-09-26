#!/usr/bin/env python3
"""ours - golden in z24 fixed-point DBFF depth captures, binned by golden depth.

#272 says ours is 2-5 units HIGH near maximum depth. The #297 edge pixels
say ours is 8 units LOW at the near plane. If both are one affine error in
the 24-bit fixed-function z mapping, the signed error should run from
negative at small z to positive at large z across a single capture.

Usage: z24_sign_by_depth.py RUN_DIR
"""
import os
import sys

import numpy as np
from PIL import Image

GOLDENS = os.environ.get("GOLDENS", "/home/justin/goldens/results")
SUITE = "Depth_buffer_fixed_function"
CAPS = [f"z24_C{c}_FZn_M{m}_ZB" for c in "ny" for m in ("400002", "800001", "c00000", "ffffff")]
EDGES = [0, 1 << 16, 1 << 20, 1 << 22, 1 << 23, 3 << 22, 15 << 20, 1 << 24]


def z24(p):
    a = np.asarray(Image.open(p).convert("RGBA"), dtype=np.int64)
    return (a[..., 3] << 16) | (a[..., 0] << 8) | a[..., 1]


def main():
    cap_dir = os.path.join(sys.argv[1], "captures1")
    for name in CAPS:
        op = os.path.join(cap_dir, f"{SUITE}::{name}.png")
        if not os.path.exists(op):
            continue
        g = z24(os.path.join(GOLDENS, SUITE, name + ".png"))
        o = z24(op)
        m = int(name.split("_M")[1][:6], 16)
        # Only pixels BOTH sides wrote (neither holds the clear value), so a
        # coverage difference cannot pose as a depth error.
        both = (g != m) & (o != m)
        print(f"{name}: {int(both.sum())} px written on both sides")
        for lo, hi in zip(EDGES, EDGES[1:]):
            sel = both & (g >= lo) & (g < hi)
            if not sel.any():
                continue
            d = (o - g)[sel]
            print(f"  golden z in [{lo:>8}, {hi:>8}): n {int(sel.sum()):>6}  "
                  f"ours-golden min {int(d.min()):>3} median {float(np.median(d)):>5.1f} "
                  f"max {int(d.max()):>3}  low {int((d < 0).sum()):>6} high {int((d > 0).sum()):>6}")


if __name__ == "__main__":
    main()
