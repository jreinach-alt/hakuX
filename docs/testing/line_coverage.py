#!/usr/bin/env python3
"""Lit pixels per capture against the width the test asked for.

A golden diff says "these pixels are wrong", which for a suite that sweeps one
parameter is the least useful true statement available. Total coverage against
the requested value says whether the parameter is arriving at all -- and for
`Line width` the answer was a column of constants: ~6,470 lit pixels for every
width from 0.0 to 64.875 while the golden's grew thirtyfold, which is the whole
finding in one table.

Written for `Line width` but the shape is general: any suite whose test names
carry the parameter they sweep can be read this way.

    line_coverage.py --captures <dir> --suite Line_width

`--captures` takes a directory of `<Suite>::<test>.png`. Test names are parsed
as `<prefix>_<integer>.<eighths>`, which is how the line width suite spells the
nine-bit eighths-of-a-pixel register.

See docs/investigations/line-width-never-reaches-the-rasteriser.md.
"""
import argparse
import os
import re
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("line_coverage.py needs numpy and pillow")

# Above the black background and below anything drawn. The suite draws on black
# and the goldens have no dither, so this is not delicate.
LIT = 40


def lit_pixels(path):
    a = np.asarray(Image.open(path).convert("RGB"))
    return int((a.max(axis=2) > LIT).sum())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", required=True,
                    help="directory of <Suite>::<test>.png")
    ap.add_argument("--suite", default="Line_width")
    ap.add_argument("--goldens", default=os.path.expanduser("~/goldens/results"))
    ap.add_argument("--prefix", default="Line",
                    help="test-name prefix whose parameter to parse")
    args = ap.parse_args()

    gdir = os.path.join(args.goldens, args.suite)
    pat = re.compile(rf"{re.escape(args.prefix)}_(\d+)\.(\d)$")

    rows = []
    for f in sorted(os.listdir(gdir)):
        if not f.endswith(".png"):
            continue
        test = f[:-4]
        m = pat.match(test)
        if not m:
            continue
        ours = os.path.join(args.captures, f"{args.suite}::{test}.png")
        if not os.path.exists(ours):
            continue
        width = int(m.group(1)) + int(m.group(2)) / 8.0
        rows.append((width, test, lit_pixels(os.path.join(gdir, f)),
                     lit_pixels(ours)))

    if not rows:
        sys.exit(f"no {args.prefix}_* captures matched in {args.captures}")

    print(f"{'width':>9} {'test':<16}{'golden':>9}{'ours':>9}{'ours/golden':>13}")
    for w, t, g, o in rows:
        print(f"{w:>9.3f} {t:<16}{g:>9}{o:>9}{(o / g if g else 0):>13.2f}")

    ours = [o for _w, _t, _g, o in rows]
    spread = (max(ours) - min(ours)) / (sum(ours) / len(ours))
    print(f"\nours: {min(ours)}..{max(ours)} over {len(ours)} captures"
          f" ({spread * 100:.1f}% spread)")
    if spread < 0.05:
        print("  ^ constant to within 5%: the swept parameter is not arriving")
    return 0


if __name__ == "__main__":
    sys.exit(main())
