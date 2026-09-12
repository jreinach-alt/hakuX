# FUNC_ADD_SIGNED: half of the rule, and the half that does not fit

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

## Next

The discriminating experiment is a destination sweep: the `#spot_` captures
only ever offer two destination values, 51 and 0. `Blend tests`' non-`#spot_`
`TestDetailed` cases vary the destination far more widely but are
`interactive_only`, so they need a disc built with them enabled. That is what
would separate "zero destination is special" from "destination alpha is
special" from something else again.

Implementability is a separate question and should not be assumed: Vulkan's
blend ops cannot express a wrap, so even a complete rule may need the blend
moved into the shader, which is a much larger change than a table entry.
