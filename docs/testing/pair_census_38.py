#!/usr/bin/env python3
"""#38 mechanism 2: a pair census with no width floor and no 4-byte ceiling.

WHY THIS EXISTS, and what it is auditing.

#38's blocker says the selection rule for the pair granularity "needs five new
captures that do not exist upstream".  The argument behind it is that the class
of draws that could show the pair has exactly two members, so the positive cell
cannot be subdivided, leaving a four-way tie between

    immediate mode /\\ w = 1        (the conjunction itself)
    ... /\\ QUADS or POLYGON        (never a triangle form)
    ... /\\ >= 512 px wide          ("one large primitive")
    ... /\\ SET_VERTEX4F

That tie is asserted against `interpolator_phase.py`'s per-row census, and
THAT INSTRUMENT CANNOT SEE TWO OF THE FOUR CONJUNCTS.  Its `row_pair_stats`
qualifies a position only when adjacent pixels differ by <= 4 per channel, and
judges a row only when at least 50 qualifying positions exist at EACH parity.
So:

  * a draw narrower than about 200 px yields < 50 positions per parity and is
    DROPPED -- which is exactly the "one large primitive" conjunct.  The
    instrument cannot report a narrow paired draw even if one exists.
  * a gradient steeper than 4 bytes/px is DROPPED for the same reason, and a
    small primitive with a full-range ramp across it is necessarily steep.

This is the #13 shape: the discriminating data may be on disk while the
instrument throws it away.  (#13's `line_priority.py --extent` recorded a run's
LENGTH while the goldens also carried its POSITION.)  So before the blocker is
believed, the census has to be re-run with those two restrictions lifted.

WHAT REPLACES THEM.

The two restrictions exist for one real reason: the `pb_print` overlay puts
3-px white glyph stems on a flat ground, and an unguarded equality test reads
those as a pair (E = 1.00, O = 0.03 on `Depth_Clamp`'s text alone).  A
magnitude bound is one way to exclude them and it is the one that costs the
two conjuncts.  This uses two cheaper properties of a glyph instead:

  MONOTONE      a linear interpolant is monotone in x; a glyph stem is not
                (B W W W B rises then falls inside a 4-px window).
  BOUNDED       |delta| <= MAXSTEP = 32 per channel, against the old 4.  A
                glyph edge steps by up to 255 and is excluded; every gradient
                from 1/px to 32/px is now admitted where the old metric kept
                only <= 4/px.

and it POOLS over the whole capture rather than requiring 50 positions per row,
so a 128-px-wide draw contributes its pairs instead of being dropped.

THE STATISTIC IS A DIFFERENCE, WHICH IS WHAT MAKES IT SELF-CONTROLLING.

  E = P(v[x] == v[x+1])  over qualifying EVEN x
  O = P(v[x] == v[x+1])  over qualifying ODD  x

Both are measured over the SAME pixel population, so any flat region
contributes 1 to both and cancels out of E - O.  Under pixel-centre sampling
(ours) a ramp gives E ~ O whatever its slope.  Under the pair rule E = 1 and
O falls to roughly 1 - 2*slope.  E - O is therefore the signal, and it needs no
assumption about the slope, the width or the draw.

CONTROLS, stated before the numbers so a zero cannot be read as good news:

  positive  Alpha_func/*            must read E ~ 1.00 with O near 0
  positive  Context_switch/GRZero   must read E > O
  negative  High_vertex_count/*     must read E ~ O  (6x6 px Gouraud quads --
                                    these are the draws the OLD metric could
                                    not judge at all, and the ones this one
                                    exists to judge)
  inverting Alpha_func in OUR OWN captures must read E ~ O, because we sample
                                    at the pixel centre.  If the instrument
                                    reported paired for whatever it is shown,
                                    this row would pair too.

IMPOSSIBLE ROW: a capture reporting E == O == 1.000 over many positions means
the monotone/non-constant filter admitted flat pixels and the run is void.

Run:  python3 docs/testing/pair_census_38.py [GOLDENDIR] [--captures DIR ...]
"""

import os
import sys

import numpy as np
from PIL import Image

GOLDENS = "/home/justin/goldens/results"

MAXSTEP = 32      # per-channel |delta| ceiling; the old metric used 4
MINPOS = 200      # pooled qualifying positions needed at each parity
PAIRED_E = 0.90   # a capture is "paired" when E > this ...
PAIRED_GAP = 0.35 # ... and E - O exceeds this


def qualifying(a):
    """Mask of x positions whose 4-px window is a bounded monotone ramp.

    Returns (mask, same) over the delta grid: mask[y, x] says the comparison
    v[y, x] vs v[y, x+1] is evidence about the interpolator, and same[y, x]
    says the two are equal.
    """
    w = a[:, :, :3].astype(np.int16)
    d = w[:, 1:, :] - w[:, :-1, :]                     # signed per-channel step
    amax = np.abs(d).max(axis=2)
    same = amax == 0

    # A window of three consecutive deltas centred on x: d[x-1], d[x], d[x+1].
    n = d.shape[1]
    if n < 3:
        return np.zeros_like(same), same
    prev = np.zeros_like(d)
    nxt = np.zeros_like(d)
    prev[:, 1:, :] = d[:, :-1, :]
    nxt[:, :-1, :] = d[:, 1:, :]

    # Monotone: within each channel the three steps never disagree in sign.
    nonneg = (prev >= 0) & (d >= 0) & (nxt >= 0)
    nonpos = (prev <= 0) & (d <= 0) & (nxt <= 0)
    mono = (nonneg | nonpos).all(axis=2)

    # Bounded: no step in the window exceeds MAXSTEP in any channel.
    bounded = (np.abs(prev).max(axis=2) <= MAXSTEP) & (amax <= MAXSTEP) & \
              (np.abs(nxt).max(axis=2) <= MAXSTEP)

    # RAMP, not a lone edge.  This is the restriction the first version of this
    # script lacked, and it produced a 1,673-capture false positive class.
    #
    # A single hard edge is monotone and, if its step is under MAXSTEP, bounded
    # -- so `Blend_tests`' swatch boundaries qualified.  Diagnosed by dumping
    # the qualifying positions of `1-dstRGB_MIN_1`: they sat at x = 14,15,16 /
    # 58,59,60 / 118,119,120, the background-to-swatch transitions
    # (32,32,32) -> (4,48,4).  At an edge two of the three window positions are
    # "same" and one is not, and because swatch grids are laid out on a regular
    # even-aligned pitch EVERY edge in the frame shares a parity -- which
    # manufactures E >> O out of geometry that has no interpolant in it.
    #
    # A genuine interpolant ramp has SEVERAL steps in a 4-px window (at
    # ~0.5 byte/px, one step every other pixel); a lone edge has exactly one.
    # So require at least two of the three window deltas to be non-zero.  That
    # keeps every real gradient from 1/px to MAXSTEP/px and drops isolated
    # edges without reintroducing a tight magnitude bound.
    nz = ((np.abs(prev).max(axis=2) > 0).astype(np.int8)
          + (amax > 0).astype(np.int8)
          + (np.abs(nxt).max(axis=2) > 0).astype(np.int8))
    varying = nz >= 2

    mask = mono & bounded & varying
    mask[:, :1] = False
    mask[:, -1:] = False
    return mask, same


def census(path):
    a = np.array(Image.open(path).convert("RGBA"))
    mask, same = qualifying(a)
    xs = np.arange(mask.shape[1])
    ev = mask & (xs % 2 == 0)[None, :]
    od = mask & (xs % 2 == 1)[None, :]
    ne, no = int(ev.sum()), int(od.sum())
    if ne < MINPOS or no < MINPOS:
        return None
    E = float((same & ev).sum()) / ne
    O = float((same & od).sum()) / no
    return ne, no, E, O


def walk(root):
    for suite in sorted(os.listdir(root)):
        d = os.path.join(root, suite)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".png"):
                yield suite, fn[:-4], os.path.join(d, fn)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = args[0] if args else GOLDENS
    print(__doc__.split("Run:")[0].rstrip())
    print("\ngoldens: %s" % root)
    print("MAXSTEP=%d (old metric: 4)   MINPOS=%d pooled (old: 50 per row)\n"
          % (MAXSTEP, MINPOS))

    rows = []
    scanned = 0
    for suite, cap, path in walk(root):
        scanned += 1
        r = census(path)
        if r is None:
            continue
        ne, no, E, O = r
        rows.append((suite, cap, ne, no, E, O))

    paired = [r for r in rows if r[4] > PAIRED_E and r[4] - r[5] > PAIRED_GAP]
    impossible = [r for r in rows if r[4] == 1.0 and r[5] == 1.0]

    print("scanned %d captures; %d measurable (both parities >= %d positions);"
          " %d paired" % (scanned, len(rows), MINPOS, len(paired)))
    print("\nPAIRED captures (E > %.2f and E - O > %.2f):\n" % (PAIRED_E, PAIRED_GAP))
    print("   %-26s %-34s %8s %8s %7s %7s %7s"
          % ("suite", "capture", "even", "odd", "E", "O", "E-O"))
    bysuite = {}
    for suite, cap, ne, no, E, O in sorted(paired, key=lambda r: -(r[4] - r[5])):
        print("   %-26s %-34s %8d %8d %7.4f %7.4f %7.4f"
              % (suite, cap[:34], ne, no, E, O, E - O))
        bysuite.setdefault(suite, 0)
        bysuite[suite] += 1

    print("\npaired captures by suite:")
    for s in sorted(bysuite):
        print("   %-26s %d" % (s, bysuite[s]))

    print("\nIMPOSSIBLE ROW CHECK (E == O == 1.000 would mean flat pixels"
          " qualified): %d" % len(impossible))
    for r in impossible[:10]:
        print("   %s/%s  even=%d odd=%d" % (r[0], r[1], r[2], r[3]))

    print("\nCONTROLS")
    want = [("Alpha_func", "positive, expect E~1 and E-O large"),
            ("Context_switch", "positive on GRZero"),
            ("High_vertex_count", "NEGATIVE, expect E~O -- the old metric"
                                  " could not judge these at all"),
            ("Shade_model", "NEGATIVE, expect E~O"),
            ("3D_primitive", "NEGATIVE, expect E~O")]
    for suite, note in want:
        sel = [r for r in rows if r[0] == suite]
        if not sel:
            print("   %-20s NO MEASURABLE CAPTURES  (%s)" % (suite, note))
            continue
        Es = [r[4] for r in sel]
        Gs = [r[4] - r[5] for r in sel]
        print("   %-20s n=%3d  E %.3f..%.3f  E-O %.3f..%.3f   %s"
              % (suite, len(sel), min(Es), max(Es), min(Gs), max(Gs), note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
