"""glarefit.py RENDER REG OVERLAY CAL VIDEO.ppm [gamma=2.2]: is the photo's position term veiling glare? (#939, (a), M10)

A camera, and a TV's local dimming, add to each pixel a wide blur of the bright picture around it. That lifts dark
pixels near bright ones and greys them, which is how the console's hull reads beside hakuX's. On the space background,
which is the same picture on both machines, the photo read through CAL minus hakuX's video frame is fitted, in linear
light (fb ** gamma), on a Gaussian blur G_s of hakuX's whole frame for several widths s, and on screen x and y. The
background's best glare coefficient then predicts how much of the hull's excess, per cube face, is glare. Errors are
a block bootstrap over 24 px blocks."""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf, vidf = sys.argv[1:6]
opt = dict(a.split("=", 1) for a in sys.argv[6:])
GAM = float(opt.get("gamma", 2.2))
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


def gauss(img, s):
    """Three box passes of radius ~ s * 0.9 approximate a Gaussian of sd s; normalised at the frame's edges."""
    r = max(1, int(round(s * 0.9)))
    num, den = img, np.ones_like(img)
    for _ in range(3):
        num, den = boxblur(num, r), boxblur(den, r)
    return num / den


vid = ppm_l(vidf)
lid = R["lid"]
h = np.nan_to_num(R["final"]) @ LUM
src = np.where(lid >= 0, h, vid)  # hakuX's whole frame: the render on the ring, the video elsewhere
lin = lambda v: np.clip(v, 0, 1) ** GAM  # noqa: E731
src_l = lin(src)
ovm = boxblur((ov > 0.06).astype(float), 2) > 0
base = ~ovm & (warped.sum(2) > 0)
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
ring = boxblur((lid >= 0).astype(float), 4) > 0
bg = base & ~ring
yy, xx = np.mgrid[0:480, 0:640]
blk = (yy // 24) * 100 + xx // 24
rng = np.random.default_rng(939)


def fit(y, cols, w_blk, nboot=200):
    A = np.stack(cols + [np.ones_like(y)], 1)
    co = np.linalg.lstsq(A, y, rcond=None)[0]
    r2 = 1 - ((y - A @ co) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    ub = np.unique(w_blk)
    idx = {b: np.nonzero(w_blk == b)[0] for b in ub}
    boots = []
    for _ in range(nboot):
        pick = np.concatenate([idx[b] for b in rng.choice(ub, len(ub))])
        boots.append(np.linalg.lstsq(A[pick], y[pick], rcond=None)[0])
    lo, hi = np.percentile(np.array(boots), [2.5, 97.5], axis=0)
    return co, lo, hi, r2


SIG = (6, 12, 24, 48, 96)
G = {s: gauss(src_l, s) for s in SIG}
e_bg = lin(con)[bg] - lin(vid)[bg]
print(f"space background: {bg.sum()} px, linear (gamma {GAM}); photo - video mean {e_bg.mean():+.4f} sd {e_bg.std():.4f}")
print("   e = beta * G_s(frame) + c, and against screen position")
best = None
for s in SIG:
    co, lo, hi, r2 = fit(e_bg, [G[s][bg]], blk[bg])
    print(f"   s {s:3d} px: beta {co[0]:+.4f} ({lo[0]:+.4f} .. {hi[0]:+.4f})  c {co[1]:+.4f}  R2 {r2:.3f}"
          f"   G mean {G[s][bg].mean():.4f}")
    if best is None or r2 > best[3]:
        best = (s, co, (lo, hi), r2)
xn, yn = xx / 640.0, yy / 480.0
co, lo, hi, r2 = fit(e_bg, [xn[bg], yn[bg]], blk[bg])
print(f"   x, y: {np.round(co, 4)}  R2 {r2:.3f}")
co, lo, hi, r2 = fit(e_bg, [G[best[0]][bg], xn[bg], yn[bg]], blk[bg])
print(f"   G_{best[0]} + x + y: beta {co[0]:+.4f} ({lo[0]:+.4f} .. {hi[0]:+.4f}), x {co[1]:+.4f}, y {co[2]:+.4f}  R2 {r2:.3f}")

s, bco = best[0], best[1]
face = np.nan_to_num(R["face"][..., 0], nan=-1).astype(int)
full = (lid == 1) & base
den = boxblur(full.astype(float), 3)
core = full & (den > 0.6)
mean = lambda img: (boxblur(np.where(full, img, 0), 3) / np.maximum(den, 1e-9))[core]  # noqa: E731
c_l, h_l, g_l = mean(lin(con)), mean(lin(h)), mean(G[s])
e_l = c_l - h_l
pred = bco[0] * g_l + bco[1]
print(f"hull core: {core.sum()} px. Excess in linear light, and the background's G_{s} fit's prediction there")
fc = face[core]
for lab, sel in (("all", np.ones_like(fc, bool)), ("face 0", fc == 0), ("face 3", fc == 3), ("face 5", fc == 5)):
    if sel.sum() < 300:
        continue
    print(f"   {lab:7s} n {sel.sum():6d}  excess {e_l[sel].mean():+.4f}  G {g_l[sel].mean():.4f}  "
          f"predicted glare {pred[sel].mean():+.4f}  left {e_l[sel].mean() - pred[sel].mean():+.4f}  "
          f"(hakuX {h_l[sel].mean():.4f}, console {c_l[sel].mean():.4f})")
co, lo, hi, r2 = fit(e_l, [g_l], blk[core])
print(f"   hull alone, e = beta G_{s} + c: beta {co[0]:+.4f} ({lo[0]:+.4f} .. {hi[0]:+.4f})  c {co[1]:+.4f}  R2 {r2:.3f}")
co, lo, hi, r2 = fit(c_l, [h_l, g_l], blk[core])
print(f"   hull, console = a h + beta G_{s} + c: a {co[0]:.3f} ({lo[0]:.3f} .. {hi[0]:.3f}), "
      f"beta {co[1]:+.4f} ({lo[1]:+.4f} .. {hi[1]:+.4f}), c {co[2]:+.4f}  R2 {r2:.3f}")

# Vignetting and a TV's uneven backlight are gains, not additions: photo = v(x, y) * scene. On the background,
# e = vid * (g0 + gx x + gy y) + c; the same v then predicts the hull's excess as h * (v - 1).
vb = lin(vid)[bg]
co, lo, hi, r2 = fit(e_bg, [vb, vb * xn[bg], vb * yn[bg]], blk[bg])
print(f"background, multiplicative: e = vid (g0 + gx x + gy y) + c: g0 {co[0]:+.3f} ({lo[0]:+.3f} .. {hi[0]:+.3f}), "
      f"gx {co[1]:+.3f} ({lo[1]:+.3f} .. {hi[1]:+.3f}), gy {co[2]:+.3f} ({lo[2]:+.3f} .. {hi[2]:+.3f}), "
      f"c {co[3]:+.4f}  R2 {r2:.3f}")
gain = co[0] + co[1] * xn[core] + co[2] * yn[core]
pv = h_l * gain
for lab, sel in (("all", np.ones_like(fc, bool)), ("face 0", fc == 0), ("face 3", fc == 3), ("face 5", fc == 5)):
    if sel.sum() < 300:
        continue
    print(f"   {lab:7s} gain - 1 {gain[sel].mean():+.3f}  predicted {pv[sel].mean():+.4f} of excess "
          f"{e_l[sel].mean():+.4f}  console / hakuX {c_l[sel].mean() / h_l[sel].mean():.2f}")
for a, b in zip([15, 160, 320, 480], [160, 320, 480, 640]):
    s_ = bg & (xx >= a) & (xx < b)
    hi_ = s_ & (lin(vid) > np.percentile(lin(vid)[s_], 90))
    print(f"   background x {a:3d}-{b:3d}: photo / video in its brightest tenth {lin(con)[hi_].mean() / lin(vid)[hi_].mean():.2f}"
          f"  (n {hi_.sum()}, video {lin(vid)[hi_].mean():.4f})")
