#!/usr/bin/env python3
"""Per-row lit share of one probe frame, printed as runs of dark rows, in the frame's own rows and in guest rows.

usage: rowlit.py <frame.ppm> [guest_height=480] [pitch=2560]
A row is dark when under 2% of its pixels have any channel above 16. Each dark run is printed with the guest rows it
covers (scaled by guest_height / frame height) and the guest byte offsets those rows start at (row * pitch), so a band
can be set against a memory map.
"""
import sys

from PIL import Image


def main():
    p = sys.argv[1]
    gh = int(sys.argv[2]) if len(sys.argv) > 2 else 480
    pitch = int(sys.argv[3]) if len(sys.argv) > 3 else 2560
    im = Image.open(p).convert("RGB")
    w, h = im.size
    px = im.load()
    dark = []
    for y in range(h):
        lit = sum(1 for x in range(w) if max(px[x, y]) > 16)
        dark.append(lit < 0.02 * w)
    s = h / gh
    print("frame %dx%d, guest height %d, pitch %d" % (w, h, gh, pitch))
    y = 0
    while y < h:
        if dark[y]:
            y0 = y
            while y < h and dark[y]:
                y += 1
            g0, g1 = int(y0 / s), int(y / s)
            print("dark rows %d-%d (%.2f-%.2f of height): guest rows %d-%d, offsets 0x%06x-0x%06x" % (
                y0, y - 1, y0 / h, y / h, g0, g1 - 1, g0 * pitch, g1 * pitch))
        else:
            y += 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
