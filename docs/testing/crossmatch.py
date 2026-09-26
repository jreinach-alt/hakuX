#!/usr/bin/env python3
"""Find tests that render *another test's* image.

A plain golden diff reports "this test does not match its reference" and stops
there. It cannot distinguish two very different faults:

  * the renderer drew the right thing slightly wrong (precision, rounding), and
  * the renderer drew the *wrong thing entirely* — the previous test's texture,
    a stale surface, a cache entry that should have been invalidated.

The second is far more serious and needs a completely different fix, but both
present as "N pixels differ". This tool separates them by asking, for every
failing test, whether some *other* golden in the same suite matches our output
better than its own golden does.

That question found issue #6: three `Texture DXT` tests reproduce their
`_alpha` sibling's image at mean |delta| 0.5, while their own golden sits 15.8
away. It is a texture-cache staleness bug, not the DXT decode bug it was
filed as.

Usage:
    crossmatch.py <results-dir> --goldens <goldens/results> [--suite NAME]

`results-dir` holds files named `Suite_name::Test_name.png`, as written by
extract_results.py. Goldens are `<goldens>/Suite_name/Test_name.png`.

Comparison is two-stage: a downsampled fingerprint ranks candidates cheaply,
then the best candidate is re-scored at full resolution. Only tests that
already fail against their own golden are cross-matched, so a clean run costs
almost nothing.
"""
import argparse
import collections
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("crossmatch.py needs numpy and pillow: pip install numpy pillow")

# A test is only worth cross-matching if it already fails this badly. Mean
# absolute per-subpixel error; DXT1 rounding noise sits near 0.5, the wrong
# texture sits near 15.
FAIL_THRESHOLD = 2.0

# How much better another golden must fit before we call it a substitution.
# The wrong-texture cases beat their own golden by ~20x; near-duplicate
# goldens within a suite differ by only a little, so keep this well clear.
SUBST_RATIO = 3.0

FINGERPRINT = (30, 40)  # rows, cols


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)


def fingerprint(img):
    h, w = FINGERPRINT
    ih, iw = img.shape[:2]
    # Mean-pool to a fixed grid; robust to the small offsets that make a
    # pixel-wise compare useless for ranking.
    ys = (np.arange(ih) * h // ih)
    xs = (np.arange(iw) * w // iw)
    out = np.zeros((h, w, 3), dtype=np.float32)
    cnt = np.zeros((h, w, 1), dtype=np.float32)
    np.add.at(out, (ys[:, None], xs[None, :]), img)
    np.add.at(cnt, (ys[:, None], xs[None, :]), 1.0)
    return (out / np.maximum(cnt, 1)).ravel()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", help="directory of Suite::Test.png files")
    ap.add_argument("--goldens", required=True, help="goldens/results directory")
    ap.add_argument("--suite", help="restrict to one suite")
    ap.add_argument("--threshold", type=float, default=FAIL_THRESHOLD,
                    help=f"only cross-match tests failing worse than this (default {FAIL_THRESHOLD})")
    args = ap.parse_args()

    by_suite = collections.defaultdict(list)
    for name in sorted(os.listdir(args.results)):
        if not name.endswith(".png") or "::" not in name:
            continue
        suite, test = name[:-4].split("::", 1)
        if args.suite and suite != args.suite:
            continue
        by_suite[suite].append(test)

    if not by_suite:
        sys.exit(f"no Suite::Test.png files found in {args.results}")

    substitutions, checked, failing = [], 0, 0

    for suite, tests in sorted(by_suite.items()):
        gdir = os.path.join(args.goldens, suite)
        if not os.path.isdir(gdir):
            continue

        golds, gfp = {}, {}
        for gname in os.listdir(gdir):
            if gname.endswith(".png"):
                g = load(os.path.join(gdir, gname))
                golds[gname[:-4]] = g
                gfp[gname[:-4]] = fingerprint(g)

        for test in tests:
            if test not in golds:
                continue
            ours = load(os.path.join(args.results, f"{suite}::{test}.png"))
            own = golds[test]
            checked += 1
            if ours.shape != own.shape:
                continue
            own_err = float(np.abs(ours - own).mean())
            if own_err <= args.threshold:
                continue
            failing += 1

            fp = fingerprint(ours)
            best, best_fp = None, None
            for cand, cfp in gfp.items():
                if cand == test or golds[cand].shape != ours.shape:
                    continue
                d = float(np.abs(fp - cfp).mean())
                if best_fp is None or d < best_fp:
                    best, best_fp = cand, d
            if best is None:
                continue

            cand_err = float(np.abs(ours - golds[best]).mean())
            if cand_err * SUBST_RATIO < own_err:
                substitutions.append((suite, test, best, own_err, cand_err))

    print(f"checked {checked} tests, {failing} failing worse than "
          f"{args.threshold}, {len(substitutions)} rendering another test's image\n")
    if substitutions:
        print(f"{'suite':<28} {'test':<30} {'actually renders':<30} {'own':>7} {'other':>7}")
        print("-" * 106)
        for suite, test, best, oe, ce in sorted(substitutions,
                                                key=lambda r: -(r[3] / max(r[4], 1e-6))):
            print(f"{suite:<28} {test:<30} {best:<30} {oe:>7.2f} {ce:>7.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
