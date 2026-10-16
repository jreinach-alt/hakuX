#!/usr/bin/env python3
"""Track the ring's displacement image to image in a crop that holds only
ring and sky (no logo, no menu text), for #939.

Per distinct image k: phase-correlation shift (dx, dy) from k-1 at full
resolution, and which of the previous 12 images k is closest to (lag 1 is
smooth motion; a larger lag means k went back to an earlier state).
Usage: ringtrack.py <clip.mp4> <x,y,w,h> [out.tsv]
"""
import json, subprocess, sys
import numpy as np

clip, crop = sys.argv[1], [int(v) for v in sys.argv[2].split(",")]
x, y, w, h = crop
pts = [float(f["pts_time"]) for f in json.loads(subprocess.check_output(
    ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
     "frame=pts_time", "-of", "json", clip]))["frames"]]
raw = subprocess.check_output(
    ["ffmpeg", "-v", "error", "-i", clip, "-fps_mode", "passthrough",
     "-vf", f"crop={w}:{h}:{x}:{y}", "-pix_fmt", "gray", "-f", "rawvideo", "-"])
n = len(raw) // (w * h)
fr = np.frombuffer(raw[: n * w * h], np.uint8).reshape(n, h, w).astype(np.float32)

keep = [0]
for i in range(1, n):
    if np.mean(np.abs(fr[i] - fr[keep[-1]])) >= 0.6:
        keep.append(i)
win = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)

def shift(a, b):  # displacement that maps a onto b
    fa, fb = np.fft.fft2((a - a.mean()) * win), np.fft.fft2((b - b.mean()) * win)
    r = fb * np.conj(fa)
    r /= np.abs(r) + 1e-9
    c = np.abs(np.fft.ifft2(r))
    dy, dx = np.unravel_index(np.argmax(c), c.shape)
    if dy > h // 2: dy -= h
    if dx > w // 2: dx -= w
    return int(dx), int(dy), float(c.max())

out = open(sys.argv[3], "w") if len(sys.argv) > 3 else sys.stdout
print("k\tframe\tpts\tdx\tdy\tpeak\tnearest_lag\tmad_lag1\tmad_nearest", file=out)
rows = []
for k in range(1, len(keep)):
    a, b = fr[keep[k - 1]], fr[keep[k]]
    dx, dy, pk = shift(a, b)
    lags = [(float(np.mean(np.abs(b - fr[keep[k - L]]))), L) for L in range(1, min(12, k) + 1)]
    m1 = lags[0][0]
    mn, lag = min(lags)
    rows.append((k, keep[k], pts[keep[k]], dx, dy, pk, lag, m1, mn))
    print(f"{k}\t{keep[k]}\t{pts[keep[k]]:.3f}\t{dx}\t{dy}\t{pk:.3f}\t{lag}\t{m1:.2f}\t{mn:.2f}", file=out)
if out is not sys.stdout:
    out.close()
d = np.array([[r[3], r[4]] for r in rows])
mag = np.hypot(d[:, 0], d[:, 1])
back = [r for r in rows if r[6] > 1]
print(f"{len(rows)} steps over {rows[-1][2] - rows[0][2]:.1f} s; |shift| median {np.median(mag):.1f} px, "
      f"p90 {np.percentile(mag, 90):.1f}, max {mag.max():.1f}; steps > 15 px: {int(np.sum(mag > 15))}; "
      f"images nearer an older image than the previous one: {len(back)}")
