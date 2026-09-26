#!/usr/bin/env python3
"""#13 line-mode families: split the residual into COLOUR and PLACEMENT, and
measure placement per minor-axis cut.  Goldens and captures on disk only.

Ink = a pixel that differs from the capture's background (its modal colour).

  placement px   ink in exactly one of golden / ours
  colour px      ink in both, max channel delta > 8
  shade px       ink in both, 0 < delta <= 8 (interpolation noise, not scored)

Cuts: every column (and every row) is scanned for isolated thin ink runs
(length <= 3, background for 2 px either side) in the GOLDEN.  The same
column of OUR capture is searched for a run overlapping [a-2, b+2].  A cut is

  exact    same a and b
  shift    same length, moved by k px (k recorded, signed ours - golden)
  size     different length
  absent   no run in ours          (e.g. a culled edge we drew, or v.v.)
and every thin run in OURS with no golden run nearby is `extra`.

Column cuts sample x-major strokes (the minor axis is y), row cuts sample
y-major strokes.  A stroke rule (extent, phase, tie) acts on the minor axis,
so it can only move `exact` <-> `shift`/`size`; it cannot make `absent` or
`extra`, and it cannot touch `colour`.
"""
import argparse
import collections
import glob
import os

import numpy as np
from PIL import Image

G = os.path.expanduser("~/goldens/results")
FAMS = {"Front_face": "FrontFace_LM_*", "Shade_model": "ProgLM_*",
        "3D_primitive": "Line*"}
# pb_print labels: top-left block on every capture, and front_face's two
# pb_printat labels (row 8, cols 19 and 38).  Identical in both images, and
# dense enough to read as thin runs, so they are masked rather than scored.
MASKS = {"*": [(0, 0, 640, 100)],
         "Front_face": [(195, 215, 250, 250), (385, 215, 425, 250)]}


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def background(img):
    flat = img.reshape(-1, 3)
    vals, counts = np.unique(flat, axis=0, return_counts=True)
    return vals[counts.argmax()]


def ink(img):
    return np.any(img != background(img), axis=2)


def thin_runs(v, maxlen=3, pad=2):
    """Isolated runs of True in a 1-D bool array: (a, b) inclusive."""
    out = []
    n = len(v)
    i = 0
    while i < n:
        if v[i]:
            j = i
            while j + 1 < n and v[j + 1]:
                j += 1
            if j - i + 1 <= maxlen:
                lo, hi = max(0, i - pad), min(n, j + pad + 1)
                if v[lo:i].sum() == 0 and v[j + 1:hi].sum() == 0:
                    out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def score_axis(gi, oi, axis):
    """axis 0: column cuts (x-major strokes); axis 1: row cuts."""
    res = collections.Counter()
    shifts = collections.Counter()
    if axis == 1:
        gi, oi = gi.T, oi.T
    for x in range(gi.shape[1]):
        gcol, ocol = gi[:, x], oi[:, x]
        oruns = thin_runs(ocol)
        used = set()
        for a, b in thin_runs(gcol):
            m = [r for r in oruns if r[1] >= a - 2 and r[0] <= b + 2]
            if not m:
                # a long or merged run in ours still counts as present
                res["absent" if not ocol[max(0, a - 2):b + 3].any()
                    else "size"] += 1
                continue
            r = m[0]
            used.add(r)
            if r == (a, b):
                res["exact"] += 1
            elif r[1] - r[0] == b - a:
                res["shift"] += 1
                shifts[r[0] - a] += 1
            else:
                res["size"] += 1
        for r in oruns:
            if r not in used and not gcol[max(0, r[0] - 2):r[1] + 3].any():
                res["extra"] += 1
    return res, shifts


def masked(suite, shape):
    m = np.ones(shape, bool)
    for x0, y0, x1, y1 in MASKS["*"] + MASKS.get(suite, []):
        m[y0:y1, x0:x1] = False
    return m


def analyse(cap, suite, test):
    g = load(os.path.join(G, suite, test + ".png"))
    c = os.path.join(cap, "%s::%s.png" % (suite, test))
    if not os.path.exists(c):
        return None
    o = load(c)
    keep = masked(suite, g.shape[:2])
    gi, oi = ink(g) & keep, ink(o) & keep
    d = np.abs(g - o).max(2)
    px = {"placement": int((gi ^ oi).sum()),
          "golden_only": int((gi & ~oi).sum()),
          "ours_only": int((oi & ~gi).sum()),
          "colour": int((gi & oi & (d > 8)).sum()),
          "shade": int((gi & oi & (d > 0) & (d <= 8)).sum()),
          "ink": int(gi.sum())}
    cuts = {}
    for axis, name in ((0, "col"), (1, "row")):
        cuts[name] = score_axis(gi, oi, axis)
    return px, cuts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", action="append", required=True,
                    help="captures dir; repeat, first hit wins")
    ap.add_argument("--family", choices=list(FAMS), action="append")
    ap.add_argument("--per-capture", action="store_true")
    args = ap.parse_args()
    for suite in args.family or list(FAMS):
        tot = collections.Counter()
        cut_tot = {"col": collections.Counter(), "row": collections.Counter()}
        sh_tot = {"col": collections.Counter(), "row": collections.Counter()}
        n = 0
        for gp in sorted(glob.glob(os.path.join(G, suite, FAMS[suite] + ".png"))):
            test = os.path.basename(gp)[:-4]
            r = None
            for cap in args.cap:
                r = analyse(cap, suite, test)
                if r:
                    break
            if not r:
                print("  MISSING", suite, test)
                continue
            n += 1
            px, cuts = r
            tot.update(px)
            for k in cuts:
                cut_tot[k].update(cuts[k][0])
                sh_tot[k].update(cuts[k][1])
            if args.per_capture:
                c, s = cuts["col"]
                rr, rs = cuts["row"]
                print("  %-34s place %5d (g %5d o %5d) colour %5d | col %s %s | row %s %s"
                      % (test, px["placement"], px["golden_only"],
                         px["ours_only"], px["colour"], dict(c), dict(s),
                         dict(rr), dict(rs)))
        print("%s: %d captures" % (suite, n))
        print("  px   ink %d  placement %d (golden-only %d, ours-only %d)  "
              "colour %d  shade %d" % (tot["ink"], tot["placement"],
                                       tot["golden_only"], tot["ours_only"],
                                       tot["colour"], tot["shade"]))
        for k in ("col", "row"):
            c = cut_tot[k]
            scored = c["exact"] + c["shift"] + c["size"]
            print("  %s cuts  exact %d  shift %d  size %d  absent %d  extra %d"
                  "   exact/(present) %.2f%%   shifts %s"
                  % (k, c["exact"], c["shift"], c["size"], c["absent"],
                     c["extra"], 100.0 * c["exact"] / max(1, scored),
                     dict(sorted(sh_tot[k].items()))))


if __name__ == "__main__":
    main()
