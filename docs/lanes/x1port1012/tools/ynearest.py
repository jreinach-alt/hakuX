#!/usr/bin/env python3
"""Is a burst's odd image (Y) the normal image (X) of some other moment?
For each Y frame, search every non-Y frame of the clip for the closest one
(gray MAD over a region) and print it with its offset in guest frames.
A ring spinning about its own axis keeps its silhouette, so a silhouette
that holds still does not rule out a different spin angle; this does."""
import subprocess, sys
import numpy as np

clip = sys.argv[1]
ys = [int(v) for v in sys.argv[2].split(",")]
X, Y, W, H = (int(v) for v in sys.argv[3].split(","))
FW, FH = 1280, 960
raw = subprocess.check_output(
    ["ffmpeg", "-v", "error", "-i", clip, "-fps_mode", "passthrough",
     "-pix_fmt", "gray", "-f", "rawvideo", "-"])
fr = np.frombuffer(raw, np.uint8).reshape(-1, FH, FW)[:, Y:Y + H:2, X:X + W:2].astype(np.float32)
n = len(fr)
# Y frames and their duplicate (next video frame) are excluded as candidates
bad = set()
for y in ys:
    bad.update((y, y + 1))
cand = [f for f in range(0, n, 1) if f not in bad]
C = fr[cand]
for y in ys:
    d = np.abs(C - fr[y]).mean(axis=(1, 2))
    order = np.argsort(d)[:3]
    best = ", ".join(f"frame {cand[i]} ({(cand[i] - y) / 2:+.1f} guest) mad {d[i]:.2f}" for i in order)
    print(f"Y {y}: {best}")
