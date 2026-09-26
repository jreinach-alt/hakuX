#!/usr/bin/env python3
"""Flat-shaded wireframe: the colour of each edge, golden vs ours.

shade_model_tests.cpp's vertex i takes kTestDiffuse[i]; this prints the modal
colour on a short probe of each named edge so the provoking vertex silicon
uses per edge can be read against that table.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lm_cuts as lc

DIFFUSE = [0xFF0000, 0x00FF00, 0x0000FF, 0xCCCCCC, 0xFF33CC, 0xFFCC33,
           0xCCFF33, 0x33FFCC, 0x33CCFF, 0xCC33FF, 0x991111, 0x119911,
           0x111199, 0x666666]
NAMES = {tuple((c >> s) & 255 for s in (16, 8, 0)): "v%d" % i
         for i, c in enumerate(DIFFUSE)}

# (label, x0, y0, x1, y1): a probe window lying on one edge
PROBES = {
    "ProgLM_Quad_Flat_First": [("Q0 top", 150, 97, 230, 103),
                               ("Q0 right", 284, 200, 290, 280),
                               ("Q0 bottom", 150, 379, 230, 385),
                               ("Q0 left", 92, 200, 98, 280),
                               ("Q1 top", 380, 97, 480, 103),
                               ("Q1 right", 541, 200, 547, 280),
                               ("Q1 bottom", 380, 379, 480, 385)],
}
PROBES["ProgLM_Quad_Flat_Last"] = PROBES["ProgLM_Quad_Flat_First"]


def modal(img, ink, x0, y0, x1, y1):
    c = collections.Counter()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if ink[y, x]:
                c[tuple(int(v) for v in img[y, x])] += 1
    return c.most_common(1)[0][0] if c else None


def main(cap):
    for test, probes in PROBES.items():
        g = lc.load(os.path.join(lc.G, "Shade_model", test + ".png"))
        o = lc.load(os.path.join(cap, "Shade_model::%s.png" % test))
        gi, oi = lc.ink(g), lc.ink(o)
        print(test)
        for lab, *box in probes:
            gc, oc = modal(g, gi, *box), modal(o, oi, *box)
            print("  %-10s golden %-16s %-4s  ours %-16s %s"
                  % (lab, gc, NAMES.get(gc, "?"), oc, NAMES.get(oc, "?")))


if __name__ == "__main__":
    main(sys.argv[1])
