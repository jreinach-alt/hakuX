#!/usr/bin/env python3
"""Classify every guest image of a clip as normal (X) or odd (Y).
An image is Y when it is far from both neighbours while the neighbours are
close to each other: a = d(i-1,i), b = d(i,i+1), c = d(i-1,i+1);
Y if min(a, b) > RATIO * c and min(a, b) - c > 1 (RATIO defaults to 1.8;
in a strict X Y X Y run the X images are flagged too). Distances are gray MAD on the
frame scaled to 320x240. For each Y image, also prints where the change
sits: the share of |Y - mean(X neighbours)| > 20 in each quarter column and
over the dark (luma < 25) versus lit pixels of the X neighbours.
Usage: yclass.py <clip> <offset_s> [RATIO]"""
import subprocess, sys
import numpy as np

clip, off = sys.argv[1], float(sys.argv[2])
RATIO = float(sys.argv[3]) if len(sys.argv) > 3 else 1.8
W, H = 320, 240
pts = [float(v) for v in subprocess.check_output(
    ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts_time",
     "-of", "csv=p=0", clip]).split()]
raw = subprocess.check_output(
    ["ffmpeg", "-v", "error", "-i", clip, "-fps_mode", "passthrough", "-vf", f"scale={W}:{H}",
     "-pix_fmt", "gray", "-f", "rawvideo", "-"])
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
n = min(len(fr), len(pts))
# distinct guest images: drop video frames that repeat the previous one
keep = [0]
for i in range(1, n):
    if np.abs(fr[i].astype(np.int16) - fr[keep[-1]]).mean() > 0.6:
        keep.append(i)
g = [fr[i].astype(np.float32) for i in keep]
d = lambda p, q: float(np.abs(p - q).mean())
ycount = 0
for k in range(1, len(g) - 1):
    a, b, c = d(g[k - 1], g[k]), d(g[k], g[k + 1]), d(g[k - 1], g[k + 1])
    if min(a, b) > RATIO * c and min(a, b) - c > 1.0:
        ycount += 1
        ref = (g[k - 1] + g[k + 1]) / 2
        big = np.abs(g[k] - ref) > 20
        quart = [big[:, j * 80:(j + 1) * 80].mean() * 100 for j in range(4)]
        dark = ref < 25
        sd = (g[k] - ref)
        print(f"+{off + pts[keep[k]]:6.2f} s  img {k:4d}  a {a:5.2f} b {b:5.2f} c {c:5.2f}  "
              f"changed% by quarter {' '.join(f'{q:4.1f}' for q in quart)}  "
              f"dark px changed {big[dark].mean()*100:4.1f}% lit {big[~dark].mean()*100:4.1f}%  "
              f"Y-X luma {sd.mean():+5.2f}")
print(f"{ycount} Y images of {len(g)} guest images, +{off + pts[keep[0]]:.1f}..+{off + pts[keep[-1]]:.1f} s")
