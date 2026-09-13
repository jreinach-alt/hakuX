#!/usr/bin/env python3
"""Decide, from the goldens alone, whether a surface's Z/O pad bits are
written by the raster or read back by the texture unit (#59 follow-on).

The two models are not a matter of degree and this needs no capture of ours,
no mapping and no fit. `Surface format` renders its scratch surface once and
then draws it to the screen twice: the top half with the sampled surface alpha
as coverage, the bottom half with **alpha forced opaque by the combiner**. So:

  read-side model   the Z/O suffix is a constant the texture unit substitutes
                    for the pad bits when sampling. It can only ever change a
                    sampled ALPHA, so it can only change the TOP half, and it
                    can never change a colour channel.

  write-side model  the raster stores the constant into the pad bits and the
                    texture unit reads the bytes plainly. Then the O and Z
                    goldens hold DIFFERENT BYTES, and any reinterpretation of
                    those bytes differs -- including in the bottom half, and
                    including in a colour channel.

`X1R5G5B5` is the discriminating format because the test samples every surface
through one fixed `LU_IMAGE_A8R8G8B8` stage at 640x480. Two 1555 words are read
as one 8888 texel, so a 1555 pad bit (bit 15, the high bit of the word's second
byte) lands in byte 1 of the texel -- GREEN -- for the first of the two words,
and in byte 3 -- alpha -- for the second. Setting it is green +128.

The 4-byte pad formats cannot discriminate: there the surface stride equals the
texture stride, so a pad byte lands in the texel's alpha and nowhere else, and
both models predict a top-half-only difference.

Exits non-zero if the read-side model survives.

Usage:
    surface_pad_write_side.py [GOLDENS_DIR]
        default GOLDENS_DIR: /home/justin/goldens/results/Surface_format
"""
import os
import sys

import numpy as np
from PIL import Image

DEFAULT_DIR = "/home/justin/goldens/results/Surface_format"

# (name, O capture, Z capture, discriminating?) -- see the module docstring for
# why only the 2-byte pair can separate the two models.
PAIRS = [
    ("X1R5G5B5", "Fmt_X1R5G5B5_O1R5G5B5", "Fmt_X1R5G5B5_Z1R5G5B5", True),
    ("X8R8G8B8", "Fmt_X8R8G8B8_O8R8G8B8", "Fmt_X8R8G8B8_Z8R8G8B8", False),
    ("X1A7R8G8B8", "Fmt_X1A7R8G8B8_O1A7R8G8B8",
     "Fmt_X1A7R8G8B8_Z1A7R8G8B8", False),
]

# The test draws the surface to the top half with the sampled alpha and to the
# bottom half with alpha forced opaque (surface_format_tests.cpp,
# render_result). 480 rows, so the split is at 240.
SPLIT = 240


def load(d, name):
    p = os.path.join(d, name + ".png")
    if not os.path.exists(p):
        raise SystemExit("missing golden: %s" % p)
    return np.array(Image.open(p).convert("RGBA")).astype(int)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR
    verdicts = []

    for label, o_name, z_name, discriminating in PAIRS:
        go, gz = load(d, o_name), load(d, z_name)
        if go.shape != gz.shape:
            raise SystemExit("%s: goldens differ in shape" % label)

        diff = (go != gz).any(axis=2)
        bottom = diff[SPLIT:]
        # Green-only, exactly +128, with R/B/A bit-identical: the signature of
        # a 1555 pad bit read as byte 1 of an 8888 texel.
        dg = go[..., 1] - gz[..., 1]
        others_equal = ((go[..., 0] == gz[..., 0]) &
                        (go[..., 2] == gz[..., 2]) &
                        (go[..., 3] == gz[..., 3]))
        green_plus_128 = (diff & others_equal & (dg == 128))

        print("%-12s O vs Z goldens differ on %7d px  "
              "(top %7d, bottom %7d)%s"
              % (label, diff.sum(), diff[:SPLIT].sum(), bottom.sum(),
                 "" if discriminating else "   [cannot discriminate]"))

        if not discriminating:
            # Both models agree here; report it, assert nothing.
            continue

        print("             bottom half: %d px, of which green exactly +128 "
              "with R/B/A identical: %d"
              % (bottom.sum(), green_plus_128[SPLIT:].sum()))
        verdicts.append((label, int(bottom.sum()),
                         int(green_plus_128[SPLIT:].sum())))

    if not verdicts:
        raise SystemExit("no discriminating pair was scored")

    failures = []
    for label, n_bottom, n_green in verdicts:
        if n_bottom == 0:
            failures.append(
                "%s: the O and Z goldens agree in the alpha-forced half, "
                "which is what the read-side model predicts" % label)
        elif n_green != n_bottom:
            failures.append(
                "%s: %d of %d bottom-half pixels are not a clean green +128; "
                "neither model as stated accounts for the rest"
                % (label, n_bottom - n_green, n_bottom))

    if failures:
        print()
        for f in failures:
            print("FAIL  %s" % f)
        return 1

    print()
    print("WRITE-SIDE: every bottom-half difference between the O and Z "
          "goldens is a green +128 and nothing else.")
    print("The alpha-forced half cannot see a sampled alpha, and a readback "
          "constant cannot reach a colour channel, so the pad bit is stored "
          "in the surface by the raster and read back plainly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
