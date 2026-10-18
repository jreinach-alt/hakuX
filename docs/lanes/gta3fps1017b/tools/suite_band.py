#!/usr/bin/env python3
"""Desktop suite arms side by side (#1049, R2/R3).

usage: suite_band.py GOLDENS REF ARM [ARM ...]

Each ARM (and REF) is a desk_suites.py output dir (results/, qemu.log).
Per arm: the tests run, golden-exact count, the tests OUTSIDE
Texture_shadow_comparator that differ from REF bit-for-bit over RGBA (that
suite varies run to run on lavapipe; gta3fps1017 NOTES 2.3), each such
test's distance to its golden, how many shadow-comparator tests differ from
REF, and every [s2tdrain]/[s2twiden]/[s2tshare] line in qemu.log -- the
lines that say whether the run reached the switch's branch at all.
"""
import os
import re
import sys

import numpy as np
from PIL import Image

SHADOW = "Texture_shadow_comparator"
LINES = re.compile(r"\[(s2tdrain|s2twiden|s2tshare)\][^\n]*")


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"))


def ndiff(x, y):
    if x.shape != y.shape:
        return -1
    return int(np.any(x != y, axis=2).sum())


def main():
    gold, ref, *arms = [os.path.abspath(a) for a in sys.argv[1:]]
    rres = os.path.join(ref, "results")
    names = sorted(n for n in os.listdir(rres) if n.endswith(".png"))
    print(f"REF {os.path.basename(ref)}: {len(names)} tests")
    for arm in [ref] + arms:
        res = os.path.join(arm, "results")
        have = set(os.listdir(res))
        exact = shadow = 0
        other = []
        for n in names:
            if n not in have:
                other.append((n, "missing", None))
                continue
            suite, test = n.split("::", 1)
            img = load(os.path.join(res, n))
            g = os.path.join(gold, suite, test)
            gd = ndiff(img, load(g)) if os.path.exists(g) else None
            exact += gd == 0
            if arm == ref:
                continue
            d = ndiff(img, load(os.path.join(rres, n)))
            if d == 0:
                continue
            if suite == SHADOW:
                shadow += 1
            else:
                other.append((n, d, gd))
        with open(os.path.join(arm, "qemu.log"), errors="replace") as f:
            lines = sorted(set(m.group(0) for m in LINES.finditer(f.read())))
        env = ""
        with open(os.path.join(arm, "qemu.log"), errors="replace") as f:
            first = f.readline()
            env = " ".join(w for w in first.split()
                           if w.startswith("HAKUX_S2T"))
        print(f"\n{os.path.basename(arm)}: env [{env or 'no S2T switch'}] "
              f"tests {len(have & set(names))} golden-exact {exact}")
        print(f"  log lines: {lines if lines else 'none'}")
        if arm != ref:
            print(f"  vs REF: {SHADOW} differ {shadow}; "
                  f"outside it differ {len(other)}")
            for n, d, gd in other:
                print(f"    {n}: {d} px vs REF, {gd} px vs golden")


if __name__ == "__main__":
    main()
