#!/usr/bin/env python3
"""Read Surface_pitch::Swizzle per result quad, and test Model E without a golden.

    swizzle_pitch_quads.py CAPTURE.png [GOLDEN.png]

TestSwizzle (nxdk_pgraph_tests surface_pitch_tests.cpp) draws four 128x128
result quads. Each is the raw bytes of one render target, read back as a LINEAR
A8R8G8B8 texture at pitch 512 and drawn 1:1:

    q0  64x64 swizzled, pitch 512       q1  64x64 swizzled, pitch 256
    q2  128x128 swizzled, pitch 512     q3  128x128 swizzled, pitch 256

q3 is the only undersized pitch (256 < 128 * 4). Un-swizzling a quad recovers
the surface the emulator left in guest memory. The un-swizzle uses Morton
order, x bits at even positions and y bits at odd, which is
generate_swizzle_masks() for a square power-of-two surface.

Printed per capture:

  * differing pixels against GOLDEN, per quad, when a golden is given;
  * the signature surface(x + 64, y) == surface(x, y + 1) on q2 and q3, over
    its 8,128 positions. Model E (a linear intermediate at the guest's pitch)
    makes it hold at every one. Model H (silicon) holds it only where the
    content happens to agree, which is 4,096 here;
  * the pixels of q3's top-right quadrant that are not the background green
    0x00AA00. Model E fills 63 rows of it with the checkerboard shifted up a
    row, which is 4,032 = 63 x 64.

Used on #109 (lane.remote, 2026-09-25):
  * base 84a67b9c reads 2,048 / 2,048 / 2,048 / 6,080 per quad, signature
    8,128 and top-right 4,032;
  * e4fb7c24 reads 2,048 on all four, signature 4,096 (the golden's) and
    top-right 0.
The 2,048 on every quad does not depend on pitch. There the checkerboard's
coloured cells take the colour of a later CPU write to the same texture
address.
"""

import sys

import numpy as np
from PIL import Image

WIDTH = 640
HEIGHT = 480
QUAD = 128
GREEN = np.array([0x00, 0xAA, 0x00])


def _deposit(value, mask):
    out, bit = 0, 0
    for i in range(16):
        if mask & (1 << i):
            if value & (1 << bit):
                out |= 1 << i
            bit += 1
    return out


SWIZZLE = np.array([[_deposit(x, 0x5555) | _deposit(y, 0xAAAA)
                     for x in range(QUAD)] for y in range(QUAD)])

# TestSwizzle's DrawResults(): the quads start a third of the free space in.
_TOP0 = (HEIGHT - 2 * QUAD) / 3
_TOP1 = _TOP0 * 2 + QUAD
_LEFT0 = (WIDTH - 2 * QUAD) // 3
_LEFT1 = _LEFT0 * 2 + QUAD
QUADS = (("q0 64x64 pitch 512", _LEFT0, _TOP0),
         ("q1 64x64 pitch 256", _LEFT1, _TOP0),
         ("q2 128x128 pitch 512", _LEFT0, _TOP1),
         ("q3 128x128 pitch 256", _LEFT1, _TOP1))


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


def quad_pixels(img, left, top):
    """The 128x128 texels of a 1:1 quad whose top edge is fractional:
    texel row v lands on the first pixel row whose centre is at or past
    top + v."""
    r0 = int(np.ceil(top - 0.5))
    return img[r0:r0 + QUAD, left:left + QUAD]


def unswizzle(pixels):
    return pixels.reshape(-1, 3)[SWIZZLE].reshape(QUAD, QUAD, 3)


def signature(surface):
    return int((surface[0:QUAD - 1, 64:QUAD] == surface[1:QUAD, 0:64])
               .all(axis=2).sum())


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.split("\n\n")[1])
        return 2
    cap = load(argv[1])
    gold = load(argv[2]) if len(argv) == 3 else None
    for name, left, top in QUADS:
        line = "%-22s" % name
        if gold is not None:
            r0 = int(np.ceil(top - 0.5))
            diff = (cap[r0:r0 + QUAD, left:left + QUAD]
                    != gold[r0:r0 + QUAD, left:left + QUAD]).any(axis=2)
            line += "  differing %6d" % int(diff.sum())
        if name.startswith(("q2", "q3")):
            surface = unswizzle(quad_pixels(cap, left, top))
            line += "  signature %5d of 8128" % signature(surface)
            if name.startswith("q3"):
                top_right = surface[0:64, 64:QUAD]
                line += "  top-right non-green %5d" % int(
                    (top_right != GREEN).any(axis=2).sum())
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
