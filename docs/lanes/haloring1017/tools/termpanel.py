"""The console's hull beside each of hakuX's terms, cropped and zoomed (#939, (a), M7).

usage: termpanel.py RENDER.npz REG.npz OUT.png [box=x0,y0,x1,y1] [zoom=2]

One row of panels over the crop box (frame pixels): the console photo
(registered, colour), hakuX's final, then t0, t1, t2.r, t2.g, the cube t3,
oD0 and oD1.a as hullsw.py samples them at the photo's pose, each stretched
to its own 1st-99th percentile on the hull so its structure shows whatever its
level. A term whose blobs and lines sit where the console's do, at the same
size, is a term the console draws; a term at the wrong scale shows features
of the wrong size.
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

rendf, regf, outf = sys.argv[1:4]
opt = dict(a.split("=", 1) for a in sys.argv[4:])
x0, y0, x1, y1 = (int(v) for v in opt.get("box", "330,150,640,452").split(","))
ZM = int(opt.get("zoom", 2))
LUM = np.array([0.299, 0.587, 0.114])
R = np.load(rendf)
con = np.load(regf)["warped"]
lid = R["lid"]
hull = lid == 1
z = lambda k: np.nan_to_num(R[k])  # noqa: E731


def stretch(v):
    lo, hi = np.percentile(v[hull], [1, 99])
    return np.clip((v - lo) / max(hi - lo, 1e-9), 0, 1)


panels = [("console", np.clip(con, 0, 1)), ("hakuX final", np.repeat(stretch(z("final") @ LUM)[..., None], 3, 2))]
for name, v in (("t0", z("t0")[..., :3] @ LUM), ("t1", z("t1")[..., :3] @ LUM), ("t2.r", z("t2")[..., 0]),
                ("t2.g", z("t2")[..., 1]), ("t3 cube", z("t3")[..., :3] @ LUM), ("oD0", z("oD0")[..., :3] @ LUM),
                ("oD1.a", z("oD1")[..., 3])):
    s = stretch(v)
    s = np.where(hull, s, 0.15 * (con @ LUM))
    panels.append((name, np.repeat(s[..., None], 3, 2)))
tiles = []
for name, img in panels:
    crop = img[y0:y1, x0:x1]
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize(((x1 - x0) * ZM, (y1 - y0) * ZM), Image.NEAREST)
    ImageDraw.Draw(im).text((4, 4), name, fill=(255, 64, 64))
    tiles.append(np.asarray(im))
cols = int(opt.get("cols", 3))
rows = []
for r in range(0, len(tiles), cols):
    row = tiles[r:r + cols]
    while len(row) < cols:
        row.append(np.zeros_like(tiles[0]))
    rows.append(np.concatenate(row, 1))
Image.fromarray(np.concatenate(rows, 0)).save(outf)
print(f"wrote {outf}: {len(panels)} panels, box {x0},{y0}-{x1},{y1} x{ZM}")
