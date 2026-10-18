"""Where are the band/hull edges: render, hakuX's own video, the console? (#939, M6)

usage: edgecmp.py DUMP.jsonl RAM.bin REG.npz OUT.png FRAME:VIDEO.ppm [FRAME:VIDEO.ppm ...]

For each pair, the geometry of `n4` (band) and `n5` (hull) at FRAME is
rasterised as hullsw.py does it, and its draw edges are drawn in red over
(1) hakuX's own frame (VIDEO.ppm, run 13's Nova video at that frame's time)
and (2) the console photo in frame pixels (REG.npz). Prints, per draw, how many
triangles have a vertex with w <= 0 (hullsw.py drops those; the GPU clips
them) and the nearest vertex w on screen.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullsw as hs  # noqa: E402

dump, ramf, regf, outf = sys.argv[1:5]
pairs = [(int(a.split(":")[0]), a.split(":", 1)[1]) for a in sys.argv[5:]]
ram = open(ramf, "rb").read()
con = np.clip(np.load(regf)["warped"], 0, 1)
session, draws, frames, skips, shaders = hs.g.load(dump)
for d in draws:
    for k in ("f", "n", "count"):
        d[k] = int(d[k])
st = hs.g.replay(draws, {f for f, _ in pairs})
geo = {}
for name, (addr, nv, strip) in hs.GEOM.items():
    rec = np.frombuffer(ram[addr:addr + nv * 32], dtype=hs.REC)
    idx = list(struct.unpack_from(f"<{strip[1]}H", ram, strip[0])) if strip else list(range(nv))
    geo[name] = (rec, hs.tris_of(idx))
rows = []
for f, vid in pairs:
    layers = []
    for d in draws:
        if d["f"] != f or d["count"] not in hs.NAMES:
            continue
        name = hs.NAMES[d["count"]]
        C = np.array([hs.g.f32(w) for w in st[(f, d["n"])]["c"]], dtype=np.float64).reshape(192, 4)
        SX, SY, SZ, PW, _ = hs.program(C, geo[name][0])
        tris = geo[name][1]
        behind = (PW[tris] <= 0).any(1)
        onscr = (SX > 0) & (SX < 640) & (SY > 0) & (SY < 480) & (PW > 0)
        print(f"f{f} {name}: tris {len(tris)}, with a vertex at w <= 0: {behind.sum()}, "
              f"min w on screen {PW[onscr].min() if onscr.any() else float('nan'):.4f}, near plane (SZ<0) verts "
              f"{((SZ < 0) & (PW > 0)).sum()}", flush=True)
        layers.append((0 if name == "n4" else 1, tris, SX, SY, SZ, PW))
    lid, _, _ = hs.raster(layers)
    edge = np.zeros(lid.shape, bool)
    edge[1:, :] |= lid[1:, :] != lid[:-1, :]
    edge[:, 1:] |= lid[:, 1:] != lid[:, :-1]
    v = hs.ppm_rgb(vid)
    a, b = v.copy(), con.copy()
    a[edge] = [1, 0, 0]
    b[edge] = [1, 0, 0]
    rows.append(np.concatenate([a[170:470, 180:520], v[170:470, 180:520], b[170:470, 180:520]], 1))
img = np.concatenate(rows, 0)
Image.fromarray((img * 255).astype(np.uint8)).save(outf)
