#!/usr/bin/env python3
"""#50: score the two surviving readings of `DrawColorAndAlphaStack` against
the whole recovered oracle, instead of against the single capture that cannot
tell them apart.

The issue's next step was to build a disc variant with unequal swatch heights,
because on the existing four-equal-band frame the two readings --

  reading 1   the four quads land at reversed y positions
  reading 2   the four quads land correctly and receive the diffuse colours
              in reverse order

-- predict the same framebuffer.  They do, and this file measures that they do
rather than assuming it: `--equivalence` builds each reading independently, in
the shape its own sentence describes, and compares the two render targets.

But they predict the same framebuffer *as each other*, not the same framebuffer
as the capture, and that is what makes the disc variant unnecessary.  Both
readings keep stack C's own draw state, in which `DrawColorAndAlphaStack`
blends all four channels.  The aliasing reading -- stack C's blit shows the
render target `DrawColorStack` left at the same guest address -- keeps stack
A's state, in which `DrawQuad` writes alpha with blending switched off.

The three predictions are therefore **identical in RGB at the render target
and differ only in alpha**, and the blit composites with SRC_ALPHA /
ONE_MINUS_SRC_ALPHA, so that one channel is visible on screen in all four.
One channel over 1,120 captures separates what a swatch-height variant was
going to separate with one.

    docs/testing/swatchorder50_readings.py --equivalence
    docs/testing/swatchorder50_readings.py --score
    docs/testing/swatchorder50_readings.py --bands 1_ADD_1

Every figure comes from captures already on disk: no device, no build.
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blend_detailed_oracle as O  # noqa: E402

CAPTURES = os.path.expanduser("~/hakux-work/res_oldblend")
GOLDENS = "/home/justin/goldens/results/Blend_tests"
PREFIX = "Blend_tests::"

Y0, H = 112, 256
CX, W = 560, 64
BAND = 64


def _quad(eqn, sf, df, sr, src, nchan):
    """One swatch's two checker phases.  nchan=4 blends alpha (stack C's
    state); nchan=3 writes the source alpha straight (stack A's state)."""
    out = {}
    for ph in (0, 1):
        dst = (51, 51, 51, 51) if ph == 0 else (0, 0, 0, 255)
        px = [O.q(O.blend(eqn, src, dst, sf, df, ch, sr)) for ch in range(nchan)]
        if nchan == 3:
            px = px + [src[3]]
        out[ph] = px
    return out


def _paint(bands):
    """bands[p] -> {phase: pixel}, laid into a 64x256 render target."""
    out = np.zeros((256, 64, 4), dtype=int)
    ys, xs = np.mgrid[0:256, 0:64]
    ph = ((xs // O.CHECK) + (ys // O.CHECK)) % 2
    for p in range(4):
        inband = (ys >= p * BAND) & (ys < (p + 1) * BAND)
        for phase in (0, 1):
            m = inband & (ph == phase)
            out[ys[m], xs[m]] = bands[p][phase]
    return out


def rt_reading1(eqn, sf, df, sr):
    """Reading 1: stack C's four draws, quad sw written at band 3-sw."""
    bands = {}
    for sw in range(4):
        bands[3 - sw] = _quad(eqn, sf, df, sr, O.CASTACK[sw], 4)
    return _paint(bands)


def rt_reading2(eqn, sf, df, sr):
    """Reading 2: band p drawn in its own place, carrying colour CASTACK[3-p]."""
    bands = {}
    for p in range(4):
        bands[p] = _quad(eqn, sf, df, sr, O.CASTACK[3 - p], 4)
    return _paint(bands)


def rt_aliasing(eqn, sf, df, sr):
    """Reading 3: the render target stack A left behind, blitted at x=560."""
    return O.rt_left(eqn, sf, df, sr, O.COLORSTACK)


def rt_correct(eqn, sf, df, sr):
    """Control: stack C drawn as the test intends."""
    return O.rt_right(eqn, sf, df, sr)


MODELS = [
    ("reading 1: reversed y positions", rt_reading1),
    ("reading 2: reversed colour order", rt_reading2),
    ("reading 3: stack A's render target", rt_aliasing),
    ("control: stack C drawn correctly", rt_correct),
]


def _cases(eqns):
    return list(O.tests(eqns))


def run_equivalence(args):
    """Measure the brief's premise: do the two readings predict one picture?"""
    print("equivalence: reading 1 vs reading 2, at the render target")
    same = diff = 0
    worst = []
    for name, eqn, sf, df in _cases(O.UNSIGNED + O.SIGNED):
        r1 = rt_reading1(eqn, sf, df, True)
        r2 = rt_reading2(eqn, sf, df, True)
        if np.array_equal(r1, r2):
            same += 1
        else:
            diff += 1
            worst.append((int((r1 != r2).sum()), name))
    worst.sort(reverse=True)
    print("  identical render targets: %d/%d   differing: %d"
          % (same, same + diff, diff))
    if worst:
        print("  worst: %s" % worst[:3])
    print("  -> the four bands are equal height, so 'quad sw at band 3-sw' and")
    print("     'band p given colour CASTACK[3-p]' are the same map.  A disc")
    print("     variant with unequal heights would separate them; nothing in")
    print("     the existing frame can.  That is the issue's premise, measured.")

    print()
    print("separation: where each reading differs from reading 3, by channel")
    for label, fn in MODELS[:2] + MODELS[3:]:
        rgb = alpha = 0
        for name, eqn, sf, df in _cases(O.UNSIGNED):
            a = fn(eqn, sf, df, True)
            b = rt_aliasing(eqn, sf, df, True)
            d = (a != b)
            rgb += int(d[:, :, 0:3].sum())
            alpha += int(d[:, :, 3].sum())
        print("  %-36s RGB %9d   alpha %9d" % (label, rgb, alpha))
    print("  -> readings 1 and 2 differ from reading 3 in ALPHA ONLY: they")
    print("     keep stack C's state, which blends all four channels, while")
    print("     stack A's DrawQuad writes alpha straight.  The blit composites")
    print("     with SRC_ALPHA, so that channel is visible on screen.")


def run_score(args):
    """Score our captures, and the goldens as a control, against all four."""
    eqns = O.UNSIGNED if args.unsigned else O.UNSIGNED + O.SIGNED
    for src, pref, label in ((args.captures, PREFIX, "ours (xemu)"),
                             (args.goldens, "", "goldens (control)")):
        res = {}
        n = 0
        for name, eqn, sf, df in _cases(eqns):
            p = os.path.join(src, pref + name + ".png")
            if not os.path.exists(p):
                continue
            img = O.load(p)[Y0:Y0 + H, CX:CX + W]
            n += 1
            for mlabel, fn in MODELS:
                eq = (img == O.blit(fn(eqn, sf, df, True), CX, Y0))
                acc = res.setdefault(mlabel, [0, 0, 0])
                acc[0] += int(eq.all())
                acc[1] += int(eq.sum())
                acc[2] += int(eq.size)
        print("stack C region, %s: %d captures" % (label, n))
        for mlabel, (ex, ce, ct) in res.items():
            print("  %-36s exact %4d/%-4d  channels %10d/%d (%.4f%%)"
                  % (mlabel, ex, n, ce, ct, 100.0 * ce / max(ct, 1)))
        print()


def run_bands(args):
    """Per-band render-target alpha, model by model, on one capture."""
    name = args.bands
    for tname, eqn, sf, df in _cases(O.UNSIGNED + O.SIGNED):
        if tname != name:
            continue
        print("render-target alpha by band, %s" % name)
        print("  %-36s %s" % ("model", "band 0  band 1  band 2  band 3"))
        for mlabel, fn in MODELS:
            rt = fn(eqn, sf, df, True)
            cells = []
            for p in range(4):
                a = rt[p * BAND:(p + 1) * BAND, :, 3]
                vals = sorted(set(a.flatten().tolist()))
                cells.append("/".join(str(v) for v in vals))
            print("  %-36s %s" % (mlabel, "  ".join("%6s" % c for c in cells)))
        print()
        print("  readings 1 and 2 must show clamp(221+51)=255 wherever the")
        print("  destination phase is the 51-grey checker; reading 3 shows the")
        print("  unblended source alpha 221 everywhere.  The capture decides.")
        return
    print("no such test: %s" % name, file=sys.stderr)
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", default=CAPTURES)
    ap.add_argument("--goldens", default=GOLDENS)
    ap.add_argument("--equivalence", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--unsigned", action="store_true",
                    help="exclude the 448 signed captures, where #43 is live")
    ap.add_argument("--bands", metavar="TEST")
    args = ap.parse_args()
    if not (args.equivalence or args.score or args.bands):
        ap.error("pick at least one of --equivalence, --score, --bands")
    rc = 0
    if args.equivalence:
        run_equivalence(args)
    if args.score:
        run_score(args)
    if args.bands:
        rc = run_bands(args) or 0
    return rc


if __name__ == "__main__":
    sys.exit(main())
