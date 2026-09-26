#!/usr/bin/env python3
"""Score the three Blend_tests swatch stacks as separate regions.

A Blend_tests frame is not one picture. `blend_tests.cpp` draws three
independent swatch stacks, each into its own render-to-texture and then
composited, and they fail for different reasons -- so scoring the whole
capture averages a bit-exact region together with a broken one and reports
something true of neither.

    stack A   DrawColorStack           cols 16-79     green, red, blue, white
    stack B   DrawAlphaStack           (not scored here)
    stack C   DrawColorAndAlphaStack   cols 560-623   white, blue, red, green

Note the two orders are OPPOSITE. A band index is not portable between them,
which is the trap this file exists to make hard to fall into.

Geometry is derived, not guessed. From blend_tests.cpp @283e2971 (the revision
behind the 2025-03-14 oracle release): the stack is kColorSwatchSize = 64 wide
and 4*64 = 256 tall, stack A composited at x = 16 and stack C at
x = framebufferWidth - (16 + 64) = 560, both at
y = (framebufferHeight - 256) / 2 = 112.

Everything here compares REGIONS. Point samples through structured content
manufacture whatever agreement you look for -- that error has been made twice
on this suite.
"""
import argparse, collections, glob, os, statistics, sys

from PIL import Image

Y0, Y1, SWATCH = 112, 368, 64
STACKS = {"A": (16, 80), "C": (560, 624)}
EQUATIONS = ("ADD", "MAX", "MIN", "REVSUB", "SUB", "SADD", "SREVSUB")


def region(im, x0, x1):
    return list(im.crop((x0, Y0, x1, Y1)).convert("RGB").getdata())


def bands(im, x0, x1):
    return [list(im.crop((x0, Y0 + i * SWATCH, x1, Y0 + (i + 1) * SWATCH))
                 .convert("RGB").getdata()) for i in range(4)]


def band_means(im, x0, x1):
    out = []
    for b in bands(im, x0, x1):
        n = len(b)
        out.append(tuple(sum(p[k] for p in b) / n for k in range(3)))
    return out


def l1(a, b):
    return sum(abs(x - y) for p, q in zip(a, b) for x, y in zip(p, q))


def equation_of(test):
    parts = test[:-4].split("_") if test.endswith(".png") else test.split("_")
    return parts[1] if len(parts) > 2 else "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", required=True)
    ap.add_argument("--goldens", default="/home/justin/goldens/results/Blend_tests")
    args = ap.parse_args()

    per_eq = {s: collections.Counter() for s in STACKS}
    totals = collections.Counter()
    flip_in, flip_rev = [], []
    flip_verdict = collections.Counter()
    band_exact = collections.Counter()
    pairs = 0

    for path in sorted(glob.glob(os.path.join(args.captures, "*.png"))):
        test = os.path.basename(path).split("::", 1)[-1]
        gold = os.path.join(args.goldens, test)
        if not os.path.exists(gold):
            continue
        try:
            cap, gld = Image.open(path), Image.open(gold)
        except Exception:
            continue
        if cap.size != (640, 480) or gld.size != (640, 480):
            continue
        pairs += 1
        eq = equation_of(test)
        totals[eq] += 1
        for name, (x0, x1) in STACKS.items():
            if region(cap, x0, x1) != region(gld, x0, x1):
                per_eq[name][eq] += 1

        # Is stack C a vertical reversal of the golden? Tested two ways: as a
        # bit-exact band permutation, and as an ordering tendency on band means
        # (values legitimately differ, so bit-exactness is the strong form).
        x0, x1 = STACKS["C"]
        ob, gb = bands(cap, x0, x1), bands(gld, x0, x1)
        if ob == gb:
            band_exact["exact"] += 1
        elif ob == gb[::-1]:
            band_exact["exact under reversal"] += 1
        else:
            band_exact["no band matches any golden band"] += 1
        om, gm = band_means(cap, x0, x1), band_means(gld, x0, x1)
        d_in, d_rev = l1(om, gm), l1(om, gm[::-1])
        flip_in.append(d_in)
        flip_rev.append(d_rev)
        flip_verdict["reversed fits better" if d_rev < d_in else
                     "in-order fits better" if d_in < d_rev else "tie"] += 1

    if not pairs:
        print("no capture/golden pairs found", file=sys.stderr)
        return 1

    print(f"capture/golden pairs: {pairs}\n")
    print("differing region, by equation")
    print(f"  {'equation':9} {'stack A':>12} {'stack C':>12}")
    for eq in EQUATIONS:
        if not totals[eq]:
            continue
        print(f"  {eq:9} {per_eq['A'][eq]:6}/{totals[eq]:<5} "
              f"{per_eq['C'][eq]:6}/{totals[eq]:<5}")
    print(f"  {'TOTAL':9} {sum(per_eq['A'].values()):6}/{pairs:<5} "
          f"{sum(per_eq['C'].values()):6}/{pairs:<5}")

    print("\nstack C as a reversal -- strong form (bit-exact bands)")
    for k, v in band_exact.most_common():
        print(f"  {v:6}  {k}")
    print("\nstack C as a reversal -- weak form (band-mean ordering)")
    for k, v in flip_verdict.most_common():
        print(f"  {v:6}  {k}")
    print(f"  median L1 to golden in order : {statistics.median(flip_in):8.1f}")
    print(f"  median L1 to golden reversed : {statistics.median(flip_rev):8.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
