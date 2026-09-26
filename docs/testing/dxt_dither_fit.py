#!/usr/bin/env python3
"""dxt_dither_fit - the NV2A dithers DXT1 decode.  Issue #6.

The DXT1 residual (up to 8/255, 87,381 of 307,200 pixels on MIPDXT1_plasma)
was parked as unmodellable on one observation: a differing 4x4 block in the
silicon capture carries 16 distinct colours, and a DXT1 block encodes 4, so
no palette lookup can produce it.  The observation is correct.  The
conclusion is not, and this script is the difference between them.

What the observation rules out is a *palette lookup*.  What it does not rule
out is a decode rule that also reads the texel's position inside the block --
and since DXT1 blocks are 4x4 and 4-aligned, (y & 3, x & 3) and
(y - y0, x - x0) are the same number.  Position inside the block is an input
a block decoder already has.

So the question is not "can 4 colours make 16" but "is the capture a function
of the decoder's inputs".  --single-valued answers it: over five DXT1
captures the output is a single-valued function of (5/6-bit code, y & 3,
x & 3) with zero conflicts, and most keys are corroborated by more than one
capture.  A function of a decoder's inputs is implementable by a decoder.

The mechanism is an ordered dither.  DXT1 is the one compressed format whose
NV2A target is 16 bit (L_DXT1_A1R5G5B5; DXT23 and DXT45 target A8R8G8B8).
Reaching 8 bits from a 5- or 6-bit field leaves a gap of 8 (or 4) counts, and
instead of landing on the replicated expansion the hardware emits whichever
value in that gap is congruent to a fixed 4x4 matrix entry.  Saturated codes
do not dither, which is why a flat black or white block still decodes to a
single colour.  This is why DXT3 and DXT5 are clean: their captures decode
from byte-identical colour blocks and show 3..4 colours per block, not 16.

Fits hw/xbox/nv2a/pgraph/s3tc.c (write_dxt1_block_to_texture).

Usage:
    dxt_dither_fit.py --colour-counts   distinct colours per 4x4 block
    dxt_dither_fit.py --single-valued   is the capture a decoder's function?
    dxt_dither_fit.py --matrix          derive the dither matrices
    dxt_dither_fit.py --score           HEAD's palette, with and without it
    dxt_dither_fit.py --residual        what the fitted rule still misses
"""

import argparse
import collections
import os
import struct
import sys

import numpy as np
from PIL import Image

GOLDEN_DIR = os.environ.get(
    "DXT_GOLDEN_DIR", "/home/justin/goldens/results/Texture_DXT")
DDS_DIR = os.environ.get(
    "DXT_DDS_DIR", "/home/justin/nxdk_pgraph_tests/resources/dxt_images")

# stem, dds, texture w, h, quad x, y.  The non-mipmap tests centre a 256x256
# quad in the 640x480 framebuffer; TestMipmap's level-0 quad is at (5, 80).
# Both are point magnification -- checked by --colour-counts, which refuses to
# report on a capture whose magnified cells are not constant.
DXT1 = [("DXT1_plasma_dxt1", "plasma_dxt1.dds", 32, 32, 192, 112),
        ("DXT1_plasma_alpha_dxt1", "plasma_alpha_dxt1.dds", 32, 32, 192, 112),
        ("MIPDXT1_plasma_dxt1", "plasma_dxt1.dds", 32, 32, 5, 80),
        ("MIPDXT1_plasma_alpha_dxt1", "plasma_alpha_dxt1.dds", 32, 32, 5, 80),
        ("MIPDXT1_64x256_bands_dxt1", "64x256_bands_dxt1.dds", 64, 256, 5, 80)]
CONTROL = [("DXT3_plasma_dxt3", "plasma_dxt3.dds", 32, 32, 192, 112, 3),
           ("DXT5_plasma_dxt5", "plasma_dxt5.dds", 32, 32, 192, 112, 5),
           ("MIPDXT3_plasma_dxt3", "plasma_dxt3.dds", 32, 32, 5, 80, 3),
           ("MIPDXT5_plasma_dxt5", "plasma_dxt5.dds", 32, 32, 5, 80, 5)]

# out mod 8 (R, B) and mod 4 (G), indexed [y & 3][x & 3].  Derived by
# --matrix; mirrored in s3tc.c as kDxt1Dither{R,G,B}.
T = [np.array([[3, 7, 4, 0], [5, 1, 6, 2], [0, 4, 7, 3], [2, 6, 1, 5]]),
     np.array([[0, 2, 3, 1], [3, 1, 2, 0], [2, 0, 1, 3], [1, 3, 0, 2]]),
     np.array([[2, 6, 1, 5], [0, 4, 7, 3], [5, 1, 6, 2], [3, 7, 4, 0]])]


# ---------------------------------------------------------------- input data

def golden(stem, w, h, qx, qy):
    """(h x w x 4 silicon texel grid, cells_are_uniform)."""
    img = np.array(Image.open(os.path.join(GOLDEN_DIR, stem + ".png"))
                   .convert("RGBA")).astype(int)
    magx, magy = 256 // w, (256 // h if h <= 256 else 1)
    reg = img[qy:qy + h * magy, qx:qx + w * magx]
    cells = reg.reshape(h, magy, w, magx, 4)
    uniform = bool((cells.max(axis=(1, 3)) == cells.min(axis=(1, 3))).all())
    return cells[:, 0, :, 0, :], uniform


def colour_blocks(dds, w, h, stride=8, coff=0):
    raw = open(os.path.join(DDS_DIR, dds), "rb").read()[128:]
    return [struct.unpack("<HHI", raw[b * stride + coff:b * stride + coff + 8])
            for b in range((w // 4) * (h // 4))]


def comps(c):
    return ((c >> 11) & 31, (c >> 5) & 63, c & 31)


# -------------------------------------------------------------- decode model

def expand(code, bits):
    return (code << (8 - bits)) | (code >> (2 * bits - 8))


def dither(v, ch, half, yy, xx):
    """The value in [v - half, v + half - 1] congruent to T mod 2*half."""
    if v <= 0:
        return 0
    if v >= 255:
        return 255
    m = 2 * half
    t = int(T[ch][yy, xx]) % m
    return max(0, min(255, v - half + ((t - v + half) % m)))


def decode(dds, w, h, use_dither):
    """HEAD's palette (replicated endpoints, round-to-nearest interpolants),
    optionally with the dither applied on the way out."""
    nbx = w // 4
    out = np.zeros((h, w, 3), int)
    for b, (c0, c1, idx) in enumerate(colour_blocks(dds, w, h)):
        r, g, bl = [0] * 4, [0] * 4, [0] * 4
        (r[0], g[0], bl[0]) = (expand(comps(c0)[0], 5), expand(comps(c0)[1], 6),
                               expand(comps(c0)[2], 5))
        (r[1], g[1], bl[1]) = (expand(comps(c1)[0], 5), expand(comps(c1)[1], 6),
                               expand(comps(c1)[2], 5))
        if c0 > c1:
            for k, (u, v) in ((2, (0, 1)), (3, (1, 0))):
                r[k] = (2 * r[u] + r[v] + 1) // 3
                g[k] = (2 * g[u] + g[v] + 1) // 3
                bl[k] = (2 * bl[u] + bl[v] + 1) // 3
        else:
            r[2], g[2], bl[2] = ((r[0] + r[1] + 1) // 2, (g[0] + g[1] + 1) // 2,
                                 (bl[0] + bl[1] + 1) // 2)
            r[3], g[3], bl[3] = 0, 0, 0
        bj, bi = divmod(b, nbx)
        for ty in range(4):
            for tx in range(4):
                i = (idx >> (2 * (ty * 4 + tx))) & 3
                Y, X = bj * 4 + ty, bi * 4 + tx
                if use_dither:
                    out[Y, X] = [dither(r[i], 0, 4, Y & 3, X & 3),
                                 dither(g[i], 1, 2, Y & 3, X & 3),
                                 dither(bl[i], 2, 4, Y & 3, X & 3)]
                else:
                    out[Y, X] = [r[i], g[i], bl[i]]
    return out


# -------------------------------------------------------------------- commands

def cmd_colour_counts(args):
    print("Distinct colours in each point-sampled 4x4 block of the silicon")
    print("capture.  A palette lookup cannot exceed 4.\n")
    print("%-28s %-9s %s" % ("capture", "cells", "colours per 4x4 block"))
    rows = [(s, w, h, x, y) for s, d, w, h, x, y in DXT1]
    rows += [(s, w, h, x, y) for s, d, w, h, x, y, f in CONTROL]
    for stem, w, h, x, y in rows:
        g, uni = golden(stem, w, h, x, y)
        c = [len(set(map(tuple, g[bj * 4:bj * 4 + 4, bi * 4:bi * 4 + 4, :3]
                         .reshape(-1, 3).tolist())))
             for bj in range(h // 4) for bi in range(w // 4)]
        print("%-28s %-9s min %2d  max %2d  mean %5.2f"
              % (stem, "uniform" if uni else "VARIES",
                 min(c), max(c), sum(c) / len(c)))
    print("\nThe DXT1 captures carry 16.  The DXT3 and DXT5 captures decode")
    print("from byte-identical colour blocks and carry 3..4, so this is the")
    print("DXT1 format path and not the data.")
    return 0


def endpoint_keys():
    """(code, y&3, x&3) -> {observed out} over every DXT1 capture, endpoint
    texels only, so no interpolation rule is assumed."""
    tab = [collections.defaultdict(set) for _ in range(3)]
    src = [collections.defaultdict(set) for _ in range(3)]
    for stem, dds, w, h, x, y in DXT1:
        g, _ = golden(stem, w, h, x, y)
        nbx = w // 4
        for b, (c0, c1, idx) in enumerate(colour_blocks(dds, w, h)):
            q = (comps(c0), comps(c1))
            bj, bi = divmod(b, nbx)
            for ty in range(4):
                for tx in range(4):
                    i = (idx >> (2 * (ty * 4 + tx))) & 3
                    if i > 1:
                        continue
                    Y, X = bj * 4 + ty, bi * 4 + tx
                    for ch in range(3):
                        k = (q[i][ch], Y & 3, X & 3)
                        tab[ch][k].add(int(g[Y, X, ch]))
                        src[ch][k].add(stem)
    return tab, src


def cmd_single_valued(args):
    tab, src = endpoint_keys()
    print("Is the silicon capture a single-valued function of the inputs a")
    print("DXT1 block decoder has?  Key = (endpoint code, y & 3, x & 3).\n")
    print("%-3s %8s %14s %14s" % ("ch", "keys", "in >1 capture", "conflicts"))
    bad = 0
    for ch, nm in ((0, "R"), (1, "G"), (2, "B")):
        mv = [k for k, v in tab[ch].items() if len(v) > 1]
        multi = [k for k, v in src[ch].items() if len(v) > 1]
        bad += len(mv)
        print("%-3s %8d %14d %14d" % (nm, len(tab[ch]), len(multi), len(mv)))
    print("\n%s" % ("A conflict would mean the capture depends on something a "
                    "decoder\ncannot see.  There are none, so it does not."
                    if not bad else
                    "CONFLICTS FOUND - the model shape is wrong."))
    return 0 if not bad else 1


def cmd_matrix(args):
    """out mod 8 (or 4) should be a constant of the cell, independent of code."""
    tab, _ = endpoint_keys()
    print("Residue of the output, by cell.  Saturated codes are excluded:")
    print("they do not dither (0 stays 0, 31/63 stays 255).\n")
    ok = True
    for ch, nm, bits in ((0, "R", 5), (1, "G", 6), (2, "B", 5)):
        step = 8 if bits == 5 else 4
        mx = (1 << bits) - 1
        cells = collections.defaultdict(collections.Counter)
        for (code, yy, xx), v in tab[ch].items():
            if code == 0 or code == mx or len(v) != 1:
                continue
            cells[(yy, xx)][next(iter(v)) % step] += 1
        m = np.zeros((4, 4), int)
        impure = []
        for (yy, xx), c in cells.items():
            m[yy, xx] = c.most_common(1)[0][0]
            if len(c) > 1:
                impure.append(((yy, xx), dict(c)))
        agree = np.array_equal(m, T[ch] % step)
        ok = ok and agree
        print("%s (mod %d), matches the matrix in s3tc.c: %s" % (nm, step, agree))
        print(m)
        if impure:
            print("   cells with more than one residue: %d (code 1, see"
                  " --residual)" % len(impure))
        print()
    return 0 if ok else 1


def cmd_score(args):
    print("HEAD's palette is already right; the dither is what was missing.")
    print("Texels decoded bit-exactly against the XBOX 1.0 goldens:\n")
    print("%-28s %14s %14s" % ("capture", "HEAD", "HEAD + dither"))
    ta = tb = tot = 0
    for stem, dds, w, h, x, y in DXT1:
        g, _ = golden(stem, w, h, x, y)
        n = w * h
        a = int((g[:, :, :3] == decode(dds, w, h, False)).all(axis=2).sum())
        b = int((g[:, :, :3] == decode(dds, w, h, True)).all(axis=2).sum())
        print("%-28s %7d/%-6d %7d/%-6d" % (stem, a, n, b, n))
        ta += a
        tb += b
        tot += n
    print("%-28s %7d/%-6d %7d/%-6d  (%.1f%% -> %.1f%%)"
          % ("TOTAL", ta, tot, tb, tot, 100.0 * ta / tot, 100.0 * tb / tot))
    print("\nThe dither must not reach DXT3 or DXT5.  Those keep the")
    print("undithered writer; --colour-counts is the evidence.")
    return 0


def cmd_residual(args):
    print("Everything the fitted rule still misses, by cause.\n")
    for stem, dds, w, h, x, y in DXT1:
        g, _ = golden(stem, w, h, x, y)
        p = decode(dds, w, h, True)
        bad = np.argwhere((g[:, :, :3] != p).any(axis=2))
        nbx = w // 4
        blks = colour_blocks(dds, w, h)
        code1 = 0
        for Y, X in bad:
            c0, c1, idx = blks[(Y // 4) * nbx + (X // 4)]
            i = (idx >> (2 * ((Y % 4) * 4 + (X % 4)))) & 3
            q = (comps(c0), comps(c1))
            if i < 2 and 1 in q[i]:
                code1 += 1
        print("%-28s %5d differing texels, %5d of them carry a code of"
              " exactly 1" % (stem, len(bad), code1))
    print("\nA code of 1 decodes to 0 in the goldens rather than to a value")
    print("near 8, except in the cells that select the top of the gap.  That")
    print("is 1 of 32 (resp. 64) codes.  On the plasma captures it is the")
    print("whole of the remaining disagreement; on 64x256_bands it is not, and")
    print("the rest of that capture's residual is unexplained.  No rule")
    print("covering either has been fitted, so s3tc.c does not special-case")
    print("it -- an unfitted exception is worse than a stated gap.")
    return 0


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--colour-counts", action="store_true")
    p.add_argument("--single-valued", action="store_true")
    p.add_argument("--matrix", action="store_true")
    p.add_argument("--score", action="store_true")
    p.add_argument("--residual", action="store_true")
    args = p.parse_args()
    ran = False
    rc = 0
    for flag, fn in (("colour_counts", cmd_colour_counts),
                     ("single_valued", cmd_single_valued),
                     ("matrix", cmd_matrix), ("score", cmd_score),
                     ("residual", cmd_residual)):
        if getattr(args, flag):
            rc |= fn(args)
            ran = True
            print()
    if not ran:
        p.print_help()
    return rc


if __name__ == "__main__":
    sys.exit(main())
