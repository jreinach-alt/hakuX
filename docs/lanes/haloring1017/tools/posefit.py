"""Which dump frame has the console photo's camera pose? (#939, (a))

usage: posefit.py DUMP.jsonl RAM.bin REG.npz OVERLAY.png F0 F1 [step=N] [roi=x0,y0,x1,y1]

The ring's geometry never moves (M1); the menu's camera does. So the pose is
the frame whose ring silhouette (n4 + n5 rasterised by hullsw.py's vertex
program, geometry only) matches the photo's. The photo (photoreg.py's
warped image, frame pixels) is split ring / space by its luminance inside
the ROI, off the overlays (OVERLAY.png, the clip's per-pixel minimum, > 0.12
is an overlay pixel) and off the display's cropped border. Reports per
frame the IoU of the two ring masks and the band (n4) IoU against the
photo's brightest ring part.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullsw as hs  # noqa: E402

dump, ramf, regf, ovf = sys.argv[1:5]
f0, f1 = int(sys.argv[5]), int(sys.argv[6])
opt = dict(a.split("=", 1) for a in sys.argv[7:])
step = int(opt.get("step", 3))
x0, y0, x1, y1 = (int(v) for v in opt.get("roi", "15,215,600,450").split(","))
ram = open(ramf, "rb").read()
reg = np.load(regf)
P = reg["warped"] @ hs.np.array([0.299, 0.587, 0.114])
ov = np.asarray(Image.open(ovf).convert("L"), dtype=np.float64) / 255
roi = np.zeros((hs.H, hs.W), bool)
roi[y0:y1, x0:x1] = True
roi &= ov < 0.12
roi &= P > 0.0  # photoreg leaves 0 outside the photo
# photo ring mask: Otsu threshold of the photo's luminance in the ROI
v = P[roi]
best = None
for t in np.linspace(np.percentile(v, 5), np.percentile(v, 95), 200):
    a, b = v[v < t], v[v >= t]
    if len(a) and len(b):
        s = len(a) * len(b) * (a.mean() - b.mean()) ** 2
        if best is None or s > best[0]:
            best = (s, t)
thr = best[1]
ring_p = (P > thr) & roi
print(f"photo: roi px {roi.sum()} threshold {thr:.3f} ring fraction {ring_p.sum() / roi.sum():.3f}")

session, draws, frames, skips, shaders = hs.g.load(dump)
for d in draws:
    for k in ("f", "n", "count"):
        d[k] = int(d[k])
want = set(range(f0, f1 + 1, step))
st = hs.g.replay(draws, want)
geo = {}
for name, (addr, nv, strip) in hs.GEOM.items():
    rec = np.frombuffer(ram[addr:addr + nv * 32], dtype=hs.REC)
    idx = list(struct.unpack_from(f"<{strip[1]}H", ram, strip[0])) if strip else list(range(nv))
    geo[name] = (rec, hs.tris_of(idx))
rows = []
for f in sorted(want):
    layers = []
    for d in draws:
        if d["f"] != f or d["count"] not in hs.NAMES:
            continue
        name = hs.NAMES[d["count"]]
        C = np.array([hs.g.f32(w) for w in st[(f, d["n"])]["c"]], dtype=np.float64).reshape(192, 4)
        SX, SY, SZ, PW, _ = hs.program(C, geo[name][0])
        layers.append((0 if name == "n4" else 1, geo[name][1], SX, SY, SZ, PW))
    if not layers:
        continue
    lid, _, _ = hs.raster(layers)
    ring_r = (lid >= 0) & roi
    iou = (ring_r & ring_p).sum() / max((ring_r | ring_p).sum(), 1)
    rows.append((f, iou, ring_r.sum() / roi.sum()))
    print(f"f{f}: ring IoU {iou:.3f} render ring fraction {ring_r.sum() / roi.sum():.3f}", flush=True)
    if "save" in opt and f == int(opt.get("savef", -1)):
        pan = np.zeros((hs.H, hs.W, 3))
        pan[..., 0] = ring_p
        pan[..., 1] = ring_r
        pan[..., 2] = roi * 0.3
        Image.fromarray((pan * 255).astype(np.uint8)).save(opt["save"])
if rows:
    fb = max(rows, key=lambda r: r[1])
    print(f"best: f{fb[0]} IoU {fb[1]:.3f}")
