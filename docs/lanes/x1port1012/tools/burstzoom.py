#!/usr/bin/env python3
"""Zoom on one region for three video frames side by side (X state, Y state,
X state), plus signed difference Y - mean(X) with + in red and - in blue."""
import subprocess, sys
import numpy as np
from PIL import Image

clip, frames, region, out = sys.argv[1], [int(v) for v in sys.argv[2].split(",")], sys.argv[3], sys.argv[4]
X, Y, W, H = (int(v) for v in region.split(","))
FW, FH = 1280, 960
raw = subprocess.check_output(
    ["ffmpeg", "-v", "error", "-i", clip, "-fps_mode", "passthrough", "-frames:v", str(max(frames) + 1),
     "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
fr = np.frombuffer(raw, np.uint8).reshape(-1, FH, FW, 3)[:, Y:Y + H, X:X + W].astype(np.int16)
a, b, c = (fr[f] for f in frames)
sd = b.mean(axis=2) - (a.mean(axis=2) + c.mean(axis=2)) / 2
pos = np.clip(sd * 3, 0, 255)
neg = np.clip(-sd * 3, 0, 255)
diff = np.stack([pos, np.zeros_like(pos), neg], axis=2)
print(f"Y brighter than X: mean +{np.clip(sd, 0, None).mean():.2f}; darker: mean -{np.clip(-sd, 0, None).mean():.2f}")
print(f"luma X {a.mean():.1f} / Y {b.mean():.1f} / X {c.mean():.1f}")
grid = np.concatenate([np.concatenate([a, b], axis=1), np.concatenate([c, diff], axis=1)], axis=0).astype(np.uint8)
Image.fromarray(grid).resize((W * 2 * 2, H * 2 * 2), Image.NEAREST).save(out)
