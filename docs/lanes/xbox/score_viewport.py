#!/usr/bin/env python3
"""Score the Viewport sub-step run with probe_viewport_ff_extents.py, unchanged.

    score_viewport.py GOLD_DIR OURS_DIR      the probe itself, sweep extended
    score_viewport.py --extents DIR [--ours] fixed-function extents of every
                                             sweep capture in ONE directory

GOLD_DIR holds <name>.png (the goldens' layout; the console writes this too),
OURS_DIR holds Viewport::<name>.png (a dispatcher result's captures1). The
seven registered offsets are appended to the probe's SWEEP exactly as it
lists the others; no line of the probe is edited. --extents is how the
registered cross-capture legs are read -- "D1's extents equal the +17/32
capture's" -- which the probe's gold-vs-ours loop cannot express.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "testing"))
import probe_viewport_ff_extents as p  # noqa: E402

NEW = [(0.548828125, "D1"), (0.53515625, "D2"), (0.5390625, "D3"),
       (0.55859375, "D4"), (-0.451171875, "D5"), (1.548828125, "D6"),
       (0.234375, "C1")]
for off, _ in NEW:
    p.SWEEP.append((off, "%.3f_%.3f-0.000_0.000" % (off, off)))
TAG = {"%.3f_%.3f-0.000_0.000" % (o, o): t for o, t in NEW}


def extents(d, ours):
    for off, name in p.SWEEP:
        path = os.path.join(d, ("Viewport::" if ours else "") + name + ".png")
        if not os.path.exists(path):
            print("%-4s %-26s MISSING %s" % (TAG.get(name, ""), name, path))
            continue
        img = p.load(path)
        cells = []
        for q, (nominal, row, idx, col) in p.QUADS.items():
            e = p.extent(img, row, idx, col)
            cells.append("%s x[%s..%s] y[%s..%s]" % ((q,) + tuple(e)) if e else "%s ?" % q)
        print("%-4s %+.9f %-26s %s" % (TAG.get(name, ""), off, name, "  ".join(cells)))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--extents":
        extents(sys.argv[2], "--ours" in sys.argv[3:])
        sys.exit(0)
    sys.exit(p.main())
