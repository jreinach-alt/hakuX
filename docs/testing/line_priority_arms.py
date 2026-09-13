#!/usr/bin/env python3
"""Ask OUR captures the question the goldens already answered: which of several
overlapping wide edges did we draw last?

`line_priority.py` derives silicon's edge-priority rule from the goldens alone.
This is the arm-side half of it, and it exists because a change to the emission
ORDER in `prim_rewrite.c` cannot be measured by any counter: the number of
lines emitted is identical before and after, so `mb_emitted`-style
instrumentation passes on both arms and proves nothing.  A pixel total is not
much better -- the priority class and the extent class overlap, so removing one
cause need not move the count.

So the measurement is a LABEL, not a number.  For each pixel whose golden
colour names exactly one covering edge (a *decisive* pixel, as
`line_priority.decisive` defines it), this asks which edge OUR capture's colour
names, and reports agreement per candidate class.  That separates the three
outcomes a total cannot:

  * arm B names the same edge as arm A        -> the change did not execute
  * arm B names a different edge, not golden's -> it executed and is wrong
  * arm B names the golden's edge              -> it executed and is right

The decisive set is built with the PERPENDICULAR footprint by default, because
that is the footprint our renderer actually draws; `--extent-rule` builds it
with silicon's wider hypot-approximation width instead, which is what the
goldens want and what we do not yet implement.

    line_priority_arms.py --a RESULTDIR [--b RESULTDIR] [--goldens DIR] \
        --min-width 8 --max-width 63.875

Captures are resolved with `captures.py`, never by globbing: a falsifier that
reports its own evidence MISSING on an arm that contains it reads exactly like
a failed render.

VOID CAPTURES.  `Line_0064.0`-`.7` and `Line_FFFFFFFF` are excluded by
default.  Their goldens' ink mask is byte-identical to `Line_0001.0`'s -- the
width register holds nine bits of eighths, 64.0 is 512 and does not fit, so
hardware left the width at the 1.0 the suite restores between tests while every
model, and this emulator, draws them at 64.  That is one statement about the
goldens, decided before any score, and it applies to exactly the set whose
register value overflows nine bits.  `--include-void` keeps them.
"""
import argparse
import os
import sys
from collections import defaultdict

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import captures as caps
import line_priority as lp

# Goldens whose ink mask is byte-identical to Line_0001.0's: the width register
# overflowed, hardware drew width 1, we draw 64.  Not measurements.
VOID = tuple("Line_0064.%d" % i for i in range(8)) + ("Line_FFFFFFFF",)

# The blocks whose emission order `prim_rewrite.c` chooses.  TRIANGLES and
# TRIANGLE_FAN keep VK_POLYGON_MODE_LINE, so Turnip orders their edges and no
# edit to prim_rewrite.c can move them; LINE_LOOP is submission order, which we
# already match.
OURS_TO_ORDER = ("Quad", "QStrip", "Poly")


def decisive_xy(g, w, extent_rule=False):
    """As line_priority.decisive, but also returns (y, x) and the candidate
    colours, so an arm's own pixel can be labelled at the same site.

    Kept a separate function rather than a change to line_priority.py: that
    file is the derivation's instrument and its numbers are on the record.
    """
    d = lp.text_mask(g)
    n_e, H, W = len(lp.EDGES), lp.H, lp.W
    deep = np.ones((n_e, H, W), dtype=bool)
    full = np.zeros((n_e, H, W), dtype=bool)
    cols = np.empty((n_e, H, W, 3))
    for i, e in enumerate(lp.EDGES):
        for bias in ((0.0, 0.0), (0.5, 0.0)):
            c, t, _a, _L = lp.field(e, w, bias, lp.MARGIN, extent_rule)
            deep[i] &= c
            f, _, _, _ = lp.field(e, w, bias, 0.0, extent_rule)
            full[i] |= f
        cols[i] = lp.edge_colour(e, t)
    nd, nf = deep.sum(0), full.sum(0)
    ys, xs = np.nonzero((nd >= 2) & (nd == nf) & ~d)
    out = []
    for y, x in zip(ys, xs):
        which = np.nonzero(deep[:, y, x])[0]
        cc = cols[which, y, x]
        sep = min(np.abs(cc[i] - cc[j]).max()
                  for i in range(len(which)) for j in range(i + 1, len(which)))
        if sep < lp.SEP:
            continue
        errs = np.abs(cc - g[y, x, :3].astype(float)).max(axis=1)
        o = np.argsort(errs)
        if errs[o[0]] > lp.TOL or errs[o[1]] <= lp.TOL * 3:
            continue
        out.append((int(y), int(x), int(which[o[0]]),
                    [int(v) for v in which], cc.copy()))
    return out


def label(pix, cand_cols, tol, ratio):
    """Which candidate this pixel's colour names, or None if it names none."""
    errs = np.abs(cand_cols - np.asarray(pix, dtype=float)).max(axis=1)
    o = np.argsort(errs)
    if errs[o[0]] > tol or errs[o[1]] <= tol * ratio:
        return None
    return int(o[0])


def changed_region(w):
    """Union of the footprints of every edge whose ORDER prim_rewrite.c picks,
    dilated by one pixel.  Nothing outside this can move when only the order of
    those edges changes, so a difference outside it is a scoping bug."""
    m = np.zeros((lp.H, lp.W), dtype=bool)
    for i, e in enumerate(lp.EDGES):
        if e[0] not in OURS_TO_ORDER:
            continue
        for bias in ((0.0, 0.0), (0.5, 0.0)):
            c, _, _, _ = lp.field(e, w, bias, 0.0, False)
            m |= c
    d = m.copy()
    for s in (1, -1):
        d |= np.roll(m, s, axis=0)
        d |= np.roll(m, s, axis=1)
    return d


def arm_capture(d, test):
    p = caps.find(d, lp.SUITE, test)
    if p is None:
        return None
    return np.asarray(Image.open(p).convert("RGBA")).astype(np.int16)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default=os.path.expanduser("~/goldens/results"))
    ap.add_argument("--a", required=True, help="arm A result or captures dir")
    ap.add_argument("--b", help="arm B result or captures dir")
    ap.add_argument("--min-width", type=float, default=8.0)
    ap.add_argument("--max-width", type=float, default=63.875)
    ap.add_argument("--extent-rule", action="store_true")
    ap.add_argument("--include-void", action="store_true")
    ap.add_argument("--tol", type=float, default=16.0,
                    help="max channel error at which an arm's pixel is taken "
                         "to name a candidate (goldens use 10)")
    ap.add_argument("--ratio", type=float, default=2.0,
                    help="the runner-up must be further than tol*ratio")
    a = ap.parse_args()

    arms = [("A", a.a)] + ([("B", a.b)] if a.b else [])
    for nm, d in arms:
        if not os.path.isdir(d):
            print("arm %s: no such directory %s" % (nm, d))
            return 2
        print("arm %s captures: %s" % (nm, caps.resolve(d, "%s::*.png" % lp.SUITE)),
              file=sys.stderr)

    # per candidate class: [n, agree_A, agree_B, unmatched_A, unmatched_B, moved]
    cls = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    per_capture = {}
    scope = {}
    missing = []

    for test, w, g in lp.captures(a.goldens, a.min_width, a.max_width):
        if test in VOID and not a.include_void:
            print("  %-14s w=%-8s VOID (golden ink == Line_0001.0)"
                  % (test, w), file=sys.stderr)
            continue
        imgs = {}
        for nm, d in arms:
            im = arm_capture(d, test)
            if im is None:
                missing.append((nm, test))
            imgs[nm] = im
        if any(imgs[nm] is None for nm, _ in arms):
            continue

        px = decisive_xy(g, w, a.extent_rule)
        row = [0, 0, 0, 0, 0, 0]
        for (y, x, win, which, cc) in px:
            key = "/".join(sorted({lp.EDGES[e][0] for e in which}))
            wi = which.index(win)
            lab = {}
            for nm, _ in arms:
                lab[nm] = label(imgs[nm][y, x, :3], cc, a.tol, a.ratio)
            for rec in (cls[key], row):
                rec[0] += 1
                if lab["A"] is None:
                    rec[3] += 1
                elif lab["A"] == wi:
                    rec[1] += 1
                if "B" in lab:
                    if lab["B"] is None:
                        rec[4] += 1
                    elif lab["B"] == wi:
                        rec[2] += 1
                    if lab["A"] != lab["B"]:
                        rec[5] += 1
        per_capture[test] = (w, row)

        if len(arms) == 2:
            diff = np.abs(imgs["A"].astype(int) - imgs["B"].astype(int)).max(axis=2) > 0
            reg = changed_region(w)
            scope[test] = (int(diff.sum()), int((diff & ~reg).sum()))

        print("  %-14s w=%-8s decisive=%-7d moved=%d"
              % (test, w, row[0], row[5]), file=sys.stderr)

    if missing:
        print("\n*** MISSING CAPTURES -- this is not a zero, it is an absence:")
        for nm, t in missing:
            print("    arm %s: %s" % (nm, t))

    def pct(n, d):
        return "%.2f%%" % (100.0 * n / d) if d else "     -"

    print("\n" + "=" * 78)
    print("decisive pixels by candidate class  (footprint: %s)"
          % ("derived extent" if a.extent_rule else "perpendicular rectangle"))
    print("=" * 78)
    print("%-18s%9s%10s%10s%9s%9s%10s"
          % ("class", "n", "A names", "B names", "unm A", "unm B", "moved"))
    tot = [0, 0, 0, 0, 0, 0]
    for key in sorted(cls, key=lambda k: -cls[k][0]):
        n, aok, bok, ua, ub, mv = cls[key]
        for i, v in enumerate(cls[key]):
            tot[i] += v
        print("%-18s%9d%10s%10s%9s%9s%10d"
              % (key + ("*" if any(b in key.split("/") for b in OURS_TO_ORDER)
                        else " "),
                 n, pct(aok, n), pct(bok, n), pct(ua, n), pct(ub, n), mv))
    n, aok, bok, ua, ub, mv = tot
    print("%-18s%9d%10s%10s%9s%9s%10d"
          % ("ALL", n, pct(aok, n), pct(bok, n), pct(ua, n), pct(ub, n), mv))
    print("\n* the class involves at least one block whose emission order "
          "prim_rewrite.c picks\n  (%s).  Tri and TFan keep "
          "VK_POLYGON_MODE_LINE, so Turnip orders them;\n  LLoop is submission "
          "order and already matched." % ", ".join(OURS_TO_ORDER))

    print("\n" + "=" * 78)
    print("per capture")
    print("=" * 78)
    print("%-14s%8s%9s%10s%10s%9s%12s%12s"
          % ("capture", "w", "decisive", "A names", "B names", "moved",
             "A!=B px", "outside*"))
    for test in sorted(per_capture, key=lambda t: per_capture[t][0]):
        w, (n, aok, bok, ua, ub, mv) = per_capture[test]
        s = scope.get(test)
        print("%-14s%8s%9d%10s%10s%9d%12s%12s"
              % (test, w, n, pct(aok, n), pct(bok, n), mv,
                 ("%d" % s[0]) if s else "-", ("%d" % s[1]) if s else "-"))
    if scope:
        print("\n* 'outside' counts pixels differing between the arms OUTSIDE "
              "the union of the\n  footprints whose order changed, dilated by "
              "one pixel.  It must be 0: a\n  reordering of those edges cannot "
              "reach anything else.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
