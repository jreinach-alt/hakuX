#!/usr/bin/env python3
"""Compare two runsuites.sh prefixes capture for capture: byte-identical
pixels, or how many pixels differ between them, plus each side's price
against the golden (pxprice.py's metric).

    onoff.py <prefix A> <prefix B>     e.g. g3off g3on

Reads build-linux/ring53runs/<prefix>-<suite>/out. A capture present on one
side only is listed as MISSING. Writes nothing.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pxprice import GOLD, RUNS, price  # noqa: E402


def caps(prefix):
    out = {}
    for d in sorted(os.listdir(RUNS)):
        o = os.path.join(RUNS, d, "out")
        if not d.startswith(prefix + "-") or not os.path.isdir(o):
            continue
        for f in os.listdir(o):
            if "::" in f and f.endswith(".png"):
                out[f[:-4].replace("::", "/", 1)] = os.path.join(o, f)
    return out


def main():
    a, b = caps(sys.argv[1]), caps(sys.argv[2])
    same = moved = 0
    for k in sorted(set(a) | set(b)):
        if k not in a or k not in b:
            print("%-52s MISSING on %s" % (k, sys.argv[1] if k not in a else sys.argv[2]))
            continue
        pa = np.asarray(Image.open(a[k]).convert("RGBA")).astype(int)
        pb = np.asarray(Image.open(b[k]).convert("RGBA")).astype(int)
        n = int((np.abs(pa - pb).max(axis=2) > 0).sum()) if pa.shape == pb.shape else -1
        if n == 0:
            same += 1
            continue
        moved += 1
        gold = os.path.join(GOLD, k + ".png")
        ga = gb = None
        if os.path.exists(gold):
            ga, gb = price(a[k], gold), price(b[k], gold)
        print("%-52s %7d px moved   golden %s -> %s" % (k, n, ga, gb))
    print("identical %d, moved %d" % (same, moved))


if __name__ == "__main__":
    sys.exit(main())
