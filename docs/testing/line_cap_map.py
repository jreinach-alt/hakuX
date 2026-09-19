#!/usr/bin/env python3
"""Scratch: print a golden-vs-derived map of one region of one Line_* capture."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import line_priority as lp
import line_extent_phase as lep


def main():
    test_want, y0, y1, x0, x1 = sys.argv[1], *[int(v) for v in sys.argv[2:6]]
    gd = os.path.expanduser("~/goldens/results")
    for test, w, g in lp.captures(gd, 0.0, 999.0):
        if test != test_want:
            continue
        lit, valid = lep.ink(g)
        u = np.zeros_like(lit)
        for e in lp.EDGES:
            u |= lep.edge_mask(e, w)
        print(f"{test} w={w}   '#'=both '+'=ours-only 'o'=golden-only '.'=neither")
        print("     " + "".join(str((x // 100) % 10) for x in range(x0, x1)))
        print("     " + "".join(str((x // 10) % 10) for x in range(x0, x1)))
        print("     " + "".join(str(x % 10) for x in range(x0, x1)))
        for y in range(y0, y1):
            row = ""
            for x in range(x0, x1):
                a, b = bool(u[y, x]), bool(lit[y, x])
                if not valid[y, x]:
                    row += "~"
                else:
                    row += "#" if (a and b) else "+" if a else "o" if b else "."
            print(f"{y:>5}{row}")
        return


if __name__ == "__main__":
    main()
