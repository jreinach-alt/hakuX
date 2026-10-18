"""Where on the ring the console exceeds hakuX, in framebuffer units (#939, (a), M7).

usage: excessmap.py RENDER.npz REG.npz OVERLAY.png CAL.npz OUT.png [blur=3] [scale=0.25]

The photo is read back to fb units per pixel through CAL.npz (photocal.py on
the space background, M7), both images are box blurred inside each draw's own
mask, and the difference console - hakuX is drawn on the ring: red where the
console is brighter, blue where it is darker, full colour at +-scale; outside
the ring the photo is shown dim. Left: the console (fb units); middle: hakuX;
right: the difference. Also prints the difference's mean per hakuX-term
quartile: D (2 t0 t1 (oD0 + t2.g)), X0 (the reflection) and t2.r, so an
excess that follows one term shows a slope over that term's quartiles.
"""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf, outf = sys.argv[1:6]
opt = dict(a.split("=", 1) for a in sys.argv[6:])
BL = int(opt.get("blur", 3))
SC = float(opt.get("scale", 0.25))
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
cal = np.load(calf)
ph = np.load(regf)["warped"] @ LUM
con = np.interp(ph, cal["ph_L"], cal["fb_L"])
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
hx = z("final") @ LUM
terms = {"D": z("diffuse") @ LUM, "X0": z("refl") @ LUM, "t2.r": z("t2")[..., 0]}
H, W = hx.shape
cs, hs = np.zeros((H, W)), np.zeros((H, W))
ring = np.zeros((H, W), bool)
for name, L in (("hull n5", 1), ("band n4", 0)):
    full = (lid == L) & base
    den = boxblur(full.astype(float), BL)
    core = full & (den > 0.5)

    def sm(img):
        return boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9)

    sc, sh = sm(con), sm(hx)
    cs[core], hs[core] = sc[core], sh[core]
    ring |= core
    d = (sc - sh)[core]
    print(f"{name}: excess mean {d.mean():+.3f} p10/50/90 {np.percentile(d, [10, 50, 90]).round(3)}")
    for tn, tv in terms.items():
        st = sm(tv)[core]
        q = np.quantile(st, [0, .25, .5, .75, 1])
        parts = []
        for a, b in zip(q[:-1], q[1:]):
            s = (st >= a) & (st <= b)
            parts.append(f"{np.median(st[s]):.3f}:{d[s].mean():+.3f}")
        print(f"   by {tn:5s} quartile (term median: excess mean)  " + "  ".join(parts))
    yy = np.nonzero(core)[0]
    for lo, hi in ((0, 150), (150, 250), (250, 350), (350, 452)):
        s = (yy >= lo) & (yy < hi)
        if s.sum():
            print(f"   rows {lo:3d}-{hi:3d}: {s.sum():6d} px, console {sc[core][s].mean():.3f} hakuX {sh[core][s].mean():.3f} "
                  f"excess {d[s].mean():+.3f}")


def grey(v):
    g = np.clip(v, 0, 1)
    return np.stack([g, g, g], -1)


dim = grey(con * 0.35)
left = np.where(ring[..., None], grey(cs), dim)
mid = np.where(ring[..., None], grey(hs), dim)
dd = np.clip((cs - hs) / SC, -1, 1)
dif = np.stack([np.clip(dd, 0, 1), np.zeros_like(dd), np.clip(-dd, 0, 1)], -1)
right = np.where(ring[..., None], dif, dim)
img = np.concatenate([left, mid, right], 1)
Image.fromarray((img * 255).astype(np.uint8)).save(outf)
print(f"wrote {outf} ({img.shape[1]}x{img.shape[0]}); difference at full colour = {SC}")
