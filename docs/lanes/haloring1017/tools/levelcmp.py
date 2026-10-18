"""Band against hull at equal hakuX value: a test with no tone curve (#939, (a), M6).

usage: levelcmp.py RENDER.npz REG.npz OVERLAY.png [blur=3] [bins=0.05,0.1,...]

The band (`n4`) and the hull (`n5`) run one shader, one combiner and one final
combiner (M3); they differ in their textures and vertices. Photo 5 holds both
at one exposure. So at pixels where hakuX's output has the same value, the
console's photo value can differ between band and hull only if the console's
output differs between them, whatever the camera's tone curve:
  - R3 (v0.a = k, a lerp to white in the final combiner) acts on both draws:
    equal hakuX value -> equal console value, band and hull alike;
  - a cause in the hull's own inputs (its t1 detail map, its t2, its vertex
    data) brightens the hull and not the band: at equal hakuX value the
    console's hull reads above the console's band.
Values are box blurred by `blur` px inside each draw's own mask (overlays and
the cropped border out), so neither side borrows from the other.
"""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf = sys.argv[1:4]
opt = dict(a.split("=", 1) for a in sys.argv[4:])
BL = int(opt.get("blur", 3))
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
con = np.load(regf)["warped"] @ LUM
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255
H, W = con.shape


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
# a draw's pixels away from its own edge by the blur radius (the photo's registration error is ~1-2 px)
fin = np.nan_to_num(R["final"] @ LUM)
edges = [float(v) for v in opt.get("bins", "0.05,0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.5,0.6,0.8,1.0").split(",")]
out = {}
for name, lid in (("band", 0), ("hull", 1)):
    m = (R["lid"] == lid) & base
    core = boxblur((~m).astype(float), BL + 1) == 0
    den = boxblur(m.astype(float), BL)
    h = boxblur(np.where(m, fin, 0), BL) / np.maximum(den, 1e-9)
    c = boxblur(np.where(m, con, 0), BL) / np.maximum(den, 1e-9)
    out[name] = (h[core], c[core])
    print(f"{name}: core px {core.sum()}, hakuX final {np.percentile(h[core], 5):.2f}..{np.percentile(h[core], 95):.2f}")
print("hakuX final bin | band: px, console median (IQR) | hull: px, console median (IQR) | hull - band")
for a, b in zip(edges[:-1], edges[1:]):
    row = []
    meds = {}
    for name in ("band", "hull"):
        h, c = out[name]
        s = (h >= a) & (h < b)
        if s.sum() >= 30:
            q1, q2, q3 = np.percentile(c[s], [25, 50, 75])
            meds[name] = q2
            row.append(f"{s.sum():6d} {q2:.3f} ({q1:.2f}-{q3:.2f})")
        else:
            row.append(f"{s.sum():6d}   -")
    diff = f"{meds['hull'] - meds['band']:+.3f}" if len(meds) == 2 else ""
    print(f"  {a:.2f}-{b:.2f} | " + " | ".join(row) + f" | {diff}")
