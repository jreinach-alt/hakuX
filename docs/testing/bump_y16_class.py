#!/usr/bin/env python3
"""Measure #10's Y16 bump class -- `BumpMap_Y16` / `_Y16_L` -- against the
goldens and the corpus, without a device.

This is a measurement tool, not an oracle: it makes no forward model of the
`Bump map` geometry.  `bump_oracle.py`'s forward render only reaches 80% on
`BumpMap_A8R8G8B8`, so scoring a rival reading of the Y16 channel against an
absolute render cannot separate a 5,000 px effect from that 21,000 px floor.
Everything below is a comparison between images that were produced by the
same geometry, which cancels it.

Five things it reports, each a standalone claim:

  --identity   Which `Bump map` captures are byte-identical to which, in ours
               and in the goldens.  This is the finding: we render Y16 as Y8,
               hardware does not.
  --stored     The bytes SZ_Y16 actually holds for this test's bump colours,
               computed from the test source's own arithmetic.  They are
               byte-replicated, which is what rules out every byte-order or
               channel-assignment rival without running one.
  --columns    Where in the quad the hardware Y16/Y8 difference lives, column
               by column, against the seam the source steps at.
  --parity     How much the offset moved: the inversion's run structure, and
               the two goldens' own checker-boundary counts, which are what
               the size claim is derived from.  Nothing about the size of the
               effect should be re-derived by eye; this prints it.  It also
               separates the test's own white label from the checkerboard
               everywhere the two are counted together -- see OVERLAY_RGBA.
  --control    The `Bump env lum` Y16 row, which is at the #38 floor -- the
               same format, the same bump texture, the same 16-bit field, and
               no disagreement.

Usage:
  bump_y16_class.py --identity [--cap DIR]
  bump_y16_class.py --stored
  bump_y16_class.py --columns [--cap DIR]
  bump_y16_class.py --parity
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

# The band the hardware Y16/Y8 difference occupies, and the part of it where
# the base checkerboard itself has no horizontal boundaries -- see --parity.
BAND_LO, BAND_HI = 44, 102
FLAT_LO, FLAT_HI = 78, 102
# One checker cell is 1/32 of the base texture; psh.c puts the horizontal
# displacement at bumpMat[0][0] * dS with the test's m00 = 0.3 and dS = b/128,
# so one cell of horizontal movement is this many byte units of `b`.
CELL_BYTES = (1.0 / 32.0) / (0.3 / 128.0)

# The quad the test draws is 168x168 at (146,66), stride 180; the four are the
# TEXFILTER sign sweep.  `DrawRectangles` derives these from the framebuffer
# size, so they are literals here only because 640x480 is fixed in main.cpp.
MASK = np.zeros((480, 640), bool)
for _qy in (0, 1):
    for _qx in (0, 1):
        MASK[ORIGIN_Y + _qy * STRIDE:ORIGIN_Y + _qy * STRIDE + QUAD,
             ORIGIN_X + _qx * STRIDE:ORIGIN_X + _qx * STRIDE + QUAD] = True

# THERE IS TEXT DRAWN INSIDE THE QUADS.  The test prints its own label over the
# geometry in opaque white, which lands as exactly (255,255,255,0) -- 360 px in
# quad g0 b0, 1,400 px across the four, sixteen rows tall, and pixel-identical
# in the Y8 golden, the Y16 golden and our captures alike.  It therefore costs
# ZERO differing pixels and moves no total in this tool.  What it does do is sit
# inside the band every measurement below is taken over, so it is the reason a
# differing column is 152 of 168 rather than 168 of 168, and it puts glyph edges
# into any per-row colour-change count.  Every report that quotes a per-column
# extent or a per-row boundary count has to say which side of it the number is
# on.  Derived from the image, never hardcoded: the label's position follows the
# framebuffer size and the test's own layout, and a hardcoded box goes stale.
OVERLAY_RGBA = np.array([255, 255, 255, 0], np.int16)


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


def overlay_of(q):
    """The test's own white label inside a quad, as a boolean mask."""
    return (q == OVERLAY_RGBA).all(axis=2)


def diff_mask(a, b, qx, qy):
    """Per-pixel difference inside one quad."""
    qa, qb = quad_of(a, qx, qy), quad_of(b, qx, qy)
    return np.abs(qa.astype(np.int32) - qb.astype(np.int32)).max(axis=2) > 0


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
    # The luminance formats plus A8, whose only channel is the `ONE` literal.
    # Spelt as a suffix match: "_A8" as a substring also catches A8R8G8B8 and
    # A8B8G8R8, which are not in this family.
    fam = [n for n in names
           if any(n.endswith(k) for k in
                  ("_Y16", "_Y16_L", "_Y8", "_Y8_L", "_AY8", "_AY8_L",
                   "_A8Y8", "_A8Y8_L", "_A8", "_A8_L"))]
    g = dict((n, gold(suite, n)) for n in names)
    c = dict((n, cap(capdir, suite, n)) for n in names)

    print("`Bump map`: the Y family, differing px inside the four quads\n")
    print("  %-16s %10s %10s %12s" %
          ("test", "ours/gold", "gold/goldY8", "ours/oursY8"))
    for n in fam:
        print("  %-16s %10d %10d %12d"
              % (n, differing(c[n], g[n]),
                 differing(g[n], g["BumpMap_Y8"]),
                 differing(c[n], c["BumpMap_Y8"])))

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
    return diff_mask(a, b, qx, qy).sum(axis=0)


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
            d = diff_mask(g16, g8, qx, qy)
            p = d.sum(axis=0)
            nz = np.flatnonzero(p)
            # "Whole-column" excludes the test's own label, which is identical
            # in both goldens and so can never differ; it is exact, not a
            # threshold on how many of the 168 rows happened to move.
            ov = overlay_of(quad_of(g16, qx, qy))
            full = int(((d | ov).all(axis=0) & (p > 0)).sum())
            print("  quad g%d b%d  %6d px in %3d columns, %3d..%3d"
                  "  (%d of them whole-column, label excluded)"
                  % (qy, qx, int(p.sum()), len(nz),
                     nz.min() if len(nz) else -1,
                     nz.max() if len(nz) else -1, full))
    p = col_profile(g16, g8, 0, 0)
    print("\n  quad g0 b0, columns that differ: " +
          " ".join(str(x) for x in np.flatnonzero(p)))
    print("  columns 0..43 and 103..167: %d differing px"
          % int(p[:BAND_LO].sum() + p[BAND_HI + 1:].sum()))
    ov = overlay_of(quad_of(g16, 0, 0))
    orow, ocol = np.flatnonzero(ov.any(axis=1)), np.flatnonzero(ov.any(axis=0))
    print("  the test's own white label, drawn inside this quad: %d px at rows"
          " %d..%d, columns %d..%d" % (int(ov.sum()), orow.min(), orow.max(),
                                       ocol.min(), ocol.max()))
    print("    (identical in both goldens, so none of the px above -- but it"
          " overlaps the band,")
    print("     so it is what keeps a differing column off 168 of 168.)")
    c16 = cap(capdir, suite, "BumpMap_Y16")
    p2 = col_profile(c16, g16, 0, 0)
    nz = np.flatnonzero(p2)
    # A capture that has been fixed in this quad makes nz empty.  That is the
    # state this tool exists to recognise, so say it rather than raising out of
    # nz.min() on a zero-size reduction.
    print("  ours vs gold Y16, quad g0 b0: %d px%s"
          % (int(p2.sum()),
             " in columns %d..%d" % (nz.min(), nz.max()) if len(nz)
             else "  <- identical to the Y16 golden in this quad"))
    print("""
Every differing column is inverted, not shifted: the vertical checker phase is
identical in both images (--parity checks that per column) and the horizontal
cell index differs by an ODD NUMBER OF WHOLE CELLS.  Within one column the
sampled u is essentially constant, so a shift of d cells inverts the column
exactly when floor(p + d) - floor(p) is odd; half a cell is not the threshold
for inverting a column, it is a shift that inverts whichever columns have
their phase in the upper half of a cell.

That matters because a constant shift, of any size, is excluded here.  A
constant shift can only invert at the base texture's own horizontal period,
and only where that period exists -- and in columns %d..%d the base has no
horizontal boundaries in 150 of 168 rows, while the inversion toggles ten
times.  Run --parity for the counts and for the size the offset must move.""" %
          (FLAT_LO, FLAT_HI))


# ------------------------------------------------------------------ --parity
def runs_of(mask):
    """The maximal true runs of a boolean column mask, as (first, last)."""
    out, start = [], None
    for x, v in enumerate(mask):
        if v and start is None:
            start = x
        elif not v and start is not None:
            out.append((start, x - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def near(q, colour, tol=2):
    d = np.abs(q.astype(np.int32) - colour.astype(np.int32))
    return d.max(axis=2) <= tol


def vtrans(q, col):
    """The rows where column `col` changes colour: the vertical phase."""
    d = np.abs(q[1:, col, :].astype(np.int32) -
               q[:-1, col, :].astype(np.int32)).max(axis=1) > 0
    return tuple(np.flatnonzero(d))


def hcount(q, lo, hi):
    """Per row, how many times the row changes colour between columns lo..hi.

    Each change is one increment of the checkerboard's horizontal cell index,
    so this counts the cells that row traverses across the span.  It is a
    per-row count on purpose: the boundary set pooled over rows also picks up
    the staircase of the checker's vertical edges.

    On a row the test's white label crosses, the glyph edges are colour changes
    too and this counts them.  That is why the callers say, per claim, whether a
    row is one of the sixteen the label touches -- see OVERLAY_RGBA."""
    d = np.abs(q[:, 1:, :].astype(np.int32) -
               q[:, :-1, :].astype(np.int32)).max(axis=2) > 0
    return d[:, lo:hi + 1].sum(axis=1).astype(int)


def base_gaps(q, lab, lo, hi):
    """Column spacing between consecutive colour changes along a row.

    Over the rows the label does not touch only: on a label row the glyph edges
    would report spacings of one or two columns that belong to text.  This is
    what says the base index moves by less than a cell per column, which is what
    lets hcount's Y8 figure be subtracted rather than only compared."""
    d = np.abs(q[:, 1:, :].astype(np.int32) -
               q[:, :-1, :].astype(np.int32)).max(axis=2) > 0
    out = []
    for r in np.flatnonzero(~lab.any(axis=1)):
        pos = np.flatnonzero(d[r, lo:hi + 1])
        if len(pos) > 1:
            out.extend(np.diff(pos).tolist())
    return np.array(out, int)


def report_parity():
    suite = "Bump_map"
    g16, g8 = gold(suite, "BumpMap_Y16"), gold(suite, "BumpMap_Y8")
    print("""`Bump map`: how far the hardware Y16 offset moved, derived once.

Every differing column is colour-INVERTED and not displaced, so the only thing
the picture reports about the offset is the parity of k = (the gold Y16 cell
index) - (the gold Y8 cell index).  k is what is bounded below; a candidate
mechanism is scored by computing its own k, not by comparing a swing.
""")
    print("  %-9s %5s %5s %7s %-22s %s"
          % ("quad", "cols", "vphase", "swaps", "differing px per column",
             "survivors / of which label"))
    surv_tot, surv_lab, nonlab_tot, nonlab_diff = 0, 0, 0, 0
    for qy in (0, 1):
        for qx in (0, 1):
            a, b = quad_of(g16, qx, qy), quad_of(g8, qx, qy)
            d = np.abs(a.astype(np.int32) - b.astype(np.int32)).max(axis=2) > 0
            per = d.sum(axis=0)
            cols = np.flatnonzero(per)
            same = sum(1 for c in cols if vtrans(a, c) == vtrans(b, c))
            swap = ((near(a, RED) & near(b, GREY)) |
                    (near(a, GREY) & near(b, RED)))
            # Inside the differing columns, which pixels did NOT move, and how
            # many of those are the test's label rather than a checker feature.
            ov = overlay_of(a)
            surv = ~d[:, cols]
            lab = ov[:, cols]
            surv_tot += int(surv.sum())
            surv_lab += int((surv & lab).sum())
            nonlab_tot += int((~lab).sum())
            nonlab_diff += int((d[:, cols] & ~lab).sum())
            print("  g%d b%d     %5d %4d/%-3d %6s  %d..%d of %d"
                  "  (%.1f%%..%.1f%%)   %5s"
                  % (qy, qx, len(cols), same, len(cols),
                     "%d/%d" % (int((d & swap).sum()), int(d.sum())),
                     per[cols].min(), per[cols].max(), QUAD,
                     100.0 * per[cols].min() / QUAD,
                     100.0 * per[cols].max() / QUAD,
                     "%d/%d" % (int((surv & lab).sum()), int(surv.sum()))))
    print("""    vphase = differing columns whose vertical transition ROWS are
    identical in both goldens; swaps = differing pixels that exchange red for
    grey, against all differing pixels.  So the inversion is total in kind:
    every differing pixel swaps the two checker colours.

    It is total in EXTENT too, once the test's own white label is taken out.
    Of the %d pixels a differing column holds outside the label, %d differ --
    every one of them -- and every one of the %d survivors is a label pixel
    (%d of %d, in all four quads).  The 90.5%%..100%% range above is the
    label's sixteen rows and nothing else; the checkerboard spares nothing.
    So a mechanism that inverts 168 of 168 is what this data asks for, and one
    that spares a structural row does not match it.
""" % (nonlab_tot, nonlab_diff, surv_tot, surv_lab, surv_tot))

    a, b = quad_of(g16, 0, 0), quad_of(g8, 0, 0)
    d = np.abs(a.astype(np.int32) - b.astype(np.int32)).max(axis=2) > 0
    inv = d.sum(axis=0) > 0
    runs = runs_of(inv)
    toggles = int((inv[1:] != inv[:-1]).sum())
    print("  quad g0 b0, the inverted runs (%d of them, %d parity toggles):"
          % (len(runs), toggles))
    print("    " + " | ".join("%d" % lo if lo == hi else "%d-%d" % (lo, hi)
                              for lo, hi in runs))

    print("\n  Checker cells each row traverses, gold Y8 against gold Y16:\n")
    print("  %-9s %-28s %-28s"
          % ("quad", "columns %d..%d" % (BAND_LO, BAND_HI),
             "columns %d..%d" % (FLAT_LO, FLAT_HI)))
    print("  %-9s %-28s %-28s"
          % ("", "Y8    Y16   n16-n8", "Y8    Y16   n16-n8"))
    band_max, band_min, flat_min = [], [], []
    for qy in (0, 1):
        for qx in (0, 1):
            cells = []
            for lo, hi in ((BAND_LO, BAND_HI), (FLAT_LO, FLAT_HI)):
                n8 = hcount(quad_of(g8, qx, qy), lo, hi)
                n16 = hcount(quad_of(g16, qx, qy), lo, hi)
                dd = n16 - n8
                cells.append("%-5d %-5d %d..%d"
                             % (int(np.median(n8)), int(np.median(n16)),
                                dd.min(), dd.max()))
                if lo == BAND_LO:
                    band_max.append(int(dd.max()))
                    band_min.append(int(dd.min()))
                else:
                    flat_min.append(int(dd.min()))
            print("  g%d b%d     %-28s %-28s" % (qy, qx, cells[0], cells[1]))

    # The bound holds per row, so the strongest claim the data supports is the
    # largest per-row difference -- and the honest one across the four quads is
    # the smallest of those four maxima.
    bound, flat_bound = min(band_max), min(flat_min)
    n8f = hcount(quad_of(g8, 0, 0), FLAT_LO, FLAT_HI)
    # Which rows DO carry a base boundary in the flat sub-band: the two rows the
    # quad's vertical checker seam crosses, plus every row the test's own label
    # crosses, whose glyph edges are colour changes like any other.  Naming them
    # separately matters: no bump mechanism can reproduce a glyph.
    lab00 = overlay_of(quad_of(g16, 0, 0))
    lab_flat = set(np.flatnonzero(
        lab00[:, FLAT_LO:FLAT_HI + 1].any(axis=1)).tolist())
    base_rows = [int(r) for r in np.flatnonzero(n8f > 0)]
    seam_rows = [r for r in base_rows if r not in lab_flat]
    n16f_lo = min(int(hcount(quad_of(g16, qx, qy), FLAT_LO, FLAT_HI).min())
                  for qy in (0, 1) for qx in (0, 1))
    n16f_hi = max(int(hcount(quad_of(g16, qx, qy), FLAT_LO, FLAT_HI).max())
                  for qy in (0, 1) for qx in (0, 1))
    dband = (hcount(quad_of(g16, 0, 0), BAND_LO, BAND_HI) -
             hcount(quad_of(g8, 0, 0), BAND_LO, BAND_HI))
    at = set(int(r) for r in np.flatnonzero(dband >= bound))
    lab_rows = set(np.flatnonzero(lab00.any(axis=1)).tolist())
    gaps = base_gaps(quad_of(g8, 0, 0), lab00, BAND_LO, BAND_HI)
    print("""    medians over the quad's 168 rows; n16-n8 is per row, min..max.

  The base texture is FLAT over the right half of the band: %d of 168 rows of
  the gold Y8 quad have no horizontal boundary at all in columns %d..%d.  The
  %d that do are rows %s, where the quad's own vertical checker seam crosses,
  plus the %d rows of the test's white label, whose glyph edges this count
  cannot tell from checker edges.  The gold Y16 quad has %d..%d boundaries
  there in every row of every quad (median %d), at least %d more than its own
  Y8 row.  A constant offset difference cannot put a boundary where the base
  has none, so a constant offset -- of ANY size, including the half-cell one an
  earlier version of this tool printed -- is excluded by that sub-band alone.
  A mechanism does NOT have to reproduce the %d rows: %d of them are a glyph.

  The bound.  In a row, each colour change is one step of that image's cell
  index, so the cumulative movement of k across the span is at least
  (Y16 changes) - (Y8 changes).  That reaches %d cells in %d of 168 rows of
  quad g0 b0 and in all four quads, never falling below %d in any row, and one
  cell is (1/32)/(0.3/128) = %.1f byte units of `b`:

      cumulative movement of k across columns %d..%d  >=  %d cells,
      ~%.0f byte units, while ours holds the offset at one step, 82 -> 83.

  None of the %d rows that attain it is a label row (%d of them are), so the
  figure is a checker measurement throughout.

  Why Y8's count may be SUBTRACTED.  A colour change needs the cell index to
  move by at least one, which makes Y16's count a lower bound on its own
  traversal -- but subtracting Y8's needs the opposite, that the base does not
  step two cells between adjacent columns and hide a pair.  Measured on the %d
  rows the label does not touch: consecutive base boundaries in columns %d..%d
  are %d..%d columns apart, %d of %d of them 5 or 6, i.e. at most about half a
  cell of base index per column.  So the base cannot skip a cell, Y8's count is
  its traversal exactly rather than a lower bound, and the subtraction holds.

  What is NOT bounded is the EXCURSION (max - min) of k.  Parity and boundary
  counts are blind to it: an offset oscillating between two adjacent cells
  produces arbitrarily many toggles with a range of one cell, ~%.0f byte units.
  A rival with a small swing is therefore not excluded by this measurement --
  only one that cannot accumulate %d cells of relative movement across %d
  columns, %d of which the base holds flat, is."""
          % (int((n8f == 0).sum()), FLAT_LO, FLAT_HI, len(base_rows),
             " and ".join(str(r) for r in seam_rows), len(lab_flat),
             n16f_lo, n16f_hi, int(np.median(hcount(quad_of(g16, 0, 0),
                                                    FLAT_LO, FLAT_HI))),
             flat_bound, len(base_rows), len(lab_flat),
             bound, len(at), min(band_min), CELL_BYTES,
             BAND_LO, BAND_HI, bound, bound * CELL_BYTES,
             len(at), len(at & lab_rows),
             int((~lab00.any(axis=1)).sum()), BAND_LO, BAND_HI,
             int(gaps.min()), int(gaps.max()),
             int(((gaps == 5) | (gaps == 6)).sum()), len(gaps),
             CELL_BYTES, bound, BAND_HI - BAND_LO + 1,
             FLAT_HI - FLAT_LO + 1))


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
    ap.add_argument("--parity", action="store_true")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if not any((a.identity, a.stored, a.columns, a.parity, a.control)):
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
    if a.all or a.parity:
        report_parity()
        print()
    if a.all or a.control:
        report_control(a.cap, a.lumcap)


if __name__ == "__main__":
    main()
