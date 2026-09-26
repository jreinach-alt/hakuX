#!/usr/bin/env python3
"""Recover the hardware's float -> byte rule for vertex colours, from goldens.

Issue #38's mechanism 1 asks one question: when a test hands the NV2A a
floating point colour component, what byte reaches the framebuffer?  The
answer decides whether the hardware truncates, rounds, or does something
else, and every attempt at that mechanism before this one was fitted to two
data points and failed on device (see #38's comment history).

This script reads the map off the goldens instead of guessing it, over every
distinct component value the corpus offers, and scores each candidate rule
against ALL of them.  A rule that misses one point is dead; the output names
which point killed it.

Method notes that matter:

  * REGIONS, NOT PIXELS.  Each probe names a box that is one flat colour in
    the golden, and the box is verified uniform before its colour is used.
    A point sample through structured content agrees with whatever you hoped.

  * RGBA, NOT RGB.  Alpha is read and checked like any other channel.

  * The float is the float32 the test actually submits, not the decimal the
    source spells.  0.1f is 0.100000001490116, and `255 * 0.1f` is
    25.5000004 -- above the tie, not on it.  That distinction is the whole
    result: the rules differ only there.

  * Point_size hands over ten values in one capture by walking a channel in
    +0.1f steps, so the accumulated float32 is reproduced here by the same
    accumulation rather than by writing 0.7 and hoping.

Usage:
  vertex_colour_quantiser.py [--goldens DIR]

Exits non-zero if the set of surviving rules is not exactly the one recorded
in EXPECTED_SURVIVORS, which is the falsifier: a new golden set, a re-dumped
disc, or a mis-stated float all show up as a change there.
"""
import argparse
import math
import os
import sys

# The rule that survived on 2026-09-12, and the only one that did.
EXPECTED_SURVIVORS = {"mantissa13_half_up"}

# ---------------------------------------------------------------------------
# The float32 values the tests submit.
#
# `acc(n)` is the value after n steps of the +0.1f accumulation that
# Point_size's RenderPoints does (`float red = 0.1f; ... red += 0.1f;`).
# Reproduced by accumulating, because the accumulated value drifts above the
# decimal and the drift is what separates the candidate rules.
# ---------------------------------------------------------------------------


def acc(n):
    import numpy as np
    v = np.float32(0.1)
    for _ in range(n - 1):
        v = np.float32(v + np.float32(0.1))
    return float(v)


def f32(x):
    import numpy as np
    return float(np.float32(x))


# ---------------------------------------------------------------------------
# Probes: (suite, test, box, {channel: (label, value_fn)})
#
# box is (x0, y0, x1, y1) inclusive and must be one colour in the golden.
# Boxes were chosen by growing a rectangle from the centre of each flat
# region, then inset, so none of them touches an edge or the debug text.
# ---------------------------------------------------------------------------
R, G, B, A = 0, 1, 2, 3

PROBES = [
    # SetDiffuse(0.1f, 0.6f, 0.1f), passthrough vertex program, A8R8G8B8
    # backbuffer, blending off.  The dark green quad covers the clip region.
    ("Surface_clip", "x0y0_w640h480_A8R8G8B8", (60, 80, 580, 440),
     {R: ("0.1f", lambda: f32(0.1)), G: ("0.6f", lambda: f32(0.6)),
      A: ("1.0f (default diffuse alpha)", lambda: 1.0)}),

    # The same colour reached through a different suite, so a single bad
    # golden cannot carry the result on its own.
    ("Null_surface", "XemuBug893", (120, 100, 520, 380),
     {R: ("0.1f", lambda: f32(0.1)), G: ("0.6f", lambda: f32(0.6))}),

    # NV097_SET_VERTEX_DATA2F_M writes diffuse components 0 and 1 only, as
    # raw floats, with NV097_SET_LIGHTING_ENABLE false.  Flat triangle.
    ("SetVertexData", "SET_VERTEX_DATA2F_M", (216, 200, 218, 330),
     {R: ("0.5f", lambda: 0.5), G: ("1.0f", lambda: 1.0)}),

    # SetDiffuse(0.75f, 0.75f, 0.75f) on the quad that closes its begin/end.
    ("Degenerate_begin_end", "BeginWithoutEnd", (484, 122, 505, 135),
     {R: ("0.75f", lambda: 0.75)}),

    # SetDiffuse(0.f, 0.75f, 0.f), full-screen quad, stencil always.
    ("Stencil_func", "Always", (140, 260, 510, 360),
     {G: ("0.75f", lambda: 0.75)}),

    # SetDiffuse(0.25f, 0.95f, 0.75f), one flat diamond.
    ("Antialiasing_tests", "FBSurfaceWithCenter1", (230, 150, 410, 330),
     {R: ("0.25f", lambda: 0.25), G: ("0.95f", lambda: f32(0.95)),
      B: ("0.75f", lambda: 0.75)}),
]

# Point_size's grid.  RenderPoints walks red down the rows and blue across
# the columns in +0.1f steps, with green pinned at 0.65f, so one capture
# hands over ten distinct component values and the constant.  The point size
# also grows along the walk, so the blocks are only full 63x63 squares from
# row 4 on; rows 1-3 contribute their rightmost (largest) block alone.
_PS = "PointSmoothOff_16_FF"
# (x0, y0, x1, y1, red_step, blue_step)
_PS_BLOCKS = [
    (590, 94, 602, 106, 1, 10),
    (580, 148, 612, 180, 2, 10),
    (570, 202, 622, 254, 3, 10),
]
for _row_y, _r in ((265, 4), (329, 5), (393, 6)):
    for _x0, _x1, _b in ((3, 47, 1), (56, 112, 2), (120, 176, 3), (184, 240, 4),
                         (248, 304, 5), (312, 368, 6), (376, 432, 7),
                         (440, 496, 8), (504, 560, 9), (568, 624, 10)):
        _PS_BLOCKS.append((_x0, _row_y, _x1, _row_y + 54, _r, _b))
for _x0, _y0, _x1, _y1, _r, _b in _PS_BLOCKS:
    PROBES.append((
        "Point_size", _PS, (_x0, _y0, _x1, _y1),
        {R: ("acc(%d) = %.9f" % (_r, acc(_r)), (lambda n: (lambda: acc(n)))(_r)),
         G: ("0.65f", lambda: f32(0.65)),
         B: ("acc(%d) = %.9f" % (_b, acc(_b)), (lambda n: (lambda: acc(n)))(_b))},
    ))

# ---------------------------------------------------------------------------
# Candidate rules.  Each takes the float32 component and returns a byte.
# ---------------------------------------------------------------------------


def _half_even(v):
    f = math.floor(v)
    if abs(v - f - 0.5) < 1e-12:
        return int(f if int(f) % 2 == 0 else f + 1)
    return int(math.floor(v + 0.5))


def _drop_mantissa(x, bits):
    """Truncate the low `bits` of the float32 mantissa, as the shader does."""
    import numpy as np
    mask = np.uint32((0xFFFFFFFF << bits) & 0xFFFFFFFF)
    u = np.uint32(np.float32(x).view(np.uint32) & mask)
    return float(np.frombuffer(u.tobytes(), dtype=np.float32)[0])


RULES = {
    # The five the issue named as candidates.
    "trunc":            lambda x: min(255, int(math.floor(f32(x) * 255.0))),
    "round_half_up":    lambda x: min(255, int(math.floor(f32(x) * 255.0 + 0.5))),
    "round_half_down":  lambda x: min(255, int(math.ceil(f32(x) * 255.0 - 0.5))),
    "round_half_even":  lambda x: min(255, _half_even(f32(x) * 255.0)),
    # The x256 family, which reading "hardware truncates" naively suggests.
    "floor_256":        lambda x: min(255, int(math.floor(f32(x) * 256.0))),
    "round_256":        lambda x: min(255, int(math.floor(f32(x) * 256.0 + 0.5))),
    # What the emulator does today: glsl/vsh.c colorPrecision() drops the low
    # ten mantissa bits, then the UNORM8 attachment rounds to nearest.
    "mantissa13_half_up":
        lambda x: min(255, int(math.floor(_drop_mantissa(x, 10) * 255.0 + 0.5))),
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", default=os.path.expanduser("~/goldens/results"))
    args = ap.parse_args(argv)

    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        sys.exit("needs numpy and pillow: %s" % e)

    # measured[(label, value)] = {byte: [sources]}
    measured = {}
    missing = []
    for suite, test, box, chans in PROBES:
        path = os.path.join(args.goldens, suite, test + ".png")
        if not os.path.exists(path):
            missing.append("%s/%s" % (suite, test))
            continue
        img = np.asarray(Image.open(path).convert("RGBA"))
        x0, y0, x1, y1 = box
        region = img[y0:y1 + 1, x0:x1 + 1]
        flat = region.reshape(-1, 4)
        if region.size == 0:
            sys.exit("empty box for %s/%s" % (suite, test))
        if not (flat == flat[0]).all():
            uniq = np.unique(flat, axis=0)
            sys.exit("box %s of %s/%s is not flat: %d colours -- fix the box, "
                     "do not widen the tolerance" % (box, suite, test, len(uniq)))
        colour = flat[0]
        for ch, (label, fn) in chans.items():
            value = fn()
            byte = int(colour[ch])
            key = (label, value)
            measured.setdefault(key, {}).setdefault(byte, []).append(
                "%s/%s[%s]" % (suite, test, "RGBA"[ch]))

    if missing:
        print("MISSING goldens (probe skipped): %s" % ", ".join(sorted(set(missing))))

    # A value read as two different bytes means a probe is wrong, not that the
    # hardware is ambiguous.  Refuse to fit anything to that.
    bad = {k: v for k, v in measured.items() if len(v) > 1}
    if bad:
        for (label, value), bymap in sorted(bad.items()):
            print("INCONSISTENT %s (%.9f): %s" % (
                label, value, "; ".join("%d from %s" % (b, ", ".join(s))
                                        for b, s in sorted(bymap.items()))))
        sys.exit("a component value read as more than one byte; probes are wrong")

    table = sorted(((v, label, list(byte.keys())[0], sum(len(s) for s in byte.values()))
                    for (label, v), byte in measured.items()))

    print()
    print("RECOVERED MAP  (%d distinct component values, %d region reads)"
          % (len(table), sum(r[3] for r in table)))
    hdr = "%-28s %14s %6s %4s  " % ("component", "255*x", "hw", "n")
    print(hdr + " ".join("%-19s" % r for r in RULES))
    for value, label, hw, n in table:
        cells = []
        for name, fn in RULES.items():
            b = fn(value)
            cells.append("%-19s" % ("%d" % b if b == hw else "%d  X" % b))
        print("%-28s %14.7f %6d %4d  %s"
              % (label, f32(value) * 255.0, hw, n, " ".join(cells)))

    print()
    survivors = set()
    for name, fn in RULES.items():
        fails = [(label, fn(v), hw) for v, label, hw, _ in table if fn(v) != hw]
        if fails:
            first = fails[0]
            print("%-20s DEAD  %d of %d wrong; e.g. %s -> %d, hardware %d"
                  % (name, len(fails), len(table), first[0], first[1], first[2]))
        else:
            survivors.add(name)
            print("%-20s reproduces all %d" % (name, len(table)))

    # How far the corpus actually constrains the surviving rule.  A bound is
    # not a value: the goldens say the mantissa truncation must drop between
    # these many bits, not that it drops exactly ten.
    print()
    ok_bits = [b for b in range(0, 24)
               if all(min(255, int(math.floor(_drop_mantissa(v, b) * 255.0 + 0.5))) == hw
                      for v, _, hw, _ in table)]
    if ok_bits:
        print("mantissa bits the corpus permits dropping: %d..%d "
              "(committed shader drops 10)" % (min(ok_bits), max(ok_bits)))
    ok_n = [n for n in range(4, 28)
            if all(min(255, int(math.floor(
                math.floor(f32(v) * (2 ** n)) / (2 ** n) * 255.0 + 0.5))) == hw
                for v, _, hw, _ in table)]
    if ok_n:
        print("a fixed-point truncation at 2^-N fits equally for N = %d..%d, so "
              "the corpus does NOT distinguish a relative (float mantissa) "
              "truncation from an absolute one" % (min(ok_n), max(ok_n)))

    print()
    if survivors == EXPECTED_SURVIVORS:
        print("OK: surviving rules = %s, as recorded" % sorted(survivors))
        return 0
    print("CHANGED: surviving rules = %s, recorded %s"
          % (sorted(survivors), sorted(EXPECTED_SURVIVORS)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
