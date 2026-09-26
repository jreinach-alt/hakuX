#!/usr/bin/env python3
"""#279: where the z/w model misses silicon, and by how much.

Usage: dotzw_residual.py GOLDEN BUMPMAP
"""
import sys

import numpy as np
from PIL import Image

import dotzw_fit as f


def main():
    gold = f.decode_depth(sys.argv[1])
    bump = np.asarray(Image.open(sys.argv[2]).convert("RGB"), dtype=np.float64)
    ys, xs = np.mgrid[0:f.N, 0:f.N]
    upper = xs >= ys
    print("rejected reading: attributes at GL pixel centres (+0.5), rint")
    for dm in ("zero_to_one",):
        p = f.predict(bump, "point", dm, "tri", 1.0, "rint")
        d = p - gold
        rel = d / np.maximum(gold, 1)
        print(f"d mean {d.mean():.2f} median {np.median(d):.1f}; rel median "
              f"{np.median(rel):.5f} p10 {np.percentile(rel, 10):.5f} "
              f"p90 {np.percentile(rel, 90):.5f}")
        for nm, m in (("upper tri", upper), ("lower tri", ~upper)):
            print(f"  {nm}: d median {np.median(d[m]):.1f} rel median "
                  f"{np.median(rel[m]):.5f}")
        for y, x in ((0, 0), (0, 255), (255, 255), (255, 0), (128, 128), (64, 192)):
            print(f"  px(y={y},x={x}): golden {gold[y, x]} model {p[y, x]:.0f}")

    # The fitted rule: pixel-corner evaluation (NV2A's integer pixel
    # centres), floor.  Where does it miss, relative to the integer grid?
    raw = f.predict(bump, "point", "zero_to_one", "tri", 1.0, "none", 0.0)
    fl = np.floor(raw)
    d = fl - gold
    frac = raw - fl
    miss = d != 0
    print(f"\nrule floor(z/w) at pixel corners: {np.sum(~miss)} exact, "
          f"{np.sum(d == 1)} one high, {np.sum(d == -1)} one low, "
          f"{np.sum(np.abs(d) > 1)} further")
    if miss.any():
        dist = np.minimum(frac, 1 - frac)
        print(f"  distance of z/w to the nearest integer: misses median "
              f"{np.median(dist[miss]):.2e} max {dist[miss].max():.2e}; "
              f"hits median {np.median(dist[~miss]):.2e}")
        print(f"  misses in upper tri {np.sum(miss & upper)}, lower tri "
              f"{np.sum(miss & ~upper)}; on the diagonal {np.sum(miss & (xs == ys))}")
        rel = np.abs(raw - np.rint(raw)) / np.maximum(raw, 1)
        print(f"  relative gap to the integer at misses: max {rel[miss].max():.2e} "
              f"(float32 half-ULP is 2^-24 = {2**-24:.2e})")


if __name__ == "__main__":
    main()
