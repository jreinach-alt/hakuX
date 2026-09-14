#!/usr/bin/env python3
"""#38 mechanism 2: the corpus DOES hold narrow, triangle and SET_VERTEX3F
members of the pair-rule class, and all of them are unpaired.

WHAT THIS SETTLES.

#38's blocker asks for five new upstream captures because "the precondition
cannot be narrowed below a four-way tie".  The four candidates are all of the
form `immediate mode /\\ w = 1 /\\ X`:

    X = TRUE                              the bare conjunction
    X = primitive is QUADS or POLYGON     never a triangle form
    X = the primitive is >= 512 px wide   "one large primitive"
    X = the vertices arrive by SET_VERTEX4F

and the tie stands because the positive cell was believed to hold exactly two
draws -- `Alpha_func`'s band and `Context_switch/GRZero` -- which share all
three of the optional conjuncts.

It holds more.  `line_width_tests.cpp` runs its whole shape set THREE TIMES
with `SetFill(true)` -- the constructor's last loop, `for (auto line_width :
{0, 1 << 3, 32 << 3})` calling `Test(name, true, width)` -- producing the
goldens `Line_width/Fill_0000.0`, `Fill_0001.0` and `Fill_0032.0`.  Under
`NV097_SET_FRONT_POLYGON_MODE_V_FILL` those are FILLED polygons, not the
wireframe the rest of the suite draws, and every one of them is a class member:

  A  `PassthroughVertexShader`, set in `LineWidthTests::Initialize`
  B  immediate mode -- `SetDiffuse`/`SetVertex` inside one `Begin`/`End`
  C  a per-vertex diffuse gradient -- `SetDiffuse(kPalette[i])` per vertex

They are also, unlike the two known positives, **narrow (60-105 px)**,
**submitted by SET_VERTEX3F**, and available as **TRIANGLES and TRIANGLE_FAN**
as well as QUAD_STRIP, POLYGON and QUADS.  So they bear directly on three of
the four candidates.

They were missed twice over: `pair_rule_candidates.py` detects the gradient by
counting distinct TEXTUAL `SetDiffuse` arguments, and `kPalette[i]` in a loop
is one string; and `interpolator_phase.py`'s row census drops any row with
fewer than 50 qualifying positions per parity, which a 60-px draw can never
reach.

WHAT THE MEASUREMENT IS.

Per block, over the block's own framebuffer rectangle, pooled:

    E = P(v[x] == v[x+1])  over qualifying EVEN x
    O = P(v[x] == v[x+1])  over qualifying ODD  x

Qualification is `pair_census_38.qualifying` -- a bounded monotone ramp, no
width floor.  Parity is taken in FRAMEBUFFER x, not in the sub-image, because
the rule is about the screen grid.

**A pair-constant field gives E = 1 at ANY gradient steepness**, because within
a pair the two pixels are equal by construction.  That is what makes a steep
ramp a good probe rather than a bad one, and it is the same argument the prior
lane used to accept `High_vertex_count` as a negative.  So E ~ 0 on a block
with a real gradient is a hard negative, not an unmeasured one.

CONTROLS, run by this script every time, because a null result decides
something here:

  positive  `Alpha_func` band        E - O must be large (measured +0.977)
  positive  `Context_switch/GRZero`  E - O must be large (measured +0.789)
  negative  `High_vertex_count`      E - O ~ 0           (measured  0.000)

If either positive control collapses, the instrument has gone blind and the
Fill readings are not evidence; the script says so and withholds the verdict.

Run:  python3 docs/testing/pair_fill_blocks_38.py
"""

import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pair_census_38 import qualifying  # noqa: E402

G = "/home/justin/goldens/results"

# Draw() is called at x = 640*0.25 = 160, y = 480*0.10 = 48, and every block's
# vertices are literals in line_width_tests.cpp.  These rectangles are the
# blocks' bounding boxes in Draw()-local coordinates.
OX, OY = 160, 48
BLOCKS = [
    ("TRIANGLES",    "tri",  "~78px", (232, 310, 19, 103)),
    ("QUAD_STRIP",   "quad", "105px", (0, 105, 120, 239)),
    ("TRIANGLE_FAN", "tri",  "~94px", (115, 210, 120, 239)),
    ("POLYGON",      "poly", "~99px", (218, 317, 120, 232)),
    ("QUADS",        "quad", " 60px", (0, 60, 340, 426)),
]
FILLS = ("Fill_0000.0", "Fill_0001.0", "Fill_0032.0")


def pair_stats(path, x0, x1, y0, y1):
    a = np.array(Image.open(path).convert("RGBA"))
    sub = a[y0:y1, x0:x1]
    m, same = qualifying(sub)
    gx = np.arange(m.shape[1]) + x0          # framebuffer parity, not sub-image
    ev = m & (gx % 2 == 0)[None, :]
    od = m & (gx % 2 == 1)[None, :]
    ne, no = int(ev.sum()), int(od.sum())
    if ne < 50 or no < 50:
        return ne, no, None, None
    return ne, no, (same & ev).sum() / ne, (same & od).sum() / no


def line(label, r):
    ne, no, E, O = r
    if E is None:
        print("   %-38s too few positions (%d / %d)" % (label, ne, no))
        return None
    print("   %-38s even=%5d odd=%5d  E=%.4f O=%.4f  E-O=%+.4f"
          % (label, ne, no, E, O, E - O))
    return E - O


def main():
    print(__doc__.split("Run:")[0].rstrip())
    print()

    print("CONTROLS")
    pos1 = line("Alpha_func band (4F, quad, 512px)",
                pair_stats(G + "/Alpha_func/AlphaFuncAlways_Disabled.png",
                           64, 576, 100, 180))
    pos2 = line("GRZero polygon (4F, poly, 512px)",
                pair_stats(G + "/Context_switch/GRZero.png", 64, 576, 48, 240))
    neg = line("High_vertex_count (arrays, 6x6 quads)",
               pair_stats(G + "/High_vertex_count/HighVtxCount-arrays.png",
                          90, 550, 150, 330))

    ok = (pos1 is not None and pos1 > 0.5 and pos2 is not None and pos2 > 0.5
          and neg is not None and abs(neg) < 0.1)
    if not ok:
        print("\n   CONTROLS FAILED -- the instrument cannot separate a paired")
        print("   draw from an unpaired one here, so nothing below is evidence.")
        return 1

    gaps = []
    for cap in FILLS:
        print("\n%s -- filled blocks, all SET_VERTEX3F, all 60-105 px" % cap)
        for name, prim, wide, (x0, x1, y0, y1) in BLOCKS:
            g = line("%-12s (3F, %-4s %s)" % (name, prim, wide),
                     pair_stats("%s/Line_width/%s.png" % (G, cap),
                                OX + x0, OX + x1, OY + y0, OY + y1))
            if g is not None:
                gaps.append((cap, name, g))

    print("\nVERDICT")
    worst = max(abs(g) for _, _, g in gaps)
    print("   %d block readings across %d captures; largest |E - O| = %.4f"
          % (len(gaps), len(FILLS), worst))
    print("   positive controls: %+.4f, %+.4f    negative control: %+.4f"
          % (pos1, pos2, neg))
    if worst < 0.1:
        print("""
   Every filled block is UNPAIRED.  Two of the four candidate selectors
   predicted that these would pair:

     immediate /\\ w = 1                      -- REFUTED, these satisfy it
     immediate /\\ w = 1 /\\ QUADS or POLYGON  -- REFUTED, the QUADS block (60px)
                                                and the POLYGON block (99px)
                                                satisfy it
   Two predicted that they would not, and survive:

     immediate /\\ w = 1 /\\ width >= 512      -- consistent, all blocks <= 105px
     immediate /\\ w = 1 /\\ SET_VERTEX4F      -- consistent, all blocks are 3F

   The tie is now TWO-way, not four-way, and the two survivors are exactly
   confounded in this evidence: every Fill block is both narrow AND 3F.
   One new capture separates them -- the Alpha_func band at its full 512 px
   submitted through SET_VERTEX3F, or the same band narrowed to 128 px and
   left on SET_VERTEX4F.  Either one decides it alone.""")
    else:
        print("   A block pairs; re-read the table, the tie has broken the")
        print("   other way and the bare conjunction may be right after all.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
