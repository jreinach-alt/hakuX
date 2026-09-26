# cloud-279: DOT_ZW draws the whole quad one wrong colour (#279)

Analysis only, no device, no code change (glsl/psh.c is held by other
lanes; the hunk is named below for a grant).

## Result

**The colour is a depth buffer, and the defect is a missing depth write,
not a missing colour gradient and not a wrong constant.** `TestDotZW`
(nxdk_pgraph_tests `pixel_shader_tests.cpp:453`) draws its quad with
DOT_ZW, then copies the Z16 buffer under the quad into an R5G6B5 texture
and draws that back over the quad (`DrawZBuffer`, `:658`). So every golden
pixel under the quad IS the 16-bit depth word:
`D = (R>>3)<<11 | (G>>2)<<5 | (B>>3)`, exactly, with no loss.

- **Silicon:** 26,173 distinct depth words, 212..47,805, top-left 9,999.
- **Us:** one depth word, 56,455, on every pixel -- the quad's own vertex
  depth. psh.c's DOT_ZW case computes the stage's dot product, sets
  `t2 = vec4(0.0)`, and leaves the depth write commented out
  (`psh.c:3147`, `// FIXME: gl_FragDepth = ...`). The colour t2 is never
  seen by this test (the final combiner reads TEX0, then DrawZBuffer
  overwrites the quad), so the only observable is depth, and we never
  write it.
- Positive control on the decoder: the console's own capture
  (`hardware/runs/2026-09-19-calib/full/out/run1`) decodes to the golden
  at **100.00% exact**. The instrument can see a hit.

## The rule silicon computes

    z  = dot(texcoord1.xyz, tex0.rgb / 255)     (stage 1, DOT_PRODUCT)
    w  = dot(texcoord2.xyz, tex0.rgb / 255)     (stage 2, DOT_ZW)
    D  = floor(z / w)                           in raw depth-word units

- **Which coordinates:** stage 1's texcoords give z (that is the previous
  stage's `dot1`), stage 2's give w (`dot2`); both dot the *same* texel,
  stage 0's (input_tex = 0), through the ZERO_TO_ONE dot mapping.
- **What it maps to:** the quotient is the depth word itself, in the
  surface's own units (0..65535 on Z16) -- *not* a [0,1] value scaled by
  zmax. The top-left vertex is scale-invariant (row0 = 10000 x row1), so
  z/w = 10000 there whatever the texel, and silicon has 9,999 one pixel
  in. Scaling by 65,535 misses every pixel.
- **Rounding:** floor, like the fixed-point depth path (`zfloor`).
- Interpolation is the usual NV2A one: quad split (v0,v1,v2)+(v0,v2,v3),
  attributes at integer pixel centres, tex0 point-sampled. That is what
  our pipeline already does -- see the control below -- so the fix needs
  nothing but `dot1 / dot2`.

## Numbers (`dotzw_fit.py`, 65,536 px under the quad)

| reading | exact | within 1 | 8x8-block mean abs diff, median / p90 |
|---|---|---|---|
| **ours today** (flat 56,455) | 0.00% | 0.00% | 50,653 / 55,386 |
| z/w x 65535 (normalised depth) | 0.00% | 0.00% | 59,733 / 64,466 |
| z/w, MINUS1_TO_1_D3D mapping | 0.04% | 0.09% | 6,567 / 39,501 |
| z/w, bilinear (not triangle) interpolation | 0.04% | 0.12% | 1,977 / 8,212 |
| z/w, GL pixel centres (+0.5), rint | 0.00% | 0.43% | 14.2 / 33.4 |
| z/w, GL pixel centres, linear tex filter | 1.72% | 5.55% | 12.9 / 87.1 |
| **z/w, NV2A pixel centres, floor (the rule)** | **99.79%** | **100.00%** | **0.0 / 0.0** |

The rule's misses, which are bounded: 65,399 exact, 131 one word high and
6 one word low, none further. Every miss sits where z/w is within 0.0093
of an integer (hits: median 0.25 away). The relative gap is at most
2.9e-7, a few float32 ULP, so these are the divider's precision and
not the rule (the same one-unit shape #16/#52 records for the fixed
depth path). A float32 `dot1/dot2` on the GPU will land on one side or the
other of these; expect up to ~137 px left and not zero.

The discriminators, which are not fits: the scale is set by one vertex
(10000 vs 9999) whatever the texel is, and the triangle split and pixel
centre are the conventions the rest of the pipeline already uses. The only
free choice, floor vs rint, is the one the fixed depth path already makes.

## Control leg

`DotST` sets up stages 0 and 1 identically (STAGE_2D_PROJECTIVE,
DOT_PRODUCT, the same water bump map and texcoord0 layout, input_tex 0)
and consumes `vec2(dot1, dot2)` from the same interpolated pT1/pT2.
It is **0 px differing** on every capture on disk (`captures_on_disk.py`:
7 runs, 09-12 through 09-25, refs ce9c4eecf8 .. 84a67b9cf8). So our
`dot1` and `dot2` are already silicon's, and the proposed hunk touches
only the DOT_ZW case, so DotST's shader text is byte-identical under it.

Captures dated: all 7 on disk draw DotZW as one depth word, the newest
at 84a67b9cf8 (2026-09-25), whose DOT_ZW hunk is identical to master
215ed58e95's `psh.c:3141-3148`. The capture is current.

## The hunk, for a grant

`hw/xbox/nv2a/pgraph/glsl/psh.c`, `case PS_TEXTUREMODES_DOT_ZW:`
(`:3141-3148` at 215ed58e95). Replace the commented-out FIXME with an
override of the depth the `clip` block already declared:

```c
mstring_append_fmt(vars, "vec4 t%d = vec4(0.0);\n", i);
if (ps->state->depth_needed) {
    /* texm3x2depth: the depth word is dot(i-1)/dot(i), in the surface's
     * own units, floored like the fixed-point path.  #279. */
    mstring_append_fmt(vars,
        "zvalue = dot%d / dot%d;\n"
        "zfloor = clamp(floor(zvalue), 0.0, clipRange.y);\n",
        i - 1, i);
}
```

`clip` (declares `zvalue`/`zfloor`) is emitted before `vars`, and the
depth-format switch at `:3641` reads them from `ps->code` after, so an
assignment in `vars` is what reaches `gl_FragDepth`. D16/D24 read
`zfloor`; F16/F24 read `zvalue`.

What this test cannot constrain, so a lane should not claim it:
- the clamp: no pixel saturates (max 47,805 on Z16) and the test's depth
  clip is 0..2^24, so both whether silicon clamps to zmax and whether depth
  clipping or discard applies to the DOT_ZW value are unobserved. The clamp
  above only keeps `gl_FragDepth` inside [0,1] on D16.
- w <= 0 and 0/0: no pixel has w = 0 (row1's weights are non-negative and
  no texel is black here).
- float depth formats (F16/F24): only Z16 fixed is drawn.
- the OpenGL renderer: `depth_needed` is only set on the non-GL path
  (`psh.c:315-320`), so under GL this hunk emits nothing, which is the same
  as today.

**Expected on an arm:** `Pixel_shader/DotZW` from 65,536 differing px to
<= ~137 (the float-divide misses above), with every other Pixel_shader
capture unchanged (DotST included, since its shader text does not move).

## Do not repeat

- Do not read the DotZW golden as colour. It is a Z16 word per pixel.
  Decode it; the R5G6B5 packing is lossless.
- Do not put the quotient through `/ clipRange.y` or any [0,1] scaling
  before the store: it is already in depth-word units.
- The top-left 9,999 vs 10,000 is the pixel-centre tell: GL-centre
  evaluation lands 9,962 there and misses every pixel by ~0.2%.

## Scripts

- `dotzw_fit.py GOLDEN BUMPMAP [CAPTURE...]` decodes the depth, scores
  the captures, and scores each reading above.
- `dotzw_residual.py GOLDEN BUMPMAP` gives where the rule misses and how
  close to an integer.
- `captures_on_disk.py GOLDEN_DIR RESULTS_DIR...` dates every DotZW and
  DotST capture and scores both.

Inputs: golden `~/goldens/results/Pixel_shader/DotZW.png`; bump map
`~/nxdk_pgraph_tests/resources/pixel_shader/water_bump_map.png`.
