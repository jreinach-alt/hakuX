#!/usr/bin/env python3
"""#38 mechanism 2: is the pair group 2x1 or 2x2?  Answered from the goldens.

WHY THIS IS A QUESTION AT ALL.

#38 mechanism 2 says silicon holds the interpolated colour constant across the
even-aligned pixel pair {2m, 2m+1} in x and evaluates it at the pair's right
edge.  That was fixed on `Alpha_func`'s red and blue bands, which are CONSTANT
IN Y and therefore carry no y information whatever.  So whether the group is
2x1 (a pair in x only) or 2x2 (a quad in x and y) is not settled by the
instrument that established the rule, and `issue57-is-issue38-mech2.md` records
it as the lane's second-least-certain point:

    "the group is established in x only.  Whether silicon's group is 2x1 or
    2x2 is not settled by the two positives ... The clean y statement is
    `Attrib_float`'s: no y pairing, phase +0.033 px.  It is an RGB ramp on an
    UNPAIRED DRAW, so it bounds our own y phase and says nothing about a
    paired draw's."

The blocker on #38 asks for five new upstream captures, and the fourth of them
is "the ramp running in y instead of x -- separates whether the group is 2x1 or
2x2".

WHY THAT DISMISSAL IS WRONG, AND THIS IS THE WHOLE POINT.

`Attrib_float` is not an unpaired draw outside the class.  It is a MEMBER of
the class, by the same three criteria the lane itself used:

  A  screen space, no perspective divide  -- `PassthroughVertexShader`, and
     `CreateGeometry` writes {x, y, 1, 1}, an explicit w = 1
  B  immediate-mode vertices              -- SetDiffuse/SetVertex inside one
     Begin(PRIMITIVE_QUADS)/End()
  C  a per-vertex diffuse gradient        -- `from` on the top two vertices,
     `to` on the bottom two

`attribute_float_tests.cpp` lines 114-178.  It was missed because
`pair_rule_candidates.py` detects C by counting DISTINCT TEXTUAL SetDiffuse
arguments inside a block, and this draw sets its colour in a loop:

    for (int v = 0; v < vb.size(); v += 8) {
      host_.SetDiffuse(vb[v + 4], vb[v + 5], vb[v + 6], vb[v + 7]);
      host_.SetVertex(&vb[v]);
    }

which is ONE textual call carrying four different colours.  The enumeration
therefore read the class as having two members when it has three.

So `Attrib_float` is a class member carrying a pure Y ramp, and the question
the fourth requested capture was to answer is answerable from the corpus.

WHAT THIS INSTRUMENT WOULD SHOW IF THE THING WERE PRESENT, stated before the
number, because a null result decides something here:

  If the group were 2x2, silicon would hold the colour constant across the
  even-aligned row pair {2n, 2n+1}, so EVERY y step in the ramp would land at
  an even y and the parity skew would be 1.000.
  If the group is 2x1, y steps fall where the ramp crosses a byte boundary,
  with no parity preference, and the skew sits at 0.5.

THE CONTROL THAT MAKES THE NULL READABLE.  The same routine is run on
`Alpha_func`'s x bands, where the pair IS known to be present.  If it reports
a skew near 1.0 there and near 0.5 on `Attrib_float`'s y, the instrument can
see a pairing when one exists and the y null is evidence.  If it reported 0.5
on both, it would be blind and the y reading would mean nothing.

Run:  python3 docs/testing/pair_y_group_38.py
"""

import sys

import numpy as np
from PIL import Image

GOLDENS = "/home/justin/goldens/results"

# Attrib_float captures whose ramp is a real 0..255 sweep.  The exceptional
# value tests (INF, NaN) do not produce a monotone ramp and are excluded by
# the ramp filter below rather than by name.
ATTRIB = ["0_1", "-1_1", "-8_1", "0_8", "1_8", "-Max_Max", "-Min_Min",
          "-MinN_MinN", "-MaxSN_MaxSN", "-1_1"]


def steps_along(vals):
    """Positions where a 1-D byte sequence changes, and whether it is a ramp.

    Returns (list of indices i where vals[i] != vals[i+1], monotone?).
    Only unit-ish steps count: a jump of more than 8 is an edge, not a ramp
    crossing, and would otherwise let the quad's border into the tally.
    """
    d = np.diff(vals.astype(int))
    idx = np.nonzero(d)[0]
    if idx.size == 0:
        return [], False
    big = np.abs(d[idx]) > 8
    mono = (d[idx][~big] >= 0).all() or (d[idx][~big] <= 0).all()
    return [int(i) for i in idx[~big]], mono


def scan_y(path, channel=1):
    """Tally y-step parity down every column that carries a clean y ramp."""
    a = np.array(Image.open(path).convert("RGB"))
    h, w, _ = a.shape
    ev = od = 0
    cols = 0
    for x in range(w):
        col = a[:, x, channel]
        # Restrict to the interior: drop the top rows, where pb_print lives.
        col = col[80:h - 8]
        span = int(col.max()) - int(col.min())
        if span < 64:
            continue
        idx, mono = steps_along(col)
        if not mono or len(idx) < 8:
            continue
        cols += 1
        for i in idx:
            y = i + 80
            if y % 2 == 0:
                ev += 1
            else:
                od += 1
    return cols, ev, od


def scan_x(path, channel=2, y0=80):
    """Tally x-step parity across every row that carries a clean x ramp."""
    a = np.array(Image.open(path).convert("RGB"))
    h, w, _ = a.shape
    ev = od = 0
    rows = 0
    for y in range(y0, h - 8):
        row = a[y, :, channel]
        span = int(row.max()) - int(row.min())
        if span < 64:
            continue
        idx, mono = steps_along(row)
        if not mono or len(idx) < 8:
            continue
        rows += 1
        for i in idx:
            x = i
            if x % 2 == 0:
                ev += 1
            else:
                od += 1
    return rows, ev, od


def skew(ev, od):
    n = ev + od
    return (max(ev, od) / n) if n else float("nan")


def main():
    print(__doc__.split("Run:")[0].rstrip())
    print()

    print("CONTROL -- x steps on Alpha_func, where the pair is KNOWN present.")
    print("A 2-pixel group in x puts every step at one parity: skew -> 1.000.\n")
    print("   %-40s %6s %8s %8s %7s" % ("capture", "rows", "even", "odd", "skew"))
    tot_e = tot_o = 0
    for cap in ("AlphaFuncAlways_Disabled", "AlphaFuncAlways_Enabled",
                "AlphaFuncNotEqual_Enabled", "AlphaFuncGreaterThan_Enabled"):
        p = "%s/Alpha_func/%s.png" % (GOLDENS, cap)
        try:
            r, e, o = scan_x(p)
        except FileNotFoundError:
            print("   %-40s MISSING" % cap)
            continue
        tot_e += e
        tot_o += o
        print("   %-40s %6d %8d %8d %7.3f" % (cap, r, e, o, skew(e, o)))
    print("   %-40s %6s %8d %8d %7.3f"
          % ("POOLED", "", tot_e, tot_o, skew(tot_e, tot_o)))

    print("\nTHE MEASUREMENT -- y steps on Attrib_float, a class member whose")
    print("ramp runs in y.  2x2 predicts skew 1.000; 2x1 predicts 0.500.\n")
    print("   %-40s %6s %8s %8s %7s" % ("capture", "cols", "even", "odd", "skew"))
    ye = yo = 0
    import os
    d = "%s/Attrib_float" % GOLDENS
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".png"):
            continue
        c, e, o = scan_y(os.path.join(d, fn))
        if c == 0:
            continue
        ye += e
        yo += o
        print("   %-40s %6d %8d %8d %7.3f" % (fn[:-4], c, e, o, skew(e, o)))
    print("   %-40s %6s %8d %8d %7.3f"
          % ("POOLED", "", ye, yo, skew(ye, yo)))

    print("\nVERDICT")
    sx, sy = skew(tot_e, tot_o), skew(ye, yo)
    print("   x on Alpha_func (pair present): skew %.3f over %d steps" % (sx, tot_e + tot_o))
    print("   y on Attrib_float (class member): skew %.3f over %d steps" % (sy, ye + yo))
    if sx > 0.9 and sy < 0.6:
        print("   => the instrument SEES a 2-px group in x and does NOT see one")
        print("      in y on a class member.  THE GROUP IS 2x1.")
    elif sx <= 0.9:
        print("   => CONTROL FAILED: the instrument cannot see the known x pair,")
        print("      so the y reading is not evidence.  Do not use this result.")
    else:
        print("   => y also skewed; the group may be 2x2.  Read the table.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
