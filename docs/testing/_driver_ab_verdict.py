#!/usr/bin/env python3
"""Sort a suite's tests into the three buckets ROADMAP.md section 3 asks for."""
import os
import sys

import numpy as np
from PIL import Image

custom, system, gold, suite = sys.argv[1:5]


def load(p):
    return np.asarray(Image.open(p).convert("RGBA"), dtype=np.int16)


agree_ok = agree_wrong = driver_diff = skipped = 0
examples = []
for f in sorted(os.listdir(custom)):
    if not f.startswith(suite + "::") or not f.endswith(".png"):
        continue
    t = f[len(suite) + 2:-4]
    p_sys = os.path.join(system, f)
    p_gold = os.path.join(gold, suite, t + ".png")
    if not (os.path.exists(p_sys) and os.path.exists(p_gold)):
        skipped += 1
        continue
    c, s, g = load(os.path.join(custom, f)), load(p_sys), load(p_gold)
    if c.shape != s.shape or c.shape != g.shape:
        skipped += 1
        continue
    if np.any(c - s):
        driver_diff += 1
        if len(examples) < 8:
            examples.append((t, int(np.abs(c - s).max()),
                             int((np.abs(c - s).max(axis=2) > 0).sum())))
    elif np.any(c - g):
        agree_wrong += 1
    else:
        agree_ok += 1

n = agree_ok + agree_wrong + driver_diff
print(f"  {n} tests compared" + (f", {skipped} skipped" if skipped else ""))
print(f"    both drivers agree, matches hardware : {agree_ok}")
print(f"    both drivers agree, differs          : {agree_wrong}"
      f"    <- our translation")
print(f"    drivers disagree                     : {driver_diff}"
      f"    <- driver-dependent")
for t, mx, px in examples:
    print(f"        {t:38s} {px:7,} px, max delta {mx}")
