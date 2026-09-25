#!/usr/bin/env python3
"""Per-swatch error of Clear's eight surface-format captures, whether each
swatch shows its own clear or swatch 0's, and the swatch alpha the golden and
the capture each hold.

    clear_swatch_quads.py CAPTURE_DIR [GOLDENS_DIR]

ClearTests::TestSurfaceFmt clears one 128x128 surface six times, once per
colour in kClearColors, draws a 4x4 black centre mark into it, and samples
it back into the Nth quad on screen. clear_surface_fmt.py (docs/testing/)
splits a capture's error into swatches that repeat an earlier swatch
(#184's defect) and the rest. This prints the rest per swatch, a stale flag
per swatch (S: its body is swatch 0's colour where the golden's is not), and
the alpha of each swatch's body, which is where the pad-bit defects of the X
formats show.

Used on #184 (lane.remote, 2026-09-25). On desktop Vulkan the X1A7 pair
stores the clear alpha's low 7 bits widened back to 8 by bit replication
(00 02 ff 00 fd ff over clear alphas 00 01 7f 80 fe ff), where the goldens
hold (X << 7) | (alpha & 0x7F). Once no swatch is stale that reads
16 / 16,384 / 16,384 / 16 / 16,384 / 16,384 on X1A7R8G8B8_Z and
16,368 / 16,368 / 0 / 16,368 / 16,368 / 0 on X1A7R8G8B8_O, as GL does, and
0 on every other format.
"""

import os
import sys

import numpy as np
from PIL import Image

# clear_tests.cpp: kLeftStart, kQuadSpacing, the two rows of three.
RECTS = ((48, 128), (192, 128), (336, 128), (480, 128), (48, 272), (192, 272))
SIZE = 128
CAPTURES = ("SFC_A8R8G8B8", "SFC_X1R5G5B5_Z1R5G5B5", "SCF_X1R5G5B5_O1R5G5B5",
            "SCF_R5G6B5", "SCF_X8R8G8B8_Z8R8G8B8", "SCF_X8R8G8B8_O8R8G8B8",
            "SCF_X1A7R8G8B8_Z1A7R8G8B8", "SCF_X1A7R8G8B8_O1A7R8G8B8")


def load(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(int)


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.split("\n\n")[1])
        return 2
    run = argv[1]
    goldens = argv[2] if len(argv) == 3 else "/tmp/goldens/results"
    for cap in CAPTURES:
        ours_path = os.path.join(run, "Clear::%s.png" % cap)
        gold_path = os.path.join(goldens, "Clear", "%s.png" % cap)
        if not (os.path.exists(ours_path) and os.path.exists(gold_path)):
            print("%-28s missing" % cap)
            continue
        ours, gold = load(ours_path), load(gold_path)
        per, alpha, stale = [], [], ""
        body0_ours = ours[RECTS[0][1] + 8, RECTS[0][0] + 8, :3]
        body0_gold = gold[RECTS[0][1] + 8, RECTS[0][0] + 8, :3]
        for x, y in RECTS:
            o = ours[y:y + SIZE, x:x + SIZE]
            g = gold[y:y + SIZE, x:x + SIZE]
            per.append(int((o != g).any(axis=2).sum()))
            alpha.append("%02x/%02x" % (o[8, 8, 3], g[8, 8, 3]))
            is_stale = ((o[8, 8, :3] == body0_ours).all()
                        and not (g[8, 8, :3] == body0_gold).all())
            stale += "S" if is_stale else "."
        print("%-28s total %6d  per swatch %s  stale %s  body alpha ours/gold %s"
              % (cap, sum(per), per, stale, " ".join(alpha)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
