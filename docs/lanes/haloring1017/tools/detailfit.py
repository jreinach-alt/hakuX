"""Is the console's hull hakuX's with the detail map faded to grey? (#939, (a), M7)

usage: detailfit.py RENDER.npz REG.npz OVERLAY.png CAL.npz [blur=3]

The hull's detail map t1 (128x128 DXT1, 6 mips) fades toward grey through its
mips: mean 0.255 at mip 0, then 0.289, 0.323, 0.357, 0.391, 0.423, the usual
detail-map fade toward 0.5, where 2 t0 t1 = t0. The band's t1 is a flat 0.502.
So the LOD at which t1 is sampled sets the hull's level (and nothing of the
band's), and any LOD difference shows as a low-frequency change in D.

Variants of D = 2 t0 t1 (oD0 + t2.g), each with hakuX's reflection X0 added:
  - hakuX (t1 as sampled);
  - t1 replaced by its own mean at mip m (no detail, the fade's level at m);
  - t1 replaced by 0.5 (the fade's limit);
  - t1 as sampled, times 0.5/mean(mip 0) (the detail kept, the level moved).
For each: rank r with the console's luminance on the hull (all, upper, lower),
the mean level, and the console read back to framebuffer units through CAL.npz.
"""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf = sys.argv[1:5]
opt = dict(a.split("=", 1) for a in sys.argv[5:])
BL = int(opt.get("blur", 3))
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
con = np.load(regf)["warped"] @ LUM
cal = np.load(calf)
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255
T1MEANS = [0.255, 0.289, 0.323, 0.357, 0.391, 0.423]  # the hull's t1, mean per mip (RAM, f507)


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


def rank(x):
    r = np.empty(len(x))
    r[np.argsort(x, kind="stable")] = np.arange(len(x))
    return r


ovm = boxblur((ov > 0.06).astype(float), 2) > 0
full = (R["lid"] == 1) & ~ovm
full[452:, :] = False
full[:, :15] = False
full[:30, :70] = False
den = boxblur(full.astype(float), BL)
core = full & (den > 0.5)
yy = np.arange(con.shape[0])[:, None]
REG = {"all": core, "upper": core & (yy < 300), "lower": core & (yy >= 300)}


def sm(img):
    return boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9)


CR = {k: rank(sm(con)[m]) for k, m in REG.items()}
z = lambda k: np.nan_to_num(R[k])  # noqa: E731
t1 = z("t1")[..., :3]
dif = z("diffuse")
X0 = z("refl") @ LUM
lod1 = z("lod1")[..., 0]
cfb = float(np.interp(con[full].mean(), cal["ph_L"], cal["fb_L"]))
print(f"hull core {core.sum()} px, blur {BL}; console mean photo {con[full].mean():.3f} = fb {cfb:.3f}")
print(f"hakuX's t1 on screen: mean {(t1[full] @ LUM).mean():.3f}; lod1 p10/50/90 "
      f"{np.percentile(lod1[full], [10, 50, 90]).round(2)}")
print("variant                              rank r: all   upper  lower | level (D + X0)  D alone")
safe = np.maximum(t1, 1e-3)
variants = [("hakuX (t1 as sampled)", dif)]
for m, v in enumerate(T1MEANS):
    variants.append((f"t1 = mip {m} mean {v:.3f}", dif / safe * v))
variants.append(("t1 = 0.5 (the fade's limit)", dif / safe * 0.5))
variants.append(("t1 detail kept, level x 0.5/0.255", dif * (0.5 / 0.255)))
for name, D in variants:
    v = D @ LUM + X0
    s = sm(v)
    r = {k: np.corrcoef(rank(s[m]), CR[k])[0, 1] for k, m in REG.items()}
    print(f"{name:36s} {r['all']:+.3f} {r['upper']:+.3f} {r['lower']:+.3f} |  {v[full].mean():.3f}         "
          f"{(D @ LUM)[full].mean():.3f}", flush=True)
