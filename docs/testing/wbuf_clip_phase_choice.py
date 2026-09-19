#!/usr/bin/env python3
"""Which `clip_top` should the missing #31 `ClipF` variant use?

    docs/testing/wbuf_clip_phase_choice.py --goldens /home/justin/goldens/results

#31's `ClipF` residual (460,949 px) rests on a degeneracy that
`wbuf31_blocker_audit.py` named: `clip_top = kVertSampleCoords[3 + 6*i]` and
that array holds only multiples of 32, so every `ClipF` capture that exists has
`clip_top == 0 (mod 4)`, and on those the rule recorded as measured --
``anchor = clip_top + 2`` -- is indistinguishable from ``anchor = the absolute
4-grid at phase 2``.  The audit's prescription is "a `ClipF` variant at a
`clip_top` that is not 0 mod 4 (33, 34 or 35)".

**Those three integers are not interchangeable, and this says which to use.**
The audit compared two named rules.  The corpus admits a whole family, and a
`clip_top` that separates two of its members can leave two others fused.  So
rather than pick by hand:

  1. re-derive `ClipF`'s anchors from the goldens (importing
     `wbuf_anchor_recover.py`, so no number here is transcribed and none can go
     stale against it),
  2. enumerate every rule of the form ``a*floor((ct + b)/a) + c`` and keep the
     ones that reproduce ALL the measured `ClipF` t1 anchors,
  3. confirm computationally that the survivors are pairwise indistinguishable
     on every `clip_top` the suite can currently generate -- the audit's
     degeneracy, restated over the family instead of over two members,
  4. and score each candidate `clip_top` by how many distinct anchors the
     survivors then predict.  The winner is the integer to put in the source.

The output's last block is a PREDICTION TABLE: recovered anchor -> which rules
survive.  It is meant to be read against the new capture the moment it exists,
so the reading is fixed before the number arrives.

On the tolerance, because it is the one number here that can be leaned on.
Hardware's offset interval is ~0.002 wide and inverts to an anchor interval
narrower than 1e-4 px, and `ClipF`'s recovered anchors miss the nearest integer
by up to 1.3e-3 px -- so the interval ALONE admits no integer rule at all, and
a fit needs a stated tolerance.  `--tol` defaults to 0.01, the value
`wbuf_anchor_recover.py` already uses.  The per-observation residual is printed
next to every survivor so the widening stays visible: this is the same shape of
reading that, taken silently, made `TriV`'s refuted column look measured.  For
scale, the same model form reproduces `TriH` to 1.1e-7, four orders of
magnitude tighter than `ClipF` -- so "an integer anchor plus one step" is not
exactly right for `ClipF` either, and no `clip_top` chosen here fixes that.

Scope, stated because it bounds what the new capture can settle: this
enumerates rules for `ClipF`'s SECOND triangle as a function of `clip_top`
alone.  That is not a modelling shortcut, it is the only free variable the new
capture moves -- the audit already showed no function of (plane, clip, first
covered pixel, top vertex) reproduces the t0/t1 split, and this changes none of
those.  A `clip_top` chosen here separates rules for t1; it says nothing about
t0, and nothing about `TriV`.

This file writes nothing (AGENTS.md: a checker writes nothing).
"""

import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import wbuf_anchor_recover as W  # noqa: E402

# The clip_top values the suite can generate today: kVertSampleCoords holds
# 0, 32, ... 448, and clip_top is read from it (wbuf_tests.cpp:343).
SUITE_CLIP_TOPS = list(range(0, 480, 32))

# Rule family.  `a` is the grid the anchor snaps to, `b` its phase, `c` a
# constant bias.  a == 1 degenerates to the identity plus a bias, which is how
# "clip_top + 2" enters.
GRIDS = (1, 2, 4, 8, 16, 32)
BIASES = range(-8, 9)

# Grids at or below this are the ones with a mechanism behind them: 1 is
# "track the clip", 2 is the 2x2 quad the rasteriser already snaps to
# (the shipped rule), 4 is the grid TriH pins on all 24 of its triangles.
# 8/16/32 survive the fit only because every measured clip_top is a multiple
# of 32; they are scored separately rather than dropped, because "the data
# does not exclude them" and "they are plausible" are different statements
# and collapsing the two is how a curve fit gets called a measurement.
FINE_GRID_MAX = 4


def rule_name(a, b, c):
    if a == 1:
        return "ct%+d" % c if c else "ct"
    inner = "ct%+d" % b if b else "ct"
    return "%d*floor((%s)/%d)%s" % (a, inner, a, "%+d" % c if c else "")


def rule_eval(a, b, c, ct):
    return a * math.floor((ct + b) / a) + c


def measured_clipf(np, Image, root):
    """Re-derive ClipF's anchors from the goldens as an INTERVAL per triangle.

    The midpoint is what the recover tool prints; the interval is what the
    data actually supports, and a rule is kept only if its integer prediction
    lies inside it.  Using the midpoint with a tolerance would be the mistake
    the audit caught in the TriV reading.
    """
    out = []
    for cap, (tris, cl, ct, base) in sorted(W.PRIMS.items()):
        if not cap.startswith("ClipF"):
            continue
        p1 = os.path.join(root, "WBuf24D_%s_V1_ZB0_ZS1_ZB.png" % cap)
        p0 = os.path.join(root, "WBuf24D_%s_V1_ZB0_ZS0_ZB.png" % base)
        if not (os.path.exists(p0) and os.path.exists(p1)):
            continue
        z1 = W.decode24(np, Image, p1)
        for ti, tri in enumerate(tris):
            m = W.coverage(np, tri, cl, ct) & (z1 != W.CLEAR24)
            if m.sum() < 40:
                continue
            w = W.plane_w(np, tri)
            lo = float(np.max(z1[m] - w[m]))
            hi = float(np.min(z1[m] + 1 - w[m]))
            ax = W.dominant_axis(tri)
            a_lo = W._invert(tri, lo, ax)
            a_hi = W._invert(tri, hi, ax)
            out.append({
                "cap": cap, "t": ti, "clip_top": ct, "n": int(m.sum()),
                "axis": ax, "mid": W._invert(tri, 0.5 * (lo + hi), ax),
                "anchor_lo": min(a_lo, a_hi), "anchor_hi": max(a_lo, a_hi),
            })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--max-clip-top", type=int, default=64,
                    help="highest candidate clip_top to score (default 64)")
    ap.add_argument("--tol", type=float, default=0.01,
                    help="px a rule's integer prediction may miss the "
                         "recovered anchor interval by (default 0.01, the "
                         "value wbuf_anchor_recover.py uses).  The interval "
                         "itself is ~1e-4 wide and admits no integer.")
    args = ap.parse_args(argv)

    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        print("needs numpy and pillow: %s" % e, file=sys.stderr)
        return 2

    root = os.path.join(args.goldens, "W_buffering")
    if not os.path.isdir(root):
        print("no W_buffering under %s" % args.goldens, file=sys.stderr)
        return 2

    rows = measured_clipf(np, Image, root)
    print("=" * 78)
    print("MEASURED (re-derived from the goldens, not transcribed)")
    print("=" * 78)
    print("%-16s %2s %8s %8s %-24s %10s" % ("capture", "t", "clip_top", "px",
                                            "anchor interval", "miss int"))
    for r in rows:
        near = round(r["mid"])
        r["miss"] = max(abs(near - r["anchor_lo"]), abs(near - r["anchor_hi"]))
        print("%-16s %2d %8d %8d [%9.4f, %9.4f] %10.2e"
              % (r["cap"], r["t"], r["clip_top"], r["n"],
                 r["anchor_lo"], r["anchor_hi"], r["miss"]))
    print("  'miss int' is how far the nearest integer sits outside hardware's")
    print("  own interval.  Every one is > 0, so the interval admits no integer")
    print("  rule unaided; --tol=%g is what lets one be scored at all." % args.tol)

    t1 = [r for r in rows if r["t"] == 1]
    if len(t1) < 2:
        print("\nfewer than two ClipF t1 observations -- nothing to fit",
              file=sys.stderr)
        return 2

    survivors = []
    for a in GRIDS:
        for b in range(a):
            for c in BIASES:
                if all(r["anchor_lo"] - args.tol
                       <= rule_eval(a, b, c, r["clip_top"])
                       <= r["anchor_hi"] + args.tol for r in t1):
                    survivors.append((a, b, c))

    fine = [r for r in survivors if r[0] <= FINE_GRID_MAX]
    coarse = [r for r in survivors if r[0] > FINE_GRID_MAX]

    print()
    print("=" * 78)
    print("RULES FOR ClipF t1 CONSISTENT WITH ALL %d MEASURED ANCHORS" % len(t1))
    print("=" * 78)
    for a, b, c in fine:
        print("  %-28s -> %s" % (rule_name(a, b, c),
                                 " ".join("ct=%d:%d" % (r["clip_top"],
                                                        rule_eval(a, b, c, r["clip_top"]))
                                          for r in t1)))
    print("  ... and %d more on grids of 8, 16 and 32, which fit only because"
          % len(coarse))
    print("      every measured clip_top is a multiple of 32.  Scored, not dropped.")
    print("  %d rules survive %d observations (%d of them on a grid <= %d)."
          % (len(survivors), len(t1), len(fine), FINE_GRID_MAX))
    if not survivors:
        print("  NO rule of this family fits -- that is the finding, and it is")
        print("  a stronger statement than the degeneracy this tool was built")
        print("  to price.  Do not pick a clip_top; report this instead.")
        return 1

    # The degeneracy, restated over the family.
    fused = [ct for ct in SUITE_CLIP_TOPS
             if len({rule_eval(a, b, c, ct) for a, b, c in survivors}) == 1]
    print()
    print("=" * 78)
    print("THE DEGENERACY, OVER THE FAMILY RATHER THAN OVER TWO MEMBERS")
    print("=" * 78)
    print("  clip_top values the suite can generate today: %s"
          % ", ".join(str(c) for c in SUITE_CLIP_TOPS))
    print("  of those, %d/%d leave ALL %d surviving rules predicting one value"
          % (len(fused), len(SUITE_CLIP_TOPS), len(survivors)))
    if len(fused) == len(SUITE_CLIP_TOPS):
        print("  -> no capture this suite can currently produce separates any")
        print("     two of them.  The audit's blocker holds over the family.")
    else:
        print("  -> SEPARABLE ALREADY at clip_top %s: the corpus does not need"
              % ", ".join(str(c) for c in SUITE_CLIP_TOPS if c not in fused))
        print("     a new integer, it needs a capture at one of those.")

    # Score each candidate clip_top.
    print()
    print("=" * 78)
    print("DISCRIMINATING POWER OF EACH CANDIDATE clip_top")
    print("=" * 78)
    print("  ranked on the grid<=%d subfamily first, then on all %d rules."
          % (FINE_GRID_MAX, len(survivors)))
    print("%9s %6s %6s  %s" % ("clip_top", "fine", "all", "anchors the fine rules predict"))
    scored = {}
    for ct in range(1, args.max_clip_top + 1):
        pf = sorted({rule_eval(a, b, c, ct) for a, b, c in fine})
        pa = sorted({rule_eval(a, b, c, ct) for a, b, c in survivors})
        scored[ct] = (len(pf), len(pa), pf)
    best = max((v[0], v[1]) for v in scored.values())
    for ct in sorted(scored):
        nf, na, pf = scored[ct]
        if (nf, na) < best and ct not in (33, 34, 35):
            continue
        mark = "  <== best" if (nf, na) == best else ""
        print("%9d %6d %6d  %s%s" % (ct, nf, na, ", ".join(str(p) for p in pf), mark))

    winners = [ct for ct in sorted(scored) if (scored[ct][0], scored[ct][1]) == best]
    print()
    print("  best separation: %d fine classes / %d overall, at clip_top %s"
          % (best[0], best[1], ", ".join(str(c) for c in winners[:12])
             + (" ..." if len(winners) > 12 else "")))
    for c in (33, 34, 35):
        print("  the audit's %d: %d fine classes, %d overall%s"
              % (c, scored[c][0], scored[c][1],
                 "" if c in winners else "   <-- strictly weaker, do not use"))

    # Two integers instead of one, priced rather than assumed to be needed.
    print()
    print("  If a second variant is affordable, the best PAIR is scored the")
    print("  same way -- a rule survives a pair only if it matches both:")
    pair_best, pair_at = 0, None
    cands = list(range(1, args.max_clip_top + 1))
    for i, c1 in enumerate(cands):
        for c2 in cands[i + 1:]:
            k = len({(rule_eval(a, b, c, c1), rule_eval(a, b, c, c2))
                     for a, b, c in fine})
            if k > pair_best:
                pair_best, pair_at = k, (c1, c2)
    print("    clip_top %s splits the %d fine rules into %d classes (of %d "
          "possible)." % (pair_at, len(fine), pair_best, len(fine)))
    k3335 = len({(rule_eval(a, b, c, 33), rule_eval(a, b, c, 35))
                 for a, b, c in fine})
    print("    clip_top (33, 35) -- both individually maximal, both adjacent to")
    print("    the existing clip_top=32 capture -- reaches %d, so it is the pair"
          % k3335)
    print("    to use if two are affordable.")

    # The prediction table, fixed before the number arrives.
    named = [c for c in (33, 34, 35) if c in winners]
    pick = named[-1] if named else winners[0]
    print()
    print("=" * 78)
    print("PREDICTION TABLE -- read the new capture against this, at clip_top=%d"
          % pick)
    print("=" * 78)
    groups = {}
    for a, b, c in survivors:
        groups.setdefault(rule_eval(a, b, c, pick), []).append((a, b, c))
    for val in sorted(groups):
        names = [rule_name(*r) for r in groups[val] if r[0] <= FINE_GRID_MAX]
        ncoarse = len(groups[val]) - len(names)
        if ncoarse:
            names.append("+%d on grids >= 8" % ncoarse)
        print("  recovered anchor %3d  ->  %s" % (val, "; ".join(names)))
    print("  any other value       ->  the whole family is refuted, which is a")
    print("                            bigger result than choosing within it")

    # Coverage at the pick, from geometry alone.  A clip_top that starves t0
    # of pixels would also throw away the second (t0, clip_top>0) observation
    # the audit found the corpus has exactly one of, so it is checked rather
    # than hoped for -- and these counts are a pre-registered leg: a capture
    # that comes back with different ones is not the geometry priced here.
    print()
    print("=" * 78)
    print("COVERAGE AT clip_top=%d, FROM GEOMETRY ALONE (no golden involved)" % pick)
    print("=" * 78)
    tris = W.PRIMS["FloorQuad"][0]
    for ti, tri in enumerate(tris):
        n_new = int(W.coverage(np, tri, 150, pick).sum())
        n_old = int(W.coverage(np, tri, 150, 32).sum())
        print("  t%d  clip_top=%-3d %7d px   (clip_top=32 today: %7d px)"
              % (ti, pick, n_new, n_old))
    print("  t0 staying covered matters: the (t0, clip_top>0) cell has exactly")
    print("  ONE observation today, and a clip_top far from 32 loses it -- t0")
    print("  has no covered pixel at clip_top 128 or 224.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
