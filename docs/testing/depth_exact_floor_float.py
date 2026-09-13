#!/usr/bin/env python3
"""An exact-floor oracle for the `Depth buffer` FLOAT-Z depth captures (#52).

    depth_exact_floor_float.py RESULTDIR/captures1 [NAME ...]

`depth_exact_floor.py` settled the z24 *fixed* cell by computing what a correct
renderer must write, in exact integers, without reference to the goldens. This
is the same idea for the `FZy` cells, which that file deliberately excludes.

Why the float cells need their own oracle, and why it is not just a rescale.
`DepthFormatTests::CreateGeometry` feeds the GPU `format.fixed_to_float(n)` for
each integer vertex depth `n` (`depth_format_tests.cpp:144`), and for a float Z
surface that is `z24_to_float` / `z16_to_float` -- it reads `n` *as an encoding*
and hands the GPU the value it denotes. So:

  * the vertex VALUES are `decode(n)`, not `n`;
  * the rasteriser interpolates those values linearly in screen space;
  * the fragment shader re-encodes, `floatBitsToUint(zvalue) >> 7` for f24
    (`glsl/psh.c`), which is a FLOOR onto the f24 lattice.

Encoding is a logarithmic map, so linear interpolation of the values is *not*
linear in the stored word. The fixed cell's integer oracle therefore does not
transfer, and a residual that looks structural in word space can be exactly
right in value space. That is the trap this file exists to avoid: #52 and #16
both carried a "float Z is structural" label that came from differencing
encoded words as if they were values.

What it computes, per pixel, is the largest f24 (or f16) word whose value does
not exceed the exact rational depth at the pixel centre -- `floor` onto the
encoding lattice, in exact arithmetic via `fractions.Fraction`, with the LESS
depth test replayed in word space (legitimate, because the encoding is
monotonic in the value for non-negative values).

Reading the output. Three columns matter and they answer different questions:

  ours-oracle    our distance from what a correct renderer must write. If this
                 is 0, our depth path is exact and any remaining disagreement
                 with the golden is silicon's, not ours.
  gold-oracle    silicon's own distance from it -- its edge walk, the floor
                 under any fix.
  ours-gold      what `score_sweep` reports, which cannot separate the two.

`ours == oracle` is the falsifier to state for a change here, never a
differing-pixel total against the golden: a pixel can be wrong for our reason
and silicon's at once and the total cannot tell them apart.

WHERE #52's REMAINING z24 FLOAT RESIDUAL ACTUALLY IS
----------------------------------------------------

Measured over all 18 `DepthFmt_z24_C{n,y}_FZy_*_ZB` captures of
`1789272013-depth52-fix2` (ref `91b0897e01`), decoding the zeta word rather
than differencing channels. The 12,816 px are two families that want different
explanations and must not be added together:

    quad split (|d| > 1)   11,768 px   11,648 of them -- 99.0% -- in GRID
                                       ROW 0, 112 in grid row 1, 8 elsewhere
    +-1 floor               1,048 px   948 OUTSIDE the grid entirely, i.e. the
                                       bottom, right and big quads; the family
                                       cell 2 settled on

The quad-split deltas are exactly `right_offset * (2k+1)/16` for
`right_offset = 12,584` -- 786.5, 2,359.5, 3,932.5 and the full 12,584 -- in
perfectly matched pairs, 3,456 above silicon against 3,456 below on `Mfeffff`.
The half-integers are why both 12,584 and 12,585, and both 786 and 787, appear.

Grid rows 2 to 31 are bit-exact on edges identical to row 0's, which is what
rules out an edge rule. And the whole quad-split family sits in the **seven
smallest binades**: the f24 exponent field of our word there is 1-7 on 11,760
of 11,768 px (181 on the remaining 8). So this is not a general interpolation
defect. It is the near-zero end of the encoding, where the test's
`z24_to_float(n)` for small `n` gives values of order 1e-38, one or two
binades above the subnormal boundary.

Two readings were tested and killed here rather than in `psh.c`:

  * *the F16 flush-to-zero rule, one format over.* The F24 path has no
    exponent-field-zero guard where the F16 path does, so a subnormal `zvalue`
    would encode as a non-zero mantissa the NV2A reads as zero. REFUTED: 0 of
    the 876 differing pixels on `Mfeffff` has a zero exponent field, in ours
    or in the golden.
  * *silicon's edge walk, as in cell 2.* Absent from 30 of the 32 grid rows
    whose edges are identical to the two that carry it.

`psh.c` is therefore unchanged: there is no measured mechanism to change it
for. Naming the binade range is the handover -- a value of 1e-38 carried as a
fraction of `f24_max = 1e30` is 1e-68 and flushes to zero in float32 long
before the fragment shader sees it, so the next step is the depth range in the
vertex path, not the encode.

WHAT THIS ORACLE CANNOT SEE, and both limits are load-bearing
-------------------------------------------------------------

**1. The big quad of the z24 float cell is not a well-posed question at all.**
`CreateGeometry` uses `back_z = format.max_depth - 1` and passes
`fixed_to_float(back_z)`, which for a float Z surface is `z24_to_float`, i.e.
`bitcast(0xFFFFFE << 7)` = `bitcast(0x7FFFFF00)` -- exponent field all ones,
mantissa non-zero, a **NaN**. So the guest hands the GPU a NaN vertex depth
over 85,192 px per capture, and what any renderer writes there is a property of
its NaN handling rather than of its depth arithmetic. Those pixels are reported
in the `unmodell` column and excluded from every count; they are not an
accuracy defect and cannot be fixed into agreement.

(The guest's own `z24_to_float` and `float_to_z24` are not inverses --
`float_to_z24` subtracts a 0x3000000 bias that `z24_to_float` does not add
back, `src/pbkit_ext.cpp:24,34`. `z24_to_float` is the one the geometry uses,
and the one the emulator's `convert_f24_to_float` matches.)

**2. Its z24 float columns are WRONG and must not be used.** Measured on
`1789272013-depth52-fix2`, `ours-oracle` and `gold-oracle` come back EQUAL TO
THE DIGIT on every z24 float capture (1,384/1,384, 34,992/34,992,
68,408/68,408) at a max deviation of 1,786,455 -- and per grid row the two
renderers agree with each other on 1,984 of 1,984 px of grid rows 2 and 3
while both differ from this oracle on all 1,984. Two independent renderers do
not agree to the digit while both diverge from the truth by six figures: that
convicts the **oracle**, not them.

The likely missing piece is the float-Z depth range -- a value is carried
through the vertex path as a fraction of `f24_max = 1e30` rather than in guest
depth units, which this file models as a plain linear interpolation of decoded
values. Until that is modelled, **trust the z16 columns only**; there the
oracle bounds both sides within one lattice step (66 against 225 on
`M00ffff`, max 1 either way), which is what a working oracle looks like.

The self-check at the end of `main` prints all of this rather than letting the
numbers read as a renderer defect -- which is how this cell got a "structural"
label twice already.
"""

import os
import struct
import sys
from fractions import Fraction

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from depth_exact_floor import W, H, GOLD, f32, grid_vertex_depths  # noqa: E402


def decode24(n):
    """convert_f24_to_float: the f24 word is the top 24 bits of a float32.

    Returns None when the encoding does not denote a finite value. This is not
    a corner case here: the test's big quad uses `back_z = max_depth - 1`, and
    `z24_to_float(0xFFFFFE)` bitcasts 0x7FFFFF00, whose exponent field is all
    ones -- a NaN. See the UNMODELLED note in the module docstring.
    """
    if n == 0:
        return Fraction(0)
    v = struct.unpack("f", struct.pack("I", (n & 0xFFFFFF) << 7))[0]
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return Fraction(v)


def decode16(n):
    """convert_f16_to_float: (f16 << 11) + 0x3C000000."""
    if n == 0:
        return Fraction(0)
    v = struct.unpack("f", struct.pack("I", ((n & 0xFFFF) << 11)
                                       + 0x3C000000))[0]
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return Fraction(v)


def float32_floor(v):
    """The largest float32 <= v, as its bit pattern. v is a non-negative Fraction."""
    if v <= 0:
        return 0
    f = np.float32(float(v))
    # float() rounds to nearest double then to nearest float32; step down while
    # the candidate exceeds v, and up while its successor still does not.
    while Fraction(float(f)) > v:
        f = np.nextafter(f, np.float32(0), dtype=np.float32)
    while True:
        nxt = np.nextafter(f, np.float32(np.inf), dtype=np.float32)
        if Fraction(float(nxt)) <= v:
            f = nxt
        else:
            break
    return struct.unpack("I", struct.pack("f", float(f)))[0]


def encode24_floor(v):
    """Largest f24 word whose value does not exceed the exact rational v.

    Truncating the 7 low mantissa bits of the float32 floor of v gives the
    largest f24 <= v, because dropping low mantissa bits only ever decreases
    the value and the f24 lattice is the float32 lattice with those bits zero.
    """
    if v <= 0:
        return 0
    return min(float32_floor(v) >> 7, 0xFFFFFF)


def encode16_floor(v):
    """Largest f16 word whose value does not exceed v.

    The lowest binade has no representation: exponent field zero means zero, so
    everything below 2^-6 encodes as 0. See the F16 note in glsl/psh.c.
    """
    if v <= 0:
        return 0
    bits = float32_floor(v)
    if bits < 0x3C800000:
        return 0
    return min((bits - 0x3C000000) >> 11, 0xFFFF)


def oracle_float(cutoff, max_depth, bits):
    """floor-onto-the-encoding-lattice depth after LESS, plus a modelled mask.

    Returns (z, modelled). `modelled` is False wherever a primitive that could
    have covered the pixel had a non-finite vertex depth, so that pixel's
    oracle value is not defined and must be excluded from any count. Saying so
    is the point: the test's big quad IS such a primitive for z24 float, and an
    oracle that silently modelled it would be inventing the answer over 153,600
    pixels.
    """
    dec = decode24 if bits == 24 else decode16
    enc = encode24_floor if bits == 24 else encode16_floor
    z = np.full((H, W), cutoff, dtype=np.int64)
    covered = np.zeros((H, W), dtype=bool)   # a MODELLED primitive drew here
    poisoned = np.zeros((H, W), dtype=bool)  # a NON-FINITE primitive drew here

    def unmodelled(x0, x1, y0, y1):
        poisoned[y0:y1, x0:x1] = True

    def blit(x0, x1, y0, y1, words, axis):
        """words is the per-column (axis=0) or per-row (axis=1) encoded depth."""
        v = np.asarray(words, dtype=np.int64)
        v = v[None, :] if axis == 0 else v[:, None]
        sub = z[y0:y1, x0:x1]
        m = v < sub                          # NV097_SET_DEPTH_FUNC_V_LESS
        sub[m] = np.broadcast_to(v, sub.shape)[m]
        covered[y0:y1, x0:x1] = True

    # grid of 8x8 quads, front to back, row major; VALUE linear in x
    for j, row in enumerate(grid_vertex_depths(max_depth)):
        y0 = 48 + 12 * j
        for i, (lz, rz) in enumerate(row):
            x0 = 134 + 12 * i
            vl, vr = dec(lz), dec(rz)
            if vl is None or vr is None:
                unmodelled(x0, x0 + 8, y0, y0 + 8)
                continue
            words = [enc(vl + (vr - vl) * Fraction(2 * k + 1, 16))
                     for k in range(8)]
            blit(x0, x0 + 8, y0, y0 + 8, words, 0)

    # bottom quad: 3/4 max depth on the left to 0 on the right
    vl, vr = dec((max_depth - 1) * 3 // 4), dec(0)
    if vl is None or vr is None:
        unmodelled(132, 492, 430, 435)
    else:
        words = [enc(vl + (vr - vl) * Fraction(2 * k + 1, 720))
                 for k in range(360)]
        blit(132, 492, 430, 435, words, 0)

    # right quad: 1 at the top to half max depth at the bottom
    vt, vb = dec(1), dec(max_depth // 2)
    if vt is None or vb is None:
        unmodelled(502, 510, 45, 435)
    else:
        words = [enc(vt + (vb - vt) * Fraction(2 * k + 1, 780))
                 for k in range(390)]
        blit(502, 510, 45, 435, words, 1)

    # big quad: 2/3 max depth at the top to max depth at the bottom
    back = max_depth - 1
    vt, vb = dec(back * 2 // 3), dec(back)
    if vt is None or vb is None:
        unmodelled(128, 512, 40, 440)
    else:
        words = [enc(vt + (vb - vt) * Fraction(2 * k + 1, 800))
                 for k in range(400)]
        blit(128, 512, 40, 440, words, 1)
    # A pixel a non-finite primitive drew over is undefined UNLESS a modelled
    # primitive also drew there and is nearer. The grid quads sit inside the
    # big quad's rectangle and are drawn first at far smaller depths, so under
    # LESS they own their pixels and the big quad cannot take them back --
    # provided a NaN loses the depth comparison, which IEEE requires and which
    # the 0 residual on those pixels then corroborates. Pixels the NaN
    # primitive alone covers stay unmodelled, and are counted and reported.
    modelled = covered | ~poisoned
    return z, modelled


def zeta_word(path, bits):
    """A `_ZB` capture is the raw zeta word, and the container depends on WIDTH.

    `TestHost::SaveZBuffer` picks the SDL format from the zeta surface's width
    alone: a Z16 surface -- fixed *or* float -- is RGB565, and Z24S8 is
    ARGB8888 with the stencil in B. Reading a z16 capture as ARGB, or a z24 one
    as RGB, is the misread that made both cells look structural.
    """
    a = np.array(Image.open(path).convert("RGBA"), dtype=np.int64)
    if bits == 24:
        return (a[:, :, 3] << 16) | (a[:, :, 0] << 8) | a[:, :, 1]
    r = a[:, :, 0] >> 3
    g = a[:, :, 1] >> 2
    b = a[:, :, 2] >> 3
    return (r << 11) | (g << 5) | b


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    capdir = argv[1]
    names = argv[2:]
    if not names:
        names = sorted(
            f.split("::", 1)[1][:-4] for f in os.listdir(capdir)
            if f.startswith("Depth_buffer::")
            and "_FZy_" in f and f.endswith("_ZB.png"))
    print("%-34s %10s %11s %11s %9s %9s %9s"
          % ("capture", "ours-gold", "ours-oracle", "gold-oracle",
             "max|o-or|", "max|g-or|", "unmodell"))
    tot = [0, 0, 0]
    suspect = []
    n_cap = 0
    for name in names:
        cutoff = int(name.split("_M")[1].split("_")[0], 16)
        bits = 16 if "_z16_" in name else 24
        max_depth = 0xFFFF if bits == 16 else 0xFFFFFF
        gp = os.path.join(GOLD, name + ".png")
        op = os.path.join(capdir, "Depth_buffer::%s.png" % name)
        if not (os.path.exists(gp) and os.path.exists(op)):
            print("%-34s  (missing capture or golden)" % name)
            continue
        g = zeta_word(gp, bits)
        o = zeta_word(op, bits)
        idl, mod = oracle_float(cutoff, max_depth, bits)
        a = int((o != g).sum())
        b = int(((o != idl) & mod).sum())
        c = int(((g != idl) & mod).sum())
        tot[0] += a
        tot[1] += b
        tot[2] += c
        n_cap += 1
        if b and b == c:
            suspect.append(name)
        print("%-34s %10d %11d %11d %9d %9d %9d"
              % (name, a, b, c,
                 int(np.abs((o - idl)[mod]).max()) if mod.any() else 0,
                 int(np.abs((g - idl)[mod]).max()) if mod.any() else 0,
                 int((~mod).sum())))
    print("%-34s %10d %11d %11d" % ("TOTAL", tot[0], tot[1], tot[2]))
    if suspect:
        print()
        print("ORACLE SELF-CHECK FAILED on %d of %d captures: ours-oracle and "
              "gold-oracle" % (len(suspect), n_cap))
        print("are equal and non-zero. Two independent renderers do not agree "
              "to the digit")
        print("while both diverge from the truth, so the ORACLE is wrong "
              "there, not them.")
        print("Do not report these as a defect. See limitation 2 in the "
              "module docstring")
        print("(the float-Z depth range clamp is not modelled).")
        for name in suspect:
            print("    %s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
