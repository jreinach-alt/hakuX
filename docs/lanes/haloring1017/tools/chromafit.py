"""The colour of the console's excess over hakuX, per channel, against each term's colour (#939, (a), M7).

usage: chromafit.py RENDER.npz REG.npz OVERLAY.png CAL.npz [blur=3]

The photo is read back to fb units per channel through CAL.npz's ph_R/G/B ->
fb_R/G/B curves (photocal.py on the space background against hakuX's own
video frame, M7), so the camera's cast is the space background's and drops
out. Both images are box blurred inside each draw's core. Printed per draw:
the console's and hakuX's mean rgb and chroma (r/g, b/g), the excess
(console - hakuX) per channel, the excess per quartile of hakuX's luminance,
and each of hakuX's terms' own chroma. Then the excess, all three channels
stacked, is fitted by least squares as a sum of candidate terms (each a
per-pixel rgb image) with a grey constant: a term whose colour is not the
excess's cannot carry it in three channels at once, which a luminance fit
(termfit.py) cannot see.
"""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf = sys.argv[1:5]
opt = dict(a.split("=", 1) for a in sys.argv[5:])
BL = int(opt.get("blur", 3))
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
cal = np.load(calf)
ph = np.load(regf)["warped"]
con = np.stack([np.interp(ph[..., c], cal["ph_" + k], cal["fb_" + k]) for c, k in enumerate("RGB")], -1)
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(out.ndim)]), axis=ax)
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
t2r = z("t2")[..., :1]
od1 = z("oD1")
terms = {
    "D (diffuse)": z("diffuse"),
    "X0 (reflection)": z("refl"),
    "t2.r*oD1.rgb*oD1.a (cube=1)": t2r * od1[..., :3] * od1[..., 3:4],
    "t2.r*oD1.rgb (cube=1, no a)": t2r * od1[..., :3],
    "t2.r (grey)": np.repeat(t2r, 3, -1),
    "t2.r*t3 (no fresnel)": t2r * z("t3")[..., :3],
    "t0": z("t0")[..., :3],
    "t1": z("t1")[..., :3],
    "t0*t1": z("t0")[..., :3] * z("t1")[..., :3],
}
hx = z("final")


def chroma(v):
    return f"rgb {np.round(v, 3)} r/g {v[0] / max(v[1], 1e-9):.2f} b/g {v[2] / max(v[1], 1e-9):.2f}"


for name, L in (("hull n5", 1), ("band n4", 0)):
    full = (lid == L) & base
    den = boxblur(full.astype(float), BL)
    core = full & (den > 0.5)

    def sm(img):
        return boxblur(np.where(full[..., None], img, 0), BL) / np.maximum(den, 1e-9)[..., None]

    sc, sh = sm(con)[core], sm(hx)[core]
    ex = sc - sh
    print(f"== {name}: {core.sum()} px")
    print(f"   console  {chroma(sc.mean(0))}")
    print(f"   hakuX    {chroma(sh.mean(0))}")
    print(f"   excess   rgb {ex.mean(0).round(3)}  (console/hakuX per channel {np.round(sc.mean(0) / sh.mean(0), 2)})")
    hl = sh @ LUM
    q = np.quantile(hl, [0, .25, .5, .75, 1])
    for a, b in zip(q[:-1], q[1:]):
        s = (hl >= a) & (hl <= b)
        print(f"   hakuX L {a:.3f}-{b:.3f}: console {chroma(sc[s].mean(0))} | hakuX {chroma(sh[s].mean(0))} | "
              f"excess {ex[s].mean(0).round(3)}")
    T = {k: sm(v)[core] for k, v in terms.items()}
    for k, v in T.items():
        print(f"   term {k:30s} {chroma(v.mean(0))}")
    y = ex.reshape(-1)
    print("   excess (3 channels stacked) = sum of terms + grey constant; least squares:")
    sets = [["D (diffuse)"], ["X0 (reflection)"], ["t2.r*oD1.rgb*oD1.a (cube=1)"], ["t2.r*oD1.rgb (cube=1, no a)"],
            ["t2.r (grey)"], ["t2.r*t3 (no fresnel)"], ["t1"], ["t0*t1"], ["D (diffuse)", "t2.r (grey)"],
            ["D (diffuse)", "t2.r*oD1.rgb (cube=1, no a)"], ["D (diffuse)", "X0 (reflection)"]]
    tot = ((y - y.mean()) ** 2).sum()
    for st in sets:
        A = np.stack([T[k].reshape(-1) for k in st] + [np.ones_like(y)], 1)
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        res = y - A @ coef
        r2 = 1 - (res ** 2).sum() / tot
        # per-channel residual mean: a term of the wrong colour leaves a channel offset
        rc = res.reshape(-1, 3).mean(0)
        print(f"     {' + '.join(st):55s} coef {np.round(coef, 3)}  R2 {r2:+.3f}  channel residual {rc.round(3)}")
