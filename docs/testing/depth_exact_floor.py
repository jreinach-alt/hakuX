#!/usr/bin/env python3
"""An exact-floor oracle for the `Depth buffer` fixed-point depth captures.

    depth_exact_floor.py RESULTDIR/captures1 [NAME ...]

Why this exists.  Scoring a `_ZB` capture against its golden says *that* we
disagree with silicon, never *which* of us is wrong.  For the fixed-point
DepthFmt cells there is a third opinion available that is neither: the test's
own geometry.  `DepthFormatTests::CreateGeometry` places 992 8x8 quads, a
bottom quad, a right quad and a 384x400 big quad at vertex depths the guest
computes in float32 and truncates to integers, then draws them front to back
under LESS.  Every vertex depth is therefore an exact integer, every edge is
axis aligned, and the depth at a pixel centre is an exact rational.  This
module evaluates that rational in Python integers, floors it, and replays the
depth test -- so it is what a *correct* renderer must write, computed without
reference to the goldens at all.

Two things come out of that which the goldens alone cannot give:

  * `max|oracle - golden| == 1` on all nine masks, and silicon sits one either
    side of the oracle roughly symmetrically (on `Mffffff_ZB`: 3,060 low,
    79,160 on it, 2,972 high).  That is the NV2A's own edge walk, and it is the
    floor under any fix -- roughly 21,845 differing pixels per compression
    half that nobody can remove.
  * Our own distance from the oracle is a separate number, and on the same
    capture it was one-*sided*: 9,738 low against 140 high, ramping with the
    barycentric.  That is ours, and it is what #52 removes.

`ours == oracle` is therefore the falsifier to state for any change to the
fixed-point depth floor, rather than a differing-pixel total: a pixel can be
wrong for our reason and silicon's at once, and the total cannot tell them
apart.  See docs/investigations/depth-barycentric-normalisation.md.
"""

import os
import struct
import sys

import numpy as np
from PIL import Image

W, H = 640, 480
GOLD = "/home/justin/goldens/results/Depth_buffer"


def f32(x):
    return struct.unpack("f", struct.pack("f", float(x)))[0]


def grid_vertex_depths(max_depth):
    """(lz, rz) per grid quad, replaying the guest's own float32 accumulation.

    z_left accumulates in float32 and is truncated to uint32 per quad, and
    right_offset alternates sign, so the pair cannot be derived in closed form
    -- it has to be replayed.
    """
    quads_per_row, quads_per_col = 31, 32
    num_quads = 3 + quads_per_row * quads_per_col
    z_inc = f32(f32(max_depth) / f32(num_quads + 1.0))
    right_offset = f32(z_inc * 0.75)
    z_left = 0.0
    out = []
    for _ in range(quads_per_col):
        row = []
        for _ in range(quads_per_row):
            z_right = f32(z_left + right_offset)
            row.append((int(z_left), int(max(0.0, z_right))))
            z_left = f32(z_left + z_inc)
            right_offset = f32(-right_offset)
        out.append(row)
    return out


def oracle(cutoff, max_depth):
    """floor(exact depth) after LESS in draw order, as an int64 (H, W) array."""
    z = np.full((H, W), cutoff, dtype=np.int64)
    xs = np.arange(W, dtype=np.int64)
    ys = np.arange(H, dtype=np.int64)

    def blit(x0, x1, y0, y1, num, den):
        v = num // den                      # exact floor, integer arithmetic
        sub = z[y0:y1, x0:x1]
        m = v < sub                         # NV097_SET_DEPTH_FUNC_V_LESS
        sub[m] = np.broadcast_to(v, sub.shape)[m]

    # the grid of 8x8 quads, front to back, row major; z linear in x
    for j, row in enumerate(grid_vertex_depths(max_depth)):
        y0 = 48 + 12 * j
        for i, (lz, rz) in enumerate(row):
            x0 = 134 + 12 * i
            k = 2 * (xs[x0:x0 + 8] - x0) + 1
            blit(x0, x0 + 8, y0, y0 + 8, (lz * 16 + k * (rz - lz))[None, :], 16)

    # bottom quad: 3/4 max depth on the left to 0 on the right
    left = (max_depth - 1) * 3 // 4
    k = 2 * (xs[132:492] - 132) + 1
    blit(132, 492, 430, 435, (left * 720 - k * left)[None, :], 720)

    # right quad: 1 at the top to half max depth at the bottom
    top, bot = 1, max_depth // 2
    k = 2 * (ys[45:435] - 45) + 1
    blit(502, 510, 45, 435, (top * 780 + k * (bot - top))[:, None], 780)

    # big quad: 2/3 max depth at the top to max depth at the bottom
    back = max_depth - 1
    top, bot = back * 2 // 3, back
    k = 2 * (ys[40:440] - 40) + 1
    blit(128, 512, 40, 440, (top * 800 + k * (bot - top))[:, None], 800)
    return z


def zeta_word(path):
    """A `_ZB` capture holds the zeta word as ARGB8888: depth is A<<16|R<<8|G.

    Reading it as RGB drops the depth word's top byte and turns a one-unit
    error that carries across a byte boundary into a 255.
    """
    a = np.array(Image.open(path).convert("RGBA"), dtype=np.int64)
    return (a[:, :, 3] << 16) | (a[:, :, 0] << 8) | a[:, :, 1]


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    capdir = argv[1]
    names = argv[2:]
    if not names:
        names = sorted(
            f.split("::", 1)[1][:-4] for f in os.listdir(capdir)
            if f.startswith("Depth_buffer::")
            and "_z24_" in f and "_FZn_" in f and f.endswith("_ZB.png"))
    print("%-34s %9s %11s %11s %9s"
          % ("capture", "ours-gold", "oracle-gold", "oracle-ours", "max|o-g|"))
    tot_o = tot_i = 0
    for name in names:
        cutoff = int(name.split("_M")[1].split("_")[0], 16)
        max_depth = 0xFFFF if "_z16_" in name else 0xFFFFFF
        g = zeta_word(os.path.join(GOLD, name + ".png"))
        o = zeta_word(os.path.join(capdir, "Depth_buffer::%s.png" % name))
        idl = oracle(cutoff, max_depth)
        a, b, c = (int((o != g).sum()), int((idl != g).sum()),
                   int((idl != o).sum()))
        tot_o += a
        tot_i += b
        print("%-34s %9d %11d %11d %9d"
              % (name, a, b, c, int(np.abs(idl - g).max())))
    print("%-34s %9d %11d" % ("TOTAL", tot_o, tot_i))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
