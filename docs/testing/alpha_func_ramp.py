#!/usr/bin/env python3
"""Measure the vertex-alpha ramp the hardware feeds the alpha test (#57).

`Alpha_func` draws four bands and compares each fragment's alpha against
NV097_SET_ALPHA_REF = 0x7F.  Three of the bands are horizontal alpha ramps
under SRC_ALPHA/ONE_MINUS_SRC_ALPHA blending over a known clear colour, which
makes the blend invertible: for a band of known source colour there is exactly
one integer source alpha 0..255 that reproduces a given RGBA output, so the
*fragment alpha the pipeline actually used* can be read back per pixel from a
capture or from a golden.  That is the quantity the alpha test consumes, and
it is what this script measures -- not a pixel count.

The discriminating band is the green one.  It ramps 0.495f -> 0.505f across
512 px, i.e. 126.225 -> 128.775 in eighth-bit units: a span of 2.55 units,
narrow enough that quantising the *endpoints* to bytes (126 -> 129, span 3)
changes the slope by 18%.  Every other gradient in the corpus has endpoints
within 0.25 of a byte over a span of tens of units, so none of them can tell
the two apart.  This one can.

Run:  python3 docs/testing/alpha_func_ramp.py [CAPTUREDIR]

CAPTUREDIR defaults to the pre-fix sweep that issue #57 was filed from.  With
no arguments the script still checks the goldens, which is the load-bearing
half: the claim about silicon does not depend on which of our binaries is on
hand.
"""

import os
import struct
import sys

import numpy as np
from PIL import Image

GOLDENS = os.environ.get(
    "ALPHA_FUNC_GOLDENS", "/home/justin/goldens/results/Alpha_func")
DEFAULT_CAPTURES = (
    "/home/justin/hakux-work/dispatch/results/"
    "z-sweep-002-Alpha_func/captures1")

# alpha_func_tests.cpp, framebuffer 640x480.
FB_W, FB_H = 640, 480
K_TOP = (FB_H - 256.0) / 3.0 * 2.0
BAND_X0, BAND_X1 = (FB_W - 512) // 2, (FB_W - 512) // 2 + 512
CLEAR = np.array([0x22, 0x23, 0x22, 0xFF], float)   # PrepareDraw(0xFF222322)

# (name, source rgb, first and last row inclusive-exclusive, submitted alphas)
BANDS = [
    ("red",   [255, 0, 0], 0,   64,  0.0,   1.0),
    ("blue",  [0, 0, 255], 64,  128, 1.0,   0.0),
    ("green", [0, 255, 0], 128, 192, 0.495, 0.505),
]

FUNCS = ["Never", "LessThan", "Equal", "LessThanOrEqual",
         "GreaterThan", "NotEqual", "GreaterThanOrEqual", "Always"]


def load(path):
    return np.array(Image.open(path)).astype(np.int16)


def trunc_mantissa(x, bits=10):
    """vsh.c colorPrecision(): drop the low `bits` mantissa bits of a float32."""
    u = struct.unpack("<I", struct.pack("<f", x))[0]
    return struct.unpack("<f", struct.pack("<I", u & ((~0 << bits) & 0xFFFFFFFF)))[0]


def blend_table(src_rgb):
    """RGBA the pipeline writes for each integer source alpha 0..255."""
    out = np.zeros((256, 4))
    for a8 in range(256):
        a = a8 / 255.0
        for ch in range(3):
            out[a8, ch] = round(src_rgb[ch] * a + CLEAR[ch] * (1 - a))
        out[a8, 3] = round(a8 * a + CLEAR[3] * (1 - a))
    return out


def recover_ramp(img, y, src_rgb):
    """Per-pixel source alpha across one band row, and whether it is unique."""
    table = blend_table(src_rgb)
    a8 = np.zeros(BAND_X1 - BAND_X0, int)
    exact = np.zeros(BAND_X1 - BAND_X0, bool)
    for i, x in enumerate(range(BAND_X0, BAND_X1)):
        dist = np.abs(table - img[y, x, :4].astype(float)).sum(axis=1)
        cand = np.where(dist == dist.min())[0]
        a8[i] = cand[0]
        exact[i] = dist.min() == 0 and len(cand) == 1
    return a8, exact


def fit_ramp(a8, exact, lo=8, hi=247):
    """Endpoints of a8 as a linear function of t over the band.

    Clamped samples are excluded: red saturates at 255 and blue at 0, and
    including either drags the slope.  t is taken at the pixel centre.
    """
    x = np.arange(BAND_X0, BAND_X1) + 0.5
    t = (x - BAND_X0) / 512.0
    keep = exact & (a8 >= lo) & (a8 <= hi)
    if keep.sum() < 32:
        return None
    slope, intercept = np.polyfit(t[keep], a8[keep].astype(float), 1)
    return intercept, intercept + slope, int(keep.sum())


def bracket_green_slope(path):
    """Bound the green ramp from the alpha test's own coverage, not a fit.

    A fit cannot do this job.  Over the green band the recovered alpha takes
    only the values 126..129 and the blend is stationary in alpha there
    (d/da of a*a + (1-a) is zero at a = 0.5), so the inversion is
    ill-conditioned and hardware and ours fit to the same numbers.  The alpha
    test itself is the precise instrument: AlphaFuncEqual_Enabled draws
    exactly the pixels whose a8 == 127, so its coverage gives the two
    crossings, 126.5 and 127.5, and the 1-unit step between them bounds the
    slope with no model of the blend at all.  This is the coverage mask, which
    is the quantity an alpha test actually decides.
    """
    y0 = int(np.ceil(K_TOP + 128)) + 2
    y1 = int(np.ceil(K_TOP + 192)) - 2
    eq = load(path)
    rows = eq[y0:y1, BAND_X0:BAND_X1, :3].astype(float)
    covered = ~np.all(rows == CLEAR[:3], axis=2)
    cols = np.where(covered.any(axis=0))[0]
    if not len(cols):
        return None
    first, last = BAND_X0 + cols[0], BAND_X0 + cols[-1]
    # a8 crosses 126.5 between (first-1) and first, 127.5 between last and last+1.
    def t(x):
        return (x + 0.5 - BAND_X0) / 512.0
    slope_lo = 1.0 / (t(last + 1) - t(first - 1))
    slope_hi = 1.0 / (t(last) - t(first))
    return first, last, slope_lo, slope_hi


def main():
    caps = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CAPTURES
    have_caps = os.path.isdir(caps)

    print("goldens :", GOLDENS)
    print("captures:", caps if have_caps else "(none on hand; goldens only)")
    print()

    # ---- 1. the ramps, read back from the blend ------------------------
    print("Fragment alpha the pipeline used, recovered per pixel from the")
    print("blended bands of AlphaFuncAlways_Disabled (every band drawn):")
    print()
    print(f"  {'band':6s} {'submitted':>16s} {'x255':>16s} "
          f"{'HARDWARE ramp':>18s} {'OURS ramp':>18s}")
    gold = load(os.path.join(GOLDENS, "AlphaFuncAlways_Disabled.png"))
    ours = (load(os.path.join(caps, "Alpha_func::AlphaFuncAlways_Disabled.png"))
            if have_caps else None)
    fits = {}
    for name, src, dy0, dy1, aL, aR in BANDS:
        y = int(K_TOP) + (dy0 + dy1) // 2
        g_a8, g_ok = recover_ramp(gold, y, src)
        g_fit = fit_ramp(g_a8, g_ok)
        if ours is not None:
            o_a8, o_ok = recover_ramp(ours, y, src)
            o_fit = fit_ramp(o_a8, o_ok)
        else:
            o_fit = None
        fits[name] = (g_fit, o_fit)
        fg = f"{g_fit[0]:7.3f} ->{g_fit[1]:7.3f}" if g_fit else "-"
        fo = f"{o_fit[0]:7.3f} ->{o_fit[1]:7.3f}" if o_fit else "-"
        print(f"  {name:6s} {f'{aL} -> {aR}':>16s} "
              f"{f'{aL*255:.3f} -> {aR*255:.3f}':>16s} {fg:>18s} {fo:>18s}")
    print()

    # ---- 2. the bracket, from coverage rather than a fit ----------------
    # What we do now: vsh.c colorPrecision() drops the low 10 mantissa bits of
    # the vertex colour (#38's measured rule) and the endpoints stay floats, so
    # the interpolator carries 126.2238 -> 128.7607.  Note this is 2.5369, not
    # the naive 2.5500: our own capture dates itself behaviourally here, and a
    # capture from a binary predating 5c2b26db2f would read 2.5500 instead.
    float_slope = (trunc_mantissa(0.505) - trunc_mantissa(0.495)) * 255
    # The candidate: quantise to the byte first, 126 -> 129.
    byte_slope = float(round(trunc_mantissa(0.505) * 255)
                       - round(trunc_mantissa(0.495) * 255))
    gb = bracket_green_slope(
        os.path.join(GOLDENS, "AlphaFuncEqual_Enabled.png"))
    ob = bracket_green_slope(
        os.path.join(caps, "Alpha_func::AlphaFuncEqual_Enabled.png")
    ) if have_caps else None

    print("Green band, bounded by the alpha test's own coverage mask:")
    print(f"  HARDWARE  a8 == 127 on x {gb[0]}..{gb[1]}  =>  slope in "
          f"({gb[2]:.4f}, {gb[3]:.4f})")
    if ob:
        print(f"  OURS      a8 == 127 on x {ob[0]}..{ob[1]}  =>  slope in "
              f"({ob[2]:.4f}, {ob[3]:.4f})")
    print(f"  float endpoints (colorPrecision, as now) predict slope "
          f"{float_slope:.4f}")
    print(f"  byte  endpoints (candidate fix)        predict slope "
          f"{byte_slope:.4f}")
    print()

    ok = True
    if not gb[2] < byte_slope < gb[3]:
        print("FAIL: the byte-endpoint slope 3.0 is outside the hardware "
              "bracket. The goldens changed and #57's finding is void.")
        ok = False
    if gb[2] < float_slope < gb[3]:
        print("FAIL: the hardware bracket no longer excludes the "
              "float-endpoint slope 2.55; the probe has lost its power.")
        ok = False
    if ob:
        if not ob[2] < float_slope < ob[3]:
            print("FAIL: our own capture no longer shows the float-endpoint "
                  "slope. Either the renderer changed -- which is the point "
                  "of the fix, so re-read this document -- or the capture is "
                  "not Alpha_func.")
            ok = False
        if ob[2] < byte_slope < ob[3]:
            print("NOTE: our capture now brackets 3.0 as well. If the vertex "
                  "stage was changed to quantise colour to bytes, this is the "
                  "fix landing and the assertions above need re-pointing.")
    print("OK: hardware interpolates the BYTE-quantised vertex alpha "
          "(126 -> 129); we interpolate the float (126.225 -> 128.775)."
          if ok else "FALSIFIED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
