"""Which model of the hull's output is the console's? (#939, (a), M6)

usage: termfit.py DUMP.jsonl RAM.bin FRAME REG.npz OVERLAY.png [blur=3] [save=TSV]

The photo's tone curve is unknown in detail (photocal.py), so models are
compared by Spearman (rank) correlation with the console's luminance on the
hull's pixels: a monotone tone curve leaves ranks alone. Both sides are box
blurred by `blur` px inside the hull mask (photojudge.py's mask: overlays out,
the display's cropped border out). The photo is at FRAME's pose and scroll
(M5), so no phase is scanned.

hakuX's hull is r0 = D + X0 with D = 2 t0 t1 (oD0 + t2.g) (the diffuse term)
and X0 = cube(R) oD1.rgb t2.r oD1.a (the reflection). Each model is D + c X for
a candidate X, with c scanned (0 to 64, log steps) for its best rank r:
  - X0 itself, c = 1 is hakuX (R1's "v1 scales it to near zero" is c >> 1);
  - the cube looked up at P R for the 48 signed axis permutations P (R1b: a
    global mirror or swap of the cube's axes; P = identity is X0);
  - the cube replaced by a constant: t2.r oD1.rgb oD1.a, t2.r oD1.a, t2.r
    (R1: a bright face everywhere, with and without the fresnel);
  - t2.r alone with D dropped (the layer by itself).
R3 (a lerp to white) is an affine map of hakuX's output: its rank r is
hakuX's, so it is judged on level, not here.
"""
import itertools
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullsw as hs  # noqa: E402

dump, ramf, frame, regf, ovf = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
opt = dict(a.split("=", 1) for a in sys.argv[6:])
BL = int(opt.get("blur", 3))
LUM = np.array([0.299, 0.587, 0.114])
ram = open(ramf, "rb").read()
S = {}
R = hs.render(dump, ram, frame, state=S)
p = S[1]
con = np.load(regf)["warped"] @ LUM
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255


def boxblur(img, r):
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
REG = {"all": keep, "upper": keep & (ys < 300), "lower": keep & (ys >= 300)}


def smooth(vals):
    g = np.zeros((hs.H, hs.W))
    g[ys, xs] = vals
    return (boxblur(g, BL) / np.maximum(den, 1e-9))[ys, xs]


def rank(x):
    r = np.empty(len(x))
    r[np.argsort(x, kind="stable")] = np.arange(len(x))
    return r


C = smooth(con[ys, xs])
CR = {k: rank(C[m]) for k, m in REG.items()}


def spearman(v):
    s = smooth(v)
    return {k: np.corrcoef(rank(s[m]), CR[k])[0, 1] for k, m in REG.items()}


def pearson(v):
    s = smooth(v)
    return {k: np.corrcoef(s[m], C[m])[0, 1] for k, m in REG.items()}


g = lambda k: R[k][ys, xs]  # noqa: E731
t0, t1, t2, t3, oD0, oD1 = g("t0"), g("t1"), g("t2"), g("t3"), g("oD0"), g("oD1")
D = (g("diffuse") @ LUM)
X0 = (g("refl") @ LUM)
Rv = g("R")
lod3 = g("lod3")[:, 0]
faces = p["tex"][3][0]


def cube(Rp):
    face, sc, tc = hs.cube_face(Rp)
    out = np.zeros((len(Rp), 4))
    for f in range(6):
        m = face == f
        if m.any():
            out[m] = hs.trilinear(faces[f], sc[m], tc[m], lod3[m], wrap=False)
    return out


def refl(t3x):
    return (np.clip(t3x[:, :3] * oD1[:, :3], 0, 1) @ LUM) * t2[:, 0] * oD1[:, 3]


CS = np.concatenate([[0], np.geomspace(0.05, 64, 40)])


def best_c(X, base=D):
    best = None
    for c in CS:
        r = spearman(base + c * X)["all"]
        if best is None or r > best[1]:
            best = (c, r)
    return best


rows = []


def report(name, X, base=D, fixed_c=None):
    c, _ = (fixed_c, None) if fixed_c is not None else best_c(X, base)
    v = base + c * X
    sp, pe = spearman(v), pearson(v)
    rows.append((name, c, sp, pe))
    print(f"{name:34s} c {c:6.2f}  rank r all {sp['all']:+.3f} upper {sp['upper']:+.3f} lower {sp['lower']:+.3f}"
          f"  | pearson all {pe['all']:+.3f}", flush=True)


print(f"f{frame}: {keep.sum()} hull px, blur {BL}")
report("hakuX as drawn (D + X0)", X0, fixed_c=1.0)
report("D alone", X0, fixed_c=0.0)
report("D + c X0 (reflection scaled)", X0)
report("D + c t2.r oD1.rgb oD1.a (cube = 1)", refl(np.ones((len(ys), 4))))
report("D + c t2.r oD1.a", t2[:, 0] * oD1[:, 3])
report("D + c t2.r", t2[:, 0])
report("t2.r alone", t2[:, 0], base=np.zeros(len(ys)), fixed_c=1.0)
report("t0 alone", t0[:, :3] @ LUM, base=np.zeros(len(ys)), fixed_c=1.0)
print("cube under signed axis permutations P (P R), best 8 by rank r:")
perm_rows = []
for perm in itertools.permutations(range(3)):
    for signs in itertools.product((1, -1), repeat=3):
        Rp = Rv[:, list(perm)] * np.array(signs)
        X = refl(cube(Rp))
        c, r = best_c(X)
        tag = "".join(("-" if s < 0 else "+") + "xyz"[a] for a, s in zip(perm, signs))
        perm_rows.append((r, c, tag, X))
perm_rows.sort(key=lambda t: -t[0])
for r, c, tag, X in perm_rows[:8]:
    report(f"D + c cube({tag}) refl", X, fixed_c=c)
ident = [t for t in perm_rows if t[2] == "+x+y+z"][0]
print(f"identity (+x+y+z) ranks {perm_rows.index(ident) + 1} of 48, rank r {ident[0]:+.3f} at c {ident[1]:.2f}")
if "save" in opt:
    with open(opt["save"], "w") as fh:
        fh.write("model\tc\tsp_all\tsp_upper\tsp_lower\tpe_all\n")
        for name, c, sp, pe in rows:
            fh.write(f"{name}\t{c:.3f}\t{sp['all']:.4f}\t{sp['upper']:.4f}\t{sp['lower']:.4f}\t{pe['all']:.4f}\n")
        for r, c, tag, X in perm_rows:
            fh.write(f"perm {tag}\t{c:.3f}\t{r:.4f}\t\t\t\n")
