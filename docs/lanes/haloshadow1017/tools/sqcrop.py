#!/usr/bin/env python3
"""Crop + contrast-stretch a region of a PPM/PNG, and print per-row channel
means, to look for a silhouette inside a shadow square (#1038).

  sqcrop.py IMAGE X0 Y0 X1 Y1 OUT.png [SCALE]
"""
import sys
from PIL import Image


def main():
    path, x0, y0, x1, y1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
    scale = int(sys.argv[7]) if len(sys.argv) > 7 else 4
    im = Image.open(path).convert("RGB").crop((x0, y0, x1, y1))
    px = list(im.getdata())
    lo = [min(p[c] for p in px) for c in range(3)]
    hi = [max(p[c] for p in px) for c in range(3)]
    st = Image.new("RGB", im.size)
    st.putdata([tuple(int(255 * (p[c] - lo[c]) / max(1, hi[c] - lo[c])) for c in range(3))
                for p in px])
    st.resize((im.size[0] * scale, im.size[1] * scale), Image.NEAREST).save(out)
    w = im.size[0]
    for y in range(0, im.size[1], 2):
        row = px[y * w:(y + 1) * w]
        print(f"y{y0 + y:4d} " + " ".join(f"{p[0]:3d},{p[1]:3d},{p[2]:3d}"
                                         for p in row[::max(1, w // 12)]))


if __name__ == "__main__":
    main()
