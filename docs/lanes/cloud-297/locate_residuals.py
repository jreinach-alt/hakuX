#!/usr/bin/env python3
"""Locate the residual pixels in the 13 captures #297 says are tagged `blank`.

For each capture: the differing pixels (coordinates, golden colour, our
colour), the colour census of both images, and whether score_sweep.py's
`blank` rule fires. For the Depth_buffer_fixed_function colour rows, the
same pixels are also read out of the paired `_ZB` depth capture (z24 =
A<<16|R<<8|G), golden and ours, so the question "do these sit at maximum
depth?" is answered from data rather than assumed.

Usage: locate_residuals.py RUN_DIR [RUN_DIR ...]
       (RUN_DIR holds captures1/Suite::Test.png)
"""
import os
import sys
from collections import Counter

import numpy as np
from PIL import Image

GOLDENS = os.environ.get("GOLDENS", "/home/justin/goldens/results")
DBFF = [f"z24_C{c}_FZy_M{m}" for c in "ny"
        for m in ("000003", "3fc002", "7f8001", "bf4000", "feffff")]
CAPS = ([("Depth_buffer_fixed_function", t) for t in DBFF]
        + [("Texture_BRDF", t) for t in ("BRDF_e0_l0", "BRDF_e0_l1", "BRDF_e1_l0")])


def load(p):
    return np.asarray(Image.open(p).convert("RGBA"), dtype=np.int32)


def z24(img):
    return (img[..., 3] << 16) | (img[..., 0] << 8) | img[..., 1]


def census(img, n=6):
    flat = [tuple(map(int, x)) for x in img[..., :3].reshape(-1, 3)]
    c = Counter(flat)
    return len(c), c.most_common(n)


def blank_rule(g, o):
    flat = o[..., :3].reshape(-1, 3)
    _, counts = np.unique(flat, axis=0, return_counts=True)
    gold_colours = len(np.unique(g[..., :3].reshape(-1, 3), axis=0))
    return (counts.max() / flat.shape[0] > 0.90 and len(counts) <= 4
            and gold_colours > 4), counts.max() / flat.shape[0], len(counts), gold_colours


def bbox(ys, xs):
    return f"x {xs.min()}..{xs.max()}, y {ys.min()}..{ys.max()}"


def main():
    for run in sys.argv[1:]:
        print(f"=== {os.path.basename(run.rstrip('/'))}")
        cap_dir = os.path.join(run, "captures1")
        for suite, test in CAPS:
            gp = os.path.join(GOLDENS, suite, test + ".png")
            op = os.path.join(cap_dir, f"{suite}::{test}.png")
            if not os.path.exists(op):
                print(f"{suite}/{test}: no capture")
                continue
            g, o = load(gp), load(op)
            d = np.abs(g - o)
            mask = (d > 0).any(axis=2)
            ys, xs = np.nonzero(mask)
            fired, top, n_ours, n_gold = blank_rule(g, o)
            print(f"\n{suite}/{test}: {mask.sum()} px differ, max rgb {d[..., :3].max()}"
                  f" alpha {d[..., 3].max()}; blank={fired} (ours top {top:.4f}, "
                  f"{n_ours} colours; golden {n_gold} colours)")
            if not mask.sum():
                continue
            print(f"  bbox {bbox(ys, xs)}")
            print(f"  golden census {census(g)}")
            print(f"  ours   census {census(o)}")
            pairs = Counter((tuple(map(int, g[y, x])), tuple(map(int, o[y, x]))) for y, x in zip(ys, xs))
            for (gc, oc), n in pairs.most_common(8):
                print(f"    golden {gc} -> ours {oc}: {n} px")
            # Rows and columns the residual occupies.
            print(f"  rows {sorted(Counter(ys.tolist()).items())[:40]}")
            print(f"  cols {sorted(Counter(xs.tolist()).items())[:40]}")
            if suite == "Depth_buffer_fixed_function":
                gzp = os.path.join(GOLDENS, suite, test + "_ZB.png")
                ozp = os.path.join(cap_dir, f"{suite}::{test}_ZB.png")
                if os.path.exists(gzp) and os.path.exists(ozp):
                    gz, oz = z24(load(gzp)), z24(load(ozp))
                    gv = Counter(gz[ys, xs].tolist())
                    ov = Counter(oz[ys, xs].tolist())
                    print(f"  golden z24 at these px {sorted(gv.items())[:8]}")
                    print(f"  ours   z24 at these px {sorted(ov.items())[:8]}")
                    zd = gz != oz
                    print(f"  _ZB capture: {zd.sum()} px differ in z24, "
                          f"{(zd & mask).sum()} of them under the colour residual")
                    # Whole-buffer census: is anything but the clear value
                    # written anywhere, on either side?
                    print(f"  golden z24 census {Counter(gz.ravel().tolist()).most_common(4)}")
                    print(f"  ours   z24 census {Counter(oz.ravel().tolist()).most_common(4)}")
            print("  px " + " ".join(f"({x},{y})" for y, x in zip(ys[:30], xs[:30])))
        edge_scope(cap_dir)


# The 24 DBFF pixels: the first small grid quad's left column (x = 136,
# y 56..71) and the right quad's top row (x 502..509, y = 53) -- the two
# edges the test places at kZNear (depth_format_fixed_function_tests.cpp
# :97-98, 115, 190). Does every other cell of the suite agree there?
EDGE = [(136, y) for y in range(56, 72)] + [(x, 53) for x in range(502, 510)]


def edge_scope(cap_dir):
    suite = "Depth_buffer_fixed_function"
    gdir = os.path.join(GOLDENS, suite)
    if not os.path.exists(os.path.join(cap_dir, f"{suite}::{DBFF[0]}.png")):
        return
    print(f"\n  edge scope: the 24 near-plane edge px in every {suite} colour capture")
    for name in sorted(os.listdir(gdir)):
        if name.endswith("_ZB.png"):
            continue
        op = os.path.join(cap_dir, f"{suite}::{name}")
        if not os.path.exists(op):
            continue
        g, o = load(os.path.join(gdir, name)), load(op)
        bad = sum(1 for x, y in EDGE if (g[y, x] != o[y, x]).any())
        total = int((g != o).any(axis=2).sum())
        gblack = sum(1 for x, y in EDGE if not g[y, x, :3].any())
        print(f"    {name[:-4]:32s} edge differ {bad:2d}/24  golden-black-at-edge {gblack:2d}"
              f"  whole-capture differ {total}")
        # The stored depth at the edge, both sides, for the z24 cells (the
        # ARGB8888 packing; z16 is RGB565 and not decoded here).
        zb = name[:-4] + "_ZB.png"
        ozp = os.path.join(cap_dir, f"{suite}::{zb}")
        if name.startswith("z24") and os.path.exists(ozp):
            gz, oz = z24(load(os.path.join(gdir, zb))), z24(load(ozp))
            col = [(int(gz[y, x]), int(oz[y, x])) for x, y in EDGE[:16]]
            row = [(int(gz[y, x]), int(oz[y, x])) for x, y in EDGE[16:]]
            print(f"      z24 (golden, ours) x=136 col: {sorted(Counter(col).items())}")
            print(f"      z24 (golden, ours) y=53 row:  {sorted(Counter(row).items())}")
            # One column/row further in, for the gradient's step size.
            nxt = [(int(gz[y, 137]), int(oz[y, 137])) for y in range(56, 72)]
            print(f"      z24 (golden, ours) x=137 col: {sorted(Counter(nxt).items())}")


if __name__ == "__main__":
    main()
