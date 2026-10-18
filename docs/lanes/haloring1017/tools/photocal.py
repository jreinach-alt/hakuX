"""The console photo's tone curve, from the menu's overlays (#939, (a)).

usage: photocal.py REG.npz RENDER.npz FRAMES_DIR [out=CAL.npz] [grad=0.02] [bins=16] [margin=0] [exclude=MASK.png]

A photo of a TV is not framebuffer values: the camera's exposure, white
balance and tone curve sit between. The menu's 2D overlays (the HALO logo,
the menu text) are the same picture on the console and in hakuX, so they
calibrate that chain. The template is the per-channel minimum over the hakuX
video frames in FRAMES_DIR (v*.ppm): the camera moves and the overlays do not,
so the minimum keeps the overlays on black.

Calibration pixels are where the render (RENDER.npz from hullsw.py, lid < 0)
has no ring, so photo and template both have space under the overlay, and
the template is locally flat (gradient < grad after a 1 px blur), so camera
blur does not decide the value. Per channel, the photo's median per template
bin is the curve photo = f(fb); it is monotone-fitted and inverted to read
any photo pixel in framebuffer units. Writes the curve (fb, photo) per channel.

lid < 0 is not "space" where the render misses ring that hakuX draws (M10: at
f507 a triangle of hull between the V's arms, top right). margin=N keeps N px
off the render's ring; exclude=MASK.png drops the mask's nonzero pixels.
"""
import glob
import os
import sys

import numpy as np

regf, rendf, fdir = sys.argv[1:4]
opt = dict(a.split("=", 1) for a in sys.argv[4:])
NB = int(opt.get("bins", 16))


def ppm_rgb(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    w, h = (int(x) for x in parts[1].split())
    return np.frombuffer(parts[3][:w * h * 3], dtype=np.uint8).reshape(h, w, 3).astype(np.float64) / 255


fs = sorted(glob.glob(os.path.join(fdir, opt.get("pattern", "v*.ppm"))))
T = None
for f in fs:
    im = ppm_rgb(f)
    T = im if T is None else np.minimum(T, im)
P = np.load(regf)["warped"]
lid = np.load(rendf)["lid"]
Tl = T @ np.array([0.299, 0.587, 0.114])
k = np.ones(3) / 3
Tb = Tl.copy()
for ax in (0, 1):
    Tb = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), ax, Tb)
gy, gx = np.gradient(Tb)
flat = np.hypot(gx, gy) < float(opt.get("grad", 0.02))
m = (lid < 0) & flat
mg = int(opt.get("margin", 0))
if mg:
    ring = (lid >= 0).astype(float)
    for ax in (0, 1):
        ring = np.apply_along_axis(lambda r: np.convolve(r, np.ones(2 * mg + 1), mode="same"), ax, ring)
    m &= ring == 0
if "exclude" in opt:
    from PIL import Image
    m &= np.asarray(Image.open(opt["exclude"]).convert("L")) == 0
m[452:, :] = False
m[:, :15] = False
m[:30, :70] = False
print(f"template from {len(fs)} frames; calibration px {m.sum()} (overlay px with T lum > 0.1: {(m & (Tl > 0.1)).sum()})")
curves = {}
LUM = np.array([0.299, 0.587, 0.114])
for c, name in enumerate("RGBL"):
    t, p = (T[m, c], P[m, c]) if c < 3 else (Tl[m], P[m] @ LUM)
    # fixed-width bins: the space pixels (most of them) would take every quantile bin
    edges = np.linspace(0.06, 1.0, NB + 1)
    xs, ys, ns = [0.0], [float(np.median(p[t <= 0.06]))], [int((t <= 0.06).sum())]
    for a, b in zip(edges[:-1], edges[1:]):
        s = (t > a) & (t <= b)
        if s.sum() >= 20:
            xs.append(float(np.median(t[s])))
            ys.append(float(np.median(p[s])))
            ns.append(int(s.sum()))
    ys = np.maximum.accumulate(np.array(ys))
    curves[name] = (np.array(xs), ys)
    print(f"{name}: " + "  ".join(f"{x:.2f}->{y:.2f}({n})" for x, y, n in zip(xs, ys, ns)))
if "out" in opt:
    np.savez(opt["out"], **{f"fb_{k}": v[0] for k, v in curves.items()}, **{f"ph_{k}": v[1] for k, v in curves.items()})
