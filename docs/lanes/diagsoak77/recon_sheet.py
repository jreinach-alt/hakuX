#!/usr/bin/env python3
"""Contact-sheet a frame dump's PPMs so a human can see what scene it caught.

    recon_sheet.py OUT.png COLSxROWS PPM...

Reconnaissance only.  The images of a schema-1 or schema-2 dump are not
pairable with their draw records (see framedump_check.py), so a sheet built
from one says what the title was RENDERING and nothing about which draws
produced it.
"""
import sys

from PIL import Image

TW, TH = 213, 160


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    out, grid, paths = argv[1], argv[2], argv[3:]
    cols, _, rows = grid.partition("x")
    cols, rows = int(cols), int(rows)
    sheet = Image.new("RGB", (cols * TW, rows * TH))
    for i, p in enumerate(paths[:cols * rows]):
        im = Image.open(p).resize((TW, TH))
        sheet.paste(im, ((i % cols) * TW, (i // cols) * TH))
    sheet.save(out)
    print("%s: %d tiles of %dx%d, source frames %s"
          % (out, min(len(paths), cols * rows), TW, TH,
             Image.open(paths[0]).size))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
