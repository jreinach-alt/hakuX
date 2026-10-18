"""swapfit.py RENDER REG OVERLAY CAL: structural variants of the hull combiner against the console (#939, (a), M9)."""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf = sys.argv[1:5]
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
t0, t1, t2, t3 = (np.nan_to_num(R[k]) for k in ("t0", "t1", "t2", "t3"))
oD0, oD1 = np.nan_to_num(R["oD0"]), np.nan_to_num(R["oD1"])
cl = lambda x: np.clip(x, 0, 1)  # noqa: E731
tt = cl(2 * t0[..., :3] * t1[..., :3])
fres = oD1[..., :3] * oD1[..., 3:4]
g_, r_ = t2[..., 1:2], t2[..., 0:1]
V = {
    "hakuX D+X0": tt * cl(oD0[..., :3] + g_) + t3[..., :3] * fres * r_,
    "swap r<->g": tt * cl(oD0[..., :3] + r_) + t3[..., :3] * fres * g_,
    "self-lit r+g": tt * cl(oD0[..., :3] + g_ + r_) + t3[..., :3] * fres * r_,
    "D + fres*t2.r (cube 1)": tt * cl(oD0[..., :3] + g_) + fres * r_,
    "D + cube*t2.r (no fresnel)": tt * cl(oD0[..., :3] + g_) + t3[..., :3] * r_,
    "D + cube*oD1.rgb*t2.r": tt * cl(oD0[..., :3] + g_) + t3[..., :3] * oD1[..., :3] * r_,
    "D alone": tt * cl(oD0[..., :3] + g_),
}
lid = R["lid"]
BL = 3
for name, L in (("hull n5", 1), ("band n4", 0)):
    full = (lid == L) & base
    den = boxblur(full.astype(float), BL)
    core = full & (den > 0.5)
    mean = lambda img: (boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9))[core]  # noqa: E731
    c = mean(con)
    ys, xs = np.nonzero(core)
    blk = (ys // 24) * 1000 + xs // 24
    ub, inv = np.unique(blk, return_inverse=True)
    print(f"{name}: core {core.sum()} px, console {c.mean():.3f}")
    print("   variant                       mean    a      b       R2    (fit console = a*variant + b)")
    for vn, img in V.items():
        x = mean(img @ LUM)
        A = np.stack([x, np.ones_like(x)], 1)
        (a, b) = np.linalg.lstsq(A, c, rcond=None)[0]
        p = A @ np.array([a, b])
        r2 = 1 - ((c - p) ** 2).sum() / ((c - c.mean()) ** 2).sum()
        print(f"   {vn:28s} {x.mean():.3f}  {a:5.2f}  {b:+.3f}  {r2:.3f}")
