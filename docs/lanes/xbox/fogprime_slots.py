#!/usr/bin/env python3
"""The per-vertex structure of the radial-fog priming captures.

    fogprime_slots.py <captures root>

<captures root> is a console run's `console/` directory or a dispatcher
result's `captures1/` (see fogprime_score.py). Writes nothing.

fogprime_score.py scores the run against PR #179's single-value models. On
silicon, V2 failed: each VS capture carries two to five adjacent fog factors.
This script measures the structure of that failure.

- **Per capture:** the colour counts; how completely the corner pattern of a
  VS quad is fixed by its draw index mod 6; and each of the 24 slots' vertex
  value (quad index mod 6 by corner). A slot's value comes from a plane fit
  per triangle over quads 180..373, which are far enough from the camera that
  perspective is negligible. Those values are set against the f8 span of the
  priming draw's last one and last two quads. The span uses the prediction's
  own geometry (`docs/testing/fog_radial_stale_vertex.py`) and exp model,
  f8 = 255 * 2^(16 * m * d) with m = -0.000875.
- **Per pair:** the shift s, in quads, at which one capture's corner
  patterns match another's.
- **The six `Fog_gen` radial captures, if present:** each one's colour, and the
  coordinate that colour inverts to.
"""
import math
import os
import sys
from collections import Counter

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import fog_radial_stale_vertex as G  # noqa: E402

M = -0.000875
SUITE_M = G.M_EXP  # the Fog gen suite's -0.00225
ROTATION = {"A0far_VS": 0, "A1mid_VS": 188, "A2near_VS": 21, "A3farLabel_VS": 0,
            "A4pad_VS": 21, "A4radial_VS": 21}
PAIRS = [("A0far_VS", "A3farLabel_VS"), ("A2near_VS", "A4pad_VS"),
         ("A2near_VS", "A4radial_VS"), ("A4pad_VS", "A4radial_VS")]
CORNERS = ["UL", "UR", "LR", "LL"]
GRID = G.quads()
YY, XX = np.mgrid[0:22, 0:22]
PX, PY = XX + 0.5, YY + 0.5
UPPER = PX > PY + 0.75  # triangle UL-UR-LR, off the shared diagonal
LOWER = PY > PX + 0.75  # triangle UL-LR-LL


def find(root, suite_dir, name):
    for p in (os.path.join(root, suite_dir, name + ".png"),
              os.path.join(root, "%s::%s.png" % (suite_dir, name))):
        if os.path.exists(p):
            return p
    return None


def factor_image(p):
    a = np.asarray(Image.open(p).convert("RGB")).astype(int)
    mix = (a[..., 0] + a[..., 2] == 255) & (a[..., 1] == 0)
    return np.where(mix, a[..., 2], -1)


def quad(f, i):
    _, left, top, _ = GRID[i]
    return f[int(top):int(top) + 22, int(left):int(left) + 22]


def corner_pattern(f, i):
    q = quad(f, i)
    return (int(q[0, 0]), int(q[0, -1]), int(q[-1, -1]), int(q[-1, 0]))


def plane(q, mask):
    a = np.stack([np.ones(mask.sum()), PX[mask], PY[mask]], 1)
    c, *_ = np.linalg.lstsq(a, q[mask].astype(float), rcond=None)
    return lambda x, y: c[0] + c[1] * x + c[2] * y


def vertex_values(f, i):
    """UL, UR, LR, LL; the two shared corners average the two triangles."""
    q = quad(f, i)
    u, lo = plane(q, UPPER), plane(q, LOWER)
    return [0.5 * (u(0, 0) + lo(0, 0)), u(22, 0), 0.5 * (u(22, 22) + lo(22, 22)), lo(0, 22)]


def f8_model(d, m=M):
    return 255.0 * 2 ** (16 * m * d)


def tail_span(rotation, nquads):
    vals = []
    for j in range(374 - nquads, 374):
        _, left, top, z = GRID[(rotation + j) % 374]
        vals += [f8_model(G.radial(sx, sy, wz)) for (_, sx, sy, wz) in G.quad_vertices(left, top, z)]
    return min(vals), max(vals)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    pats = {}
    for name, rot in ROTATION.items():
        p = find(root, "Fog_radial_priming", name)
        if not p:
            print("%s: MISSING" % name)
            continue
        f = factor_image(p)
        colours = Counter(f[f >= 0].tolist())
        pats[name] = [corner_pattern(f, i) for i in range(374)]
        purity = sum(Counter(pats[name][i] for i in range(k, 374, 6)).most_common(1)[0][1]
                     for k in range(6)) / 374.0
        print("== %s: %d px, colours %s" % (name, sum(colours.values()), sorted(colours.items())))
        print("   corner pattern fixed by (draw index mod 6) on %.3f of the 374 quads" % purity)
        slots = np.array([np.mean([vertex_values(f, i) for i in range(k, 374, 6) if i >= 180], axis=0)
                          for k in range(6)])
        for k in range(6):
            print("   i%%6=%d  %s" % (k, "  ".join("%s %7.2f" % (CORNERS[c], slots[k, c]) for c in range(4))))
        lo1, hi1 = tail_span(rot, 1)
        lo2, hi2 = tail_span(rot, 2)
        print("   slot values %.2f .. %.2f; the priming draw's last quad spans %.2f .. %.2f, "
              "its last two %.2f .. %.2f" % (slots.min(), slots.max(), lo1, hi1, lo2, hi2))
    print("== phase: the quad shift s at which B's corner patterns match A's")
    for a, b in PAIRS:
        if a not in pats or b not in pats:
            continue
        fr = [sum(1 for i in range(368) if pats[a][i] == pats[b][i + s]) / 368.0 for s in range(6)]
        best = max(range(6), key=lambda s: fr[s])
        uniform = len(set(pats[a])) == 1
        print("   %-13s -> %-13s s=%d (%.2f of quads)%s   [%s]" % (
            a, b, best, fr[best], "  -- uniform capture, no phase to read" if uniform else "",
            " ".join("%.2f" % x for x in fr)))
    print("== the six Fog gen VS radial captures")
    for mode in G.MODES:
        p = find(root, "Fog_gen", "FogGen_VS-%s-radial" % mode)
        if not p:
            continue
        f = factor_image(p)
        colours = Counter(f[f >= 0].tolist())
        top, n = colours.most_common(1)[0]
        if mode.startswith("exp") and not mode.startswith("exp2") and 0 < top < 255:
            coord = "coordinate %.2f (exp, suite multiplier)" % (-math.log2(top / 255.0) / 16.0 / -SUITE_M)
        elif mode.startswith("linear") and 0 < top < 255:
            coord = "coordinate %.2f (linear, fog end %.0f)" % (G.FOG_END * (1 - top / 255.0), G.FOG_END)
        else:
            coord = ""
        print("   %-11s %d colour(s), f8 %d on %d px  %s" % (mode, len(colours), top, n, coord))
    return 0


if __name__ == "__main__":
    sys.exit(main())
