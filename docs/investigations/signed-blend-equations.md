# The signed blend equations: the source is a signed byte

Scope: issue #43, the two signed blend equations. Measured against the 30
`Blend tests` `#spot_*_SADD` / `#spot_*_SREVSUB` captures, which give 15 source
factors x 15 destination factors x 4 source colours x 2 destinations per
equation -- a far denser fit set than the two `Texture_signed_component` tests
the issue was opened on.

## Why this is the target

Reclassifying every capture on hand with the boundary-shift detector and
subtracting both the +-1 population and the boundary band leaves a ranking of
genuine, non-precision error. The signed blend equations are the largest single
item in the corpus by a wide margin:

| suite | captures | exact | non-precision channels |
|---|---|---|---|
| **`Blend tests`, the 30 signed captures** | 30 | 0 | **6,499,076** |
| `Fog gen` | 60 | 4 | 2,063,464 |
| `Line width` | 61 | 1 | 815,089 |
| `Bump map` | 38 | 0 | 780,558 |

Everything else large is precision: `Fog exceptional value`'s 3.66M differing
pixels are 93% a one-step difference in one channel, `Bump env lum`'s 70,959 per
capture carry only 1,688 above one step and those sit on eight rows.

## VERIFIED: on a non-zero destination, SADD is an 8 bit wrap and ignores both factors

Recovering the render-target byte from the screen byte (the blit's alpha is
221/255, so the inverse is unique almost everywhere) over `#spot_1_SADD`, cell
`dfactor=0`, against the grey checker destination (51, 51, 51):

| source | S + D | S + D mod 256 | hardware |
|---|---|---|---|
| 0 | 51 | 51 | **51** |
| 221 | 272 | 16 | **16** |
| 255 | 306 | 50 | **50** |

All four `DrawColorStack` colours agree, on every channel, and `dfactor=0` and
`dfactor=1` give identical output -- so the equation **ignores both blend
factors** and adds the raw 8 bit operands with a wrap at 256 rather than a
clamp. That matches the issue's own hardware table (`191 + 127 -> 62`,
`236 + 127 -> 107`, `255 + 255 -> 254`).

## UNRESOLVED: the same rule fails completely on a zero destination

Against the black checker destination (0, 0, 0) with destination alpha 255,
every source produces zero:

| source | S + D mod 256 | hardware |
|---|---|---|
| 0 | 0 | 0 |
| 221 | 221 | **0** |
| 255 | 255 | **0** |

Verified against the raw golden pixels rather than only through the recovery:
at render-target (2, 74), source white, the golden screen value is 0 where the
wrap model wants 221.

So the wrap model explains one destination exactly and the other not at all.
What distinguishes them is the destination value itself and its alpha, 51
against 255. The factors are ruled out as the cause -- the two cells fitted
above differ in `dfactor` and behave identically.

A brute-force fit over the obvious candidate space -- factors honoured or
ignored, bias of 0 or 0.5, clamp or wrap, 7,200 sampled pixels across all 30
captures -- tops out at 44.6% (factors ignored, no bias, wrap). No candidate in
that space is the rule, which is why this document stops here rather than
proposing one.

## VERIFIED against a second suite, with a control

`Texture signed component tests` draws a 256 texel gradient 1:1 over a CPU
written 12 pixel checkerboard of 255 and 127, straight to the framebuffer with
no render target in the way. The texel value is `x & 0xFF` and the quads sit at
x in [64, 320) and [320, 576), so the source is known analytically rather than
read back from our own render -- which matters, because this suite exists to
question our texture decode, and an earlier attempt to read the source from our
own capture produced 192 of 256 source values mapping to more than one result.

Each mask block alternates unsigned and signed rows; only the unsigned ones are
used here. Each is drawn twice, at source alpha 255 and 127.

**The control:** the suite's plain `ADD` case fits `S*a + D*(1-a)` on
**795 of 795** consistent triples. Layout, checkerboard phase, channel mapping
and source model are therefore all correct, and the signed numbers below rest
on a validated harness.

### Both factors are ignored

Source alpha 127 and 255 give **identical** results for every observed
`(S, D)` under both signed equations, though the factors are
`SRC_ALPHA`/`INV_SRC_ALPHA` and the control case varies strongly with it. Taken
with `dfactor=0` and `dfactor=1` being identical in the `#spot_` captures, the
signed equations ignore both blend factors.

### The rule, and where it stops

| destination | hardware |
|---|---|
| 0 (`#spot_`) | 0 for every source, white included |
| 51 (`#spot_`) | `(S + D) mod 256` exactly |
| 127 (this suite) | `(S + D) mod 256` exactly, across the whole source range |
| 255 (this suite) | **255** for S up to ~124, then `(S + D) mod 256 = S - 1` from S ~144 |

At D = 127 the wrap is clean end to end: S = 124 gives 251, S = 144 gives 15
(271 - 256), S = 252 gives 123. At D = 255 the top half wraps the same way --
S = 144 gives 143, S = 252 gives 251 -- but the bottom half saturates at 255
instead of wrapping to S - 1.

So the rule is `(S + D) mod 256` with both factors ignored **for mid-range
destinations**, and something else at both extremes of D. Candidates tried and
rejected against the full curve: clamp everywhere; clamp when the wrapped
result would be below 128 (fits D = 255, contradicts D = 127); signed 8 bit
operands; saturation in 9 bits; a 0.5 bias in any of the forms above.

## SOLVED: the source is read as a signed 8 bit value

    signed(S) = S - 256 if S >= 128 else S

    FUNC_ADD_SIGNED              result = clamp(signed(S) + D, 0, 255)
    FUNC_REVERSE_SUBTRACT_SIGNED result = clamp(D - signed(S), 0, 255)

Both blend factors are ignored. The destination stays unsigned. The clamp is an
ordinary saturate, not a wrap -- the wrap seen earlier was the signed source
being read as unsigned.

| | fit |
|---|---|
| `Texture signed component` `SADD`, D = 127 and 255 | **324 / 324** consistent (S, D) pairs |
| `Texture signed component` `SREVSUB` | **325 / 325** |
| `Blend tests` `#spot_*_SADD`, D = 0 and 51, through the render target and blit | **3600 / 3600** sampled pixels |
| `Blend tests` `#spot_*_SREVSUB` | **3600 / 3600** |

Four destination values, the full source range, two suites that reach the
framebuffer by different paths, and a plain-`ADD` control fitting
`S*a + D*(1-a)` at 795/795 on the same harness.

Every earlier anomaly falls out of it. At D = 0 every source gave 0 because a
source of 221 or 255 is signed -35 or -1, and a negative sum clamps to zero. At
D = 255 the saturation below S = 128 and the wrap above it are the positive and
negative halves of the signed source: +4 + 255 saturates at 255, while
-112 + 255 is 143. The transition sits exactly at S = 128, the sign bit. What
looked like a wrap at mid-range destinations was `signed(221) + 51 = 16`, which
is also `(221 + 51) mod 256` by coincidence whenever the sum stays in range.

## Implementing it is the open question, not deriving it

Vulkan cannot express this with a blend op. The natural form -- remap the
source to its signed value in the fragment shader, then blend `ONE`/`ONE` with
`VK_BLEND_OP_ADD` -- fails because a fixed-point colour attachment clamps the
source to [0, 1] *before* blending, which destroys the negative half. That is
exactly the half that distinguishes these equations from plain add.

So it needs either a floating point intermediate target, or the blend moved
into the shader with framebuffer fetch (an input attachment plus a subpass
self-dependency, or `VK_EXT_rasterization_order_attachment_access`). Both are
substantially larger than a table entry in `pgraph_blend_equation_vk_map`, and
the choice should be made deliberately rather than discovered during
implementation.

The prize is 6,499,076 non-precision channels across 30 `Blend tests` captures
plus the two `Texture signed component` cases -- the largest single item in the
corpus.

## Method notes worth keeping

### The disc that was going to be needed, and was not

The discriminating experiment is a destination sweep: the `#spot_` captures
only ever offer two destination values, 51 and 0. `Blend tests`' non-`#spot_`
`TestDetailed` cases vary the destination far more widely but are
`interactive_only`, so they need a disc built with them enabled. That is what
would separate "zero destination is special" from "destination alpha is
special" from something else again.

Implementability is a separate question and should not be assumed: Vulkan's
blend ops cannot express a wrap, so even a complete rule may need the blend
moved into the shader, which is a much larger change than a table entry.
