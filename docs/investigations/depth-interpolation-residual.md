# Depth ±1 residual after exact-floor (#32)

After the split-floor fix, `Depth_buffer` z24 captures still differ from the
goldens by ±1 on ~3 % of pixels. This note separates what is ours from what
is the hardware's.

## An exact model of the test

`DepthFmt_z24_*_Mffffff`: 31×32 quads of 8×8 px with z linear in x
(`lz → rz`, integer vertex z, |Δz| = 12 633 across 8 px), inside a 384×400
background quad with z linear in y (11 184 809 → 16 777 214,
13 981.0125 per row). Vertex z reaches both rasterisers as exact integers
(`fixed_to_float` is a cast, the passthrough shader copies `oPos`, and the
guest's float accumulation is the same on both platforms). Exact per-pixel z
is therefore computable, with the LESS test applied in draw order.

## Hardware vs the exact model

| region | pixels | golden = ⌊exact⌋ |
|---|---|---|
| grid quads | 63 488 | **63 488** (0 residuals, either capture) |
| background quad | 85 192 | 78 422 (−1: 3 481, +1: 3 289, none larger) |

The grid quads are exact on hardware: their slope, ±12 633/8, has three
fractional bits. The background quad's slope, 13 981 + 1/80, is not binary
representable, and its residual is structured: −1 where the exact fractional
part is near 0, +1 where it is near 1, tails reaching ±5/16 of a unit, byte-
identical between the Cn and Cy captures. Along one row (z constant in x)
the residual alternates with a period of about three pixels, and the sign
drifts across the 384-px width as well as down the 400 rows. Neither a plane
nor a bilinear surface fits it (5–7 % of pixels violate any such fit); it is
per-pixel rounding inside an edge-stepping interpolator, i.e. the NV2A's own
arithmetic.

## Ours vs the golden (build 3439aaab75)

| region | ours = golden | −1 | +1 |
|---|---|---|---|
| grid quads | 63 452 / 63 488 | 36 | 0 |
| background quad | 76 287 / 85 192 | 5 509 | 3 396 |

On the grid we are exact except for 36 pixels where the background quad wins
the depth test by less than a unit. On the background quad our own float32
interpolation error (a 5.6 M span at 2^24 has an ULP of 1) combines with the
hardware's.

## Conclusion

The remaining ±1 is not a formula error. Matching it would mean reproducing
the NV2A's fixed-point edge walk in the fragment shader; even an exact
rasteriser (integer edge functions, `umulExtended`) would match the hardware
only where the hardware itself is exact, i.e. the grid, where we already are.
Recommendation: score depth with a ±1 tolerance on primitives whose slope is
not binary-representable, and leave #32 at exact-floor.
