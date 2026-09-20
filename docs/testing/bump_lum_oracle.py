#!/usr/bin/env python3
"""An offline oracle for the LUMINANCE multiply of the `Bump env lum`
BUMPENVMAP_LUM path, for scoring rival quantisation rules against the hardware
goldens without a device.

`bump_oracle.py` renders the plain `Bump map` path and scores rival readings of
the OFFSET channels; it answers a question about geometry -- where each texel
lands.  This answers a question about VALUE: given the texel that lands, what
colour does the luminance multiply produce.  It deliberately models no
geometry at all.  The `Bump env lum` picture is two flat colours per quad (the
two checker texels, scaled), so the whole of the value question is "which
colours appear", and a rule that predicts a colour the golden does not hold is
refused whatever the geometry is.  Sensitivity to WHERE they land is
bump_oracle's job and bump_sign_quads.py's.

The ladder, all of it a literal in the test source:

  env texel   a 256x256 checkerboard of 0x7F0000FE / 0x7F202122, bound
              A8R8G8B8 at stage 1 (bump_env_lum_tests.cpp:89) -- as bytes,
              (254,0,0,127) and (34,33,32,127)
  L           component 0 of the stage-0 texel through the bound format's
              view swizzle (gl/constants.h kelvin_color_format_gl_map), read
              by psh.c's append_bump_channel luminance branch.  The bump
              texture holds two values, colors[(y>=2)*2 + (x>=2)] of
              {0x7f014500, 0x80034500, ...} written as SDL RGBA8888, so
              R=0x7f/0x80, G=0x01/0x03, B=0x45 (bump_env_lum_tests.cpp:74,225)
              and the quad straddles the step.  The test ties rsigned to
              bsigned (:164), so the luminance is flagged in two of the four
              quads and both flag states have to be enumerated.
  colour      tex1.rgb * (0.7*L + 0.3), clamped; tex1.a untouched
              (SetBumpEnv(0.3, 0.0, 0.0, 5.0, 0.7, 0.3), :103)
  output      SRC_ALPHA/ONE_MINUS_SRC_ALPHA over a 0xFE202020 clear

The two rival axes:

  --lum    how the filtered luminance channel is read back before the
           multiply: round255 (psh.c's bump_unsigned today) / trunc255 /
           exact / f8round / f8trunc (the last two quantise the assembled
           scale 0.7*L+0.3 to eight bits instead of L)
  --quant  how the scaled colour reaches the 8-bit render target: round
           (today, the RT write rounds) / trunc / none

Gate, checked before any rival is believed (--gate, and refused automatically):
SZ_A8 and SZ_Y16 drive component 0 from the literal ONE, so their scale is
exactly 1.0 and EVERY rival must reproduce their goldens.  A rival table in
which they do not is measuring the blend, not the luminance.

Usage:
  bump_lum_oracle.py --rivals
  bump_lum_oracle.py --rivals --test BumpEnvLum_Y8
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# bump_oracle owns the quad geometry, the RGBA8888/ABGR8888 word order and the
# integer blend over the clear, all already validated against the `Bump map`
# goldens.  Re-deriving them beside it is how the two drift apart.
import bump_oracle as bo

GOLD = bo.GOLD
QUAD, STRIDE = bo.QUAD, bo.STRIDE
ORIGIN_X, ORIGIN_Y = bo.ORIGIN_X, bo.ORIGIN_Y

# bump_env_lum_tests.cpp:74 and :89 -- RGBA8888 and A8R8G8B8 words.
BUMP_COLORS = [0x7F014500, 0x80034500]
CHECKER = (0x7F0000FE, 0x7F202122)
BUMP_SCALE, BUMP_OFFSET = 0.7, 0.3

LUM_MODES = ["round255", "trunc255", "exact", "f8round", "f8trunc"]
QUANT_MODES = ["round", "trunc", "none"]
LABELS = ["Gu Bu", "Gu Bs", "Gs Bu", "Gs Bs"]

# Which stored byte component 0 comes from, per bound format.  'r' is the
# source texel's red byte; 'y' the luminance byte pbkitplusplus writes for the
# Y8 family -- texture_stage.cpp:237 is a static_cast, so it TRUNCATES
# 0.299R + 0.587G + 0.114B; None is the literal ONE.
LUM_SRC = {
    "BumpEnvLum_A8R8G8B8": "r", "BumpEnvLum_A8R8G8B8_L": "r",
    "BumpEnvLum_X8R8G8B8": "r", "BumpEnvLum_X8R8G8B8_L": "r",
    "BumpEnvLum_A8B8G8R8": "r", "BumpEnvLum_A8B8G8R8_L": "r",
    "BumpEnvLum_B8G8R8A8": "r", "BumpEnvLum_B8G8R8A8_L": "r",
    "BumpEnvLum_R8G8B8A8": "r", "BumpEnvLum_R8G8B8A8_L": "r",
    # {GL_GREEN, GL_RED, GL_RED, GL_GREEN} over GL_RG16, so component 0 is the
    # second stored field.  Listed as 'r' because that is what it resolves to
    # in the capture -- see NOTES: R16B16 carries a SECOND defect this
    # value-ladder tool does not model, so run it with a higher --min-px.
    "BumpEnvLum_R16B16": "r", "BumpEnvLum_R16B16_L": "r",
    # {GL_RED, GL_GREEN, GL_RED, GL_GREEN} over GL_RG8.  Component 0 lands on
    # the source texel's BLUE byte, 0x45 -- which is NOT what reading the
    # swizzle off the first stored byte predicts (that would be G, 0x01/0x03,
    # and it is refuted below by both pictures at once).  0x45 is not fitted
    # to the golden: it is the only byte that reproduces OUR capture under
    # round AND the golden under trunc, four colours from one parameter.
    # A third luminance far from the other two, so it is the ladder's own
    # falsifier as much as it is evidence about the quantiser.
    "BumpEnvLum_G8B8": "b", "BumpEnvLum_G8B8_L": "b",
    "BumpEnvLum_Y8": "y", "BumpEnvLum_Y8_L": "y",
    "BumpEnvLum_AY8": "y", "BumpEnvLum_AY8_L": "y",
    "BumpEnvLum_A8Y8": "y",
    "BumpEnvLum_A8": None, "BumpEnvLum_A8_L": None,
    "BumpEnvLum_Y16": None, "BumpEnvLum_Y16_L": None,
}
# The gate: component 0 is the literal ONE, so the scale is exactly 1.0.
GATE_TESTS = ["BumpEnvLum_A8", "BumpEnvLum_Y16"]
DEFAULT_TESTS = ["BumpEnvLum_A8R8G8B8", "BumpEnvLum_A8B8G8R8", "BumpEnvLum_G8B8",
                 "BumpEnvLum_Y8", "BumpEnvLum_AY8", "BumpEnvLum_A8Y8"]


def lum_bytes(src):
    """The two stored luminance bytes the bump texture holds, in order."""
    if src is None:
        return [255.0]                       # the literal ONE, as a byte
    out = []
    for w in BUMP_COLORS:
        r, g, b, _ = bo.rgba8888(w)
        out.append({"r": float(r), "g": float(g), "b": float(b),
                    # texture_stage.cpp:237 is a static_cast, so it TRUNCATES
                    "y": float(int(0.299 * r + 0.587 * g + 0.114 * b))}[src])
    return out


def scales(src, flagged, lum, steps):
    """Every scale 0.7*L + 0.3 the quad can reach, for one flag state.

    Between the two texels the bilinear filter sweeps the whole interval, so
    an unquantised rule reaches a continuum (sampled `steps` ways) and a
    quantised one reaches the integers in between.
    """
    lo, hi = min(lum_bytes(src)), max(lum_bytes(src))
    if src is None:
        flagged = False          # psh.c's tex_comp0_const branch, 93196d2d05
    raw = np.linspace(lo, hi, steps)
    if flagged:
        # sampler signs each texel over 127 (-128 clamps to -1), filters, and
        # bump_snorm rounds the filtered value back over 127; sign3_to_0_to_1
        # then folds it into 0..1.
        s = np.where(raw >= 128.0, raw - 256.0, raw)
        s = np.maximum(s / 127.0, -1.0)
        v = s * 127.0
        x = (np.round(v) if lum == "round255" else
             np.floor(v) if lum == "trunc255" else v) / 128.0
        L = np.where(x >= 0.0, x / 2.0, 1.0 + x / 2.0)
    else:
        L = (np.round(raw) if lum == "round255" else
             np.floor(raw) if lum == "trunc255" else raw) / 255.0
    f = BUMP_SCALE * L + BUMP_OFFSET
    if lum == "f8round":
        f = np.round(f * 255.0) / 255.0
    elif lum == "f8trunc":
        f = np.floor(f * 255.0) / 255.0
    return np.unique(f)


def predict(src, lum, quant, steps):
    """The set of output colours the rival can produce in one quad."""
    ca, cr, cg, cb = bo.CLEAR_ARGB
    out = set()
    for flagged in (False, True):
        for f in scales(src, flagged, lum, steps):
            for word in CHECKER:
                tr, tg, tb, ta = bo.abgr8888(word)
                a = ta / 255.0
                px = []
                for t, d in ((tr, cr), (tg, cg), (tb, cb)):
                    s = t * f
                    if quant == "round":
                        s = round(s)
                    elif quant == "trunc":
                        s = float(int(s))
                    px.append(int(round(min(max(s, 0.0), 255.0) * a + d * (1 - a))))
                px.append(int(round(ta * a + ca * (1 - a))))
                out.add(tuple(px))
    return out


def observed(path, min_px):
    """The colours a capture actually holds inside the four quads, above a
    population floor so the checker-edge pixels do not pollute the ladder."""
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.int64)
    seen = {}
    for gs in (0, 1):
        for bs in (0, 1):
            x, y = ORIGIN_X + bs * STRIDE, ORIGIN_Y + gs * STRIDE
            q = a[y:y + QUAD, x:x + QUAD].reshape(-1, 4)
            v, n = np.unique(q, axis=0, return_counts=True)
            for c, k in zip(v, n):
                t = tuple(int(z) for z in c)
                if t[:3] == (255, 255, 255):
                    continue          # the quad border the test leaves white
                seen[t] = seen.get(t, 0) + int(k)
    return {c for c, k in seen.items() if k >= min_px}


def verdict(src, gold, lum, quant, steps):
    p = predict(src, lum, quant, steps)
    return sorted(p - gold), sorted(gold - p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="append", dest="tests")
    ap.add_argument("--rivals", action="store_true")
    ap.add_argument("--lum", default="round255", choices=LUM_MODES)
    ap.add_argument("--quant", default="round", choices=QUANT_MODES)
    ap.add_argument("--min-px", type=int, default=1000,
                    help="ignore colours rarer than this across the four quads")
    ap.add_argument("--steps", type=int, default=4097)
    ap.add_argument("--capture", help="a result dir to score beside the golden")
    a = ap.parse_args(argv)

    # --- gate ---------------------------------------------------------------
    bad = []
    for t in GATE_TESTS:
        gold = observed("%s/Bump_env_lum/%s.png" % (GOLD, t), a.min_px)
        for lum in LUM_MODES:
            for quant in QUANT_MODES:
                extra, miss = verdict(LUM_SRC[t], gold, lum, quant, a.steps)
                if extra or miss:
                    bad.append((t, lum, quant, extra, miss))
    print("gate: literal-ONE classes %s reproduced by all %d rivals: %s"
          % ("/".join(GATE_TESTS), len(LUM_MODES) * len(QUANT_MODES),
             "yes" if not bad else "NO"))
    for t, lum, quant, extra, miss in bad[:8]:
        print("   %s %s/%s extra=%s missing=%s" % (t, lum, quant, extra, miss))
    if bad:
        print("   the blend model is wrong; no rival below means anything")
        return 1
    print()

    tests = a.tests or DEFAULT_TESTS
    combos = ([(l, q) for l in LUM_MODES for q in QUANT_MODES]
              if a.rivals else [(a.lum, a.quant)])
    for test in tests:
        gold = observed("%s/Bump_env_lum/%s.png" % (GOLD, test), a.min_px)
        print("%s  golden holds %s" % (test, sorted(gold)))
        if a.capture:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import captures as capmod
            root = capmod.resolve(a.capture, "Bump_env_lum::*.png")
            ours = observed(os.path.join(root, "Bump_env_lum::%s.png" % test),
                            a.min_px)
            print("%s  we emit      %s" % (" " * len(test), sorted(ours)))
        print("   %-10s%-7s%-8s %s" % ("lum", "quant", "verdict", "colours"))
        for lum, quant in combos:
            extra, miss = verdict(LUM_SRC[test], gold, lum, quant, a.steps)
            note = []
            if extra:
                note.append("emits %s, absent from the golden" % extra)
            if miss:
                note.append("never emits %s, which the golden holds" % miss)
            print("   %-10s%-7s%-8s %s" % (lum, quant,
                  "ok" if not note else "REFUSED", "; ".join(note) or "exact"))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
