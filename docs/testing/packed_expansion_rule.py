#!/usr/bin/env python3
"""Re-derive, from the hardware goldens alone, how silicon expands a packed
colour channel narrower than 8 bits -- and exit non-zero if any rule other
than bit replication survives.

    packed_expansion_rule.py [--goldens DIR]

Issue #59. The claim under test is a *decoded value*, not a pixel count:

    a 5-bit field of 3 decodes to 24, and 6-bit 12 decodes to 48.

Both are one count below the exact ratio -- round(3*255/31) = 25,
round(12*255/63) = 49 -- which is what the Vulkan and GL native packed
formats are specified to produce, and what we produced while we claimed them.

WHY THIS IS MAPPING-FREE, AND WHY THAT MATTERS
----------------------------------------------
The obvious way to read an expansion out of a golden is to fit the
screen->texel mapping, recover each pixel's source field value and compare.
That was done for R6G5B5 (docs/investigations/r6g5b5-golden-packing.md) and it
works, but it makes the answer depend on a regression fit with a residual, and
on the test's source bytes being the ones the golden was captured with -- which
for R6G5B5 they are not.

None of that is needed to separate two *level sets*. Each rule maps a field to
a fixed set of at most 64 8-bit values, and the two sets differ:

    5-bit  replicate-only: 24, 57, 198, 231
           ratio-only:     25, 58, 197, 230
    6-bit  replicate-only: 44, 48, 52, 56, 60, 195, 199, 203, 207, 211
           ratio-only:     45, 49, 53, 57, 61, 194, 198, 202, 206, 210

So the question is only "which values does this channel of this golden
contain", which needs no mapping, no fit and no assumption about which texel
landed where. Fourteen discriminating levels per format family; a golden that
holds any of them settles the rule for that width, and a golden that holds
values from both sets refutes a single uniform rule outright.

At 4 bits -- A4R4G4B4 -- the two rules are the SAME map, v*17, at every one of
the sixteen values. There is nothing to decide and nothing to fix, which is why
A4R4G4B4 is excluded from the conversion in pgraph_convert_texture_data and
checked here only to confirm that it cannot discriminate.

The suites used walk a 256x256 synthetic gradient, so every field value
appears; `Surface_clip/rt_*` holds exactly one colour and is reported
separately as the capture that motivated the issue.
"""
import argparse
import collections
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    print("SKIP: PIL/numpy not available")
    sys.exit(0)


def load(path):
    """One golden as an (h, w, 4) array of ints. RGBA, never RGB: the
    comparison the corpus is scored with keeps alpha, so this one does too."""
    return np.array(Image.open(path).convert("RGBA")).astype(int)


def replicate(v, bits):
    """Silicon's rule: the field's high bits fill the low ones."""
    return (v << (8 - bits)) | (v >> (2 * bits - 8))


def ratio(v, bits):
    """The Vulkan/GL native packed rule: round(v * 255 / (2**bits - 1))."""
    return round(v * 255 / ((1 << bits) - 1))


def level_sets(bits):
    rep = {replicate(v, bits) for v in range(1 << bits)}
    rat = {ratio(v, bits) for v in range(1 << bits)}
    return rep, rat


# Channel widths per golden. The suffix-free and _L variants of a Texture
# format test are the swizzled and linear layouts of the same image.
INSTRUMENTS = [
    ("Texture_format/TexFmt_R5G6B5", (5, 6, 5)),
    ("Texture_format/TexFmt_R5G6B5_L", (5, 6, 5)),
    ("Texture_format/TexFmt_A1R5G5B5", (5, 5, 5)),
    ("Texture_format/TexFmt_A1R5G5B5_L", (5, 5, 5)),
    ("Texture_format/TexFmt_X1R5G5B5", (5, 5, 5)),
    ("Texture_format/TexFmt_X1R5G5B5_L", (5, 5, 5)),
    # R6G5B5's golden was packed 565 by a different revision of the test
    # (issue #21), so it cannot be scored -- but a level set does not care
    # which texel a value came from, only that hardware emitted it.
    ("Texture_format/TexFmt_R6G5B5", (6, 5, 5)),
    # 4-bit control: must discriminate nothing.
    ("Texture_format/TexFmt_A4R4G4B4", (4, 4, 4)),
    ("Texture_format/TexFmt_A4R4G4B4_L", (4, 4, 4)),
]

# The capture this issue was split out of. One colour pair, one discriminating
# value, and the reason it read as a rounding wobble for so long.
SINGLE_COLOUR = [
    "Surface_clip/rt_x0y0_w512h384",
    "Surface_clip/rt_x0y0_w640h480",
    "Surface_clip/rt_x16y8_w512h384",
    "Surface_clip/rt_x8y16_w632h464",
    "Surface_clip/rt_x0y240_w640h240",
    "Surface_clip/rt_x320y240_w320h240",
    "Surface_clip/rt_x0y0_w0h0",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    args = ap.parse_args()

    print("discriminating levels, by field width")
    for bits in (4, 5, 6):
        rep, rat = level_sets(bits)
        print("  %d-bit  replicate-only %-42s ratio-only %s"
              % (bits, sorted(rep - rat), sorted(rat - rep)))
    print()

    tally = collections.Counter()
    failures = []
    missing = []

    for name, widths in INSTRUMENTS:
        path = os.path.join(args.goldens, name + ".png")
        if not os.path.exists(path):
            missing.append(name)
            continue
        arr = load(path)
        print(name)
        for idx, ch in enumerate("RGB"):
            bits = widths[idx]
            rep, rat = level_sets(bits)
            only_rep, only_rat = rep - rat, rat - rep
            seen = set(arr[:, :, idx].ravel().tolist())
            hit_rep = sorted(seen & only_rep)
            hit_rat = sorted(seen & only_rat)
            if not only_rep:
                verdict = "cannot discriminate (rules coincide at %d bits)" % bits
                tally["neutral"] += 1
            elif hit_rep and not hit_rat:
                verdict = "REPLICATE (%d/%d discriminating levels present)" \
                          % (len(hit_rep), len(only_rep))
                tally["replicate"] += 1
            elif hit_rat and not hit_rep:
                verdict = "RATIO -- refutes replication"
                tally["ratio"] += 1
                failures.append("%s %s holds ratio-only %s" % (name, ch, hit_rat))
            elif hit_rep and hit_rat:
                verdict = "MIXED -- no single uniform rule"
                tally["mixed"] += 1
                failures.append("%s %s holds both %s and %s"
                                % (name, ch, hit_rep, hit_rat))
            else:
                verdict = "silent (no discriminating level in this capture)"
                tally["silent"] += 1
            print("  %s(%d bits): %s" % (ch, bits, verdict))
        print()

    print("Surface_clip/rt_* -- the captures this issue was filed on")
    for name in SINGLE_COLOUR:
        path = os.path.join(args.goldens, name + ".png")
        if not os.path.exists(path):
            missing.append(name)
            continue
        counts = collections.Counter(map(tuple, load(path).reshape(-1, 4)))
        # The dark green quad: SetDiffuse(0.1, 0.6, 0.1) stored as 565.
        expect = (replicate(3, 5), replicate(38, 6), replicate(3, 5), 255)
        got = [c for c in counts if c[:3] == expect[:3]]
        if got:
            print("  %-36s holds %s x%d  <- 5-bit 3 -> %d, 6-bit 38 -> %d"
                  % (name, expect, counts[expect], replicate(3, 5),
                     replicate(38, 6)))
            tally["surface_clip"] += 1
        else:
            wrong = (ratio(3, 5), ratio(38, 6), ratio(3, 5), 255)
            if wrong in counts:
                failures.append("%s holds the ratio colour %s" % (name, wrong))
            print("  %-36s does NOT hold %s" % (name, expect))
    print()

    if missing:
        print("goldens not found (%d): %s" % (len(missing), ", ".join(missing)))
    print("channels: %s" % dict(tally))

    if failures:
        print("\nFAIL: a rule other than bit replication survives")
        for f in failures:
            print("  " + f)
        return 1
    if not tally["replicate"]:
        print("\nFAIL: no golden discriminated the two rules -- nothing was "
              "tested. Check --goldens.")
        return 1
    print("\nPASS: bit replication on %d channels, the exact ratio on none, "
          "%d channels where the two rules coincide and cannot decide."
          % (tally["replicate"], tally["neutral"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
