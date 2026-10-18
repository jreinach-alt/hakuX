"""spatial.py RENDER REG OVERLAY CAL VIDEO.ppm: is the photo uniform over the screen? (#939, (a), M9)

Off the ring and the overlays, the space background is the same picture on both machines.
The photo read through CAL against hakuX's video frame there, by screen band, says whether
the photo (camera vignetting, the monitor's own falloff, glare) adds a position term. Then on
the hull: the excess c - h fitted on t2.r and screen y together."""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf, vidf = sys.argv[1:6]
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
cal = np.load(calf)
warped = np.load(regf)["warped"]
con = np.interp(warped @ LUM, cal["ph_L"], cal["fb_L"])
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def ppm_l(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    w, h = (int(x) for x in parts[1].split())
    return (np.frombuffer(parts[3][:w * h * 3], dtype=np.uint8).reshape(h, w, 3).astype(np.float64) / 255) @ LUM


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


vid = ppm_l(vidf)
ovm = boxblur((ov > 0.06).astype(float), 2) > 0
base = ~ovm & (warped.sum(2) > 0)
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
lid = R["lid"]
ring = boxblur((lid >= 0).astype(float), 4) > 0
bg = base & ~ring
yy, xx = np.mgrid[0:480, 0:640]
print(f"space background: {bg.sum()} px; photo-in-fb minus video, by screen band (median, and of the bright half)")
for lab, coord, edges in (("y", yy, [0, 100, 200, 300, 400, 452]), ("x", xx, [15, 160, 320, 480, 640])):
    for a, b in zip(edges[:-1], edges[1:]):
        s = bg & (coord >= a) & (coord < b)
        if s.sum() < 50:
            print(f"   {lab} {a:3d}-{b:3d}: {s.sum()} px")
            continue
        d = con[s] - vid[s]
        hi = s & (vid > np.median(vid[s]))
        print(f"   {lab} {a:3d}-{b:3d}: n {s.sum():6d}  video {vid[s].mean():.3f}  photo {con[s].mean():.3f}  "
              f"diff med {np.median(d):+.3f}  bright half {np.median(con[hi] - vid[hi]):+.3f}")

full = (lid == 1) & base
den = boxblur(full.astype(float), 3)
core = full & (den > 0.5)
mean = lambda img: (boxblur(np.where(full, img, 0), 3) / np.maximum(den, 1e-9))[core]  # noqa: E731
c = mean(con)
h = mean(np.nan_to_num(R["final"]) @ LUM)
t2r = mean(np.nan_to_num(R["t2"])[..., 0])
D = mean(np.nan_to_num(R["diffuse"]) @ LUM)
X0 = mean(np.nan_to_num(R["refl"]) @ LUM)
y = yy[core] / 480.0
x = xx[core] / 640.0
print(f"hull core {core.sum()} px: corr(t2.r, y) {np.corrcoef(t2r, y)[0, 1]:.3f}, corr(D, y) {np.corrcoef(D, y)[0, 1]:.3f}")
for lab, cols in (("t2.r", [t2r]), ("y", [y]), ("t2.r + y", [t2r, y]), ("t2.r + y + x", [t2r, y, x]),
                  ("D + t2.r + y", [D, t2r, y])):
    A = np.stack(cols + [np.ones_like(c)], 1)
    co = np.linalg.lstsq(A, c - h, rcond=None)[0]
    p = A @ co
    r2 = 1 - (((c - h) - p) ** 2).sum() / (((c - h) - (c - h).mean()) ** 2).sum()
    print(f"   c - h ~ {lab:14s}: coef {np.round(co, 3)}  R2 {r2:.3f}")
print("   by x band: n, c-h, t2.r, D, and the slope of c-h on t2.r inside the band")
for a, b in zip([15, 160, 320, 400, 480, 540], [160, 320, 400, 480, 540, 640]):
    s = (xx[core] >= a) & (xx[core] < b)
    if s.sum() > 100:
        A = np.stack([t2r[s], np.ones(s.sum())], 1)
        k = np.linalg.lstsq(A, (c - h)[s], rcond=None)[0][0]
        print(f"      x {a:3d}-{b:3d}: {s.sum():6d}  {(c - h)[s].mean():+.3f}  {t2r[s].mean():.3f}  {D[s].mean():.3f}"
              f"   k {k:+.3f}")
print("   by y band: n, c-h, t2.r, D")
for a, b in zip([0, 100, 200, 300, 400], [100, 200, 300, 400, 452]):
    s = (yy[core] >= a) & (yy[core] < b)
    if s.sum():
        print(f"      y {a:3d}-{b:3d}: {s.sum():6d}  {(c - h)[s].mean():+.3f}  {t2r[s].mean():.3f}  {D[s].mean():.3f}")
