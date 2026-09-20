#!/usr/bin/env python3
"""Measure #10's Y16 bump class -- `BumpMap_Y16` / `_Y16_L` -- against the
goldens and the corpus, without a device.

This is a measurement tool, not an oracle: it makes no forward model of the
`Bump map` geometry.  `bump_oracle.py`'s forward render only reaches 80% on
`BumpMap_A8R8G8B8`, so scoring a rival reading of the Y16 channel against an
absolute render cannot separate a 5,000 px effect from that 21,000 px floor.
Everything below is a comparison between images that were produced by the
same geometry, which cancels it.

Four things it reports, each a standalone claim:

  --identity   Which `Bump map` captures are byte-identical to which, in ours
               and in the goldens.  This is the finding: we render Y16 as Y8,
               hardware does not.
  --stored     The bytes SZ_Y16 actually holds for this test's bump colours,
               computed from the test source's own arithmetic.  They are
               byte-replicated, which is what rules out every byte-order or
               channel-assignment rival without running one.
  --columns    Where in the quad the hardware Y16/Y8 difference lives, column
               by column, against the seam the source steps at.
  --control    The `Bump env lum` Y16 row, which is at the #38 floor -- the
               same format, the same bump texture, the same 16-bit field, and
               no disagreement.

Usage:
  bump_y16_class.py --identity [--cap DIR]
  bump_y16_class.py --stored
  bump_y16_class.py --columns [--cap DIR]
  bump_y16_class.py --control [--cap DIR] [--lumcap DIR]
  bump_y16_class.py --all
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures  # noqa: E402

GOLD = "/home/justin/goldens/results"
CAP_DEFAULT = ("/home/justin/hakux-work/dispatch/results/"
               "z-repeat-c866527e03-011-Bump_map")
LUMCAP_DEFAULT = ("/home/justin/hakux-work/dispatch/results/"
                  "z-repeat-c866527e03-010-Bump_env_lum")
QUAD, STRIDE = 168, 180
ORIGIN_X, ORIGIN_Y = 146, 66
RED = np.array([254, 0, 0, 255], np.int16)
GREY = np.array([33, 32, 32, 191], np.int16)

# The quad the test draws is 168x168 at (146,66), stride 180; the four are the
# TEXFILTER sign sweep.  `DrawRectangles` derives these from the framebuffer
# size, so they are literals here only because 640x480 is fixed in main.cpp.
MASK = np.zeros((480, 640), bool)
for _qy in (0, 1):
    for _qx in (0, 1):
        MASK[ORIGIN_Y + _qy * STRIDE:ORIGIN_Y + _qy * STRIDE + QUAD,
             ORIGIN_X + _qx * STRIDE:ORIGIN_X + _qx * STRIDE + QUAD] = True


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16)


def gold(suite, test):
    return load("%s/%s/%s.png" % (GOLD, suite, test))


def cap(d, suite, test):
    p = captures.find(d, suite, test)
    if not p:
        sys.exit("no capture for %s::%s under %s" % (suite, test, d))
    return load(p)


def differing(a, b, tol=0):
    """Pixels inside the four quads differing by more than `tol` per channel."""
    d = np.abs(a[MASK].astype(np.int32) - b[MASK].astype(np.int32)).max(axis=1)
    return int((d > tol).sum())


def quad_of(img, qx, qy):
    left, top = ORIGIN_X + qx * STRIDE, ORIGIN_Y + qy * STRIDE
    return img[top:top + QUAD, left:left + QUAD]


# ------------------------------------------------------------------ --stored
def luminance8(r, g, b):
    """`texture_stage.cpp:220/237/274-277` -- a float32 sum, then a C cast."""
    f = np.float32
    v = f(0.299) * f(r) + f(0.587) * f(g) + f(0.114) * f(b)
    return int(v)


def stored_y16(y8):
    """`texture_stage.cpp:270-277` -- trunc(Y8 / 255 * 65535), in float32."""
    f = np.float32
    return int(f(f(y8) / f(255.0)) * f(65535.0))


def report_stored():
    print("What SZ_Y16 holds for `Bump map`'s two bump colours")
    print("(bump_map_tests.cpp:76, SDL RGBA8888, so the bytes are R,G,B,A)\n")
    print("  %-12s %-14s %5s   %-8s %-9s %-9s" %
          ("colour", "R,G,B", "Y8", "v16", "low byte", "high byte"))
    for word in (0x007F4500, 0x00804500):
        r, g, b = (word >> 24) & 0xFF, (word >> 16) & 0xFF, (word >> 8) & 0xFF
        y8 = luminance8(r, g, b)
        v = stored_y16(y8)
        print("  0x%08X   %3d,%3d,%3d   %5d   0x%04X   %8d   %8d" %
              (word, r, g, b, y8, v, v & 0xFF, v >> 8))
    print("""
Both words are byte-replicated: v16 = Y8 * 257 exactly, so the low byte, the
high byte and the 8-bit luminance are the same number.  SZ_Y8 stores that same
byte (texture_stage.cpp:237), and SZ_Y16's view swizzle {ONE,R,R,ONE} puts the
field in components 1 and 2 -- the two `append_bump_channel` reads for
BUMPENVMAP (psh.c:3045-3046).  So no permutation of byte lanes or channel
assignments can make a Y16 texel differ from a Y8 one here, and the goldens
below say hardware's do differ.  Whatever separates them is not a stored byte.""")


# ---------------------------------------------------------------- --identity
def report_identity(capdir):
    suite = "Bump_map"
    names = sorted(os.path.basename(p)[:-4]
                   for p in glob.glob("%s/%s/*.png" % (GOLD, suite)))
    fam = [n for n in names
           if any(k in n for k in ("_Y16", "_Y8", "_AY8", "_A8Y8", "_A8"))]
    g = dict((n, gold(suite, n)) for n in names)
    c = dict((n, cap(capdir, suite, n)) for n in names) if capdir else {}

    print("`Bump map`: the Y family, differing px inside the four quads\n")
    print("  %-16s %10s %10s %12s" %
          ("test", "ours/gold", "gold/goldY8", "ours/oursY8"))
    for n in fam:
        row = [n, differing(c[n], g[n]) if c else -1,
               differing(g[n], g["BumpMap_Y8"]),
               differing(c[n], c["BumpMap_Y8"]) if c else -1]
        print("  %-16s %10d %10d %12d" % tuple(row))

    if c:
        print("\n  Everything of ours that is byte-identical to our Y16:")
        same = [n for n in names if differing(c[n], c["BumpMap_Y16"]) == 0]
        print("    " + ", ".join(same))
        print("  Everything of the goldens' that is identical to gold Y16:")
        same = [n for n in names if differing(g[n], g["BumpMap_Y16"]) == 0]
        print("    " + ", ".join(same))
        print("""
Read the first two rows together.  Our Y16 sits at the #38 floor against the
*Y8* golden and 22,374 px from its own, and it is byte-identical to our Y8 --
so the defect is not in the geometry, the blend or the combiner, which all
reproduce a Y8 picture exactly.  It is that we compute the same bump offsets
for a Y16 source as for a Y8 one, and hardware does not.""")


# ----------------------------------------------------------------- --columns
def col_profile(a, b, qx, qy):
    qa, qb = quad_of(a, qx, qy), quad_of(b, qx, qy)
    d = np.abs(qa.astype(np.int32) - qb.astype(np.int32)).max(axis=2) > 0
    return d.sum(axis=0)


def report_columns(capdir):
    suite = "Bump_map"
    g16, g8 = gold(suite, "BumpMap_Y16"), gold(suite, "BumpMap_Y8")
    print("""`Bump map`: where the hardware Y16/Y8 difference sits in the quad.

The draw sets TEXCOORD0 to 1/w..3/w (bump_map_tests.cpp:124), so the quad
spans bump texels 1..3 and crosses GenerateBumpMapSurface's x >= 2 seam at
its midpoint, column 84 of 168.  Columns are counted from the quad's left.
""")
    for qy in (0, 1):
        for qx in (0, 1):
            p = col_profile(g16, g8, qx, qy)
            nz = np.flatnonzero(p)
            full = int((p >= QUAD - 12).sum())
            print("  quad g%d b%d  %6d px in %3d columns, %3d..%3d"
                  "  (%d of them whole-column)"
                  % (qy, qx, int(p.sum()), len(nz),
                     nz.min() if len(nz) else -1,
                     nz.max() if len(nz) else -1, full))
    p = col_profile(g16, g8, 0, 0)
    print("\n  quad g0 b0, columns that differ: " +
          " ".join(str(x) for x in np.flatnonzero(p)))
    print("  columns 0..43 and 103..167: %d differing px"
          % int(p[:44].sum() + p[103:].sum()))
    if capdir:
        c16 = cap(capdir, suite, "BumpMap_Y16")
        p2 = col_profile(c16, g16, 0, 0)
        nz = np.flatnonzero(p2)
        print("  ours vs gold Y16, quad g0 b0: %d px in columns %d..%d"
              % (int(p2.sum()), nz.min(), nz.max()))
    print("""
Every differing column is inverted, not shifted: the vertical checker phase is
identical in both images and the horizontal cell index differs by an odd
number.  A whole-column inversion needs the horizontal offset to move by about
half a checker cell, and the sign of the difference toggles every two or three
columns across the band, so hardware's Y16 offset sweeps many cells' worth
across the seam region while ours steps by one byte -- 82 to 83.""")


# ----------------------------------------------------------------- --control
def report_control(capdir, lumcap):
    print("""The `Bump env lum` control: same format, same 16-bit field, no defect.

`BumpEnvLum_Y16` uses SZ_Y16 over the same GenerateBumpMapSurface seam, and
its stored words are byte-replicated in exactly the same way (its colours give
Y8 = 46 and 47, so v16 = 0x2E2E and 0x2F2F).  If the Y16 defect were a
property of reading a 16-bit field through a bump stage, it would fire here
too -- and `Bump env lum`'s matrix is (0.3, 0, 0, 5.0), ten times `Bump map`'s
vertical term, so it would fire harder.""")
    print("\n  %-22s %12s" % ("test", "ours/gold"))
    for suite, d, tests in (("Bump_map", capdir,
                             ("BumpMap_Y16", "BumpMap_Y8", "BumpMap_A8")),
                            ("Bump_env_lum", lumcap,
                             ("BumpEnvLum_Y16", "BumpEnvLum_Y8",
                              "BumpEnvLum_A8"))):
        if not d:
            continue
        for t in tests:
            print("  %-22s %12d" % (t, differing(cap(d, suite, t),
                                                 gold(suite, t))))
    print("""
  (`Bump env lum`'s Y8 row carries #10's luminance-truncation class, which is
  a one-step colour error and not an offset error; it is counted here at
  tol=0 so it shows.  The Y16 row is at the 1,576 px #38 floor: hardware's
  Y16 bump offsets there agree with the 8-bit reading we emit.)
""")
    # What the control could have shown, before believing that it shows
    # nothing: a blind region would report the same silence.
    a = quad_of(gold("Bump_env_lum", "BumpEnvLum_Y16"), 0, 0)
    b = quad_of(gold("Bump_env_lum", "BumpEnvLum_A8"), 0, 0)
    d = (np.abs(a.astype(np.int32) - b.astype(np.int32)).max(axis=2) > 0)
    p = d.sum(axis=0)
    print("  Is that region blind?  `BumpEnvLum_Y16` against `BumpEnvLum_A8`,")
    print("  which differ only in the bump offsets (both take the luminance")
    print("  from the same ONE literal), quad g0 b0:")
    print("    columns   0-43: %5d px" % int(p[:44].sum()))
    print("    columns  44-102: %4d px   <- the band the Y16 defect occupies"
          % int(p[44:103].sum()))
    print("    columns 103-167: %4d px" % int(p[103:].sum()))
    print("""  so `Bump env lum` does respond to a changed offset in exactly
  the columns where `Bump map`'s Y16 defect lives.  The control is a silence
  the instrument could have broken, not a region it cannot see.""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", default=CAP_DEFAULT)
    ap.add_argument("--lumcap", default=LUMCAP_DEFAULT)
    ap.add_argument("--identity", action="store_true")
    ap.add_argument("--stored", action="store_true")
    ap.add_argument("--columns", action="store_true")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if not any((a.identity, a.stored, a.columns, a.control)):
        a.all = True
    if a.all or a.stored:
        report_stored()
        print()
    if a.all or a.identity:
        report_identity(a.cap)
        print()
    if a.all or a.columns:
        report_columns(a.cap)
        print()
    if a.all or a.control:
        report_control(a.cap, a.lumcap)


if __name__ == "__main__":
    main()
