#!/usr/bin/env python3
"""Score issue #43's factor half by the quantity it changes: the source byte.

Why not a pixel count
---------------------

The F24 depth fix was very nearly reverted on a pixel count that moved the
wrong way while its mechanism was in fact correct, because two independent
residuals overlapped in the same pixels and counts cannot be subtracted. #43
has exactly that shape. Silicon computes

    signed(S) = S - 256 if S >= 128 else S
    FUNC_ADD_SIGNED              = clamp(signed(S) + D, 0, 255)
    FUNC_REVERSE_SUBTRACT_SIGNED = clamp(D - signed(S), 0, 255)

with both blend factors ignored. Fixed-function blend state can express the
"factors ignored" half (force ONE/ONE) and provably cannot express the signed
fold of S -- silicon's output is discontinuous in the source at S = 128 and
every blend op is a continuous map of it. So the fix is exact wherever the
source byte is below 128 and still wrong above it, in the *same captures*, and
a whole-capture count mixes the two.

This separates them. It recovers the source and destination byte of every
channel of `Texture signed component tests`' three `txt_A8R8G8B8_*` captures
from the *goldens*, splits the channels on the sign bit of the recovered
source, and reports how many are wrong in each half.

    signed_blend_source_halves.py RESULTDIR [--goldens DIR]

The prediction the factor fix is judged on: **zero** wrong channels in the
S < 128 half. The S >= 128 half is expected to stay wrong, and to get slightly
worse under SREVSUB -- today's SRC_ALPHA factors happen to land on the right
answer for some of those channels by arithmetic accident.

How the recovery works, and why it is trustworthy
-------------------------------------------------

Three goldens constrain every channel:

    gold_ADD     = round((S*As + D*(255-As))/255)      (the plain-ADD case)
    gold_SADD    = clamp(signed(S) + D)
    gold_SREVSUB = clamp(D - signed(S))

The destination alpha is 255, read off the unblended background, so the source
alpha follows in closed form from whichever signed golden has not saturated.
With the source alpha known, (S, D) is found by an exhaustive sweep checked
against all three goldens at once; a channel is used only if exactly one
(S, D) satisfies all three. That solves 1,221,589 of 1,228,800 channels
(99.4%), and the unsolved remainder is the pb_print label's glyphs and a few
ties.

Two things make this a measurement rather than a fit. It never reads our own
render -- the recovery is golden-against-golden, so it cannot launder our
defect into its own reference. And the scene it recovers is independently
confirmed: our render of `txt_A8R8G8B8_ADD` is bit-exact against silicon, 0
differing channels over 640x480, so the layout, the texture decode, the
checkerboard phase and the unsigned blend arithmetic are all already right in
this suite, and the signed equation is the only thing left in the other two
captures. The recovered destinations come out as exactly {127, 255} and the
recovered sources cover all 256 values, which is what the suite draws.
"""
import argparse
import glob
import os
import sys

import numpy as np

GOLDENS = "/home/justin/goldens/results/Texture_signed_component_tests"
SUITE = "Texture_signed_component_tests"
DST_ALPHA = 255
DST_CANDIDATES = (0, 127, 128, 255)


def load(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.int64)


def cl(v):
    return np.clip(v, 0, 255)


def recover(goldens):
    """(S, D, usable) per channel, from the goldens alone."""
    g_add = load(os.path.join(goldens, "txt_A8R8G8B8_ADD.png"))
    g_sadd = load(os.path.join(goldens, "txt_A8R8G8B8_SADD.png"))
    g_srev = load(os.path.join(goldens, "txt_A8R8G8B8_SREVSUB.png"))
    h, w = g_add.shape[:2]

    # Source alpha, in closed form. The destination alpha is 255, so SADD
    # saturates for every As < 128 and SREVSUB for every As >= 128: whichever
    # has not saturated gives signed(As) directly, and if both saturate then
    # signed(As) is pinned to 0 from both sides.
    sa, sr = g_sadd[:, :, 3], g_srev[:, :, 3]
    sig = np.where(sa < 255, sa - DST_ALPHA,
                   np.where(sr < 255, DST_ALPHA - sr, 0))
    src_alpha = sig & 0xFF
    ok_alpha = (cl(sig + DST_ALPHA) == sa) & (cl(DST_ALPHA - sig) == sr)

    a = np.repeat(src_alpha[:, :, None], 4, axis=2)
    hits = np.zeros((h, w, 4), dtype=np.int64)
    S = np.zeros((h, w, 4), dtype=np.int64)
    D = np.zeros((h, w, 4), dtype=np.int64)
    for d in DST_CANDIDATES:
        for s in range(256):
            g = s - 256 if s >= 128 else s
            m = ((cl(g + d) == g_sadd) & (cl(d - g) == g_srev) &
                 (((s * a + d * (255 - a) + 127) // 255) == g_add))
            hits += m
            S = np.where(m, s, S)
            D = np.where(m, d, D)
    usable = np.repeat(ok_alpha[:, :, None], 4, axis=2) & (hits == 1)
    return dict(S=S, D=D, usable=usable, g_add=g_add, g_sadd=g_sadd,
                g_srev=g_srev)


def find_capture(resultdir, test):
    """Locate one capture inside a dispatcher result directory.

    The dispatcher does not put PNGs at the top of a result directory: it puts
    them in captures<N>/, one per run, named "<Suite>::<test>.png". Searching
    only the top level made this tool report all three captures MISSING on a
    result that in fact contained them, which reads exactly like an arm that
    failed to render -- the most alarming possible false negative for a tool
    whose entire job is to decide whether a prediction held.
    """
    names = ("%s::%s.png" % (SUITE, test), "%s.png" % test)
    roots = [resultdir]
    roots += sorted(glob.glob(os.path.join(resultdir, "captures*")))
    sub = os.path.join(resultdir, SUITE)
    if os.path.isdir(sub):
        roots.append(sub)
    for root in roots:
        for name in names:
            p = os.path.join(root, name)
            if os.path.exists(p):
                return p
    return None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("resultdir", help="a dispatcher result directory")
    ap.add_argument("--goldens", default=GOLDENS)
    args = ap.parse_args()

    r = recover(args.goldens)
    S, D, usable = r["S"], r["D"], r["usable"]
    lo, hi = usable & (S < 128), usable & (S >= 128)
    print("recovered from the goldens: %d of %d channels usable (%.1f%%)"
          % (usable.sum(), usable.size, 100.0 * usable.sum() / usable.size))
    print("  destinations recovered: %s" % sorted(set(D[usable].tolist())))
    print("  source bytes below 128: %d channels;  at or above: %d"
          % (int(lo.sum()), int(hi.sum())))
    print()

    rc = 0
    for test, gold in (("txt_A8R8G8B8_ADD", r["g_add"]),
                       ("txt_A8R8G8B8_SADD", r["g_sadd"]),
                       ("txt_A8R8G8B8_SREVSUB", r["g_srev"])):
        p = find_capture(args.resultdir, test)
        if p is None:
            print("%-24s MISSING from %s" % (test, args.resultdir))
            rc = 2
            continue
        ours = load(p)
        bad = ours != gold
        print("%-24s %7d px / %7d channels differ" %
              (test, int(bad.any(axis=2).sum()), int(bad.sum())))
        print("%-24s   source < 128 : %7d of %7d channels wrong"
              % ("", int((bad & lo).sum()), int(lo.sum())))
        print("%-24s   source >= 128: %7d of %7d channels wrong"
              % ("", int((bad & hi).sum()), int(hi.sum())))
        print("%-24s   unrecovered  : %7d of %7d channels wrong"
              % ("", int((bad & ~usable).sum()), int((~usable).sum())))
        if test != "txt_A8R8G8B8_ADD" and int((bad & lo).sum()):
            rc = 1
    if rc == 1:
        print("\nFALSIFIED for the S < 128 half: forcing ONE/ONE should make "
              "every one of those channels exact. If they are not, the "
              "'both factors are ignored' half of the rule is wrong.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
