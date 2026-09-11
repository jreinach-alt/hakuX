#!/usr/bin/env python3
"""Compare where a capture's edges land against the golden's, row by row.

A pixel count says how much a capture disagrees with hardware. It does not say
whether the shape is right and displaced, or wrong. This asks the narrower
question: down one column, at which rows does the image change between light
and dark, and how does that list differ from the golden's?

The useful outcomes are:

  every edge shifted by the same amount   the whole image is offset
  one edge shifted, the rest exact        one boundary is computed wrong,
                                          and the geometry around it is right
  edge counts differ                      a feature is missing or extra

The middle case is the one worth chasing: it isolates a single computed
threshold from everything the rasteriser did correctly around it. It found
the shadow suite's remaining defect, where one comparison boundary lands a
single scanline late in 100 of 112 failing tests while every label and quad
edge on the same column is exact.

Usage:
    edge_shift.py --captures DIR --goldens DIR [--suite NAME] [--limit N]
"""
import argparse
import collections
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("needs numpy and Pillow")


def edges(gray, col, threshold=127):
    """Rows where column COL crosses between dark and light."""
    lit = gray[:, col] > threshold
    return [r for r in range(1, len(lit)) if lit[r] != lit[r - 1]]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--captures", required=True)
    p.add_argument("--goldens", required=True,
                   help="directory of golden PNGs for one suite")
    p.add_argument("--suite", help="only captures named <suite>::<test>.png")
    p.add_argument("--limit", type=int, default=8,
                   help="how many worked examples to print")
    args = p.parse_args()

    files = sorted(f for f in os.listdir(args.captures) if f.endswith(".png"))
    if args.suite:
        files = [f for f in files if f.startswith(args.suite + "::")]
    if not files:
        sys.exit(f"no captures in {args.captures}")

    shifts = collections.Counter()
    examples = []
    compared = skipped = clean = 0

    for f in files:
        test = f.split("::")[-1][:-4]
        gold_path = os.path.join(args.goldens, test + ".png")
        if not os.path.exists(gold_path):
            skipped += 1
            continue
        a = np.asarray(Image.open(os.path.join(args.captures, f)).convert("L"),
                       dtype=int)
        b = np.asarray(Image.open(gold_path).convert("L"), dtype=int)
        if a.shape != b.shape:
            skipped += 1
            continue
        compared += 1
        d = np.abs(a - b) > 0
        if not d.any():
            clean += 1
            continue
        col = int(np.bincount(np.nonzero(d)[1]).argmax())
        ea, eb = edges(a, col), edges(b, col)
        if len(ea) == len(eb) and ea:
            key = tuple(sorted({x - y for x, y in zip(ea, eb)}))
        else:
            key = (f"edge count {len(ea)} vs {len(eb)}",)
        shifts[key] += 1
        if len(examples) < args.limit:
            examples.append((test, col, eb, ea))

    print(f"compared {compared}, of which {clean} exact; {skipped} skipped")
    print("\nrow shift of the capture's edges against the golden's, "
          "down the busiest column:")
    for key, n in shifts.most_common():
        print(f"  {str(key):36s} {n:>4} tests")

    if examples:
        print("\nexamples:")
        for test, col, eb, ea in examples:
            print(f"  {test}  (column {col})")
            print(f"    hw   {eb}")
            print(f"    ours {ea}")


if __name__ == "__main__":
    main()
