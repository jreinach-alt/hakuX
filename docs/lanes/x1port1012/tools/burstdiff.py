#!/usr/bin/env python3
"""Full-resolution look at one burst: frames A (before), B (in burst, odd
one), C (next, should match A's state). Writes a sheet: A | B | 4x|B-A| |
4x|C-A|, and prints where |B-A| is concentrated (row/column profile)."""
import subprocess, sys
import numpy as np
from PIL import Image

clip, fa, fb, fc, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
W, H = 1280, 960
need = max(fa, fb, fc) + 1
raw = subprocess.check_output(
    ["ffmpeg", "-v", "error", "-i", clip, "-fps_mode", "passthrough", "-frames:v", str(need),
     "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3).astype(np.int16)
A, B, C = fr[fa], fr[fb], fr[fc]
dba = np.abs(B - A).sum(axis=2)
dca = np.abs(C - A).sum(axis=2)
amp = lambda d: np.clip(d * 4 // 3, 0, 255).astype(np.uint8)
top = np.concatenate([A, B], axis=1).astype(np.uint8)
bot = np.concatenate([np.repeat(amp(dba)[:, :, None], 3, 2), np.repeat(amp(dca)[:, :, None], 3, 2)], axis=1)
Image.fromarray(np.concatenate([top, bot], axis=0)).resize((W, H)).save(out)
print(f"mean |B-A| {dba.mean():.1f}, mean |C-A| {dca.mean():.1f}")
mask = dba > 60
ys, xs = np.nonzero(mask)
print(f"|B-A|>60: {mask.mean()*100:.1f}% of pixels; bbox x {xs.min()}-{xs.max()}, y {ys.min()}-{ys.max()}")
for name, prof in (("rows", mask.mean(axis=1)), ("cols", mask.mean(axis=0))):
    bins = prof.reshape(-1, 80).mean(axis=1)
    print(name, " ".join(f"{b*100:4.0f}" for b in bins))
