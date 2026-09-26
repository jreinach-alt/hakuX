#!/usr/bin/env python3
"""Golden-vs-capture pixel survey of the three #13 line-mode families."""
import glob
import os
import sys

import numpy as np
from PIL import Image

G = os.path.expanduser("~/goldens/results")
FAMS = {"Front_face": "FrontFace_LM_*", "Shade_model": "ProgLM_*",
        "3D_primitive": "Line*"}


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def main(cap):
    for s, p in FAMS.items():
        for g in sorted(glob.glob(os.path.join(G, s, p + ".png"))):
            t = os.path.basename(g)[:-4]
            c = os.path.join(cap, "%s::%s.png" % (s, t))
            if not os.path.exists(c):
                print(s, t, "MISSING")
                continue
            a, b = load(g), load(c)
            if a.shape != b.shape:
                print(s, t, "shape", a.shape, b.shape)
                continue
            d = np.abs(a - b).max(2)
            print("%-13s %-36s %6d %6d" % (s, t, (d > 0).sum(), (d > 8).sum()))


if __name__ == "__main__":
    main(sys.argv[1])
