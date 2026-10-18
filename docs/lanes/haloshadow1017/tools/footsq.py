#!/usr/bin/env python3
"""Stock-driver square vs a correct driver's frame, aligned and by region (#1038).

  footsq.py A B REF=x0,y0,x1,y1 BOX=x0,y0,x1,y1 [NAME=x0,y0,x1,y1 ...]

A and B are two frames of the same camera shot from different sessions (PPM or PNG, 640x480).
REF is a static background box (no characters). The integer shift (dx, dy) within +-8 px that
minimises the mean absolute difference over REF aligns B onto A. Then, over BOX, it prints a map
of A / B luminance: '#' < 0.80, '+' < 0.90, '.' within 0.90-1.10, 'o' > 1.10. Then, for each
NAME box, it prints the mean r, g, b of A and of shifted B, their per-channel ratio, and the count
of pixels with luminance ratio < 0.85. A floor box inside a stock square reads well under 1 on a
stock-vs-correct pair; a control box reads ~1.0.
"""
import sys
import numpy as np
from PIL import Image


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)


def box(s):
    return tuple(int(v) for v in s.split(","))


def shifted(b, dx, dy, x0, y0, x1, y1):
    return b[y0 + dy:y1 + dy, x0 + dx:x1 + dx]


def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    named = dict(arg.split("=", 1) for arg in sys.argv[3:])
    rx0, ry0, rx1, ry1 = box(named.pop("REF"))
    bx0, by0, bx1, by1 = box(named.pop("BOX"))
    best = None
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            d = np.abs(a[ry0:ry1, rx0:rx1] - shifted(b, dx, dy, rx0, ry0, rx1, ry1)).mean()
            if best is None or d < best[0]:
                best = (d, dx, dy)
    mad, dx, dy = best
    print(f"shift B by ({dx},{dy}); REF mean |A-B| {mad:.2f}")
    la = lum(a[by0:by1, bx0:bx1])
    lb = lum(shifted(b, dx, dy, bx0, by0, bx1, by1))
    r = la / np.maximum(lb, 1)
    for y in range(0, r.shape[0], 4):
        row = ""
        for x in range(0, r.shape[1], 4):
            v = r[y:y + 4, x:x + 4].mean()
            row += "#" if v < 0.80 else "+" if v < 0.90 else "o" if v > 1.10 else "."
        print(f"y{by0 + y:4d} {row}")
    print(f"     x from {bx0}, 4 px a column")
    for name, s in named.items():
        x0, y0, x1, y1 = box(s)
        pa = a[y0:y1, x0:x1].reshape(-1, 3)
        pb = shifted(b, dx, dy, x0, y0, x1, y1).reshape(-1, 3)
        ma, mb = pa.mean(0), pb.mean(0)
        rr = lum(a[y0:y1, x0:x1]) / np.maximum(lum(shifted(b, dx, dy, x0, y0, x1, y1)), 1)
        print(f"{name:8s} {x0},{y0},{x1},{y1} n={len(pa)}  A {ma[0]:.1f},{ma[1]:.1f},{ma[2]:.1f}"
              f"  B {mb[0]:.1f},{mb[1]:.1f},{mb[2]:.1f}"
              f"  A/B {ma[0]/mb[0]:.3f},{ma[1]/mb[1]:.3f},{ma[2]/mb[2]:.3f}"
              f"  lum<0.85: {int((rr < 0.85).sum())}")


if __name__ == "__main__":
    main()
