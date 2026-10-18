#!/usr/bin/env python3
"""Lay images side by side at one height, each with a caption, into one PNG (the evidence strips in NOTES.md).

usage: strip.py OUT.png HEIGHT IMG:CAPTION [IMG:CAPTION ...]
"""
import sys

from PIL import Image, ImageDraw


def main():
    out, h = sys.argv[1], int(sys.argv[2])
    tiles = []
    for spec in sys.argv[3:]:
        path, cap = spec.split(":", 1)
        im = Image.open(path).convert("RGB")
        im = im.resize((max(1, im.width * h // im.height), h), Image.NEAREST)
        t = Image.new("RGB", (im.width, h + 14), (40, 40, 40))
        t.paste(im, (0, 14))
        ImageDraw.Draw(t).text((2, 1), cap, fill=(255, 255, 255))
        tiles.append(t)
    w = sum(t.width for t in tiles) + 4 * (len(tiles) - 1)
    s = Image.new("RGB", (w, h + 14), (0, 0, 0))
    x = 0
    for t in tiles:
        s.paste(t, (x, 0))
        x += t.width + 4
    s.save(out, optimize=True)
    print("%s %dx%d" % (out, s.width, s.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
