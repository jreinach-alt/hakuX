#!/usr/bin/env python3
"""Classify frames as stipple / clean by the founding artifact's MAGNITUDE.

    stipple_classify.py [--region X0,Y0,X1,Y1] [--mosaic CxR] [--json OUT]
                        [--window 10] [--ratio 1.45] FRAMES...

WHY THIS IS NOT `galleon_flash_rate.py`.  That tool is the right instrument for
the artifact and this one imports its two measurements verbatim rather than
re-deriving them.  What this replaces is its BAR, and only for one input
shape: a run of CONSECUTIVE frames.

`galleon_flash_rate.py` sets an outlier bar at `median + k*1.4826*MAD` over the
frames it is handed.  That is correct over a contact sheet of SAMPLED frames of
a moving scene -- the founding `galleon-deck-cycle.png` and
`galleon-town-cycle.png` -- where neighbouring tiles are unrelated and the MAD
is a real spread.  Over consecutive frames of a parked camera it is not, and
the failure is not subtle.  Measured on the 30 consecutive frames of frame dump
`1789811606-diagdump77-4099630`:

      HF energy   median 1.20  mad 0.02  bar 1.28  (k=3.0)
      STIPPLE    4 / 30  =  13.3 per 100   [16, 17, 18, 19]

13.3 per 100 is inside the founding 10-14 per 100 baseline and it is a SWORD.
The per-frame column climbs smoothly 1.13 -> 1.34 over frames 0..17 and falls
back: a +12% animation ramp, with `d1/d2` never leaving 0.97-1.07.  Consecutive
frames are nearly equal to their neighbours, so the MAD collapses to 0.02 and
the k=3 bar lands 7% above the median; anything with a trend clears it.  A
soak-derived rate measured that way is uninterpretable AND it lands in the same
bracket as the real thing, which is the dangerous combination.

SO THE BAR HERE IS ABSOLUTE AND ANCHORED ON THE ARTIFACT, not on the data:

    base(f)  = median HF over the +-W frames around f, EXCLUDING f.
               A local median removes a smooth trend, which is what
               manufactured the 13.3 above.  It does not remove a one-frame
               step, which is what the artifact is.
    STIPPLE  iff  hf(f) >= RATIO * base(f).

RATIO defaults to 1.45, the bottom of the founding excursion bracket: the four
hatched deck frames run 6.80..8.96 against a median of 4.65, i.e. 1.46x..1.93x.
Rounded down once, and not tuned since.  Moving it to fit a dump is the curve
fit this file exists to avoid.

DIRECTION IS REPORTED, NOT GATED.  A hatch lying along one diagonal moves
`d1/d2`, and the founding set reverses it (0.50-0.92 on hatched frames against
1.56-1.90 on frames 14/21/31).  Those are absolute ratios over a whole set and
there is no honest conversion of them into a local-window threshold, so
`d1/d2` and its deviation from the local window are printed for every flagged
frame and take no part in the decision.

A NULL RESULT IS ONLY ABOUT THE REGION GIVEN.  That warning is inherited whole
from `galleon_flash_rate.py` and is not weakened here: over a full frame the
artifact is a few per cent of the pixels.
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "testing"))
from galleon_flash_rate import anisotropy, hf_energy, load_frames  # noqa: E402

DEFAULT_WINDOW = 10
DEFAULT_RATIO = 1.45


def local_baseline(v, i, window):
    """Median of v over +-window around i, EXCLUDING i itself.

    A baseline should not contain the sample it is the baseline for; that is
    the reason, and it is the only one claimed.  MEASURED SCOPE, so nobody
    reads more into it: with a +-10 window and an artifact lasting one or two
    frames, excluding self moves the reported ratio slightly and moves the
    CLASSIFICATION not at all -- the median of 21 values does not care about
    one of them.  It changes the verdict only when the excursion is about as
    long as the window itself (L >= W+1), where the included-self median lands
    inside the excursion and the frame is tested against a baseline it wrote.
    The selftest pins that boundary case rather than pretending the choice is
    load-bearing at the sizes this lane actually uses.
    """
    lo = max(0, i - window)
    hi = min(len(v), i + window + 1)
    neigh = np.concatenate([v[lo:i], v[i + 1:hi]])
    if len(neigh) == 0:
        return float("nan")
    return float(np.median(neigh))


def classify_hf(hf, aniso=None, means=None, window=DEFAULT_WINDOW,
                ratio=DEFAULT_RATIO):
    """The decision, over measured quantities rather than over pixels.

    Split out from classify() so a fixture of HF numbers recorded from a real
    run can be replayed without its PPMs -- which is how the selftest pins the
    bar failure this file was written for, on the actual measurements rather
    than on a synthetic imitation of them.
    """
    hf = np.asarray(hf, dtype=float)
    if aniso is None:
        aniso = [(float("nan"), float("nan"))] * len(hf)
    d_ratio = np.array([a / b if b else float("nan") for a, b in aniso])

    rows = []
    for i in range(len(hf)):
        base = local_baseline(hf, i, window)
        d_base = local_baseline(d_ratio, i, window)
        r = float(hf[i] / base) if base else float("nan")
        rows.append(dict(
            frame=i,
            hf=float(hf[i]),
            base=base,
            ratio=r,
            d1=float(aniso[i][0]), d2=float(aniso[i][1]),
            d_ratio=float(d_ratio[i]),
            d_base=d_base,
            d_dev=float(d_ratio[i] / d_base) if d_base else float("nan"),
            mean=float(means[i]) if means is not None else float("nan"),
            stipple=bool(r >= ratio) if r == r else False,
        ))
    return rows


def classify(frames, window=DEFAULT_WINDOW, ratio=DEFAULT_RATIO):
    return classify_hf([hf_energy(f) for f in frames],
                       [anisotropy(f) for f in frames],
                       [f.mean() for f in frames], window, ratio)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--mosaic", metavar="COLSxROWS")
    ap.add_argument("--region", metavar="X0,Y0,X1,Y1")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--ratio", type=float, default=DEFAULT_RATIO)
    ap.add_argument("--json", metavar="OUT")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    mosaic = None
    if args.mosaic:
        c, _, r = args.mosaic.partition("x")
        mosaic = (int(c), int(r))
    region = tuple(int(x) for x in args.region.split(",")) if args.region \
        else None
    if region and len(region) != 4:
        sys.exit("--region takes X0,Y0,X1,Y1")

    frames = load_frames(args.paths, mosaic, region)
    if len(frames) < 2 * args.window + 2:
        # Not fatal -- the baseline just gets shorter -- but a reader must not
        # discover it from a suspiciously round rate.
        print("WARNING: %d frames against a +-%d window: every frame's "
              "baseline is truncated, so the ratios below are noisier than "
              "the threshold assumes." % (len(frames), args.window))

    rows = classify(frames, args.window, args.ratio)
    flagged = [r for r in rows if r["stipple"]]

    if not args.quiet:
        print("%d frames, region %s, %dx%d px each" %
              (len(frames), region or "whole frame",
               frames[0].shape[1], frames[0].shape[0]))
        print("  local baseline: median HF over +-%d frames excluding self"
              % args.window)
        print("  STIPPLE iff hf >= %.2f * baseline" % args.ratio)
        print()
        print("  STIPPLE  %3d / %d  = %5.1f per 100   %s"
              % (len(flagged), len(rows),
                 100.0 * len(flagged) / len(rows),
                 [r["frame"] for r in flagged]))
        if flagged:
            print()
            print("  flagged frames (direction is REPORTED, not gated):")
            for r in flagged:
                side = "main diagonal" if r["d1"] > r["d2"] else "anti-diagonal"
                print("    frame %3d  HF %6.2f  base %6.2f  ratio %5.2f  "
                      "d1/d2 %5.2f (local %5.2f, dev %5.2f)  %s"
                      % (r["frame"], r["hf"], r["base"], r["ratio"],
                         r["d_ratio"], r["d_base"], r["d_dev"], side))
            dirs = {"main" if r["d1"] > r["d2"] else "anti" for r in flagged}
            if len(dirs) > 1:
                print("    BOTH DIRECTIONS PRESENT")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(dict(region=list(region) if region else None,
                           window=args.window, ratio=args.ratio,
                           n=len(rows), rows=rows), fh, indent=1)
        if not args.quiet:
            print("\nwrote %s" % args.json)

    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
