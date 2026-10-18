"""Gain or added layer: the console's hull binned by lighting and by the cube (#939, (a), M8).

usage: unlitjudge.py RENDER.npz REG.npz OVERLAY.png CAL.npz [blur=3] [frame=VIDEO.ppm]

M7 left two accounts of the console's brighter hull at photo 5's pose:
  R10    console = g x D + X0       (the diffuse counts for ~1.4x more)
  R1/R9  console = D + X0 + k x t2.r (a t2.r-shaped layer, not gated by the cube)
with D = 2 t0 t1 (oD0 + t2.g) and X0 = cube(R) oD1.rgb t2.r oD1.a, hullsw.py's
terms. At photo 5 the hull is lit everywhere and D and t2.r correlate at 0.79,
so the two fit equally. They part where D is low and t2.r is not: under R10 the
console stays at ~1.4x a dark hakuX there, under R1/R9 it sits ~k x t2.r above
it. So the hull's core pixels (as transfer.py: overlays, the display's border
and edges out, BLUR px box mean) are binned by the lighting oD0, by D, and by
the cube term X0, and both models are fitted on all of them, their residuals
reported per bin. The console is read in fb units through CAL.npz's L curve
(photocal.py on hakuX's own video frame at the photo's pose).
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


ovm = boxblur((ov > 0.06).astype(float), 2) > 0
base = ~ovm & (warped.sum(2) > 0)
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
lid = R["lid"]
terms = {
    "hakuX": np.nan_to_num(R["final"]) @ LUM,
    "D": np.nan_to_num(R["diffuse"]) @ LUM,
    "X0": np.nan_to_num(R["refl"]) @ LUM,
    "t2r": np.nan_to_num(R["t2"])[..., 0],
    "oD0": np.nan_to_num(R["oD0"])[..., :3] @ LUM,
    "console": con,
}
if "frame" in opt:
    terms["video"] = ppm_l(opt["frame"])

for name, L in (("hull n5", 1), ("band n4", 0)):
    full = (lid == L) & base
    den = boxblur(full.astype(float), BL)
    core = full & (den > 0.5)
    if core.sum() < 200:
        print(f"{name}: core {core.sum()} px, too few")
        continue
    v = {k: (boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9))[core] for k, img in terms.items()}
    c, h, D, X0, t2r = v["console"], v["hakuX"], v["D"], v["X0"], v["t2r"]
    print(f"{name}: core {core.sum()} px; console {c.mean():.3f}, hakuX {h.mean():.3f}"
          + (f", video {v['video'].mean():.3f}" if "video" in v else "")
          + f"; D {D.mean():.3f}, X0 {X0.mean():.3f}, t2.r {t2r.mean():.3f}, oD0 {v['oD0'].mean():.3f}"
          + f" (p10 {np.percentile(v['oD0'], 10):.3f}, p90 {np.percentile(v['oD0'], 90):.3f})")
    # the two models, each with a constant (the curve's floor is uncertain)
    A = np.stack([D, np.ones_like(D)], 1)
    gR10, bR10 = np.linalg.lstsq(A, c - X0, rcond=None)[0]
    pR10 = gR10 * D + X0 + bR10
    A = np.stack([t2r, np.ones_like(D)], 1)
    kR1, bR1 = np.linalg.lstsq(A, c - D - X0, rcond=None)[0]
    pR1 = D + X0 + kR1 * t2r + bR1
    A = np.stack([D, X0, t2r, np.ones_like(D)], 1)
    free = np.linalg.lstsq(A, c, rcond=None)[0]
    pF = A @ free

    def r2(p):
        return 1 - ((c - p) ** 2).sum() / ((c - c.mean()) ** 2).sum()

    print(f"   R10: console = {gR10:.2f} D + X0 {bR10:+.3f}   R2 {r2(pR10):.3f}")
    print(f"   R1 : console = D + X0 + {kR1:.2f} t2.r {bR1:+.3f}   R2 {r2(pR1):.3f}")
    print(f"   free: {free[0]:.2f} D + {free[1]:.2f} X0 + {free[2]:.2f} t2.r {free[3]:+.3f}   R2 {r2(pF):.3f}")
    print(f"   corr(D, t2.r) {np.corrcoef(D, t2r)[0, 1]:.3f}, corr(D, oD0) {np.corrcoef(D, v['oD0'])[0, 1]:.3f}")
    # both at once, X0 kept at hakuX's weight: console - X0 = g D + k t2.r + b. R10 is (g ~1.4, k 0),
    # R1/R9 (g 1, k > 0). Neighbouring pixels share texels and blur, so the spread is a bootstrap over
    # 24 px blocks, not the per-pixel standard error.
    ys, xs = np.nonzero(core)
    blk = (ys // 24) * 1000 + xs // 24
    ub, inv = np.unique(blk, return_inverse=True)

    def boot(A, y):
        rng = np.random.default_rng(939)
        bs = []
        for _ in range(400):
            sw = np.sqrt(np.bincount(rng.integers(0, len(ub), len(ub)), minlength=len(ub))[inv].astype(float))
            bs.append(np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)[0])
        return np.linalg.lstsq(A, y, rcond=None)[0], np.percentile(np.array(bs), [2.5, 97.5], axis=0)

    (g2, k2, b2), (lo, hi) = boot(np.stack([D, t2r, np.ones_like(D)], 1), c - X0)
    print(f"   joint: console - X0 = {g2:.2f} D + {k2:.2f} t2.r {b2:+.3f}; {len(ub)} blocks, 95%: "
          f"g {lo[0]:.2f}..{hi[0]:.2f}, k {lo[1]:.2f}..{hi[1]:.2f}")
    # X0 free as well: a console response convex in hakuX's own value would load on X0 (weight > 1),
    # which is t2.r-weighted, rather than on t2.r alone
    fr, (lo, hi) = boot(np.stack([D, X0, t2r, np.ones_like(D)], 1), c)
    print(f"   free, bootstrapped: D {fr[0]:.2f} ({lo[0]:.2f}..{hi[0]:.2f}), X0 {fr[1]:.2f} ({lo[1]:.2f}..{hi[1]:.2f}),"
          f" t2.r {fr[2]:.2f} ({lo[2]:.2f}..{hi[2]:.2f})")
    for key in ("oD0", "D", "X0"):
        x = v[key]
        qs = np.quantile(x, np.linspace(0, 1, 6))
        print(f"   by {key}: bin           n   console  hakuX  ratio  c-h    t2.r   resid R10  resid R1")
        for a, b in zip(qs[:-1], qs[1:]):
            s = (x >= a) & (x <= b)
            cm, hm = c[s].mean(), h[s].mean()
            print(f"      {a:.3f}-{b:.3f} {s.sum():6d}   {cm:.3f}   {hm:.3f}  {cm / max(hm, 1e-6):5.2f} {cm - hm:+.3f}  "
                  f"{t2r[s].mean():.3f}   {(c - pR10)[s].mean():+.4f}    {(c - pR1)[s].mean():+.4f}")
    # within each D bin, the pixels split at that bin's t2.r median: under R10 the excess c - h is
    # D's alone and the two halves agree; under R1/R9 the high-t2.r half carries more
    qs = np.quantile(D, np.linspace(0, 1, 6))
    print("   within D bins, t2.r low half | high half:  t2.r        c-h")
    for a, b in zip(qs[:-1], qs[1:]):
        s = (D >= a) & (D <= b)
        m = np.median(t2r[s])
        lo_, hi_ = s & (t2r <= m), s & (t2r > m)
        print(f"      D {a:.3f}-{b:.3f}: {t2r[lo_].mean():.3f} | {t2r[hi_].mean():.3f}   "
              f"{(c - h)[lo_].mean():+.3f} | {(c - h)[hi_].mean():+.3f}")
    # the discriminating pixels: D low, t2.r high (and the reverse)
    dq, tq = np.quantile(D, [0.3, 0.7]), np.quantile(t2r, [0.3, 0.7])
    for lab, s in (("D low, t2.r high", (D <= dq[0]) & (t2r >= tq[1])),
                   ("D high, t2.r low", (D >= dq[1]) & (t2r <= tq[0]))):
        if s.sum():
            print(f"   {lab}: n {s.sum()}, console {c[s].mean():.3f}, hakuX {h[s].mean():.3f}, "
                  f"R10 pred {pR10[s].mean():.3f}, R1 pred {pR1[s].mean():.3f}")
