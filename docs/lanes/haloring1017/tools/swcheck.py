"""How well does hullsw.py's render match an image of the same frame? (#939, (a))

usage: swcheck.py RENDER.npz IMAGE.ppm [layer=1]

For the layer's pixels (n5 = 1): mean and spread of render - image, the
correlation of luminance at box blurs 1, 4, 16 px (fine detail vs the
broad shading), the best integer shift within +-3 px, and a least-squares
fit of the image on the render's terms (diffuse, reflection, constant),
whose coefficients are 1, 1, 0 when the render is the image.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hullsw import ppm_rgb  # noqa: E402

npz, imgf = sys.argv[1], sys.argv[2]
opt = dict(a.split("=", 1) for a in sys.argv[3:])
L = int(opt.get("layer", 1))
R = np.load(npz)
img = ppm_rgb(imgf)
lum = np.array([0.299, 0.587, 0.114])
m = R["lid"] == L
# the menu's overlays (logo, menu text, the FPS counter) are drawn over the hull in the image
# and not in the render: x0,y0,x1,y1 rectangles kept out, "none" for none
for rect in opt.get("exclude", "0,110,640,205;210,245,435,390;0,0,70,25").split(";"):
    if rect != "none":
        x0, y0, x1, y1 = (int(v) for v in rect.split(","))
        m[y0:y1, x0:x1] = False
fin = np.nan_to_num(R["final"])
d = fin[m] - img[m]
print(f"px {m.sum()}  render-image mean {d.mean(0).round(4)} sd {d.std(0).round(4)} "
      f"|d|>0.1: {np.mean(np.abs(d @ lum) > 0.1):.3f}")


def box(a, k):
    if k == 1:
        return a
    c = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
    out = np.full_like(a, np.nan)
    h = k // 2
    H, W = a.shape
    y0, y1 = np.clip(np.arange(H) - h, 0, H), np.clip(np.arange(H) + h + 1, 0, H)
    x0, x1 = np.clip(np.arange(W) - h, 0, W), np.clip(np.arange(W) + h + 1, 0, W)
    out = (c[y1][:, x1] - c[y0][:, x1] - c[y1][:, x0] + c[y0][:, x0])
    return out


inner = m.copy()
for k in (1, 4, 16):
    # keep pixels whose whole box is on the layer, so the blur never mixes in the background
    cover = box(m.astype(float), k) / box(np.ones_like(m, dtype=float), k)
    keep = m & (cover > 0.999)
    a = box(np.where(m, fin @ lum, 0), k)
    b = box(np.where(m, img @ lum, 0), k)
    if keep.sum() > 100:
        print(f"blur {k:2d}: px {keep.sum():6d} r {np.corrcoef(a[keep], b[keep])[0, 1]:.3f}")

best = None
yy, xx = np.nonzero(m)
ok = (yy > 3) & (yy < 476) & (xx > 3) & (xx < 636)
yy, xx = yy[ok], xx[ok]
for dy in range(-3, 4):
    for dx in range(-3, 4):
        r = np.corrcoef(fin[yy, xx] @ lum, img[yy + dy, xx + dx] @ lum)[0, 1]
        if best is None or r > best[0]:
            best = (r, dy, dx)
print(f"best shift: image at (y{best[1]:+d}, x{best[2]:+d}) r {best[0]:.3f}")

A = np.stack([R["diffuse"][m] @ lum, R["refl"][m] @ lum, np.ones(m.sum())], 1)
coef, *_ = np.linalg.lstsq(A, img[m] @ lum, rcond=None)
pred = A @ coef
print(f"image ~ {coef[0]:.3f}*diffuse + {coef[1]:.3f}*refl + {coef[2]:.3f}  "
      f"r {np.corrcoef(pred, img[m] @ lum)[0, 1]:.3f}")
for c, name in enumerate("rgb"):
    print(f"  {name}: render mean {fin[m][:, c].mean():.4f} image {img[m][:, c].mean():.4f} "
          f"r {np.corrcoef(fin[m][:, c], img[m][:, c])[0, 1]:.3f}")
if "save" in opt:
    from PIL import Image
    show = np.zeros((480, 640 * 2, 3))
    show[:, :640][m] = fin[m]
    show[:, 640:][m] = img[m]
    Image.fromarray((np.clip(show * 2, 0, 1) * 255).astype(np.uint8)).save(opt["save"])
