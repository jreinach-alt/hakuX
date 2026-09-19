#!/usr/bin/env python3
"""Selftest for stipple_classify.py.

Two jobs, and the second is the one that makes the first mean anything.

  1. POSITIVE CONTROL ON REAL DATA.  Run the classifier over the two founding
     mosaics and check it finds the artifact where the artifact is known to be.
     A classifier that cannot do that cannot be trusted to report an ABSENCE
     anywhere else, which is the result this lane is most likely to publish.

  2. THE MUTANT.  The whole point of this file's existence is that
     `galleon_flash_rate.py`'s default bar flags a smooth animation ramp on
     consecutive frames.  So the selftest builds that ramp and asserts BOTH
     halves: the old bar flags it, and the new one does not.  Asserting only
     the second would make "no false positives" a free verdict -- true of any
     threshold high enough, including one that can never fire.

Run:  python3 docs/lanes/diagsoak77/stipple_classify_selftest.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))

import galleon_flash_rate as gfr  # noqa: E402
import stipple_classify as sc  # noqa: E402

IMAGES = os.path.join(HERE, "..", "..", "investigations", "images")

# The founding sets, from galleon_flash_rate.py's own docstring.
DECK_FOUNDING = {4, 8, 13, 32}
TOWN_FOUNDING = {3, 5, 7, 11, 22, 48, 49}

fails = []


def check(name, ok, detail=""):
    print("%-58s %s%s" % (name, "ok" if ok else "FAIL",
                          "" if ok else "   " + detail))
    if not ok:
        fails.append(name)


# --------------------------------------------------------------- real data

deck = gfr.load_frames([os.path.join(IMAGES, "galleon-deck-cycle.png")],
                       (8, 5), (4, 4, 196, 84))
deck_rows = sc.classify(deck)
deck_hit = {r["frame"] for r in deck_rows if r["stipple"]}
check("deck mosaic: recovers the founding set exactly",
      deck_hit == DECK_FOUNDING, "got %s want %s" % (sorted(deck_hit),
                                                     sorted(DECK_FOUNDING)))

# The direction reversal must survive too: all four founding deck frames lie on
# the anti-diagonal while their own local window sits at ~1.0.  This is the
# observable the mip-level reading was abandoned over, so it is checked rather
# than assumed -- a classifier that found four frames with no direction
# structure would have found something else.
deck_dev = [r["d_dev"] for r in deck_rows if r["stipple"]]
check("deck mosaic: every flagged frame deviates in direction",
      all(d < 0.95 for d in deck_dev), "devs %s" % [round(d, 2) for d in deck_dev])

town = gfr.load_frames([os.path.join(IMAGES, "galleon-town-cycle.png")],
                       (10, 5), (0, 100, 110, 150))
town_rows = sc.classify(town)
town_hit = {r["frame"] for r in town_rows if r["stipple"]}

# THE TOLERANCE, stated rather than tuned.  The absolute 1.45x bar is stricter
# than the k=3 global-MAD bar the founding set was drawn at, and it misses the
# two weakest members: frame 5 at 1.29x and frame 22 at 1.42x.  Those two are
# also the only two of the seven with NO direction deviation (d_dev 0.94 and
# 0.97, against 1.23-1.69 and 0.82 for the five it does find), so what the
# stricter bar drops is the part of the founding set that carries the least
# evidence of being the artifact.  The threshold is NOT moved to collect them;
# moving it to fit is the curve fit this classifier exists to avoid.
check("town mosaic: flags only founding frames (no false positive)",
      town_hit <= TOWN_FOUNDING, "extra %s" % sorted(town_hit - TOWN_FOUNDING))
check("town mosaic: finds 5 of the 7 founding frames",
      len(town_hit & TOWN_FOUNDING) == 5, "got %s" % sorted(town_hit))

# Rank recovery is the stronger statement and it is clean: ordered by ratio,
# the seven founding frames ARE the top seven of fifty.  So the two misses are
# a threshold choice, not a failure to see them.
town_rank = {r["frame"] for r in sorted(town_rows, key=lambda r: -r["ratio"])[:7]}
check("town mosaic: the founding seven are the top seven by ratio",
      town_rank == TOWN_FOUNDING, "top7 %s" % sorted(town_rank))


# --------------------------------------------------------------- the mutant

# THE MEASURED SEQUENCE, not an imitation of it.  These are the 30 whole-frame
# HF values `galleon_flash_rate.py --per-frame` printed for the consecutive
# PPMs of run 1789811606-diagdump77-4099630 (Galleon, Thor, spec 30,after120).
# They are the sword flourish: a smooth rise and fall with no step anywhere in
# it.  Embedded rather than recomputed because the run's 30 PPMs live under
# dispatch/results and are not in the repository -- and because the claim being
# pinned is about the BAR ARITHMETIC over an HF sequence, which needs the
# numbers and not the pixels.
RECON_HF = [1.13, 1.14, 1.15, 1.15, 1.15, 1.15, 1.17, 1.19, 1.20, 1.20,
            1.20, 1.20, 1.20, 1.23, 1.28, 1.28, 1.29, 1.34, 1.31, 1.30,
            1.28, 1.20, 1.19, 1.20, 1.20, 1.19, 1.19, 1.20, 1.20, 1.20]
RECON_OLD_HIT = [16, 17, 18, 19]   # what the k=3 bar reported: 13.3 per 100

recon = np.array(RECON_HF)
_, recon_mad, recon_bar = gfr.robust_bar(recon)
old_hit = [int(i) for i in np.nonzero(recon > recon_bar)[0]]

# The half that makes the next line cost something.  If the old bar ever stops
# flagging this sequence, the replacement is buying nothing and the docstring
# that justifies this whole file is wrong.
check("recon sequence: galleon_flash_rate's k=3 bar DOES flag it",
      old_hit == RECON_OLD_HIT,
      "got %s want %s (mad %.3f bar %.3f)"
      % (old_hit, RECON_OLD_HIT, recon_mad, recon_bar))
print("      (the mutant: mad %.3f collapses the bar to %.3f, %.0f%% above the "
      "median, and flags %d of 30 -- %.1f per 100 -- on a smooth +%.0f%% ramp)"
      % (recon_mad, recon_bar, 100 * (recon_bar / np.median(recon) - 1),
         len(old_hit), 100.0 * len(old_hit) / len(recon),
         100 * (recon.max() / np.median(recon) - 1)))

recon_hit = [r["frame"] for r in sc.classify_hf(recon) if r["stipple"]]
check("recon sequence: the local-baseline bar flags nothing",
      not recon_hit, "flagged %s" % recon_hit)

# ...and it is not merely a bar nothing can clear: drop the artifact's own
# magnitude onto the same sequence and it must be found.
for mult, want in ((1.45, [17]), (1.93, [17])):
    inj = recon.copy()
    inj[17] = sc.local_baseline(recon, 17, sc.DEFAULT_WINDOW) * mult
    hit = [r["frame"] for r in sc.classify_hf(inj) if r["stipple"]]
    check("recon sequence + a %.2fx excursion at f17: caught, and only it"
          % mult, hit == want, "flagged %s" % hit)

# Just under the bar must NOT be caught, or the threshold is decorative.
inj = recon.copy()
inj[17] = sc.local_baseline(recon, 17, sc.DEFAULT_WINDOW) * 1.44
check("recon sequence + a 1.44x excursion: below the bar, not flagged",
      not [r["frame"] for r in sc.classify_hf(inj) if r["stipple"]])

# A two-frame excursion -- the length the artifact is reported at -- must not
# suppress itself through the shared baseline.
inj = recon.copy()
for i in (17, 18):
    inj[i] = sc.local_baseline(recon, i, sc.DEFAULT_WINDOW) * 1.6
hit = [r["frame"] for r in sc.classify_hf(inj) if r["stipple"]]
check("a two-frame excursion: both frames caught", hit == [17, 18],
      "flagged %s" % hit)

# THE BASELINE-EXCLUDES-SELF BOUNDARY.  At the window sizes and excursion
# lengths this lane operates at the choice changes nothing, and the docstring
# says so.  Where it separates the two is narrow and worth pinning exactly: an
# excursion L frames long against a half-window W contaminates the
# including-self median once L >= W+1 (it is then the majority of the 2W+1
# values), while the excluding-self median only falls inside the excursion at
# L >= W+2.  In the gap, L = W+1, the excluded median is the midpoint of the
# two levels, so the flip needs the excursion to be more than 2*RATIO-1 times
# the baseline.  W=3, L=4, 3.0x -- deliberately a bigger excursion than the
# artifact's own 1.46-1.93x, because this is a boundary in the arithmetic and
# not a regime this lane measures in.  Said plainly so the check is not read as
# a claim that self-exclusion matters to any result below.
long_exc = np.full(30, 4.0)
long_exc[12:16] = 4.0 * 3.0
W = 3


def _including_self(v, i, window):
    lo, hi = max(0, i - window), min(len(v), i + window + 1)
    return float(np.median(v[lo:hi]))


real_hit = [r["frame"] for r in sc.classify_hf(long_exc, window=W)
            if r["stipple"]]
_real = sc.local_baseline
try:
    sc.local_baseline = _including_self
    mutant_hit = [r["frame"] for r in sc.classify_hf(long_exc, window=W)
                  if r["stipple"]]
finally:
    sc.local_baseline = _real
check("W=3, L=4: excluding self keeps frames the including-self mutant loses",
      set(mutant_hit) < set(real_hit) and len(real_hit) > 0,
      "real %s mutant %s" % (real_hit, mutant_hit))

# And the honest converse, so nobody reads the line above as a general claim.
real10 = [r["frame"] for r in sc.classify_hf(long_exc, window=10)
          if r["stipple"]]
try:
    sc.local_baseline = _including_self
    mut10 = [r["frame"] for r in sc.classify_hf(long_exc, window=10)
             if r["stipple"]]
finally:
    sc.local_baseline = _real
check("W=10, L=4: the two agree -- the choice is not load-bearing here",
      real10 == mut10, "real %s mutant %s" % (real10, mut10))

print()
if fails:
    print("FAILED: %d check(s): %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("all checks passed")
