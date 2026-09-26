#!/usr/bin/env python3
"""#53: test the six-slot carry model on the lit ControlFlags_VS quads.

    cf53_slots.py [--root /home/justin/goldens/results]

For `Specular` and `Specular_back`, it reads the eight lit diffuse quads (rows
1 and 3) of `ControlFlags_VS`. Each corner's red value comes from a plane fit
per triangle, split on the UL-LR diagonal. The corner is classed H or L at the
midpoint between `ControlFlags_FF`'s two corner levels.

The model: a lit vertex-program vertex reads one of six slots, which hold the
fixed-function lighting results of the last six vertices of the preceding FF
draw. The slot word is therefore *predicted*, not fitted: it is the H/L
pattern of `ControlFlags_FF`'s final two quads read as a vertex stream, taking
the last six. Corners UL, UR, LR and LL of one quad read four consecutive
slots.

It reports, per suite:
- whether the distinct corner codes are windows of the predicted word;
- each quad's window start;
- whether the starts step by a constant within each row.

Writes nothing. Exit 0 only when every code is a window of the predicted
word AND the start steps by one constant, nonzero amount within each row. The
windows alone are not enough: shuffled quads, or the FF image itself, also
pass them. The mutation test showed both.
"""
import argparse
import sys

import numpy as np
from PIL import Image

QW, QH = 640 / 6.0, 80.0
LEFTS = [QW + i * (QW + 15) for i in range(4)]
TOPS = {1: 190.0, 3: 380.0}     # the lit diffuse rows; rows 0 and 2 are specular


def corner_values(a, left, top):
    """Red at UL, UR, LR, LL from a plane fit per triangle (UL-LR diagonal)."""
    x0, y0 = int(np.ceil(left)), int(np.ceil(top))
    q = a[y0:int(np.ceil(top + QH)), x0:int(np.ceil(left + QW)), 0].astype(float)
    h, w = q.shape
    yy, xx = np.mgrid[0:h, 0:w]
    X, Y = (xx + 0.5) / w, (yy + 0.5) / h
    fits = []
    for m in (X > Y + 0.02, Y > X + 0.02):
        A = np.stack([np.ones(m.sum()), X[m], Y[m]], 1)
        fits.append(np.linalg.lstsq(A, q[m], rcond=None)[0])
    P = lambda c, x, y: c[0] + c[1] * x + c[2] * y
    up, lo = fits
    return [0.5 * (P(up, 0, 0) + P(lo, 0, 0)), P(up, 1, 0), 0.5 * (P(up, 1, 1) + P(lo, 1, 1)), P(lo, 0, 1)]


def load(root, suite, test):
    return np.asarray(Image.open("%s/%s/%s.png" % (root, suite, test)).convert("RGB"))


def analyse(root, suite):
    ff, vs = load(root, suite, "ControlFlags_FF"), load(root, suite, "ControlFlags_VS")
    ffv = {(r, c): corner_values(ff, LEFTS[c], t) for r, t in TOPS.items() for c in range(4)}
    allff = np.concatenate([np.array(v) for v in ffv.values()])
    thr = 0.5 * (np.percentile(allff, 25) + np.percentile(allff, 75))
    hl = lambda vals: "".join("H" if v > thr else "L" for v in vals)
    last_two = hl(ffv[(3, 2)]) + hl(ffv[(3, 3)])   # the FF test's final two quads, as a vertex stream
    word = last_two[-6:]
    windows = {p: "".join(word[(p + k) % 6] for k in range(4)) for p in range(6)}
    rows, ok = [], True
    for (r, c) in sorted(ffv):
        code = hl(corner_values(vs, LEFTS[c], TOPS[r]))
        starts = [p for p, w in windows.items() if w == code]
        ok = ok and bool(starts)
        rows.append((r * 4 + c, code, starts[0] if starts else None))
    steps = {}
    for r in TOPS:
        ps = [p for d, _, p in rows if d // 4 == r]
        steps[r] = sorted({(b - a) % 6 for a, b in zip(ps, ps[1:])}) if None not in ps else None
    return thr, word, rows, steps, ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/home/justin/goldens/results")
    a = ap.parse_args()
    all_ok = True
    for suite in ("Specular", "Specular_back"):
        thr, word, rows, steps, ok = analyse(a.root, suite)
        all_ok = all_ok and ok
        print("== %s: threshold %.1f, predicted slot word %s (last six FF vertices)" % (suite, thr, word))
        print("   (draw index, code, window start): %s" % rows)
        const = all(v is not None and len(v) == 1 and v[0] != 0 for v in steps.values())
        all_ok = all_ok and const
        print("   every code a window of the word: %s; per-quad start step within rows 1 and 3: %s; constant nonzero: %s" % (ok, steps, const))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
