"""FZy captures: where do ours and the golden differ, and is it the near-plane edge?"""
import os
import sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from price import word, GOLD, RES  # noqa: E402

run = sys.argv[1] if len(sys.argv) > 1 else "0-a-now-8e683b3a26-023-Depth_buffer_fixed_function"
edge = np.zeros((480, 640), bool)
edge[53, 502:510] = True
edge[56:72, 136] = True
for name in sorted(f[:-4] for f in os.listdir(GOLD) if "_FZy_" in f):
    z16 = name.startswith("z16")
    cap = os.path.join(RES, run, "captures1", "Depth_buffer_fixed_function::%s.png" % name)
    if not os.path.exists(cap):
        print(name, "no capture")
        continue
    if name.endswith("_ZB"):
        g, o = word(os.path.join(GOLD, name + ".png"), z16), word(cap, z16)
        dif = g != o
        extra = ""
        if dif.any():
            e = edge & dif
            extra = "edge gold %s ours %s" % (np.unique(g[edge]).tolist()[:4], np.unique(o[edge]).tolist()[:4])
    else:
        g = np.array(Image.open(os.path.join(GOLD, name + ".png")).convert("RGB"), dtype=np.int64)
        o = np.array(Image.open(cap).convert("RGB"), dtype=np.int64)
        dif = (g != o).any(axis=2)
        extra = ""
    print("%-24s diff %6d  on-edge %3d  off-edge %6d %s" % (name, dif.sum(), (dif & edge).sum(), (dif & ~edge).sum(), extra))
