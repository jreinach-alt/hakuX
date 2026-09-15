#!/usr/bin/env python3
"""Read the fixed-function quad extents out of every Viewport capture.

The Viewport suite draws four fixed-function quads at known integer screen
positions and sweeps SetViewportOffset; #49 is the two offsets that put the
post-offset coordinate exactly on a 1/16 snap boundary. This probe reports,
per quad and per capture, the exact covered extent in the golden and in ours,
and classifies each vertex as HIGH (the edge stayed at n + 9/16, so pixel n
is not covered on a left edge) or LOW (the snap dropped it to n + 8/16, so
pixel n is covered).

It reads whole runs, never point samples. Fixed function is drawn last, so
the FF colour is the exact extent of FF coverage; and each extent is taken
along a scan line that crosses only the quads being measured, so every
number below is the end of a 99-100 px run of one colour:

    row 190 crosses prog q0, FF q1, prog q2, FF q3   -> x extents, band 0
    row 290 crosses FF q4, prog q5, FF q6, prog q7   -> x extents, band 1
    col 150 crosses prog q0 then FF q4               -> y extent of q4
    col 250 crosses FF q1 then prog q5               -> y extent of q1
    col 350 crosses prog q2 then FF q6               -> y extent of q6
    col 450 crosses FF q3 then prog q7               -> y extent of q3

The HIGH/LOW distinction only means anything at the two failing offsets. At
0, +-17/32 and +-1 both hypotheses predict the same coverage -- which is why
those ten captures cannot see this -- so for them only the gold-equals-ours
verdict carries information, not the label.

It also prints the residual a small negative pre-snap bias would leave. Such
a bias drops every grid-exact value one step, which makes +9/16 render as
offset 0 does and -7/16 render as -17/32 does; both of those are already
bit-identical to their goldens, so the residual is the golden-to-golden
difference and needs no device run. See
docs/investigations/viewport-9-16-boundary.md.

Usage: probe_viewport_ff_extents.py GOLDEN_DIR CAPTURE_DIR
  GOLDEN_DIR   e.g. ~/goldens/results/Viewport
  CAPTURE_DIR  e.g. ~/hakux-work/res_Viewport  (files "Viewport::<name>.png")
Needs numpy and pillow.
"""
import math
import os
import sys

import numpy as np
from PIL import Image

# Captures are stored with the channels in BGR order.
FF = (187, 51, 0)  # 0xFF0033BB, the fixed-function quads

# quad -> (nominal x0, x1, y0, y1), the scan row for its x extent (which run
# of FF on that row, 0 or 1), and the column for its y extent.
QUADS = {
    "q1": ((220, 320, 140, 240), 190, 0, 250),
    "q3": ((420, 520, 140, 240), 190, 1, 450),
    "q4": ((120, 220, 240, 340), 290, 0, 150),
    "q6": ((320, 420, 240, 340), 290, 1, 350),
}

# Scale-0 sweep only; the five scale-2.0 twins are identical on both sides.
SWEEP = [
    (0.0, "0.000_0.000-0.000_0.000"),
    (0.53125, "0.531_0.531-0.000_0.000"),
    (0.5625, "0.562_0.562-0.000_0.000"),
    (-0.53125, "-0.531_-0.531-0.000_0.000"),
    (-0.4375, "-0.438_-0.438-0.000_0.000"),
    (1.0, "1.000_1.000-0.000_0.000"),
    (-1.0, "-1.000_-1.000-0.000_0.000"),
]

# A tiny negative pre-snap bias renders these offsets as their surrogate does.
BIAS_SURROGATE = {
    "0.562_0.562-0.000_0.000": "0.000_0.000-0.000_0.000",
    "-0.438_-0.438-0.000_0.000": "-0.531_-0.531-0.000_0.000",
}


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


def ff_runs(line):
    """Start/end index of each maximal run of the FF colour along a line."""
    m = np.abs(line - np.array(FF)).max(axis=1) <= 6
    runs = []
    start = None
    for i, v in enumerate(m):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(m) - 1))
    return runs


def extent(img, row, run_index, col):
    xr = ff_runs(img[row])
    yr = ff_runs(img[:, col])
    if len(xr) <= run_index or len(yr) != 1:
        return None
    return xr[run_index] + yr[0]


def classify(seen, nominal, off):
    """HIGH/LOW per vertex. A low (left/top) edge at n covers pixel n only if
    the snapped edge is at or below the sample at n + 0.5; a high (right or
    bottom) edge at n covers pixel n only if it is above that sample."""
    out = {}
    for n, got, is_low in zip(nominal, seen,
                              (True, False, True, False)):
        exact = n + off
        hi = math.ceil(exact - 0.5) - (0 if is_low else 1)
        lo = math.ceil(exact - 1 / 16 - 0.5) - (0 if is_low else 1)
        out[n] = "HIGH" if got == hi else ("LOW" if got == lo else "?%d" % got)
    return out


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    gold_dir, ours_dir = sys.argv[1], sys.argv[2]
    disagree = 0

    for off, name in SWEEP:
        g = load(os.path.join(gold_dir, name + ".png"))
        o = load(os.path.join(ours_dir, "Viewport::" + name + ".png"))
        px = int((g != o).any(axis=2).sum())
        print(f"=== offset {off:+.5f}  {name}  {px} differing px")
        for q, (nominal, row, idx, col) in QUADS.items():
            rg = extent(g, row, idx, col)
            ro = extent(o, row, idx, col)
            if rg is None or ro is None:
                print(f"  {q}: could not isolate a run")
                continue
            cg = classify(rg, nominal, off)
            co = classify(ro, nominal, off)
            if rg != ro:
                disagree += 1
            print(f"  {q} nominal x[{nominal[0]},{nominal[1]}] "
                  f"y[{nominal[2]},{nominal[3]}]")
            print(f"     gold x[{rg[0]}..{rg[1]}] y[{rg[2]}..{rg[3]}]  "
                  + " ".join(f"{k}:{v}" for k, v in cg.items())
                  + ("" if rg == ro else "   <<< DIFFERS"))
            print(f"     ours x[{ro[0]}..{ro[1]}] y[{ro[2]}..{ro[3]}]  "
                  + " ".join(f"{k}:{v}" for k, v in co.items()))

    print("\n=== residual a small negative pre-snap bias would leave")
    total_now = total_bias = 0
    for name, surrogate in BIAS_SURROGATE.items():
        gold = load(os.path.join(gold_dir, name + ".png"))
        now = int((gold != load(os.path.join(
            ours_dir, "Viewport::" + name + ".png"))).any(axis=2).sum())
        sg = load(os.path.join(gold_dir, surrogate + ".png"))
        so = load(os.path.join(ours_dir, "Viewport::" + surrogate + ".png"))
        check = int((sg != so).any(axis=2).sum())
        bias = int((gold != sg).any(axis=2).sum())
        print(f"  {name}: current {now} px -> bias {bias} px "
              f"(surrogate {surrogate} gold-vs-ours {check} px, must be 0)")
        total_now += now
        total_bias += bias
    print(f"  total {total_now} px -> {total_bias} px")
    print(f"\n{disagree} quad extents differ from gold across the sweep")
    return 0


if __name__ == "__main__":
    sys.exit(main())
