"""facemap.py RENDER REG OVERLAY CAL OUT.png: the excess c - h beside the cube face R lands on (#939, (a), M9)."""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf, outf = sys.argv[1:6]
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
cal = np.load(calf)
warped = np.load(regf)["warped"]
con = np.interp(warped @ LUM, cal["ph_L"], cal["fb_L"])
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


ovm = boxblur((ov > 0.06).astype(float), 2) > 0
base = ~ovm & (warped.sum(2) > 0)
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
lid = R["lid"]
face = np.nan_to_num(R["face"][..., 0], nan=-1).astype(int)
full = (lid == 1) & base
den = boxblur(full.astype(float), 3)
h = np.nan_to_num(R["final"]) @ LUM
e = np.where(full, (boxblur(np.where(full, con - h, 0), 3) / np.maximum(den, 1e-9)), np.nan)
pal = np.array([[255, 255, 255], [255, 0, 0], [0, 255, 0], [0, 128, 255], [255, 255, 0], [255, 0, 255]], float)
fimg = np.zeros((480, 640, 3))
hull = lid == 1
for f in range(6):
    fimg[hull & (face == f)] = pal[f] * 0.8
# excess: grey 0.5 = 0, +-0.25 full scale; outside the judged pixels, dark
emap = np.zeros((480, 640, 3))
v = np.clip(0.5 + np.nan_to_num(e) / 0.5, 0, 1)
emap[full] = np.stack([v, v, v], -1)[full] * 255
emap[full & (np.nan_to_num(e) > 0.08)] = [255, 80, 0]
img = np.concatenate([fimg, emap, np.repeat((con * 255)[..., None], 3, -1), np.repeat((h * 255)[..., None], 3, -1)], 1)
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(outf)
for f in range(6):
    s = full & (face == f)
    if s.sum() > 300:
        ys, xs = np.nonzero(s)
        print(f"face {f}: {s.sum()} px, x {xs.min()}-{xs.max()} (med {int(np.median(xs))}), "
              f"y {ys.min()}-{ys.max()} (med {int(np.median(ys))}), excess {np.nanmean(e[s]):+.3f}")
