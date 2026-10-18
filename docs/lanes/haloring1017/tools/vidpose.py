"""Which video frame of a hakuX run has a console photo's camera pose? (#939, (a))

usage: vidpose.py VIDEO.mp4 T0 T1 REG.npz OVERLAY.png [roi=x0,y0,x1,y1] [blur=R] [save=PNG]

posefit.py needs a gd dump at the photo's pose. Run 13's dump covers video
13-33 s only, and photos 1-4 sit outside it. Its video covers the whole menu
loop, so this matches the photo against every video frame in [T0, T1]:
the photo (photoreg.py's warp, frame pixels) and each frame (scaled to
640x480) as luminance, blurred, off the overlays (OVERLAY.png > 0.12) and
inside the ROI; scored by NCC. The ring and the planet both move with the
camera, so the peak is the pose. The video's frame clock is its own
(59.94 fps); M2b's anchor line maps it to dump frames where it applies.

The frame rate is the stream's r_frame_rate (ffprobe), which is the rate
ffmpeg's rawvideo output runs at. Run 13's video is 60000/1001. The Nova's
video of 1792329678 (display at 120 Hz) is variable-rate on a 120/1 base,
and ffmpeg repeats frames to fill it, so a fixed 59.94 put photo 4 at
51.99 s instead of 40.98 s.
"""
import subprocess
import sys

import numpy as np
from PIL import Image


def blur(img, r):
    """Three passes of a (2r+1) box (photoreg.py's, which runs on import)."""
    if r < 1:
        return img
    out = img
    for _ in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(out.ndim)], mode="edge"),
                          axis=ax)
            n = out.shape[ax]
            out = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)) \
                / (2 * r + 1)
    return out


video, t0, t1, regf, ovf = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
opt = dict(a.split("=", 1) for a in sys.argv[6:])
W, H = 640, 480
LUM = np.array([0.299, 0.587, 0.114])
x0, y0, x1, y1 = (int(v) for v in opt.get("roi", "0,0,640,480").split(","))
br = int(opt.get("blur", 3))

P = np.load(regf)["warped"] @ LUM
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255
m = np.zeros((H, W), bool)
m[y0:y1, x0:x1] = True
m &= ov < 0.12
m &= P > 0.0  # photoreg leaves 0 outside the photo
Pb = blur(P, br)[m]
Pb = (Pb - Pb.mean()) / Pb.std()

rate = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                       "-of", "csv=p=0", video], capture_output=True, check=True, text=True).stdout.strip()
num, _, den = rate.partition("/")
FPS = float(num) / float(den or 1)
cmd = ["ffmpeg", "-v", "error", "-ss", f"{t0}", "-i", video, "-t", f"{t1 - t0}",
       "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
raw = subprocess.run(cmd, capture_output=True, check=True).stdout
n = len(raw) // (W * H * 3)
fr = np.frombuffer(raw[:n * W * H * 3], dtype=np.uint8).reshape(n, H, W, 3)
print(f"photo px {m.sum()}, {n} video frames from {t0} s at {FPS:.3f} fps")
rows = []
for i in range(n):
    V = blur(fr[i].astype(np.float64) / 255 @ LUM, br)[m]
    V = (V - V.mean()) / V.std()
    r = float((V * Pb).mean())
    t = t0 + i / FPS
    rows.append((t, r, i))
    print(f"t {t:.3f} ncc {r:.4f}")
tb, rb, ib = max(rows, key=lambda x: x[1])
print(f"best: t {tb:.3f} ncc {rb:.4f}")
if "save" in opt:
    v = fr[ib].astype(np.float64) / 255
    pan = np.concatenate([np.load(regf)["warped"], v], axis=1)
    Image.fromarray((np.clip(pan, 0, 1) * 255).astype(np.uint8)).save(opt["save"])
