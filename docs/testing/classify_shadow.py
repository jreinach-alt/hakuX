#!/usr/bin/env python3
"""Decompose Texture_shadow_comparator failures by what the comparator got wrong.

The suite runs each depth-texture configuration under all eight comparison
functions.  That redundancy is the whole point: the eight results over-determine
the one thing the shader actually computes, so a per-op score can be turned back
into a statement about the depth value.

For one texel let h be the hardware's relation between the stored depth and the
reference and o be ours, each one of '<', '=', '>'.  Then

    EQ is wrong  <=>  (h == '=') != (o == '=')
    GE is wrong  <=>  (h != '<') != (o != '<')
    GT is wrong  <=>  (h == '>') != (o == '>')

and NE, LT, LE are the exact complements of EQ, GE, GT, so they carry no extra
information.  ALWAYS and NEVER never read the depth at all.  Intersecting the
three masks names the disagreement:

    in EQ and GT, not GE   the two values are equal on hardware and ordered
                           one way for us (or the reverse) -- a *tie*
    in EQ and GE, not GT   a tie, broken the other way
    in GE and GT, not EQ   neither side calls it a tie and we land on the
                           wrong side -- a real magnitude error

A result dominated by the first two classes is a tie-breaking problem: the
comparison functions are right and the depth value is a hair off.  Only the
third class means the depth is actually wrong.

Usage:
    classify_shadow.py --captures DIR [--goldens DIR] [--tsv OUT]
"""
import argparse
import collections
import os
import re
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("needs numpy and Pillow")

SUITE = "Texture_shadow_comparator"
FAMILY_RE = re.compile(r"^([23][A-Z]\d+f?)")


def load_mask(captures, goldens, test):
    cap = os.path.join(captures, f"{SUITE}::{test}.png")
    gold = os.path.join(goldens, f"{test}.png")
    if not (os.path.exists(cap) and os.path.exists(gold)):
        return None
    a = np.asarray(Image.open(cap).convert("RGB"), dtype=int)
    b = np.asarray(Image.open(gold).convert("RGB"), dtype=int)
    if a.shape != b.shape:
        return None
    return np.abs(a - b).max(axis=2) > 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--captures", required=True)
    p.add_argument("--goldens",
                   default=os.path.expanduser(f"~/goldens/results/{SUITE}"))
    p.add_argument("--tsv")
    args = p.parse_args()

    bases = sorted({
        re.sub(r"_[A-Z]+$", "", f[len(SUITE) + 2:-4])
        for f in os.listdir(args.captures)
        if f.startswith(SUITE + "::") and f.endswith(".png")
    })
    if not bases:
        sys.exit(f"no {SUITE} captures in {args.captures}")

    fam = collections.defaultdict(lambda: [0, 0, 0, 0])
    rows = []
    for base in bases:
        masks = {op: load_mask(args.captures, args.goldens, f"{base}_{op}")
                 for op in ("EQ", "GE", "GT")}
        if any(m is None for m in masks.values()):
            print(f"  skipping {base}: missing captures or goldens")
            continue
        eq, ge, gt = masks["EQ"], masks["GE"], masks["GT"]
        hi = int((eq & gt & ~ge).sum())
        lo = int((eq & ge & ~gt).sum())
        cross = int((ge & gt & ~eq).sum())
        rest = int((eq | ge | gt).sum()) - hi - lo - cross
        m = FAMILY_RE.match(base)
        key = m.group(1) if m else "?"
        f = fam[key]
        f[0] += hi
        f[1] += lo
        f[2] += cross
        f[3] += 1
        rows.append((base, hi, lo, cross, rest))

    print(f"{'family':8s} {'n':>3} {'tie->high':>10} {'tie->low':>9} "
          f"{'crossing':>9}")
    total = [0, 0, 0]
    for key in sorted(fam):
        hi, lo, cross, n = fam[key]
        total[0] += hi
        total[1] += lo
        total[2] += cross
        print(f"{key:8s} {n:>3} {hi:>10} {lo:>9} {cross:>9}")
    print(f"{'TOTAL':8s} {'':>3} {total[0]:>10} {total[1]:>9} {total[2]:>9}")
    grand = sum(total)
    if grand:
        ties = total[0] + total[1]
        print(f"\nties {ties} px ({100.0 * ties / grand:.1f}%), "
              f"true crossings {total[2]} px "
              f"({100.0 * total[2] / grand:.1f}%)")
        if ties > total[2]:
            print("The comparison functions agree with hardware. The depth "
                  "value reaching them does not.")

    if args.tsv:
        with open(args.tsv, "w") as fh:
            fh.write("test\ttie_high\ttie_low\tcrossing\tunclassified\n")
            for row in rows:
                fh.write("\t".join(str(c) for c in row) + "\n")
        print(f"\nwrote {args.tsv}")


if __name__ == "__main__":
    main()
