#!/usr/bin/env python3
"""A closed-form model of what silicon does in Blend tests' #spot_ captures.

Every `#spot_<sfactor>_<EQN>` test renders a 5x3 grid, one cell per destination
factor, into a 512x512 A8R8G8B8 render target whose background is an 8 pixel
checkerboard, then blits that target to screen through an A8B8G8R8 texture
stage.  This walks the whole chain for the leftmost column of each cell (the
`DrawColorStack` swatches, where RGB is blended and alpha is written straight):

    blend -> 8 bit store -> byte reinterpretation -> alpha blit -> 8 bit store

and scores a capture directory against the goldens, sampling four pixels per
swatch.  The point of it is the quantiser: with round-to-nearest at both stores
the model reproduces silicon on every sampled pixel of all 75 captures that are
not FUNC_ADD_SIGNED/FUNC_REVERSE_SUBTRACT_SIGNED, which is what says the blend
factor and equation tables are right and any residual is arithmetic precision.

    blend_model.py --captures <dir>            score a capture dir
    blend_model.py --self-test                 check the model against silicon

`--captures` takes a directory of `Blend_tests::<test>.png`, as produced by
extract_results.py.  Goldens default to /tmp/goldens/results/Blend_tests.
"""
import argparse
import collections
import os
import sys
from fractions import Fraction as F

import numpy as np
from PIL import Image

FACTORS = ["0", "1", "srcRGB", "1-srcRGB", "srcA", "1-srcA", "dstA", "1-dstA",
           "dstRGB", "1-dstRGB", "srcAsat", "cRGB", "1-cRGB", "cA", "1-cA"]
#: The signed equations belong to a separate defect and are excluded.
EQNS = ["ADD", "SUB", "REVSUB", "MIN", "MAX"]

#: kBlendColorConstant, decoded the way NV097_SET_BLEND_COLOR packs it.
CONST = (85, 85, 85, 85)
#: DrawColorStack's four quads, top to bottom.  NV097_SET_DIFFUSE_COLOR4I packs
#: ABGR -- red in the low byte -- so 0xDDDD0000 is blue, not red.  Reading it
#: the other way inverts every conclusion drawn from these captures.
STACK = [(0, 221, 0, 221), (0, 0, 221, 221), (221, 0, 0, 221), (255, 255, 255, 221)]

#: Grid geometry, from blend_tests.cpp: test_width 99 with 4 of spacing,
#: test_height 136, swatches 24 square, render target blitted to +64,+64.
CELL_DX, CELL_DY, SWATCH, BLIT_X, BLIT_Y = 103, 136, 24, 64, 64


def q_round(x):
    return min(255, max(0, int(x * 255 + F(1, 2))))


def q_floor(x):
    return min(255, max(0, int(x * 255)))


QUANT = {"round": q_round, "floor": q_floor}


def factor(name, src, dst, ch):
    """Blend factor for channel ch (0..2 colour, 3 alpha), exact."""
    s, d, c = src, dst, CONST
    return {
        "0":         lambda: F(0),
        "1":         lambda: F(1),
        "srcRGB":    lambda: F(s[ch], 255),
        "1-srcRGB":  lambda: 1 - F(s[ch], 255),
        "srcA":      lambda: F(s[3], 255),
        "1-srcA":    lambda: 1 - F(s[3], 255),
        "dstA":      lambda: F(d[3], 255),
        "1-dstA":    lambda: 1 - F(d[3], 255),
        "dstRGB":    lambda: F(d[ch], 255),
        "1-dstRGB":  lambda: 1 - F(d[ch], 255),
        # Vulkan defines the saturate factor as 1 on the alpha channel.
        "srcAsat":   lambda: F(1) if ch == 3 else F(min(s[3], 255 - d[3]), 255),
        "cRGB":      lambda: F(c[ch], 255),
        "1-cRGB":    lambda: 1 - F(c[ch], 255),
        "cA":        lambda: F(c[3], 255),
        "1-cA":      lambda: 1 - F(c[3], 255),
    }[name]()


def blend(eqn, src, dst, sf, df, ch):
    s, d = F(src[ch], 255), F(dst[ch], 255)
    if eqn == "MIN":
        return min(s, d)
    if eqn == "MAX":
        return max(s, d)
    a = s * factor(sf, src, dst, ch)
    b = d * factor(df, src, dst, ch)
    v = {"ADD": a + b, "SUB": a - b, "REVSUB": b - a}[eqn]
    return min(F(1), max(F(0), v))


def screen_bg(x, y):
    """The screen checkerboard under the blit: a 256x256 texture of
    0xFF202020/0xFF000000 in 16 texel checkers, stretched over 640x480."""
    return 32 if ((x // 40) + (y // 30)) % 2 == 0 else 0


def predict(eqn, sf, df, swatch, rx, ry, qb, qt):
    """Screen RGB for a DrawColorStack pixel at render-target (rx, ry)."""
    dst = (51, 51, 51, 51) if ((rx // 8) + (ry // 8)) % 2 == 0 else (0, 0, 0, 255)
    src = STACK[swatch]
    rt = [qb(blend(eqn, src, dst, sf, df, ch)) for ch in range(3)]
    rt.append(src[3])                      # alpha is written with blending off
    # An A8R8G8B8 surface is bytes B,G,R,A; sampled as A8B8G8R8 those read back
    # as R,G,B,A, so the channels come back reversed.
    samp = (rt[2], rt[1], rt[0], rt[3])
    a = F(samp[3], 255)
    bg = F(screen_bg(BLIT_X + rx, BLIT_Y + ry), 255)
    return tuple(qt(F(samp[c], 255) * a + bg * (1 - a)) for c in range(3))


def sample_points():
    """(eqn, sfactor, dfactor, swatch, rx, ry) for every sampled pixel."""
    for eqn in EQNS:
        for sf in FACTORS:
            for i, df in enumerate(FACTORS):
                rx0, ry0 = (i % 5) * CELL_DX, (i // 5) * CELL_DY
                for sw in range(4):
                    for dx, dy in ((2, 2), (10, 2), (2, 10), (10, 10)):
                        yield eqn, sf, df, sw, rx0 + dx, ry0 + sw * SWATCH + dy


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"), dtype=int)


def score(directory, prefix, goldens, qb, qt):
    hits = misses = 0
    by_sf = collections.Counter()
    cache = {}
    for eqn, sf, df, sw, rx, ry in sample_points():
        name = f"#spot_{sf}_{eqn}"
        if name not in cache:
            p = os.path.join(directory, prefix + name + ".png")
            if not os.path.exists(p):
                cache[name] = None
            else:
                cache[name] = load(p)
        img = cache[name]
        if img is None:
            continue
        got = tuple(img[BLIT_Y + ry, BLIT_X + rx][:3])
        want = predict(eqn, sf, df, sw, rx, ry, QUANT[qb], QUANT[qt])
        if got == want:
            hits += 1
        else:
            misses += 1
            by_sf[sf] += 1
    return hits, misses, by_sf


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", help="directory of Blend_tests::<test>.png")
    ap.add_argument("--goldens", default="/tmp/goldens/results/Blend_tests")
    ap.add_argument("--self-test", action="store_true",
                    help="score the goldens themselves and require a perfect fit")
    args = ap.parse_args()

    if args.self_test or not args.captures:
        for qb in QUANT:
            for qt in QUANT:
                h, m, _ = score(args.goldens, "", args.goldens, qb, qt)
                print(f"  silicon, blend {qb:>5} / blit {qt:>5}: {h} hit, {m} miss")
        h, m, _ = score(args.goldens, "", args.goldens, "round", "round")
        if m:
            print(f"self-test FAILED: {m} sampled pixels unexplained", file=sys.stderr)
            return 1
        print("self-test ok: round/round reproduces silicon exactly")
        if not args.captures:
            return 0

    h, m, by_sf = score(args.captures, "Blend_tests::", args.goldens, "round", "round")
    print(f"\n{args.captures}: {h} of {h + m} sampled pixels match the model")
    for sf, n in by_sf.most_common():
        print(f"  sfactor {sf:>9}: {n} deviating")
    return 0


if __name__ == "__main__":
    sys.exit(main())
