#!/usr/bin/env python3
"""Which Front_face line-mode primitives does silicon draw, per golden?

front_face_tests.cpp draws, per test: a CCW quad (left, x 138-310), a CW quad
(right, x 330-502), and two ZERO-AREA triangles whose three vertices share
one x (left+5 = 133 and right-5 = 507).  In line mode each is visible as its
own strokes, so presence is read off one pixel column / row each:

  left quad   golden ink on column 200 at y 100-420 (its diagonal)
  right quad  golden ink on column 470 at y 100-420 (its diagonal)
  tri @133    golden ink at x 133, y 150-400
  tri @507    golden ink at x 507, y 150-400
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lm_cuts as lc


def main(cap=None):
    for gp in sorted(glob.glob(os.path.join(lc.G, "Front_face", "FrontFace_LM_*.png"))):
        t = os.path.basename(gp)[:-4]
        row = [t]
        for src in ([gp] + ([os.path.join(cap, "Front_face::%s.png" % t)] if cap else [])):
            i = lc.ink(lc.load(src))
            row.append("L%d R%d t133:%d t507:%d" % (
                i[100:420, 200].any(), i[100:420, 470].any(),
                i[150:400, 133].any(), i[150:400, 507].any()))
        print("  %-26s golden %s%s" % (row[0], row[1],
                                        ("   ours " + row[2]) if cap else ""))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
