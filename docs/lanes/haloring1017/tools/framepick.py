"""framepick.py DUMP RAM REG OVERLAY F0 F1 [video=PPM] [roi=x0,y0,x1,y1] [blur=3] [out=DIR] (#939, (a), M10)

posefit.py finds a photo's pose to a few frames by silhouette. This picks the frame: each candidate in F0..F1 is
rendered by hullsw.py, and its final luminance on the render's own ring pixels (inside the ROI, off the overlays,
inside the photo) is correlated, after a box blur, with
  - VIDEO, the run's own video frame at the photo's pose (vidpose.py): hakuX against hakuX, so pose and scroll both
    have to be right for a high r (M2b's anchors), and
  - the photo (REG.npz's warp): the console's textures scroll on the same clock as its camera (M5), so its r peaks
    at the same frame if the pose is right.
The dump is loaded once. With out=DIR the best frame by video r (else by photo r) is saved as DIR/render_<f>.npz.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullsw as hs  # noqa: E402

dump, ramf, regf, ovf = sys.argv[1:5]
f0, f1 = int(sys.argv[5]), int(sys.argv[6])
opt = dict(a.split("=", 1) for a in sys.argv[7:])
BL = int(opt.get("blur", 3))
LUM = np.array([0.299, 0.587, 0.114])
x0, y0, x1, y1 = (int(v) for v in opt.get("roi", "15,30,560,452").split(","))
ram = open(ramf, "rb").read()
P = np.load(regf)["warped"] @ LUM
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255
roi = np.zeros((hs.H, hs.W), bool)
roi[y0:y1, x0:x1] = True
roi &= ov < 0.12
roi &= P > 0.0
V = hs.ppm_rgb(opt["video"]) @ LUM if "video" in opt else None


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


def ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-12))


loaded = hs.g.load(dump)
rows, keep = [], {}
for f in range(f0, f1 + 1):
    try:
        R = hs.render(dump, ram, f, loaded=loaded)
    except SystemExit as e:
        print(f"f{f}: refused: {e}")
        continue
    ring = (R["lid"] >= 0) & roi
    den = boxblur(ring.astype(float), BL)
    core = ring & (den > 0.6 * (2 * BL + 1) ** 2)
    if core.sum() < 500:
        print(f"f{f}: {core.sum()} ring px in the ROI, skipped")
        continue
    sm = lambda img: (boxblur(np.where(ring, img, 0), BL) / np.maximum(den, 1e-9))[core]  # noqa: E731
    h = sm(np.nan_to_num(R["final"]) @ LUM)
    rp = ncc(h, sm(P))
    rv = ncc(h, sm(V)) if V is not None else float("nan")
    hull = (R["lid"] == 1) & core
    rows.append((f, rv, rp))
    keep[f] = R
    if len(keep) > 3:  # only the running best and its neighbours are worth keeping in memory
        best = max(rows, key=lambda x: x[1] if V is not None else x[2])[0]
        for k in list(keep):
            if abs(k - best) > 1 and k != f:
                del keep[k]
    print(f"f{f}: core px {core.sum()} (hull {hull.sum()})  r video {rv:.4f}  r photo {rp:.4f}", flush=True)
if rows:
    bv = max(rows, key=lambda x: x[1]) if V is not None else None
    bp = max(rows, key=lambda x: x[2])
    if bv:
        print(f"best by video: f{bv[0]} r {bv[1]:.4f}")
    print(f"best by photo: f{bp[0]} r {bp[2]:.4f}")
    if "out" in opt:
        fb = (bv or bp)[0]
        R = keep.get(fb) or hs.render(dump, ram, fb, loaded=loaded)
        os.makedirs(opt["out"], exist_ok=True)
        np.savez_compressed(os.path.join(opt["out"], f"render_{fb}.npz"), **R)
        print(f"saved {opt['out']}/render_{fb}.npz")
