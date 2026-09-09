#!/usr/bin/env python3
"""Fail a test when it renders a colour the hardware never produces.

Many pgraph tests draw from a tiny fixed palette. The bump-map suite draws a
red/grey checkerboard: hardware emits **four** distinct colours across the whole
frame, two of them the background and the on-screen label. Any other colour is
something we invented -- a blend that silicon does not produce -- and it is a
failure regardless of how few pixels carry it.

Pixel-difference scoring cannot express that. It treats "wrong by one level" and
"a colour that cannot exist" as the same kind of error, differing only in
magnitude, so a change that trades a thousand invented colours for a slightly
larger pixel count reads as a regression. That is exactly backwards, and it cost
real time here before anyone looked at the images.

So: derive the palette from the golden, and hold our render to it.

    palette_gate.py --goldens goldens/results --results res_dir Bump_map
    palette_gate.py --goldens goldens/results --results res_dir --all

A suite qualifies when its goldens are genuinely low-palette (default: at most
64 distinct colours). Continuous-tone suites are skipped -- the check is
meaningless there and reporting it would be noise.
"""
import argparse
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("needs numpy and pillow: pip install numpy pillow")

# A golden with more distinct colours than this is continuous-tone; the gate
# does not apply.
MAX_PALETTE = 64


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def palette_of(img):
    return np.unique(img.reshape(-1, 3), axis=0)


def check(gold, ours):
    """Return (off_palette_px, total, distinct_ours, mean_distance)."""
    pal = palette_of(gold)
    flat = ours.reshape(-1, 3).astype(np.int32)
    # Chebyshev distance to the nearest colour hardware actually produced.
    dist = np.min(np.abs(flat[:, None, :] - pal[None, :, :]).max(axis=2), axis=1)
    return (int((dist > 0).sum()), flat.shape[0],
            len(palette_of(ours)), float(dist.mean()))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suites", nargs="*")
    ap.add_argument("--goldens", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--all", action="store_true", help="every suite present")
    ap.add_argument("--max-palette", type=int, default=MAX_PALETTE)
    args = ap.parse_args()

    names = sorted(n[:-4] for n in os.listdir(args.results)
                   if n.endswith(".png") and "::" in n)
    if not args.all:
        if not args.suites:
            sys.exit("name a suite, or pass --all")
        names = [n for n in names if n.split("::", 1)[0] in args.suites]
    if not names:
        sys.exit("nothing to check")

    rows, skipped = [], 0
    for name in names:
        suite, test = name.split("::", 1)
        gp = os.path.join(args.goldens, suite, f"{test}.png")
        op = os.path.join(args.results, f"{name}.png")
        if not os.path.exists(gp):
            continue
        gold, ours = load(gp), load(op)
        if gold.shape != ours.shape:
            continue
        pal = palette_of(gold)
        if len(pal) > args.max_palette:
            skipped += 1
            continue
        off, total, distinct, mean = check(gold, ours)
        rows.append((suite, test, len(pal), distinct, off, total, mean))

    if not rows:
        print(f"no low-palette tests found ({skipped} continuous-tone, skipped)")
        return 0

    w = max(len(r[1]) for r in rows) + 1
    print(f"{'test':<{w}} {'hw':>4} {'ours':>7} {'off-palette':>13} {'mean dist':>10}  verdict")
    print("-" * (w + 50))
    failed = 0
    for suite, test, npal, distinct, off, total, mean in rows:
        ok = off == 0
        failed += not ok
        pct = off / total * 100
        print(f"{test:<{w}} {npal:>4} {distinct:>7,} {off:>9,} {pct:>5.1f}% "
              f"{mean:>10.2f}  {'PASS' if ok else 'FAIL'}")

    print(f"\n  {len(rows) - failed}/{len(rows)} render only colours the hardware produces")
    if skipped:
        print(f"  {skipped} continuous-tone test(s) skipped — gate does not apply")
    if failed:
        print("\n  A failing test is drawing colours silicon never emits. That is a\n"
              "  structural fault, not a precision one, and no pixel count makes it\n"
              "  acceptable.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
