#!/usr/bin/env python3
"""#50: is `Blend tests` stack C a reversal, or is it stack A's render target?

`BlendTests::TestDetailed` renders three swatch stacks, each into its own
render-to-texture, then blits each to the screen as a textured quad:

    stack A  DrawColorStack          64x256 RT at T   blitted at x=16
    stack B  DrawAlphaStack         256x256 RT at T   blitted at x=192
    stack C  DrawColorAndAlphaStack  64x256 RT at T   blitted at x=560

All three render-to-textures use the SAME guest address T (texture memory for
stage 1, `RenderToTextureStart(1, pitch)`), and A and C use the same geometry,
the same pitch, the same surface format and the same texture state.  Only the
draws between them differ.

Stack A draws green, red, blue, white top to bottom; stack C draws that list
**reversed**.  So "stack C shows stack A's render target" and "stack C's four
swatches are in reverse order" produce the same swatch colours, and the issue
was filed as the second.  It is the first.

## The comparison that must not be made naively

`blend-stacks-are-two-defects.md` reports render-target aliasing as tested and
**falsified** -- "compared our stack C against both our own stack A and the
golden's stack A on all 1,568 captures: 0 matches either way".  That test is
invalid, and this file exists to say why in code.

`RenderTexturedQuad` calls `SetBlend(true)` and composites the sampled texel
over whatever is already on screen, which is a 24-texel checkerboard stretched
from a 256x256 texture across 640x480.  The checker is therefore ~60px wide and
45px tall in screen space, and it is **not** in phase between x=16..79 and
x=560..623.  Two blits of one identical render target land as two different
pictures.  Comparing the two screen regions pixel for pixel compares the
backgrounds, not the render targets, and returns 0 matches for a frame in which
the aliasing is total.

Two valid comparisons are implemented instead:

`--aliasing`  MODEL-FREE.  Restrict to the 1,024 pixels per capture where the
              screen checker tone happens to agree between the two blits.  If
              stack C's blit shows stack A's render target, our stack A pixel
              and our stack C pixel must be bit-identical there.  Uses only our
              own captures; no model, no golden, no scene constants.

`--model`     MODEL-BASED.  Score our three regions against
              `blend_detailed_oracle.py`'s closed-form prediction, and score
              our stack C against the prediction for **stack A blitted at stack
              C's screen position**.  The oracle reproduces silicon on
              440,401,920 of 440,401,920 channels, so it can predict what any
              render target would look like anywhere on screen.

`--geometry`  Where each band starts and ends, in ours and in the golden.  This
              is the "is it reversed, rotated or mirrored" question asked
              directly: it is none of those, the geometry does not move.

`--naive`     Reproduces the invalid comparison and its 0 matches, so the
              falsification that has to be withdrawn can be re-run.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blend_detailed_oracle as O  # noqa: E402

CAPTURES = os.path.expanduser("~/hakux-work/res_oldblend")
PREFIX = "Blend_tests::"

# rows 112..367, and the three blit columns.  From blend_detailed_oracle.BLITS.
Y0, H = 112, 256
AX, CX, W = 16, 560, 64
BX, BW = 192, 256


def capture_names(goldens):
    return sorted(f[:-4] for f in os.listdir(goldens)
                  if f.endswith(".png") and not f.startswith("#spot"))


def load_pair(captures, goldens, name):
    op = os.path.join(captures, PREFIX + name + ".png")
    gp = os.path.join(goldens, name + ".png")
    if not os.path.exists(op) or not os.path.exists(gp):
        return None, None
    return O.load(op), O.load(gp)


def matched_tone_mask():
    """Pixels where the screen checkerboard tone agrees under both blits."""
    bg = O.bg_arrays()
    return bg[Y0:Y0 + H, AX:AX + W] == bg[Y0:Y0 + H, CX:CX + W]


def run_aliasing(args):
    same = matched_tone_mask()
    print("model-free: stack C's blit shows stack A's render target")
    print("  comparable pixels per capture: %d of %d (screen checker in phase)"
          % (same.sum(), same.size))
    for label, src, pref in (("ours", args.captures, PREFIX),
                             ("golden (control)", args.goldens, "")):
        n = exact = ch_eq = ch_tot = 0
        misses = []
        for name in capture_names(args.goldens):
            p = os.path.join(src, pref + name + ".png")
            if not os.path.exists(p):
                continue
            img = O.load(p)
            a = img[Y0:Y0 + H, AX:AX + W][same]
            c = img[Y0:Y0 + H, CX:CX + W][same]
            eq = (a == c)
            n += 1
            ch_eq += int(eq.sum())
            ch_tot += int(eq.size)
            if eq.all():
                exact += 1
            else:
                misses.append((int((~eq).sum()), name))
        misses.sort(reverse=True)
        print("  %-18s %4d/%d captures bit-exact, %d/%d channels (%.4f%%)"
              % (label, exact, n, ch_eq, ch_tot, 100.0 * ch_eq / max(ch_tot, 1)))
        if misses:
            print("       misses: %d, worst: %s" % (len(misses), misses[:3]))


def run_model(args):
    print("model-based: our three regions against the closed-form oracle")
    eqns = O.UNSIGNED if args.unsigned else O.UNSIGNED + O.SIGNED
    res = {}
    n = 0
    for name, eqn, sf, df in O.tests(eqns):
        p = os.path.join(args.captures, PREFIX + name + ".png")
        if not os.path.exists(p):
            continue
        img = O.load(p)
        n += 1
        rt_a = O.rt_left(eqn, sf, df, True, O.COLORSTACK)
        rt_b = O.rt_center(eqn, sf, df, True)
        rt_c = O.rt_right(eqn, sf, df, True)
        for label, x0, w, rt in (
                ("stack A vs model A", AX, W, rt_a),
                ("stack B vs model B", BX, BW, rt_b),
                ("stack C vs model C", CX, W, rt_c),
                ("stack C vs model A blitted at C", CX, W, rt_a),
        ):
            eq = (img[Y0:Y0 + H, x0:x0 + w] == O.blit(rt, x0, Y0))
            acc = res.setdefault(label, [0, 0, 0])
            acc[0] += int(eq.all())
            acc[1] += int(eq.sum())
            acc[2] += int(eq.size)
    print("  captures: %d" % n)
    for label, (ex, ce, ct) in res.items():
        print("  %-34s exact %4d/%d   channels %d/%d (%.4f%%)"
              % (label, ex, n, ce, ct, 100.0 * ce / max(ct, 1)))


def band_edges(region):
    """Rows (relative to the region) where the row content changes class."""
    edges = []
    for y in range(1, region.shape[0]):
        if not np.array_equal(np.unique(region[y].reshape(-1, region.shape[2]), axis=0),
                              np.unique(region[y - 1].reshape(-1, region.shape[2]), axis=0)):
            edges.append(y)
    return edges


def run_geometry(args):
    print("geometry: band boundaries and swatch centre rows, ours vs golden")
    name = args.capture
    ours, gold = load_pair(args.captures, args.goldens, name)
    if ours is None:
        print("  missing capture pair for", name)
        return
    for label, img in (("golden", gold), ("ours", ours)):
        reg = img[Y0:Y0 + H, CX:CX + W]
        # A swatch band is 64 rows; report the colour set of each band and the
        # centre-row pixel, so a reversal, a rotation and a mirror would all
        # show up as a moved boundary or a moved centre.
        print("  %s stack C (%s)" % (label, name))
        for i in range(4):
            centre = Y0 + i * 64 + 32
            px = img[centre, CX + 32].tolist()
            vals = np.unique(reg[i * 64:(i + 1) * 64].reshape(-1, reg.shape[2]),
                             axis=0)
            print("     band %d rows %3d..%3d  centre row %3d = %-22s  %d distinct colours"
                  % (i, Y0 + i * 64, Y0 + i * 64 + 63, centre, str(px), len(vals)))
        print("     content-change rows inside the region: %s"
              % (band_edges(reg)[:12],))


def run_naive(args):
    print("naive (invalid) comparison: screen region against screen region")
    print("  this ignores that the two blits sit on different checker phases")
    n = ex_own = ex_gold = 0
    for name in capture_names(args.goldens):
        ours, gold = load_pair(args.captures, args.goldens, name)
        if ours is None:
            continue
        n += 1
        c = ours[Y0:Y0 + H, CX:CX + W]
        if np.array_equal(c, ours[Y0:Y0 + H, AX:AX + W]):
            ex_own += 1
        if np.array_equal(c, gold[Y0:Y0 + H, AX:AX + W]):
            ex_gold += 1
    print("  captures: %d" % n)
    print("  our stack C == our stack A    (screen pixels): %d/%d" % (ex_own, n))
    print("  our stack C == golden stack A (screen pixels): %d/%d" % (ex_gold, n))
    print("  Both are 0 and both are meaningless; see --aliasing.")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", default=CAPTURES)
    ap.add_argument("--goldens", default=O.GOLDENS)
    ap.add_argument("--aliasing", action="store_true")
    ap.add_argument("--model", action="store_true")
    ap.add_argument("--geometry", action="store_true")
    ap.add_argument("--naive", action="store_true")
    ap.add_argument("--unsigned", action="store_true",
                    help="--model: score only the 1,120 unsigned captures, where "
                         "stacks A and B are bit-exact and #43 cannot contaminate")
    ap.add_argument("--capture", default="1_ADD_0",
                    help="--geometry: which capture to tabulate")
    args = ap.parse_args()
    if not (args.aliasing or args.model or args.geometry or args.naive):
        args.aliasing = args.geometry = True
    if args.geometry:
        run_geometry(args)
    if args.aliasing:
        run_aliasing(args)
    if args.model:
        run_model(args)
    if args.naive:
        run_naive(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
