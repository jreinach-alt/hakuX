"""maskfit.py RENDER REG OVERLAY CAL [blur=3]: which mask on the cube term fits the console (#939, (a), M9).

console = a*D + b*X + c with X = t3 * MASK for each candidate MASK (hakuX's is t2.r * oD1.rgb * oD1.a), on the
hull's core pixels pooled and per cube face. Then the same with X's term for hakuX's own final as the control:
the fit must return a = 1, b = 1 on hakuX's final, or the term set is not what hakuX draws."""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf = sys.argv[1:5]
opt = dict(a.split("=", 1) for a in sys.argv[5:])
BL = int(opt.get("blur", 3))
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
t2, t3, oD1 = (np.nan_to_num(R[k]) for k in ("t2", "t3", "oD1"))
r_, a_ = t2[..., 0:1], oD1[..., 3:4]
masks = {
    "t2.r oD1.rgb oD1.a (hakuX)": r_ * oD1[..., :3] * a_,
    "1": np.ones_like(r_),
    "oD1.rgb": oD1[..., :3],
    "oD1.a": a_,
    "oD1.rgb oD1.a": oD1[..., :3] * a_,
    "t2.r": r_,
    "t2.r oD1.a": r_ * a_,
    "t2.r oD1.rgb": r_ * oD1[..., :3],
    "t2.b": t2[..., 2:3],
    "t2.g": t2[..., 1:2],
}
Dimg = np.nan_to_num(R["diffuse"]) @ LUM
himg = np.nan_to_num(R["final"]) @ LUM
X = {k: (t3[..., :3] * m) @ LUM for k, m in masks.items()}
for lab, sel in (("hull, all faces", None), ("face 0", 0), ("face 3", 3), ("face 5", 5)):
    full = (lid == 1) & base
    if sel is not None:
        full &= face == sel
    den = boxblur(full.astype(float), BL)
    core = full & (den > 0.6)
    mean = lambda img: (boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9))[core]  # noqa: E731
    c, D, h = mean(con), mean(Dimg), mean(himg)
    print(f"{lab}: {core.sum()} px; console = a D + b X + c")
    for k, img in X.items():
        x = mean(img)
        A = np.stack([D, x, np.ones_like(D)], 1)
        co = np.linalg.lstsq(A, c, rcond=None)[0]
        r2 = 1 - ((c - A @ co) ** 2).sum() / ((c - c.mean()) ** 2).sum()
        ctl = ""
        if k.endswith("(hakuX)"):
            ch_ = np.linalg.lstsq(A, h, rcond=None)[0]
            ctl = f"   control on hakuX's final: a {ch_[0]:.2f} b {ch_[1]:.2f} c {ch_[2]:+.3f}"
        print(f"   {k:28s} X {x.mean():.3f}  a {co[0]:5.2f}  b {co[1]:5.2f}  c {co[2]:+.3f}  R2 {r2:.3f}{ctl}")
