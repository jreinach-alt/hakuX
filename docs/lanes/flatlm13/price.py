#!/usr/bin/env python3
"""Price a flat-edge colour rule on an existing capture, offline.

In a flat line-mode capture every edge is drawn in its FIRST emitted
endpoint's colour, and each of those colours is unique to one edge, so a
capture can be recoloured edge by edge to what a different rule would draw.
Colour px = ink in both golden and ours with a different colour (the
definition cloud-13's lm_attrib.py uses for class C).

Rules:
  now     the capture as it is
  orient  prim_rewrite.c alone: an edge that touches the provoking vertex p
          is emitted p-first; any other edge keeps its first endpoint
  whole   every edge of a quad / the polygon takes p (silicon; needs geom.c)

  price.py CAPDIR
  price.py --verify CAPDIR_A CAPDIR_B    B == orient(A), pixel for pixel
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edge_colour import DIFFUSE, G, VERTS, project  # noqa: E402

RGB = [tuple((c >> s) & 255 for s in (0, 8, 16)) for c in DIFFUSE]

# Edges as prim_rewrite.c emits them today (first endpoint first), with the
# provoking vertex silicon uses for the quad / polygon the edge belongs to.
EMITTED = {
    # rewrite_quads_line: (v1,v2), (v0,v1), (v2,v3), (v3,v0); p = v3
    "Quad": [((1, 2), 3), ((0, 1), 3), ((2, 3), 3), ((3, 0), 3),
             ((5, 6), 7), ((4, 5), 7), ((6, 7), 7), ((7, 4), 7)],
    # rewrite_quad_strip_line: (v2,v0), (v0,v1), (v1,v3), (v3,v2); p = v3
    "QuadStrip": [((2, 0), 3), ((0, 1), 3), ((1, 3), 3), ((3, 2), 3),
                  ((4, 2), 5), ((2, 3), 5), ((3, 5), 5), ((5, 4), 5)],
    # rewrite_polygon_line at count 5: (v1,v2), (v0,v1), (v2,v3), (v3,v4),
    # (v4,v0); p = v0
    "Poly": [((1, 2), 0), ((0, 1), 0), ((2, 3), 0), ((3, 4), 0),
             ((4, 0), 0)],
}


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def colour_px(g, o):
    bg = np.array([44, 48, 46])
    gi = np.any(g != bg, axis=2)
    oi = np.any(o != bg, axis=2)
    return int((gi & oi & np.any(g != o, axis=2)).sum())


def near(shape, a, b, r=2.5):
    """Pixels whose centre lies within r px of the segment a-b."""
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]]
    px, py = xs + 0.5, ys + 0.5
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = np.clip(((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy),
                0, 1)
    return np.hypot(px - a[0] - t * dx, py - a[1] - t * dy) <= r


def recolour(o, prim, rule):
    """Each edge is recoloured where it shows its own (first-endpoint)
    colour near its own segment; the strip reuses a colour on two edges, so
    colour alone does not identify an edge."""
    out = o.copy()
    pts = [project(*v) for v in VERTS[prim]]
    for (a, b), p in EMITTED[prim]:
        if rule == "orient":
            new = p if p in (a, b) else a
        elif rule == "whole":
            new = p
        else:
            new = a
        if new != a:
            m = near(o.shape, pts[a], pts[b]) & np.all(o == RGB[a], axis=2)
            out[m] = RGB[new]
    return out


def verify(cap_a, cap_b):
    """The arm's magnitude leg: B must be A recoloured by `orient`, pixel for
    pixel.  Exit 1 if any of the six captures is not."""
    bad = 0
    print("%-28s %6s %6s %6s %8s" % ("capture", "A", "orient", "B",
                                     "B!=pred"))
    for prim in ("Quad", "QuadStrip", "Poly"):
        for pv in ("First", "Last"):
            test = "ProgLM_%s_Flat_%s" % (prim, pv)
            g = load(os.path.join(G, test + ".png"))
            a = load(os.path.join(cap_a, "Shade_model::%s.png" % test))
            b = load(os.path.join(cap_b, "Shade_model::%s.png" % test))
            pred = recolour(a, prim, "orient")
            off = int(np.any(pred != b, axis=2).sum())
            bad += off != 0
            print("%-28s %6d %6d %6d %8d" % (test, colour_px(g, a),
                                             colour_px(g, pred),
                                             colour_px(g, b), off))
    print("VERIFY %s" % ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


def main(cap):
    print("%-28s %6s %6s %6s" % ("capture", "now", "orient", "whole"))
    for prim in ("Quad", "QuadStrip", "Poly"):
        for pv in ("First", "Last"):
            test = "ProgLM_%s_Flat_%s" % (prim, pv)
            g = load(os.path.join(G, test + ".png"))
            o = load(os.path.join(cap, "Shade_model::%s.png" % test))
            row = [colour_px(g, recolour(o, prim, r))
                   for r in ("now", "orient", "whole")]
            print("%-28s %6d %6d %6d" % (test, *row))


if __name__ == "__main__":
    if sys.argv[1] == "--verify":
        sys.exit(verify(sys.argv[2], sys.argv[3]))
    main(sys.argv[1])
