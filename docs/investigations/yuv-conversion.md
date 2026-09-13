# The YUV texture decode: right coefficients, wrong arithmetic

Six golden captures disagreed with us on every pixel that carried colour:
`TexFmt_YUY2_L`, `TexFmt_UYVY_L`, `BumpMap_YUY2_L`, `BumpMap_UYVY_L`,
`BumpEnvLum_YUY2_L`, `BumpEnvLum_UYVY_L` — 719,784 px in total. This is the
derivation of what silicon actually computes, and it is now exact.

## The answer first

The BT.601 coefficients in `convert_yuy2_to_rgb` were never wrong. What was
wrong is that we evaluate **one rounded dot product** where the hardware
**rounds each term on its own and then adds**:

```c
int luma = (298 * c - 96) >> 8;                      /* c = Y - 16  */
r = luma + 2 * ((409 * e + 127) >> 9);               /* e = Cr - 128 */
g = luma + 2 * ((-50 * d + 254) >> 8)
         + 2 * ((-104 * e + 248) >> 8) + 1;          /* d = Cb - 128 */
b = luma + ((516 * d) >> 8);
```

298, 409, 516 and the doubled −50 / −104 (i.e. −100 and −208) are exactly the
constants we already had. Only the shape of the arithmetic changed.

## How the source triples were recovered

There is no capture of the source texels, so they were recovered from our own
output. Restricting to pixels where no channel clips under our formula makes
the inversion unique:

| | |
|---|---|
| triples converting without clipping | 2,567,998 of 16,777,216 |
| distinct unclipped (ours, gold) pairs | 37,497 |
| of those inverting to a **unique** (Y,Cb,Cr) | **37,497** |

Two facts had to be established before any of this was worth doing, and both
were checked rather than assumed:

- **The geometry is exact.** `TexFmt_R5G6B5` draws the identical quad and
  differs from its golden by 0 px, so the disagreement is entirely in the
  decode, not in sampling or placement.
- **Sampling is point, not filtered.** Run lengths of identical pixels along
  golden row 240 are {3:63, 1:63, 2:59} at 370/256 magnification. Each output
  pixel is therefore exactly one converted texel. (An earlier note of mine
  claimed the quad was filtered and that coefficients were consequently
  underivable. That was wrong, and it was the thing blocking this derivation.)

## What the data ruled out

**Every named formula.** Brute force over all 16.7M triples against the 600
most common observed pairs: BT.601 limited 0/600, BT.601 limited without
rounding 1/600, BT.601 full 0/600, BT.709 limited 0/600, BT.709 full 0/600,
the 359/88/183/454 integer set 0/600.

**Chroma interpolation, dithering, and anything else stateful.** The 37,497
samples contain 37,497 distinct (Y,Cb,Cr) keys and zero conflicts: the gold
output is a pure function of the single texel's own triple. A hardware unit
that blended chroma across a pixel pair could not produce that.

**A single affine expression with one rounding.** Fitting
`gold = floor(a·Y + b·(Cb−128) + c·(Cr−128) + d)` is a linear feasibility
problem, and it is infeasible. A simultaneous-projection solve left 9,179
violated constraints on B and 21,819 on G; solving the Cr term's coefficient
interval exactly gives a maximum slack of −0.987, i.e. no such line exists.

## The observation that cracked it

Group the samples by chroma value and compare columns at shared Y. If the
output were a single rounded sum, columns would differ by a constant **±1** —
the floor would wobble. They do not wobble at all:

| decomposition | columns compared | spread 0 | spread > 0 |
|---|---|---|---|
| B against (Y, Cb) | 178 | 178 | 0 |
| R against (Y, Cr) | 210 | 210 | 0 |
| G residual against (Cb \| Cr) | 212 | 212 | 0 |

Zero spread everywhere means each term is quantised to an integer
independently and the integers are then summed. That is a sum of separately
rounded products, and it is the whole defect.

The decomposition also cross-checks: the luma term extracted from the R
channel and the one extracted from the B channel differ by a **single
constant (−96) across all 167 shared Y values**. Both channels see the same
luma path, as they must.

## Pinning the constants

With the structure known, each term's coefficient interval can be computed
exactly (the feasible set is convex, so its projection is a single interval):

| term | feasible slope | unique integer at /256 |
|---|---|---|
| luma | [1.163934426, 1.164179104] | **298** |
| B, Cb | [2.015503876, 2.015748031] | **516** |

The Cr term behaved differently: its increments are **0 or 2, never 1**. Three
of the four chroma terms carry one bit less than the luma term and so move in
steps of two; `516·(Cb−128) >> 8` is the exception and is full precision. Once
fitted at that granularity, the Cr coefficient is 409/512 doubled — again
exactly the 409 we already had, and the G terms resolve to −50 and −104
doubled, i.e. the −100 and −208 we already had.

## Verification

All three channels, every recovered sample, exact:

| channel | exact |
|---|---|
| R | 37,497 / 37,497 |
| G | 37,497 / 37,497 |
| B | 37,497 / 37,497 |

## Measured, lavapipe, against matched baselines

| capture | before | after |
|---|---|---|
| `TexFmt_YUY2_L` | 136,900 px | **0 — exact** |
| `TexFmt_UYVY_L` | 136,900 px | **0 — exact** |
| `Texture_format` suite | 16/40 exact | **18/40 exact** |
| `Texture_DXT`, `Volume_texture` | — | unchanged to the pixel |

Mean absolute error on `TexFmt_YUY2_L` goes 0.708 -> 0.000 and the worst
channel error 4 -> 0, over the whole 307,200 px image. The decode is not
merely closer; it is the hardware function.

## The bump captures are not a decode problem, and this corrects me

I previously characterised `Bump_map` and `Bump_env_lum` as "YUV plus a
boundary floor". The measurement says otherwise. With the decode now exact:

| capture | px wrong | mean abs error |
|---|---|---|
| `BumpMap_YUY2_L` | 111,496 -> 111,496 | 33.96 -> 35.10 |
| `BumpMap_UYVY_L` | 111,496 -> 111,496 | 33.96 -> 35.10 |
| `BumpEnvLum_YUY2_L` | 111,496 -> 111,496 | 17.45 -> 17.45 |

48,886 px of our own output moved in each, so the decode is genuinely being
exercised — it just fixes nothing there, and the mean drifts slightly the
wrong way. Two things follow.

First, the bump suite has a defect that has nothing to do with YUV: every
format in it is wrong by roughly 57,000 px (`BumpMap_A1R5G5B5` 57,082,
`BumpMap_A8R8G8B8` 57,365, and so on), with a worst channel error of 255.
That is structural, and it swamps any rounding-level concern.

Second, the YUV entries are wrong by *twice* that, and that excess survives
an exact decode. So the residue points at how the bump stage consumes a YUV
source — plausibly that hardware does not colour-convert a bump map at all
and reads the bytes directly — not at the conversion. That is a separate
investigation and is not claimed here.

Feeding a verified-correct decode into a broken consumer can move its error
either way; that the mean rose by 1.1 is a property of the bump defect, not
evidence against the decode, which is independently exact on the test that
isolates it.

## Limits worth stating

- The sampled ranges are Y 42..209 and Cb, Cr 17..238. Outside those the
  affine form is extrapolated, not measured.
- The rounding constants (−96, 127, 254, 248) and the trailing +1 are one
  representative choice. Each is free over a small range that a compensating
  change in the trailing constant absorbs; the fit is exact for any choice in
  that range.
- The derivation is from the **texture** unit. `gl/display.c` and
  `vk/display.c` call the same helpers for YUV display surfaces and therefore
  inherit it. They shared one implementation before this change and still do,
  so no divergence is introduced — but the display path's conversion has not
  been measured against hardware and could in principle differ.
