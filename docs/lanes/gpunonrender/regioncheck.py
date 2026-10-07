#!/usr/bin/env python3
"""Region check for an A/B frame pair (lane.gpunonrender, scope (D)).

    regioncheck.py <request-id-A> <request-id-B> [step ...]

For each route step named (the part of the frame name after the time, for
example s10-main_menu; default: every s-step both runs have), loads the
route frame of both runs and prints the differing-pixel count, its share,
and the bounding box, with the FPS overlay (top-left 130x50) masked. Then
the same over a 4x4 grid of regions, so a difference confined to moving
content can be told from one in a static panel. A pixel differs when any
channel differs by more than --tol (default 8).
"""
import os, re, sys

import numpy as np
from PIL import Image

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
args = [a for a in sys.argv[1:]]
tol = 8
if "--tol" in args:
    i = args.index("--tol")
    tol = int(args[i + 1])
    del args[i:i + 2]
ra, rb = args[0], args[1]
want = args[2:]


def frames(rid):
    d = os.path.join(D, rid, "route-frames")
    out = {}
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        m = re.match(r"\d{6}-(s\d\d-[\w-]+)\.png$", f)
        if m:
            out[m.group(1)] = os.path.join(d, f)
    return out


fa, fb = frames(ra), frames(rb)
steps = want or sorted(set(fa) & set(fb))
for s in steps:
    if s not in fa or s not in fb:
        print("%-24s missing in %s" % (s, ra if s not in fa else rb))
        continue
    a = np.asarray(Image.open(fa[s]).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(fb[s]).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        print("%-24s shapes differ %s %s" % (s, a.shape, b.shape))
        continue
    diff = (np.abs(a - b).max(axis=2) > tol)
    diff[:50, :130] = False
    n = int(diff.sum())
    h, w = diff.shape
    if n:
        ys, xs = np.nonzero(diff)
        bbox = "x %d-%d y %d-%d" % (xs.min(), xs.max(), ys.min(), ys.max())
    else:
        bbox = "-"
    print("%-24s differ %7d px (%5.1f%%)  bbox %s" % (s, n, 100.0 * n / (h * w), bbox))
    grid = []
    for gy in range(4):
        row = []
        for gx in range(4):
            c = diff[gy * h // 4:(gy + 1) * h // 4, gx * w // 4:(gx + 1) * w // 4]
            row.append("%5.1f" % (100.0 * c.mean()))
        grid.append(" ".join(row))
    print("    region % differing (4x4, rows top to bottom):")
    for g in grid:
        print("      " + g)
