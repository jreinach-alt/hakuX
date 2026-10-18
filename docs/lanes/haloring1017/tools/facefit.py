"""facefit.py RENDER REG OVERLAY CAL [blur=3]: the console's reflection per cube face (#939, (a), M9).

Per draw and per cube face the pixel's R lands on, the slope of (console - D) on
W = t2.r * oD1.rgb * oD1.a (the reflection with the cube taken out) is the cube value the
console's reflection behaves as if it read there; the same slope of (hakuX - D) is hakuX's,
and the face's own mean texel what hakuX samples. A face whose console value is far above
hakuX's says the console reads another texel (another face, or another texture) for it."""
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
lid, face = R["lid"], R["face"][..., 0].astype(int)
oD1 = np.nan_to_num(R["oD1"])
Wimg = np.nan_to_num(R["t2"])[..., 0] * ((oD1[..., :3] * oD1[..., 3:4]) @ LUM)
t3l = np.nan_to_num(R["t3"])[..., :3] @ LUM
Dimg = np.nan_to_num(R["diffuse"]) @ LUM
himg = np.nan_to_num(R["final"]) @ LUM
t2r = np.nan_to_num(R["t2"])[..., 0]
for name, L in (("hull n5", 1), ("band n4", 0)):
    print(f"{name}: face   px    W mean  hakuX t3  slope hakuX  slope console (c - D on W, + const)  "
          f"console - hakuX  t2.r")
    for f in range(6):
        full = (lid == L) & base & (face == f)
        if full.sum() < 300:
            continue
        den = boxblur(full.astype(float), BL)
        core = full & (den > 0.6)
        if core.sum() < 200:
            continue
        mean = lambda img: (boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9))[core]  # noqa: E731
        c, D, W, h, t3, tr = mean(con), mean(Dimg), mean(Wimg), mean(himg), mean(t3l), mean(t2r)
        A = np.stack([W, np.ones_like(W)], 1)
        sh = np.linalg.lstsq(A, h - D, rcond=None)[0]
        sc = np.linalg.lstsq(A, c - D, rcond=None)[0]
        print(f"         {f}  {core.sum():6d}  {W.mean():.3f}   {t3.mean():.3f}     {sh[0]:.3f}        "
              f"{sc[0]:.3f} ({sc[1]:+.3f})                       {(c - h).mean():+.3f}       {tr.mean():.3f}")
        e = c - h
        out = []
        for lab, x in (("D", D), ("W", W), ("t2.r", tr)):
            A = np.stack([x, np.ones_like(x)], 1)
            co = np.linalg.lstsq(A, e, rcond=None)[0]
            r2 = 1 - ((e - A @ co) ** 2).sum() / ((e - e.mean()) ** 2).sum()
            out.append(f"{lab} {x.mean():.3f} sd {x.std():.3f}: slope {co[0]:+.3f} R2 {r2:.3f}")
        print("              c-h on " + ";  ".join(out) + f";  c-h / t2.r {e.mean() / tr.mean():.3f}")
