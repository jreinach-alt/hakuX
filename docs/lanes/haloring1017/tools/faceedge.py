"""faceedge.py RENDER REG OVERLAY CAL FA FB [blur=2] [reach=48]: does the excess step where hakuX's R crosses a cube edge? (#939, (a), M10)

On photo 5 cube face 3 is also the photo's lower right, which the photo itself reads brighter (R11), so a per-face
excess cannot say which. A cube edge is a sharp line on screen; the photo's position term, the lighting and the
textures are smooth across it. So the console's excess c - h is binned by signed distance from the FA|FB edge
(negative inside FA), on the hull's core, with hakuX's own final h, diffuse D and reflection X0 binned the same way.
A step in c - h at 0 is the console's cube term differing between the two faces; a ramp through 0 is not. Each side's
fit is a line in distance on [-reach, -4] and [4, reach]; the step is their difference at 0, with a block bootstrap
over 24 px blocks.

units=photo judges in the photo's own units instead: c is the photo's luma and h is hakuX's final put through CAL's
forward curve (fb -> photo). The curve flattens at its top (fb 0.39-0.44 is photo 0.65-0.67 on photo 5), so inverting
it there multiplies photo noise; going forward instead can only shrink a step that saturates, never grow one."""
import sys

import numpy as np
from PIL import Image

rendf, regf, ovf, calf = sys.argv[1:5]
FA, FB = int(sys.argv[5]), int(sys.argv[6])
opt = dict(a.split("=", 1) for a in sys.argv[7:])
BL = int(opt.get("blur", 2))
REACH = int(opt.get("reach", 48))
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
cal = np.load(calf)
warped = np.load(regf)["warped"]
PHOTO = opt.get("units", "fb") == "photo"
con = warped @ LUM if PHOTO else np.interp(warped @ LUM, cal["ph_L"], cal["fb_L"])
ov =np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def boxblur(img, r):
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


def dist_to(mask, steps):
    """City-block-ish distance (8-neighbour dilation steps) from each pixel to the mask, capped at steps + 1."""
    d = np.full(mask.shape, steps + 1, dtype=np.int32)
    cur = mask.copy()
    d[cur] = 0
    for k in range(1, steps + 1):
        nxt = cur.copy()
        nxt[1:, :] |= cur[:-1, :]
        nxt[:-1, :] |= cur[1:, :]
        nxt[:, 1:] |= cur[:, :-1]
        nxt[:, :-1] |= cur[:, 1:]
        nxt[1:, 1:] |= cur[:-1, :-1]
        nxt[:-1, :-1] |= cur[1:, 1:]
        nxt[1:, :-1] |= cur[:-1, 1:]
        nxt[:-1, 1:] |= cur[1:, :-1]
        d[nxt & ~cur] = k
        cur = nxt
    return d


ovm = boxblur((ov > 0.06).astype(float), 2) > 0
base = ~ovm & (warped.sum(2) > 0)
base[452:, :] = False
base[:, :15] = False
base[:30, :70] = False
base[:, 585:] = False
lid = R["lid"]
face = np.nan_to_num(R["face"][..., 0], nan=-1).astype(int)
hull = lid == 1
A, B = hull & (face == FA), hull & (face == FB)
dA, dB = dist_to(A, REACH + 4), dist_to(B, REACH + 4)
sd = np.where(A, -dB, np.where(B, dA, 10 ** 6)).astype(float)  # negative inside FA
judged = base & (A | B)
# blur each side separately so no bin mixes the two faces
hfin = np.nan_to_num(R["final"]) @ LUM
if PHOTO:
    hfin = np.interp(hfin, cal["fb_L"], cal["ph_L"])
terms = {"c": con, "h": hfin, "D": np.nan_to_num(R["diffuse"]) @ LUM,
         "X0": np.nan_to_num(R["refl"]) @ LUM, "t2.r": np.nan_to_num(R["t2"])[..., 0]}
sm = {k: np.zeros((480, 640)) for k in terms}
ok = np.zeros((480, 640), bool)
for side in (A, B):
    m = judged & side
    den = boxblur(m.astype(float), BL)
    ok |= m & (den > 0.5 * (2 * BL + 1) ** 2)
    for k, img in terms.items():
        sm[k] = np.where(m, boxblur(np.where(m, img, 0), BL) / np.maximum(den, 1e-9), sm[k])
sel = ok & (np.abs(sd) <= REACH)
print(f"edge face {FA} | face {FB}: {(sel & A).sum()} px on {FA}'s side, {(sel & B).sum()} on {FB}'s, within {REACH} px; "
      f"blur {BL} per side; c and h in {'photo' if PHOTO else 'fb'} units")
print(" dist    n     c - h      c       h       D      X0     t2.r")
for a in range(-REACH, REACH, 4):
    s = sel & (sd >= a) & (sd < a + 4)
    if s.sum() < 30:
        continue
    print(f" {a:+4d} {s.sum():5d}   {(sm['c'] - sm['h'])[s].mean():+.4f}  {sm['c'][s].mean():.4f}  {sm['h'][s].mean():.4f}  "
          f"{sm['D'][s].mean():.4f}  {sm['X0'][s].mean():.4f}  {sm['t2.r'][s].mean():.4f}")
yy, xx = np.mgrid[0:480, 0:640]
blk = ((yy // 24) * 100 + xx // 24)
rng = np.random.default_rng(939)


def step(key):
    y = (sm["c"] - sm["h"]) if key == "excess" else sm[key]
    L = sel & A & (sd <= -4)
    Rr = sel & B & (sd >= 4)
    at0 = [np.polyval(np.polyfit(sd[m], y[m], 1), 0.0) for m in (L, Rr)]
    return at0[1] - at0[0]


def boot(key, n=300):
    y = (sm["c"] - sm["h"]) if key == "excess" else sm[key]
    L = sel & A & (sd <= -4)
    Rr = sel & B & (sd >= 4)
    bl = blk[L | Rr]
    ub = np.unique(bl)
    flat_idx = np.nonzero((L | Rr).ravel())[0]
    by = {b: flat_idx[bl == b] for b in ub}
    yv, dv, Lv = y.ravel(), sd.ravel(), L.ravel()
    res = []
    for _ in range(n):
        pick = np.concatenate([by[b] for b in rng.choice(ub, len(ub))])
        pl, pr = pick[Lv[pick]], pick[~Lv[pick]]
        if len(pl) < 20 or len(pr) < 20:
            continue
        cl = np.polyfit(dv[pl], yv[pl], 1)
        cr = np.polyfit(dv[pr], yv[pr], 1)
        res.append(np.polyval(cr, 0.0) - np.polyval(cl, 0.0))
    return np.percentile(res, [2.5, 97.5])


print(f"step at the edge (face {FB}'s side minus face {FA}'s, each side's line taken to 0):")
for key in ("excess", "c", "h", "D", "X0", "t2.r"):
    lo, hi = boot(key)
    print(f"   {key:6s} {step(key):+.4f}  ({lo:+.4f} .. {hi:+.4f})")
