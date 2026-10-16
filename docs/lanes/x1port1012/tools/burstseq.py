#!/usr/bin/env python3
"""Per-frame structure of a burst. For video frames f0..f1 (passthrough),
crop the hull region and print, for each frame, MAD to the previous 1, 2, 3
frames. Two states alternating frame by frame show as d1 high, d2 low."""
import subprocess, sys
import numpy as np

clip, f0, f1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
X, Y, W, H = (int(v) for v in sys.argv[4].split(",")) if len(sys.argv) > 4 else (0, 150, 440, 300)
FW, FH = 1280, 960
raw = subprocess.check_output(
    ["ffmpeg", "-v", "error", "-i", clip, "-fps_mode", "passthrough", "-frames:v", str(f1 + 1),
     "-pix_fmt", "gray", "-f", "rawvideo", "-"])
fr = np.frombuffer(raw, np.uint8).reshape(-1, FH, FW)[:, Y:Y + H, X:X + W].astype(np.float32)
for f in range(f0, f1 + 1):
    d = [float(np.mean(np.abs(fr[f] - fr[f - j]))) for j in (1, 2, 3, 4)]
    print(f"{f}  d1 {d[0]:5.2f}  d2 {d[1]:5.2f}  d3 {d[2]:5.2f}  d4 {d[3]:5.2f}")
