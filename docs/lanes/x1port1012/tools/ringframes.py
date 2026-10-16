#!/usr/bin/env python3
"""Frame-by-frame read of a screenrecord clip for #939 (ring rotation jumps).

For every recorded frame: pts, change from the previous frame, and per-band
change (8 horizontal bands). Recorded frames are collapsed into distinct
images (the menu draws at 30 Hz on a 60 Hz display, so each image should
appear twice). For each distinct image k it reports:
  step   = mean |k - (k-1)|          (how far the picture moved)
  back2  = mean |k - (k-2)|          (should exceed step for forward motion)
  stale  = back2 < step              (k looks more like k-2 than k-1: a jump back)
  shift  = phase-correlation (dx, dy) from k-1 to k
  split  = some bands changed and others did not (mid-frame candidate)
  hold   = how many recorded frames showed this image (2 expected)
Usage: ringframes.py <clip.mp4> [crop x,y,w,h in source pixels]
"""
import json, subprocess, sys
import numpy as np

clip = sys.argv[1]
crop = [int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else None

probe = json.loads(subprocess.check_output(
    ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
     "stream=width,height:frame=pts_time", "-of", "json", clip]))
W, H = probe["streams"][0]["width"], probe["streams"][0]["height"]
pts = [float(f["pts_time"]) for f in probe["frames"]]

vf = []
if crop:
    x, y, w, h = crop
    vf.append(f"crop={w}:{h}:{x}:{y}")
    W, H = w, h
SW, SH = W // 2, H // 2
vf.append(f"scale={SW}:{SH}")
raw = subprocess.check_output(
    ["ffmpeg", "-v", "error", "-i", clip, "-fps_mode", "passthrough",
     "-vf", ",".join(vf), "-pix_fmt", "gray", "-f", "rawvideo", "-"])
n = len(raw) // (SW * SH)
frames = np.frombuffer(raw[: n * SW * SH], np.uint8).reshape(n, SH, SW).astype(np.float32)
pts = pts[:n]

def mad(a, b):
    return float(np.mean(np.abs(a - b)))

def bands(a, b, k=8):
    hh = a.shape[0] // k
    return [float(np.mean(np.abs(a[i*hh:(i+1)*hh] - b[i*hh:(i+1)*hh]))) for i in range(k)]

def shift(a, b):
    fa, fb = np.fft.fft2(a - a.mean()), np.fft.fft2(b - b.mean())
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-9
    c = np.abs(np.fft.ifft2(r))
    dy, dx = np.unravel_index(np.argmax(c), c.shape)
    if dy > c.shape[0] // 2: dy -= c.shape[0]
    if dx > c.shape[1] // 2: dx -= c.shape[1]
    return int(dx) * 2, int(dy) * 2  # back to source pixels

SAME = 0.6   # mean abs grey-level change below which two recorded frames are the same image
gaps = [round((pts[i] - pts[i-1]) * 1000, 1) for i in range(1, n)]
print(f"clip {clip}: {n} frames over {pts[-1]-pts[0]:.2f} s, {W}x{H}{' crop '+sys.argv[2] if crop else ''}")
print(f"pts gaps ms: min {min(gaps)} max {max(gaps)}; gaps > 25 ms: {sum(g > 25 for g in gaps)}")

distinct, hold = [0], [1]
for i in range(1, n):
    if mad(frames[i], frames[i-1]) < SAME:
        hold[-1] += 1
    else:
        distinct.append(i); hold.append(1)
print(f"distinct images: {len(distinct)}; hold histogram: "
      + ", ".join(f"{h}x{hold.count(h)}" for h in sorted(set(hold))))

print("k\tframe\tpts\thold\tstep\tback2\tshift\tbands(min/max)\tflags")
steps = []
for k in range(1, len(distinct)):
    a, b = frames[distinct[k]], frames[distinct[k-1]]
    step = mad(a, b)
    back2 = mad(a, frames[distinct[k-2]]) if k >= 2 else float("nan")
    sh = shift(b, a)
    bd = bands(a, b)
    flags = []
    if k >= 2 and back2 < step: flags.append("STALE")
    if max(bd) > 4 * SAME and min(bd) < SAME: flags.append("SPLIT")
    if hold[k] != 2: flags.append(f"HOLD{hold[k]}")
    steps.append(step)
    print(f"{k}\t{distinct[k]}\t{pts[distinct[k]]:.3f}\t{hold[k]}\t{step:.2f}\t{back2:.2f}\t{sh}\t"
          f"{min(bd):.2f}/{max(bd):.2f}\t{' '.join(flags)}")
if steps:
    s = np.array(steps)
    print(f"step: median {np.median(s):.2f} p90 {np.percentile(s, 90):.2f} max {s.max():.2f}; "
          f"outliers (> 2x median): {int(np.sum(s > 2 * np.median(s)))}")
