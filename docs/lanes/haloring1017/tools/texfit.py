"""texfit.py RENDER REG OVERLAY CAL [blur=3]: what texture the console's hull follows, per cube face (#939, (a), M9).

Inside one cube face the pooled terms (D, W, t2.r) leave the console's excess flat. The console still shows a
mottled layer there, so something varies with it: each texture channel and the hull's products are fitted
alone against the console (and against c - h) on each face's core pixels, R2 reported."""
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
T = {k: np.nan_to_num(R[k]) for k in ("t0", "t1", "t2", "t3", "oD0", "oD1")}
ch = {}
for k in ("t0", "t1", "t2", "t3"):
    for i, cn in enumerate("rgba"):
        if T[k].shape[-1] > i:
            ch[f"{k}.{cn}"] = T[k][..., i]
ch["t0 lum"] = T["t0"][..., :3] @ LUM
ch["t1 lum"] = T["t1"][..., :3] @ LUM
ch["2 t0 t1"] = np.clip(2 * T["t0"][..., :3] * T["t1"][..., :3], 0, 1) @ LUM
ch["oD0"] = T["oD0"][..., :3] @ LUM
ch["oD1.a"] = T["oD1"][..., 3]
ch["D"] = np.nan_to_num(R["diffuse"]) @ LUM
ch["X0"] = np.nan_to_num(R["refl"]) @ LUM
ch["hakuX"] = np.nan_to_num(R["final"]) @ LUM
ch["2t0t1 t2.r"] = ch["2 t0 t1"] * ch["t2.r"]
ch["2t0t1 t2.b"] = ch["2 t0 t1"] * ch["t2.b"]
ch["t0 t2.r"] = ch["t0 lum"] * ch["t2.r"]
ch["t1 t2.r"] = ch["t1 lum"] * ch["t2.r"]
h = ch["hakuX"]
for L, name in ((1, "hull n5"), (0, "band n4")):
    for f in range(6):
        full = (lid == L) & base & (face == f)
        if full.sum() < 1500:
            continue
        den = boxblur(full.astype(float), BL)
        core = full & (den > 0.6)
        mean = lambda img: (boxblur(np.where(full, img, 0), BL) / np.maximum(den, 1e-9))[core]  # noqa: E731
        c = mean(con)
        e = c - mean(h)
        print(f"{name} face {f}: {core.sum()} px, console {c.mean():.3f} sd {c.std():.3f}, c-h {e.mean():+.3f} sd {e.std():.3f}")
        rows = []
        for k, img in ch.items():
            x = mean(img)
            if x.std() < 1e-6:
                continue
            rc = np.corrcoef(x, c)[0, 1]
            re = np.corrcoef(x, e)[0, 1]
            rows.append((abs(rc), k, x.mean(), x.std(), rc, re))
        for _, k, m, s, rc, re in sorted(rows, reverse=True)[:12]:
            print(f"   {k:12s} mean {m:.3f} sd {s:.3f}   corr with console {rc:+.3f}   with c-h {re:+.3f}")
