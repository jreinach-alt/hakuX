#!/usr/bin/env python3
"""#50: is the region the race corrupts one that is otherwise BIT-EXACT?

#50's entry records "at 16-76 ours matches hardware exactly. Only 560-620 is
reversed" -- but that was measured on the TestDetailed ORACLE set
(`iso_oldbt.iso`), and the 22 race events are release-disc captures. Two
different capture sets, so the statement cannot be carried across; this file
measures it where the race actually happens.

Why it matters. If the left stack is bit-exact in the run that does NOT
depart, then the race is corrupting pixels the emulator otherwise gets
exactly right, and it is separable from the structural defect that owns the
right stack. That also hands any future fix a free oracle: the left column of
those captures must stay at 0 differing.

Both columns are printed for every mover, over rows 112-367, against the
golden. A capture where BOTH columns differ is not a counterexample -- the
signed-add tests are wrong on both by the entry's own measurement -- it just
carries no oracle.
"""
import os, sys, csv, json, collections
import numpy as np
from PIL import Image

R = os.environ.get("HAKUX_RESULTS", "/home/justin/hakux-work/dispatch/results")
G = os.environ.get("GOLDENS", "/home/justin/goldens/results")
SUITE = "Blend_tests"
BAND = slice(112, 368)
LEFT, RIGHT = slice(16, 80), slice(560, 624)

# the 22 captures that moved across the 13 full-disc runs, from
# blend_race_perrun_50.py; kept explicit so this file is readable on its own
MOVERS = [
    "1-cA_ADD_1-dstA", "1-cA_SADD_1-srcA", "1-cRGB_SADD_1-dstA",
    "1-dstA_SADD_1-srcRGB", "1-dstA_SUB_1-cRGB", "1-dstRGB_MAX_1-cA",
    "1-dstRGB_MIN_1", "1-srcRGB_ADD_1-srcRGB", "1-srcRGB_SADD_0",
    "1-srcRGB_SADD_1", "1_ADD_1", "1_MIN_dstRGB", "1_REVSUB_cRGB",
    "cA_MIN_srcRGB", "dstA_MIN_1-cRGB", "srcA_MAX_1-dstA", "srcA_MAX_cA",
    "srcA_MAX_cRGB", "srcA_REVSUB_1-cA", "srcAsat_SADD_0",
    "srcAsat_SUB_srcAsat", "srcRGB_ADD_0",
]
# a clean thor run: thor departed on none of its five, so captures1 here is
# the modal image for every one of the 22
CLEAN = os.path.join(R, "1789819556-blendrace50-thor-414959", "captures1")


def px(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.uint8)


def main():
    print("Modal (non-departing) capture vs golden, rows 112-367.")
    print("A 0 means the emulator is BIT-EXACT with hardware in that column.")
    print()
    print("  %-24s %10s %10s   %s" % ("capture", "left diff", "right diff", "reading"))
    clean_left = 0
    for t in MOVERS:
        cp = os.path.join(CLEAN, "%s::%s.png" % (SUITE, t))
        gp = os.path.join(G, SUITE, "%s.png" % t)
        if not (os.path.exists(cp) and os.path.exists(gp)):
            print("  %-24s (capture or golden missing)" % t)
            continue
        c, g = px(cp), px(gp)
        l = int(np.any(c[BAND, LEFT] != g[BAND, LEFT], axis=2).sum())
        r = int(np.any(c[BAND, RIGHT] != g[BAND, RIGHT], axis=2).sum())
        note = "left is an ORACLE the race breaks" if l == 0 else "no oracle here"
        clean_left += 1 if l == 0 else 0
        print("  %-24s %10d %10d   %s" % (t, l, r, note))
    print()
    print("  %d of %d movers have a bit-exact left column in the modal run."
          % (clean_left, len(MOVERS)))
    print("  On those, the race corrupts pixels the emulator otherwise gets")
    print("  exactly right -- which is what makes it separable from the")
    print("  structural defect, and is a free regression oracle for a fix.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
