"""Which combiner term is the console's hull made of? (#939, (a))

usage: photojudge.py DUMP.jsonl RAM.bin FRAME REG.npz OVERLAY.png OUTDIR [blur=3] [step0=0.002] [step1=0.0003]

FRAME is the dump frame with the photo's camera pose (posefit.py). The
photo (photoreg.py's warp, frame pixels) is compared with hullsw.py's
render of the hull (n5) at that frame, on the hull's pixels, off the
overlays (OVERLAY.png > 0.06, grown 2 px) and the display's cropped border.

The ring's turn is a texture scroll (M1), and the photo's scroll phase is
not the dump's: the camera loops, the ring takes ~34 min a turn. So every
scroll-dependent term is scanned over the phase d added to oT0.x:
  - t0 and t2 (1024x512, period 1 in d) at step0 over [0, 1);
  - t1 (oT1 = 10 x oT0, period 0.1) at step1 over [0, 0.1).
At each d, the console's luminance and the term's are correlated after a
box blur of `blur` px inside the hull mask (so registration error of a few
px does not decide it). The scroll-free terms (the cube t3, oD0, oD1, the
reflection without its t2.r mask) are correlated once. Region rows: all,
upper (y < 300: the console is dark with lights there), lower.

Writes OUTDIR/judge_<FRAME>.tsv (term, region, d, r) and a summary.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullsw as hs  # noqa: E402

dump, ramf, frame, regf, ovf, outdir = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6]
opt = dict(a.split("=", 1) for a in sys.argv[7:])
BL = int(opt.get("blur", 3))
LUM = np.array([0.299, 0.587, 0.114])
ram = open(ramf, "rb").read()
S = {}
R = hs.render(dump, ram, frame, state=S)
os.makedirs(outdir, exist_ok=True)
np.savez_compressed(os.path.join(outdir, f"render_{frame}.npz"), **R)
p = S[1]
con = np.load(regf)["warped"] @ LUM
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def boxblur(img, r):
    if r < 1:
        return img
    out = img
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if a == ax else (0, 0) for a in range(2)]), axis=ax)
        n = out.shape[ax]
        out = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, np.arange(0, n), axis=ax)
    return out


ovm = boxblur((ov > 0.06).astype(float), 2) > 0
mask = (R["lid"] == 1) & ~ovm
mask[452:, :] = False
mask[:, :15] = False
mask[:30, :70] = False
ys, xs = np.nonzero(mask)
den = boxblur(mask.astype(float), BL)
keep = den[ys, xs] > 0.5
REG = {"all": np.ones(len(ys), bool), "upper": ys < 300, "lower": ys >= 300}
print(f"f{frame}: hull px {len(ys)} (upper {REG['upper'].sum()}, lower {REG['lower'].sum()})", flush=True)


def smooth(vals):
    g = np.zeros((hs.H, hs.W))
    g[ys, xs] = vals
    return (boxblur(g, BL) / np.maximum(den, 1e-9))[ys, xs]


C = smooth(con[ys, xs])


def corr(v):
    s = smooth(v)
    return {k: np.corrcoef(s[m & keep], C[m & keep])[0, 1] for k, m in REG.items()}


T0 = R["T0"][ys, xs]
lod0, lod1 = R["lod0"][ys, xs, 0], R["lod1"][ys, xs, 0]
t3 = R["t3"][ys, xs]
oD0, oD1 = R["oD0"][ys, xs], R["oD1"][ys, xs]
ch = {s: p["tex"][s][0] for s in range(3)}
c12 = p["C"][12, :2]

rows = []


def term_maps(d, which):
    u, v = T0[:, 0] + d, T0[:, 1]
    out = {}
    if "t0" in which or "t2" in which:
        t0 = hs.trilinear(ch[0], u, v, lod0)
        t2 = hs.trilinear(ch[2], u, v, lod0)
        out["t0"] = t0[:, :3] @ LUM
        out["t2r"], out["t2g"] = t2[:, 0], t2[:, 1]  # t2.b is constant on this map
        out["refl_masked"] = (t3[:, :3] * oD1[:, :3]) @ LUM * t2[:, 0] * oD1[:, 3]
    if "t1" in which:
        t1 = hs.trilinear(ch[1], u * c12[0], v * c12[1], lod1)
        out["t1"] = t1[:, :3] @ LUM
    return out


# scroll-free terms
fixed = {"final@dump": R["final"][ys, xs] @ LUM, "cube": t3[:, :3] @ LUM, "oD0": oD0[:, :3] @ LUM,
         "oD1": oD1[:, :3] @ LUM, "cube*oD1": (t3[:, :3] * oD1[:, :3]) @ LUM}
for k, v in fixed.items():
    rs = corr(v)
    rows += [(k, reg, "", r) for reg, r in rs.items()]
    print(f"  {k:12s} " + " ".join(f"{reg} {r:+.3f}" for reg, r in rs.items()), flush=True)

scan = {}
for d in np.arange(0, 1, float(opt.get("step0", 0.002))):
    for k, v in term_maps(d, ("t0",)).items():
        for reg, r in corr(v).items():
            scan.setdefault((k, reg), []).append((d, r))
for d in np.arange(0, 0.1, float(opt.get("step1", 0.0003))):
    for k, v in term_maps(d, ("t1",)).items():
        for reg, r in corr(v).items():
            scan.setdefault((k, reg), []).append((d, r))
with open(os.path.join(outdir, f"judge_{frame}.tsv"), "w") as fh:
    fh.write("term\tregion\td\tr\n")
    for k, reg, d, r in rows:
        fh.write(f"{k}\t{reg}\t{d}\t{r:.4f}\n")
    for (k, reg), lst in scan.items():
        for d, r in lst:
            fh.write(f"{k}\t{reg}\t{d:.5f}\t{r:.4f}\n")
print("scanned terms: best |r| over the phase, and the spread of r (a peak far above the spread is a match):")
for (k, reg), lst in sorted(scan.items()):
    a = np.array(lst)
    i = int(np.argmax(np.abs(a[:, 1])))
    print(f"  {k:12s} {reg:5s} best d {a[i, 0]:.5f} r {a[i, 1]:+.3f}  median |r| {np.median(np.abs(a[:, 1])):.3f} "
          f"p95 |r| {np.percentile(np.abs(a[:, 1]), 95):.3f}", flush=True)
