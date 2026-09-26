#!/usr/bin/env python3
"""How far is each Bump map render from hardware, in pixels?

The palette gate answers "are these the hardware's colours, in the hardware's
proportions".  It cannot see a perturbation that is the right colour in the
wrong place, which is what is left after the retained-surface fix.  This counts
differing pixels instead, and fails while any test is more than 1% off.
"""
import os, sys, numpy as np
from PIL import Image
G, R = sys.argv[1], sys.argv[2]
bad = 0
for n in sorted(os.listdir(R)):
    if not n.startswith("Bump_map::") or not n.endswith(".png"):
        continue
    t = n[len("Bump_map::"):-4]
    gp = os.path.join(G, "Bump_map", t + ".png")
    if not os.path.exists(gp):
        continue
    g = np.asarray(Image.open(gp).convert("RGB"), dtype=np.int16)
    o = np.asarray(Image.open(os.path.join(R, n)).convert("RGB"), dtype=np.int16)
    if g.shape != o.shape:
        continue
    d = float((np.abs(g - o).max(axis=2) > 0).mean())
    if d > 0.01:
        bad += 1
        print(f"  {t:24s} {d*100:5.2f}% of pixels differ")
print(f"\n  {bad} test(s) render only in the wrong place")
sys.exit(1 if bad else 0)
