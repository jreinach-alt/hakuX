"""gainfield.py RENDER REG OVERLAY CAL VIDEO.ppm [gamma=2.2] [far=40] [blur=3]: is photo 5's hull excess the photo's own gain? (#939, (a), M11)

On the space background both machines draw the same picture, so whatever the photo does to hakuX's pixels there is
the camera, the TV or the display chain, not the ring's draw. glarefit.py's last block fits that as a gain field,
photo - video = video * (g0 + gx x + gy y) + c in linear light, and applies it to hakuX's hull. This puts errors on
that prediction and tries to break it:
  - both sides are box means of radius `blur` inside their own mask, as the hull's are, so that misregistration of
    the fine background art does not dilute the fit toward a gain of -1;
  - the prediction per cube face carries a block bootstrap (24 px blocks): every bootstrap fit predicts the hull;
  - hold-out: the field fitted only on background more than `far` px from the ring;
  - level-only control: photo - video = g1 video + g2 video^2 + c, no position. If it predicts as well, the lift is
    the photo's tone curve at the dark end (still not the ring's draw); if only the position model predicts, it is
    the photo's position term (R11);
  - the band `n4` (lid 0) is judged the same way where it is on screen.
A hull excess inside the prediction's interval is the photo's; one outside it, on a face, is the console's."""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf, vidf = sys.argv[1:6]
opt = dict(a.split("=", 1) for a in sys.argv[6:])
GAM = float(opt.get("gamma", 2.2))
FAR = int(opt.get("far", 40))
BL = int(opt.get("blur", 3))
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


lin = lambda v: np.clip(v, 0, 1) ** GAM  # noqa: E731
vid = ppm_l(vidf)
lid = R["lid"]
h = np.nan_to_num(R["final"]) @ LUM
face = np.nan_to_num(R["face"][..., 0], nan=-1).astype(int)
ovm = boxblur((ov > 0.06).astype(float), 2) > 0
base = ~ovm & (warped.sum(2) > 0)
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
ringd = boxblur((lid >= 0).astype(float), 4) > 0
bg_all = base & ~ringd
yy, xx = np.mgrid[0:480, 0:640]
xn, yn = xx / 640.0, yy / 480.0
blk = (yy // 24) * 100 + xx // 24
rng = np.random.default_rng(939)


def masked_mean(img, m):
    den = boxblur(m.astype(float), BL)
    core = m & (den > 0.6 * (2 * BL + 1) ** 2)
    return boxblur(np.where(m, img, 0), BL) / np.maximum(den, 1e-9), core


cb, bg = masked_mean(lin(con), bg_all)
vb, _ = masked_mean(lin(vid), bg_all)
farm = bg & ~(boxblur((lid >= 0).astype(float), FAR) > 0)


def design(v, m, kind):
    if kind == "position":
        return [v[m], v[m] * xn[m], v[m] * yn[m]]
    return [v[m], v[m] ** 2]


def fit(m, kind, nboot=300):
    y = cb[m] - vb[m]
    A = np.stack(design(vb, m, kind) + [np.ones(m.sum())], 1)
    co = np.linalg.lstsq(A, y, rcond=None)[0]
    r2 = 1 - ((y - A @ co) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    w = blk[m]
    ub = np.unique(w)
    idx = {b: np.nonzero(w == b)[0] for b in ub}
    boots = [np.linalg.lstsq(A[p], y[p], rcond=None)[0]
             for p in (np.concatenate([idx[b] for b in rng.choice(ub, len(ub))]) for _ in range(nboot))]
    return co, np.array(boots), r2


def predict(co, v, m, kind):
    """The model's excess at m, given hakuX's own linear value v there."""
    cols = design(v, m, kind)
    return sum(c * col for c, col in zip(co, cols)) + co[-1]


judged = {}
for lab, l_ in (("hull n5", 1), ("band n4", 0)):
    full = (lid == l_) & base
    c_l, core = masked_mean(lin(con), full)
    h_l, _ = masked_mean(lin(h), full)
    if core.sum() < 300:
        print(f"{lab}: {core.sum()} px on screen, not judged")
        continue
    judged[lab] = (core, c_l, h_l)

print(f"space background: {bg.sum()} px ({farm.sum()} more than {FAR} px from the ring); box means radius {BL}; "
      f"linear light, gamma {GAM}")
for kind, m, name in (("position", bg, "position, all background"), ("position", farm, f"position, background > {FAR} px off"),
                      ("level", bg, "level only (no position), all background")):
    co, boots, r2 = fit(m, kind)
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    terms = "  ".join(f"{c:+.3f} ({a:+.3f} .. {b:+.3f})" for c, a, b in zip(co, lo, hi))
    print(f"\n{name}: R2 {r2:.3f}; coefficients (gain terms, then c): {terms}")
    for lab, (core, c_l, h_l) in judged.items():
        fc = face[core]
        groups = [("all", np.ones_like(fc, bool))] + [(f"face {f}", fc == f) for f in (0, 3, 5) if lab == "hull n5"]
        for g, sel in groups:
            if sel.sum() < 300:
                continue
            ex = (c_l - h_l)[core][sel].mean()
            pv = predict(co, h_l, core, kind)[sel].mean()
            bp = np.array([predict(b, h_l, core, kind)[sel].mean() for b in boots])
            plo, phi = np.percentile(bp, [2.5, 97.5])
            inside = "inside" if plo <= ex <= phi else "OUTSIDE"
            print(f"   {lab} {g:7s} n {sel.sum():6d}  excess {ex:+.4f}  predicted {pv:+.4f} ({plo:+.4f} .. {phi:+.4f})  "
                  f"{inside}   hakuX {h_l[core][sel].mean():.4f} console {c_l[core][sel].mean():.4f}")
