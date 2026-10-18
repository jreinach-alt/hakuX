"""Is the console's lunar mottling t1, the detail map, at some other scale? (#939, (a), M7)

usage: t1scale.py DUMP.jsonl RAM.bin FRAME REG.npz OVERLAY.png OUTDIR [scales=1,2,5,10] [box=x0,y0,x1,y1]

The hull's VP writes oT1 = oT0 * c12.xy, and c12.xy is (10, 10) in the dump:
the detail map t1 (128x128, a grey crater texture whose mips fade to 0.5) tiles
ten times per t0 tile. hullsw.py re-renders the hull with c12.xy set to each
scale (t1's coordinates and its LOD both follow), and the console's structure
is compared with each term's by band-pass correlation: each image's luminance
is smoothed inside the hull (normalised box blur) at two radii and the
difference taken, so level, tone curve and the lighting gradient drop out and
only features of that size remain. A t1 scale whose features sit where the
console's do correlates; a wrong scale does not. Upper and lower hull (y below
or above 250) are reported apart, since the console's mottling is in the lower.
Writes OUTDIR/t1scale_<s>.npz per scale (cached) and OUTDIR/t1scale.png.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullsw as hs  # noqa: E402

dump, ramf, frame, regf, ovf, outdir = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6]
opt = dict(a.split("=", 1) for a in sys.argv[7:])
scales = [float(s) for s in opt.get("scales", "1,2,5,10").split(",")]
bx0, by0, bx1, by1 = (int(v) for v in opt.get("box", "400,120,590,452").split(","))
LUM = np.array([0.299, 0.587, 0.114])
os.makedirs(outdir, exist_ok=True)
ram = open(ramf, "rb").read()
loaded = hs.g.load(dump)
R = {}
for s in scales:
    f = os.path.join(outdir, f"t1scale_{s:g}.npz")
    if not os.path.exists(f):
        out = hs.render(dump, ram, frame, loaded=loaded, cpatch={(1, 12, 0): s, (1, 12, 1): s})
        np.savez_compressed(f, **{k: out[k] for k in ("lid", "t0", "t1", "t2", "final", "diffuse", "lod1")})
    R[s] = np.load(f)
ref = R[max(scales)] if 10.0 not in R else R[10.0]
lid = ref["lid"]
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
hull = (lid == 1) & ~ovm
hull[452:, :] = False
hull[:, :15] = False


def band(img, r1, r2):
    def sm(r):
        return boxblur(np.where(hull, img, 0), r) / np.maximum(boxblur(hull.astype(float), r), 1e-9)
    return (sm(r1) if r1 else img) - sm(r2)


core = hull & (boxblur(hull.astype(float), 12) > 0.8 * 625)
yy = np.arange(hull.shape[0])[:, None] + np.zeros(hull.shape, int)
parts = {"upper (y<250)": core & (yy < 250), "lower (y>=250)": core & (yy >= 250)}
print(f"hull core {core.sum()} px; " + ", ".join(f"{k} {v.sum()}" for k, v in parts.items()))
cands = {"t0 (lum)": ref["t0"][..., :3] @ LUM, "t2.r": ref["t2"][..., 0], "hakuX final": ref["final"] @ LUM}
for s in scales:
    cands[f"t1 at c12.xy={s:g}"] = R[s]["t1"][..., :3] @ LUM
    cands[f"final at c12.xy={s:g}"] = R[s]["final"] @ LUM
for s in scales:
    lod = R[s]["lod1"][..., 0][core]
    print(f"   c12.xy={s:g}: t1 lod p10/50/90 {np.percentile(lod, [10, 50, 90]).round(2)}; "
          f"t1 mean on hull {np.nanmean(R[s]['t1'][..., :3][core] @ LUM):.3f}")
for r1, r2 in ((1, 4), (3, 10), (8, 24)):
    cb = band(con, r1, r2)
    print(f"band-pass box r{r1} - r{r2}: Pearson r of the console's band with each term's")
    for name, v in cands.items():
        vb = band(np.nan_to_num(v), r1, r2)
        row = []
        for pn, m in parts.items():
            a, b = cb[m], vb[m]
            row.append(f"{pn} {np.corrcoef(a, b)[0, 1]:+.3f}")
        print(f"   {name:24s} " + "  ".join(row))
# panel: console, hakuX final, then t1 at each scale, over the box
LUMS = [("console", con)] + [("hakuX final", ref["final"] @ LUM)] + [(f"t1 x{s:g}", R[s]["t1"][..., :3] @ LUM) for s in scales]
tiles = []
for name, v in LUMS:
    crop = np.nan_to_num(v[by0:by1, bx0:bx1])
    m = hull[by0:by1, bx0:bx1]
    lo, hi = np.percentile(crop[m], [1, 99]) if m.any() else (0, 1)
    img = np.where(m, np.clip((crop - lo) / max(hi - lo, 1e-9), 0, 1), 0.1)
    im = Image.fromarray((img * 255).astype(np.uint8)).resize(((bx1 - bx0) * 2, (by1 - by0) * 2), Image.NEAREST)
    ImageDraw.Draw(im).text((4, 4), name, fill=255)
    tiles.append(np.asarray(im))
cols = 3
rows = []
for r in range(0, len(tiles), cols):
    row = tiles[r:r + cols]
    while len(row) < cols:
        row.append(np.zeros_like(tiles[0]))
    rows.append(np.concatenate(row, 1))
Image.fromarray(np.concatenate(rows, 0)).save(os.path.join(outdir, "t1scale.png"))
print(f"wrote {os.path.join(outdir, 't1scale.png')}")
