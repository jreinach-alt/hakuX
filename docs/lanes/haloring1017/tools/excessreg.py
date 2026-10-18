"""The console's hull level against hakuX's terms, jointly (#939, (a), M7).

usage: excessreg.py RENDER.npz REG.npz OVERLAY.png CAL.npz [blur=3] [chan=L|G|B]

The console (read back to fb units through CAL.npz on one channel) is fitted
per pixel, on the blurred hull core, as a linear sum of hakuX's terms with no
constant and with one: D = 2 t0 t1 v0 (the diffuse), Dn = t0 v0 (the diffuse
with the detail map neutral, t1 = 0.5), X0 (hakuX's reflection), t2.r and
t2.r oD1.rgb (the reflection's mask and its fresnel tint, cube = 1). A model
that names the right term fits with a coefficient near 1 on hakuX's terms and
a small residual; D x k and D + c t2.r fit the rank equally (reflfit,
detailfit), so here they meet head to head, and also on the pixels where D and
t2.r disagree (t2.r high, D low and the reverse), where only one can be right.
"""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf = sys.argv[1:5]
opt = dict(a.split("=", 1) for a in sys.argv[5:])
BL = int(opt.get("blur", 3))
CH = opt.get("chan", "L")
LUM = np.array([0.299, 0.587, 0.114])
ci = {"L": None, "R": 0, "G": 1, "B": 2}[CH]
R = np.load(rendf)
cal = np.load(calf)
ph = np.load(regf)["warped"]
phc = ph @ LUM if ci is None else ph[..., ci]
con = np.interp(phc, cal["ph_" + CH], cal["fb_" + CH])
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


ovm = boxblur((ov > 0.06).astype(float), 2) > 0
base = ~ovm
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
lid = R["lid"]
z = lambda k: np.nan_to_num(R[k])  # noqa: E731
ch = (lambda v: v @ LUM) if ci is None else (lambda v: v[..., ci])  # noqa: E731
t0, t1, t2, od1 = z("t0")[..., :3], z("t1")[..., :3], z("t2"), z("oD1")
v0 = np.where(t0 > 1e-6, z("diffuse") / np.maximum(2 * t0 * t1, 1e-9), 0)
terms = {
    "D": ch(z("diffuse")),
    "Dn (t1=0.5)": ch(t0 * v0),
    "X0": ch(z("refl")),
    "t2.r": t2[..., 0],
    "t2.r*oD1.rgb": ch(t2[..., :1] * od1[..., :3]),
}
full = (lid == 1) & base
den = boxblur(full.astype(float), BL)
core = full & (den > 0.5)


def sm(img):
    return boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9)


y = sm(con)[core]
T = {k: sm(v)[core] for k, v in terms.items()}
hx = T["D"] + T["X0"]
print(f"hull core {core.sum()} px, channel {CH}: console {y.mean():.3f}, hakuX D + X0 {hx.mean():.3f}, "
      f"corr(D, t2.r) {np.corrcoef(T['D'], T['t2.r'])[0, 1]:+.3f}")
models = [["D", "X0"], ["D"], ["Dn (t1=0.5)"], ["Dn (t1=0.5)", "X0"], ["D", "t2.r"], ["D", "t2.r*oD1.rgb"],
          ["Dn (t1=0.5)", "t2.r"], ["D", "Dn (t1=0.5)"], ["D", "Dn (t1=0.5)", "t2.r"]]
tot = ((y - y.mean()) ** 2).sum()
for const in (False, True):
    print(f"-- {'with' if const else 'no'} constant")
    for m in models:
        A = np.stack([T[k] for k in m] + ([np.ones_like(y)] if const else []), 1)
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        res = y - A @ coef
        print(f"   {' + '.join(m):32s} coef {np.round(coef, 3)!s:28s} R2 {1 - (res ** 2).sum() / tot:+.3f} "
              f"rms {np.sqrt((res ** 2).mean()):.4f}")
# where D and t2.r disagree
zD = (T["D"] - T["D"].mean()) / T["D"].std()
zr = (T["t2.r"] - T["t2.r"].mean()) / T["t2.r"].std()
for name, s in (("t2.r high, D low", (zr > 0.5) & (zD < -0.5)), ("t2.r low, D high", (zr < -0.5) & (zD > 0.5)),
                ("both high", (zr > 0.5) & (zD > 0.5)), ("both low", (zr < -0.5) & (zD < -0.5))):
    if s.sum() < 50:
        print(f"   {name}: {s.sum()} px, too few")
        continue
    print(f"   {name:18s} {s.sum():6d} px: console {y[s].mean():.3f}  hakuX {hx[s].mean():.3f}  "
          f"ratio {y[s].mean() / hx[s].mean():.2f}  excess {y[s].mean() - hx[s].mean():+.3f} | "
          f"D {T['D'][s].mean():.3f} Dn {T['Dn (t1=0.5)'][s].mean():.3f} t2.r {T['t2.r'][s].mean():.3f}")
