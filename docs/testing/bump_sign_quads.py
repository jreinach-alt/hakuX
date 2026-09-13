#!/usr/bin/env python3
"""Per-quad differing pixels for the four TEXFILTER sign-flag quads of a
`Bump map` or `Bump env lum` capture.

    bump_sign_quads.py RESULTDIR [RESULTDIR ...] [--suite Bump_env_lum]
                       [--tests BumpEnvLum_A8,BumpEnvLum_Y16]

Why a per-quad number and not a total.  Both suites draw the SAME picture four
times and change nothing but the TEXFILTER sign flags:
`bump_env_lum_tests.cpp` sweeps `gsigned` x `bsigned` and ties
`rsigned = bsigned`, laying the quads out at (146 + 180*bsigned,
66 + 180*gsigned), 168 px square.  So the capture carries its own control: a
quad whose flags are clear is the unflagged answer, measured, in the same frame
as the flagged ones.

That is what localises #10's luminance defect without transferring a floor
between captures.  Measured at `0026f00534`, quads in (gsigned, bsigned) order:

    BumpEnvLum_A8     310 / 14,241 /   422 / 14,187
    BumpEnvLum_Y16    310 / 13,755 /   422 / 13,645
    BumpEnvLum_Y8   7,139 /  7,441 / 7,301 /  7,501
    BumpMap_A8        310 /    422 /   422 /    422

The first two have their damage in exactly the two quads carrying BSIGNED --
and therefore RSIGNED, which reaches the luminance -- while quad 2, which
carries GSIGNED on a real data channel, sits at the same 422 as the unflagged
quads.  `BumpMap_A8` has no luminance stage and is at the floor throughout.
`BumpEnvLum_Y8` is the contrast: component 0 is real data there, and all four
quads are wrong together, so it is a different defect and not this one.

The tool also prints the GOLDEN's own quad-vs-quad0 counts, which is the
control that says whether the instrument can see a live flag at all: hardware
gives 0/586/312/612 on every A8, Y16 and R16B16 capture in both suites -- its
positional floor -- against 0/586/8,212/8,431 on `BumpMap_G8B8` and
0/13,796/312/13,814 on `BumpEnvLum_R8B8`, which are byte texels.

Writes nothing.
"""

import argparse
import glob
import os
import sys

QUAD_W = 168
# (146 + 180*bsigned, 66 + 180*gsigned), from bump_env_lum_tests.cpp:
#   bh = h*3/8 = 180, th = bh*120/128 = 168, sh = 6, sx = w/2-bh+sh = 146
ORIGINS = [(146 + 180 * b, 66 + 180 * g) for g in (0, 1) for b in (0, 1)]
LABELS = ["Gu Bu", "Gu Bs", "Gs Bu", "Gs Bs"]


def quads(np, a):
    return [a[y:y + QUAD_W, x:x + QUAD_W] for (x, y) in ORIGINS]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+", help="dispatcher result directories")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--suite", default=None,
                    help="Bump_map or Bump_env_lum (default: whatever is there)")
    ap.add_argument("--tests", default=None, help="comma-separated test names")
    args = ap.parse_args(argv)

    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        print("needs numpy and pillow: %s" % e, file=sys.stderr)
        return 2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # captures.py owns the two directory shapes the dispatcher produces, and it
    # is imported without a fallback on purpose: a hand-rolled walk beside it is
    # how a wrong call goes unnoticed, which is what happened to the first
    # version of this file.
    import captures as capmod

    def load(p):
        return np.asarray(Image.open(p).convert("RGBA")).astype(np.int64)

    want = set(args.tests.split(",")) if args.tests else None
    for rd in args.results:
        print("=" * 78)
        print(rd)
        print("=" * 78)
        # captures.py owns the two directory shapes; do not join paths by hand.
        found = []
        for suite in (args.suite,) if args.suite else ("Bump_map", "Bump_env_lum"):
            root = capmod.resolve(rd, "%s::*.png" % suite)
            found += sorted(glob.glob(os.path.join(root, "%s::*.png" % suite)))
        rows = 0
        for path in sorted(found):
            base = os.path.basename(path)[:-4]
            suite, test = base.split("::", 1)
            if args.suite and suite != args.suite:
                continue
            if not suite.startswith("Bump"):
                continue
            if want and test not in want:
                continue
            gp = os.path.join(args.goldens, suite, test + ".png")
            if not os.path.exists(gp):
                print("  %-26s no golden" % test)
                continue
            gold, ours = load(gp), load(path)
            gq, oq = quads(np, gold), quads(np, ours)
            per, one = [], []
            for i in range(4):
                d = oq[i] - gq[i]
                nz = (d != 0).any(axis=2)
                per.append(int(nz.sum()))
                one.append(int((nz & (np.abs(d).max(axis=2) == 1)).sum()))
            gv = [int((gq[i] != gq[0]).any(axis=2).sum()) for i in range(4)]
            print("  %-26s total %7d" % (test, int((ours != gold).any(axis=2).sum())))
            print("      per quad   %s" % "  ".join("%s=%-7d" % (LABELS[i], per[i])
                                                    for i in range(4)))
            print("      one step   %s" % "  ".join("%s=%-7d" % (LABELS[i], one[i])
                                                    for i in range(4)))
            print("      GOLD q-q0  %s   <- hardware's own flag sensitivity"
                  % "  ".join("%s=%-7d" % (LABELS[i], gv[i]) for i in range(4)))
            rows += 1
        if not rows:
            print("  no Bump captures found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
