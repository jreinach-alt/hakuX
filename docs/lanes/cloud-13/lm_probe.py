#!/usr/bin/env python3
"""Print golden vs ours ink along one column or row: lm_probe.py CAP SUITE TEST col|row IDX LO HI"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lm_cuts as lc

cap, suite, test, axis, idx, lo, hi = sys.argv[1:8]
idx, lo, hi = int(idx), int(lo), int(hi)
g = lc.load(os.path.join(lc.G, suite, test + ".png"))
o = lc.load(os.path.join(cap, "%s::%s.png" % (suite, test)))
gi, oi = lc.ink(g), lc.ink(o)
for k in range(lo, hi):
    y, x = (k, idx) if axis == "col" else (idx, k)
    print(k, int(gi[y, x]), int(oi[y, x]), tuple(g[y, x]), tuple(o[y, x]))
