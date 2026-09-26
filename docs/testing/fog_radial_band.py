#!/usr/bin/env python3
"""Recover the program-mode RADIAL fog coordinate from the Fog goldens (#41).

    fog_radial_band.py [--goldens DIR]

`Fog_gen`'s `VS radial` cell is the largest single residue on the structural
board, 2,172,192 channels over six captures, and it has twice been written up
as *unfalsifiable*: the golden holds one colour across the whole region we
differ in, so -- the argument went -- every model that saturates the fog
scores identically and the corpus cannot choose between them.

That argument is wrong, and this script is the refutation. Two of the six
captures are **not saturated**. `FogGen_VS-exp-radial` and
`FogGen_VS-exp_abs-radial` hold (254, 0, 1) on all 181,016 drawn pixels, one
step short of the fog colour, and one step short of a clip is an inversion.
`unfalsifiable-goldens.md` already carries the rule that catches this -- "a
single-colour golden still pins a value exactly if that colour is a partial
mix rather than a clip" -- and still lists this cell as its headline case.

The chain is three measurements, each read out of a golden:

1. **The transfer function is invertible.** `fog_gen_tests.cpp` sets diffuse
   to (0, 0, 1) and the fog colour to (1, 0, 0), and its final combiner is
   `f*diffuse + (1-f)*fog`. Neither end clips, so the 8-bit fog factor is the
   blue channel and 255 minus the red, and every drawn pixel carries it.

2. **The hardware's exp response is calibrated, not assumed.** `psh.c` warns
   that silicon's own 2^x approximation sits above the true value at small
   factors, which is exactly the region this inversion lands in, so assuming
   either truncation or rounding would beg the question. The `Fog_param`
   sweeps drive a *known* coordinate through that region at three different
   multipliers, so the fogX window that reads as each 8-bit factor is
   measured, and the three sweeps must agree.

3. **The windows intersect.** Six mode functions, one coordinate.

Output is the coordinate window, plus the two things that decide what to do
with it: how much a saturating model would still leave (it is not zero), and
where the same band sits in the *fixed function* radial captures.
"""

import argparse
import collections
import math
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("needs numpy and pillow")

DEFAULT_GOLDENS = "/mnt/wslg/distro/home/justin/goldens/results"

# ---------------------------------------------------------------------------
# Test geometry, from nxdk_pgraph_tests.

# fog_param_tests.cpp: 24px quads, 1px spacing, 60/70 padding, coord -1.4 +0.01
PARAM = dict(qw=24.0, sp=60.0, tp=70.0, sh=1.0, sv=1.0, c0=-1.4, dc=0.01)
# fog_gen_tests.cpp: 22px quads, 2px spacing, 48/70 padding, coord 50 -0.2
GEN = dict(qw=22.0, sp=48.0, tp=70.0, sh=2.0, sv=2.0, c0=50.0, dc=-0.2)

FB_W, FB_H = 640.0, 480.0

# fog_gen_tests.cpp constants
LN256, SQRT_LN256, DENSITY = 5.5452, 2.3548, 0.025
FOG_END = 200.0
M_LINEAR = -1.0 / FOG_END
B_LINEAR = 1.0 + -FOG_END * M_LINEAR
M_EXP = -DENSITY / (2.0 * LN256)
M_EXP2 = -DENSITY / (2.0 * SQRT_LN256)
# fog_param_tests.cpp ZeroBias() for exp
PARAM_BIAS_EXP = 1.51

GEN_BG = (0x23, 0x26, 0x23)


def grid(cfg):
    """The quad list a Fog test draws, in draw order."""
    qw = cfg["qw"]
    right, bottom = FB_W - (cfg["sp"] + qw), FB_H - qw
    out, left, top, c, i = [], cfg["sp"], cfg["tp"], cfg["c0"], 0
    while top < bottom:
        out.append((i, left, top, c))
        left += qw + cfg["sh"]
        if left >= right:
            left, top = cfg["sp"], top + qw + cfg["sv"]
        c += cfg["dc"]
        i += 1
    return out


def factor_at(img, left, top, qw, inset=4):
    """The 8-bit fog factor at a quad's centre, or None if it is not uniform.

    Requires red + blue == 255, which is what says the pixel really is the
    f*(0,0,1) + (1-f)*(1,0,0) mix and not background or printed text.
    """
    x, y = int(left + qw / 2), int(top + qw / 2)
    blk = img[y - 3:y + 3, x - 3:x + 3]
    r, b = blk[..., 0].astype(int), blk[..., 2].astype(int)
    if r.min() != r.max() or b.min() != b.max():
        return None
    if int(r[0, 0]) + int(b[0, 0]) != 255:
        return None
    return int(b[0, 0])


def load(root, suite, name):
    p = os.path.join(root, suite, name + ".png")
    if not os.path.exists(p):
        sys.exit("missing golden: %s" % p)
    return np.array(Image.open(p).convert("RGB"))


# ---------------------------------------------------------------------------


def calibrate_exp(root):
    """Measure, per 8-bit factor, the fogX window silicon's exp unit reports.

    Three multipliers sweep the same fogX range at different coordinate
    steps; a window that did not agree between them would mean the model of
    fogX itself is wrong, not just its quantisation.
    """
    obs = collections.defaultdict(list)
    per_mult = {}
    for mult in (-2.0, -1.0, -0.5):
        img = load(root, "Fog_param", "FogParam%.2f-exp" % mult)
        seen = collections.defaultdict(list)
        for (_, l, t, c) in grid(PARAM):
            v = factor_at(img, l, t, PARAM["qw"])
            if v is None:
                continue
            fog_x = PARAM_BIAS_EXP + c * mult - 1.5
            obs[v].append(fog_x)
            seen[v].append(fog_x)
        per_mult[mult] = seen
    return obs, per_mult


def band_for(obs, v):
    """(low, high) fogX bounds for factor v, exclusive, from its neighbours."""
    lo = max(obs[v - 1]) if (v - 1) in obs and obs[v - 1] else -math.inf
    hi = min(obs[v + 1]) if (v + 1) in obs and obs[v + 1] else math.inf
    return lo, hi


def our_factor(mode, c):
    """psh.c's model of the fog factor, so the two windows can be compared."""
    if mode in ("linear", "linear_abs"):
        d = abs(c) if mode == "linear_abs" else c
        f = min(max(B_LINEAR + d * M_LINEAR - 1.0, 0.0), 1.0)
        return math.floor(f * 255.0 + 0.03125) / 255.0
    if mode in ("exp", "exp_abs"):
        fog_x = c * M_EXP
        f = 2.0 ** (-16.0 * abs(fog_x)) if mode == "exp_abs" \
            else 2.0 ** (16.0 * fog_x)
    else:
        fog_x = c * M_EXP2
        f = 2.0 ** (-32.0 * fog_x * fog_x)
    return min(max(f, 0.0), 1.0)


MODES = ["linear", "exp", "exp2", "exp_abs", "exp2_abs", "linear_abs"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldens", default=DEFAULT_GOLDENS)
    args = ap.parse_args()
    root = args.goldens

    # ---- 1. what the six VS radial goldens actually hold -----------------
    print("== FogGen_VS-*-radial: the drawn region, colour by colour ==")
    drawn_colour = {}
    for m in MODES:
        g = load(root, "Fog_gen", "FogGen_VS-%s-radial" % m)
        h, w, _ = g.shape
        flat = g.reshape(-1, 3)
        cnt = collections.Counter(map(tuple, flat))
        # the mix pixels are exactly those with r + b == 255 and g == 0
        mix = [(c, n) for c, n in cnt.items()
               if c[1] == 0 and c[0] + c[2] == 255]
        assert len(mix) == 1, (m, mix)
        (colour, n), = mix
        colour = tuple(int(v) for v in colour)
        drawn_colour[m] = (colour, n)
        clipped = "CLIPPED" if colour[2] == 0 else "interior -> INVERTIBLE"
        print("  %-12s %-15s x%-7d f8=%-3d  %s"
              % (m, str(colour), n, colour[2], clipped))

    # ---- 2. calibrate the exp unit --------------------------------------
    obs, per_mult = calibrate_exp(root)
    print("\n== silicon's exp response, from the Fog_param sweeps ==")
    for v in sorted(k for k in obs if k <= 4):
        per = " ".join("%+.2f:[%+.4f,%+.4f]"
                       % (mu, min(s[v]), max(s[v]))
                       for mu, s in per_mult.items() if s.get(v))
        print("  f8=%-2d fogX in [%+.4f, %+.4f]  n=%-4d  %s"
              % (v, min(obs[v]), max(obs[v]), len(obs[v]), per))
    lo_x, hi_x = band_for(obs, 1)
    print("  => f8=1 iff fogX in (%+.4f, %+.4f), from 3 independent sweeps"
          % (lo_x, hi_x))

    # ---- 3. invert ------------------------------------------------------
    print("\n== the coordinate, per mode ==")
    lo, hi = -math.inf, math.inf
    for m in MODES:
        f8 = drawn_colour[m][0][2]
        if m in ("exp", "exp_abs"):
            # fogX = coord * M_EXP, bias 1.5 cancels; M_EXP < 0 flips the order
            a, b = hi_x / M_EXP, lo_x / M_EXP
        elif m in ("linear", "linear_abs"):
            # floor(255 f + 1/32) == 0  <=>  f < (1 - 1/32)/255
            fmax = (1.0 - 1.0 / 32.0) / 255.0
            a, b = (B_LINEAR - 1.0 - fmax) / -M_LINEAR, math.inf
        else:
            fmax = (1.0 - 1.0 / 32.0) / 255.0
            a = math.sqrt(-math.log2(fmax) / 32.0) / -M_EXP2
            b = math.inf
        lo, hi = max(lo, a), min(hi, b)
        print("  %-12s f8=%d  ->  coord in (%.2f, %s)"
              % (m, f8, a, "%.2f" % b if b != math.inf else "inf"))
    print("\n  MEASURED: coord in (%.2f, %.2f), width %.2f"
          % (lo, hi, hi - lo))

    # what OUR shader needs, which is not the same window: psh.c rounds the
    # exponential modes and does not model silicon's 2^x approximation.
    ours = [c / 100.0 for c in range(15000, 30000)]
    ok = [c for c in ours
          if all(round(255 * our_factor(m, c)) == drawn_colour[m][0][2]
                 for m in MODES)]
    print("  our pipeline reproduces all six for coord in (%.2f, %.2f]"
          % (min(ok) - 0.01, max(ok)))
    print("  overlap: (%.2f, %.2f]" % (max(lo, min(ok) - 0.01), min(hi, max(ok))))

    # ---- 4. what a saturating model would still leave --------------------
    print("\n== cost of the 'just fully fog it' model ==")
    total = 0
    for m in MODES:
        colour, n = drawn_colour[m]
        ch = n * (2 if colour[2] != 0 else 0)
        total += ch
        print("  FogGen_VS-%-12s %6d px drawn, saturating leaves %7d channels"
              % (m + "-radial", n, ch))
    print("  total %d channels, against %d today -- a saturating fix is a "
          "67%% cut, not a fix" % (total, sum(n * 2 for _, n in
                                              drawn_colour.values())))

    # ---- 5. where that band sits under fixed function --------------------
    print("\n== the same band in FogGen_FF-exp-radial ==")
    ff = load(root, "Fog_gen", "FogGen_FF-exp-radial")
    gq = grid(GEN)
    inband, last = [], None
    for (i, l, t, _) in gq:
        s = ff[int(t) + 4:int(t + GEN["qw"]) - 4,
               int(l) + 4:int(l + GEN["qw"]) - 4, 2]
        if s.max() <= 1:
            inband.append(i)
        last = i
    print("  %d of %d fixed-function quads read f8<=1 across their interior: %s"
          % (len(inband), len(gq), inband))
    print("  (22 quads per row, so those are the corners of the final row --"
          " the farthest points in the scene)")
    print("  the last quad drawn is i=%d -- %s"
          % (last, "IN that band" if last in inband else "NOT in that band"))

    # How far the fixed-function radial distance travels over the same
    # vertices, which is what the program-mode coordinate's <18 has to be
    # compared against. Read off the least-fogged quad; the quantiser is
    # near-exact at large factors, so this end needs no calibration.
    best = max(factor_at(ff, l, t, GEN["qw"]) or 0 for (_, l, t, _) in gq)
    near = math.log2(best / 255.0) / 16.0 / M_EXP
    print("  least-fogged quad reads f8=%d -> radial distance ~%.1f, so the"
          % (best, near))
    print("  fixed-function distance spans ~%.0f over the same 374 quads,"
          % (hi - near))
    print("  against <%.2f of variation in the program-mode coordinate (%.1f%%)"
          % (hi - lo, 100.0 * (hi - lo) / (hi - near)))


if __name__ == "__main__":
    main()
