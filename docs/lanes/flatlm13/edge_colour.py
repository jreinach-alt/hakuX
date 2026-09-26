#!/usr/bin/env python3
"""Flat line-mode quad/strip/polygon: the colour silicon gives each edge.

Projects shade_model_tests.cpp's vertices through its PerspectiveVertexShader
(camera z=-7, fov pi/4, 640x480, D3D viewport), samples the middle 70% of every
boundary edge in a 3 px band, and names the modal ink colour by the vertex
whose kTestDiffuse it is.  Goldens only by default; `--cap DIR` adds a
capture's colour beside each golden one.

  edge_colour.py [--cap CAPDIR] [--prims Quad,QuadStrip,Poly] [--shade Flat]
"""
import argparse
import collections
import math
import os

import numpy as np
from PIL import Image

G = os.path.expanduser("~/goldens/results/Shade_model")
DIFFUSE = [0xFF0000, 0x00FF00, 0x0000FF, 0xCCCCCC, 0xFF33CC, 0xFFCC33,
           0xCCFF33, 0x33FFCC, 0x33CCFF, 0xCC33FF, 0x991111, 0x119911,
           0x111199, 0x666666]
NAMES = {tuple((c >> s) & 255 for s in (0, 8, 16)): "v%d" % i
         for i, c in enumerate(DIFFUSE)}
L, R, T, B = -2.75, 2.75, 1.75, -1.75
VERTS = {
    "Quad": [(L, T), (-0.4, T), (-0.4, B), (L, B),
             (0.15, T), (R, T), (R, B), (0.0, B)],
    "QuadStrip": [(L, B), (L, T), (0.0, -1.35), (0.0, 1.0), (R, B), (R, T)],
    "Poly": [(L, B), (-1.4, 1.1), (-0.3, T), (2.0, 0.3), (R, -1.5)],
}
# Boundary edges per primitive (the wireframe draws no internal diagonal).
EDGES = {
    "Quad": [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)],
    # quad k = (2k, 2k+1, 2k+2, 2k+3); edges v0v1, v1v3, v3v2, v2v0
    "QuadStrip": [(0, 1), (1, 3), (2, 0), (3, 2), (3, 5), (4, 2), (5, 4)],
    "Poly": [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)],
}


def project(x, y, z=0.1):
    d = z + 7.0
    t = math.tan(math.pi / 8)
    return (320 + 320 * (x / d) / (t * 640 / 480), 240 - 240 * (y / d) / t)


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def edge_colour(img, a, b):
    bg = collections.Counter(map(tuple, img.reshape(-1, 3))).most_common(1)[0][0]
    c = collections.Counter()
    for k in range(15, 86):
        t = k / 100
        x = a[0] + (b[0] - a[0]) * t
        y = a[1] + (b[1] - a[1]) * t
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                px = img[int(round(y)) + dy, int(round(x)) + dx]
                if tuple(px) != bg:
                    c[tuple(int(v) for v in px)] += 1
    if not c:
        return None, 0.0
    col, n = c.most_common(1)[0]
    return col, n / sum(c.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap")
    ap.add_argument("--prims", default="Quad,QuadStrip,Poly")
    ap.add_argument("--shade", default="Flat")
    a = ap.parse_args()
    for prim in a.prims.split(","):
        pts = [project(*v) for v in VERTS[prim]]
        for pv in ("First", "Last"):
            test = "ProgLM_%s_%s_%s" % (prim, a.shade, pv)
            g = load(os.path.join(G, test + ".png"))
            o = (load(os.path.join(a.cap, "Shade_model::%s.png" % test))
                 if a.cap else None)
            print(test)
            for i, j in EDGES[prim]:
                gc, gf = edge_colour(g, pts[i], pts[j])
                line = "  edge v%d-v%d  golden %-4s (%3.0f%%)" % (
                    i, j, NAMES.get(gc, str(gc)), gf * 100)
                if o is not None:
                    oc, of = edge_colour(o, pts[i], pts[j])
                    line += "   ours %-4s (%3.0f%%)" % (
                        NAMES.get(oc, str(oc)), of * 100)
                print(line)


if __name__ == "__main__":
    main()
