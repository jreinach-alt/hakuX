"""Which factor of the reflection does the console drop? (#939, (a), M7)

usage: reflfit.py RENDER.npz REG.npz OVERLAY.png CAL.npz [blur=3]

hakuX's reflection is X0 = t3 . oD1.rgb . t2.r . oD1.a (stage 4: the cube times
the fresnel colour; stage 2: r1.a = t2.r times oD1.a; stage 7: t3 times r1.a).
M6 found the console fits D + c t2.r better than D + c X0. Here every subset of
X0's three other factors (the cube t3, oD1.rgb, oD1.a) is dropped in turn
(replaced by 1), and for each variant:
  - the rank r with the console's luminance on the hull (all, upper, lower) at
    the best c, and at c = 1 (the term at full strength, as the hardware would
    draw it if that factor read 1);
  - the mean level at c = 1, hull and band, against the console read back to
    framebuffer units through CAL.npz's L curve.
RENDER.npz is hullsw.py's render at the photo's pose (M5: f507).
"""
import itertools
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
base = ~ovm
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
yy = np.arange(con.shape[0])[:, None]
lid = R["lid"]
full = {"hull": (lid == 1) & base, "band": (lid == 0) & base}
cores = {}
for name, m in full.items():
    den = boxblur(m.astype(float), BL)
    cores[name] = (m & (den > 0.5), den)
REG = {"all": cores["hull"][0], "upper": cores["hull"][0] & (yy < 300), "lower": cores["hull"][0] & (yy >= 300),
       "band": cores["band"][0]}
REGOF = {"all": "hull", "upper": "hull", "lower": "hull", "band": "band"}


def sm(img, name):
    m, den = cores[name][1], full[name]
    return boxblur(np.where(den, img, 0), BL) / np.maximum(m, 1e-9)


CS = {k: sm(con, REGOF[k])[REG[k]] for k in REG}
CR = {k: rank(v) for k, v in CS.items()}


def rr(img):
    s = {name: sm(img, name) for name in full}
    return {k: np.corrcoef(rank(s[REGOF[k]][REG[k]]), CR[k])[0, 1] for k in REG}


z = lambda k: np.nan_to_num(R[k])  # noqa: E731
D = z("diffuse") @ LUM
t2r = z("t2")[..., 0]
t3 = z("t3")[..., :3]
d1 = z("oD1")
fin = z("final") @ LUM
print(f"check: D + X0 against hakuX's final, max |diff| on the ring "
      f"{np.abs((D + (np.clip(t3 * d1[..., :3], 0, 1) @ LUM) * t2r * d1[..., 3]) - fin)[lid >= 0].max():.4f}")
cfb = {name: float(np.interp(con[full[name]].mean(), cal["ph_L"], cal["fb_L"])) for name in full}
print(f"console in fb units: hull {cfb['hull']:.3f}  band {cfb['band']:.3f}  (blur {BL}; hull core {REG['all'].sum()} px, "
      f"band core {REG['band'].sum()} px)")
print("factors kept       c*    rank r at c*: all   upper  lower  band  | at c=1: all   lower  band | level c=1: hull  band")
CSCAN = np.concatenate([[0], np.geomspace(0.05, 16, 30)])
for keep in itertools.product((True, False), repeat=3):
    k3, krgb, ka = keep
    col = (t3 if k3 else np.ones_like(t3)) * (d1[..., :3] if krgb else 1.0)
    X = (np.clip(col, 0, 1) @ LUM) * t2r * (d1[..., 3] if ka else 1.0)
    best = max(((rr(D + c * X)["all"], c) for c in CSCAN))
    rb, r1 = rr(D + best[1] * X), rr(D + X)
    lv = {name: (D + X)[full[name]].mean() for name in full}
    tag = " ".join(f for f, k in zip(("t3", "oD1.rgb", "oD1.a"), keep) if k) or "(t2.r only)"
    print(f"{tag:18s} {best[1]:5.2f}   {rb['all']:+.3f} {rb['upper']:+.3f} {rb['lower']:+.3f} {rb['band']:+.3f} |"
          f" {r1['all']:+.3f} {r1['lower']:+.3f} {r1['band']:+.3f} |   {lv['hull']:.3f} {lv['band']:.3f}", flush=True)
