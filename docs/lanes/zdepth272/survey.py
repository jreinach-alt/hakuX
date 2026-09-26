"""Signed depth-word residual (ours - golden) for every _ZB capture outside DBFF."""
import glob
import os
import sys
import numpy as np
from PIL import Image

RES = "/home/justin/hakux-work/dispatch/results"
GOLD = "/home/justin/goldens/results"
SUITES = ["Color_zeta_overlap", "Color_Zeta_Disable", "Depth_Clamp", "Depth_function", "Stencil",
          "Stencil_func", "W_buffering", "ZPass_pixel_count", "Clear"]


def newest(suite):
    fs = glob.glob(os.path.join(RES, "*", "captures1", suite + "::*ZB*.png"))
    runs = {}
    for f in fs:
        r = f.split("/")[-3]
        runs[r] = max(runs.get(r, 0), os.path.getmtime(f))
    return sorted(runs, key=runs.get)[-1] if runs else None


def w24(p):
    a = np.array(Image.open(p).convert("RGBA"), dtype=np.int64)
    return (a[:, :, 3] << 16) | (a[:, :, 0] << 8) | a[:, :, 1], a


only = sys.argv[1:] or SUITES
for suite in only:
    run = newest(suite)
    print("== %s  (run %s)" % (suite, run))
    for g in sorted(glob.glob(os.path.join(GOLD, suite, "*ZB*.png"))):
        name = os.path.basename(g)
        cap = os.path.join(RES, run, "captures1", "%s::%s" % (suite, name))
        if not os.path.exists(cap):
            continue
        gw, ga = w24(g)
        ow, oa = w24(cap)
        dif = gw != ow
        n = int(dif.sum())
        if n == 0:
            print("   %-44s exact" % name)
            continue
        d = (ow - gw)[dif]
        small = np.abs(d) <= 16
        u, c = np.unique(d[small], return_counts=True)
        top = sorted(zip(c.tolist(), u.tolist()), reverse=True)[:6]
        print("   %-44s diff %6d  |d|<=16: %6d  top(ours-gold) %s  gold-depth-median %d" % (
            name, n, small.sum(), [(v, k) for k, v in top], int(np.median(gw[dif]))))
