#!/usr/bin/env python3
"""Does the ring come back to the angles it had during the bursts?
For each probe time in segment 1 (soak s), find the closest frame (mean abs
diff, top crop, gray) among frames of the later menu (soak +80..+111 s, from
segments 1 and 2), and report it beside the probe's distance to its own
neighbours 1 s away (the scale of "a different angle")."""
import json, subprocess, sys
import numpy as np

R = "/home/justin/hakux-work/dispatch/results/1792166308-x1port1012-1386872/video/"
X, Y, W, H = 120, 40, 880, 190
SEG = {1: 37.0, 2: 97.0}

def frames(seg, t0, t1, step):
    off = SEG[seg]
    raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-ss", f"{t0 - off:.3f}", "-to", f"{t1 - off:.3f}",
         "-i", R + f"v0000{seg}.mp4", "-vf", f"fps={1/step},crop={W}:{H}:{X}:{Y}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"])
    n = len(raw) // (W * H)
    a = np.frombuffer(raw[: n * W * H], np.uint8).reshape(n, H, W).astype(np.float32)
    return [(t0 + i * step, a[i]) for i in range(n)]

late = frames(1, 80, 96.9, 0.1) + frames(2, 97.1, 111, 0.1)
early = frames(1, 37.5, 79.5, 0.5)
for t, f in early:
    d = [(float(np.mean(np.abs(f - g))), tl) for tl, g in late]
    best, tb = min(d)
    near = [float(np.mean(np.abs(f - g))) for tg, g in early if abs(tg - t - 1.0) < 0.01]
    print(f"+{t:5.1f}  best late match +{tb:5.1f}  mad {best:5.2f}  (same run 1 s later: {near[0] if near else float('nan'):5.2f})")
