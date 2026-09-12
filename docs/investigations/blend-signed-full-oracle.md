# The signed blend rule holds on the full 1,568-test oracle

Measured 2026-09-12 against the retired `Blend tests` oracle, goldens at
`/home/justin/goldens/results/Blend_tests`. Tool:
[`docs/testing/blend_detailed_oracle.py`](../testing/blend_detailed_oracle.py).

Issue #43's rule, derived elsewhere from 3,600 points drawn from 105 `#spot_`
grid captures:

    signed(S) = S - 256 if S >= 128 else S

    FUNC_ADD_SIGNED               result = clamp(signed(S) + D, 0, 255)
    FUNC_REVERSE_SUBTRACT_SIGNED  result = clamp(D - signed(S), 0, 255)

with both blend factors ignored and the destination left unsigned.

**Verdict: it holds, on 15x the data, with nothing left over. Safe to
implement.**

## The verdict region and its control

`BlendTests::TestDetailed` — still in `nxdk_pgraph_tests` as an interactive-only
test — emits one capture per `<sfactor>_<eqn>_<dfactor>` triple: 1,568 captures,
448 of them the two signed equations. Each frame carries three independently
drawn stacks, blitted to screen through an A8B8G8R8 texture stage:

| | region | what is blended |
|---|---|---|
| **stack A** `DrawColorStack` | cols 16-79, rows 112-368 | RGB blended, alpha written with blending off |
| stack B `DrawAlphaStack` | cols 192-447, rows 112-368 | RGB written straight, alpha blended through four nested quads in turn |
| stack C `DrawColorAndAlphaStack` | cols 560-623, rows 112-368 | all four channels blended |

Stack A is the verdict region, because it comes with a control that separates
the defect from everything else in the frame. Our own renders of the oracle are
**bit-exact against silicon there under all five unsigned equations — 0
differing channels over 1,120 captures — and wrong on every one of the 448
signed captures.** Perfect separation, so a residual in stack A is the
signed-equation defect alone.

## What was measured

A closed-form model of the whole chain — blend, 8-bit store, byte
reinterpretation at the blit, alpha composite over the screen checkerboard,
8-bit store — predicted from the test source, and compared **region against
region**: every pixel of every stack, all four channels. No point samples. The
model never reads one of our captures; it is scene description against golden.

**The control comes first.** On the five unsigned equations the model
reproduces silicon exactly:

| | captures | channels |
|---|---|---|
| unsigned control, all three stacks | **1,120 / 1,120** exact | **440,401,920 / 440,401,920** |

Then the signed equations, under #43's rule:

| | captures | channels |
|---|---|---|
| signed-byte rule, all three stacks | **448 / 448** exact | **176,160,768 / 176,160,768** |
| stack A alone, SADD | **224 / 224** exact | 14,680,064 / 14,680,064 |
| stack A alone, SREVSUB | **224 / 224** exact | 14,680,064 / 14,680,064 |
| for contrast: as we render today | 0 / 448 | 59,690,400 / 176,160,768 |

Zero misses. **0 of 224 factor pairs deviate**, for either equation, on any
channel. There is no combination of sfactor, dfactor and equation where the
rule breaks, because there is no miss anywhere to characterise.

The rule is also confirmed on the alpha channel, which the `#spot_` fit could
not reach: stack C blends all four channels in one pass and stack B blends
alpha through a four-deep chain of nested quads, each blending against the
previous result. Both are exact. So the signed equations treat alpha the same
way they treat colour, and the rule survives being composed with itself.

## The fit is not vacuous

Each rival below is the rule with one thing changed, scored on the same 448
goldens. Every one is rejected, including both near-neighbours of the sign
threshold:

| rival | channels of 176,160,768 | |
|---|---:|---|
| **signed byte, saturate (#43)** | **176,160,768** | **fits** |
| sign threshold 127 not 128 | 92,384,768 | rejected |
| sign threshold 129 not 128 | 135,697,408 | rejected |
| wrap at 256 instead of saturate | 107,613,184 | rejected |
| signed source *and* signed destination | 98,305,536 | rejected |
| factors honoured, source still signed | 67,935,760 | rejected |
| 0.5 bias on the signed source | 56,655,872 | rejected |
| destination signed, source unsigned | 91,521,024 | rejected |

The scene constants are pinned the same way: moving the nested-quad increment
from 24 to 23, or the render-target checker from 16 to 8, breaks the control.
So the geometry is measured, not assumed — which matters, because an arithmetic
fit computed over the wrong picture is worthless.

## Provenance: the layout is pinned, not assumed

A revision mismatch between the 2025 oracle disc and the goldens was raised
mid-measurement (#50). It cannot reach this verdict, for two reasons.

The first is structural: **the fit is model-against-golden and never reads a
capture from the disc.** The disc's revision is not an input.

The second is measured. For each of the 448 signed goldens the model was
re-predicted under all 24 permutations of the four source colours in stacks A
and C. **Every golden accepts exactly one of the 24 — the current source's
order — and rejects the other 23.** Nothing is degenerate. So the goldens carry
the layout that today's `blend_tests.cpp` draws, and a reordered revision is
excluded by the goldens themselves rather than by argument. (The other lane
separately confirmed both stacks are byte-identical in draw order and swatch
colours between `283e2971` and `2cfe6073`.)

One modelling ambiguity is worth naming because it looks like a bug and is not.
`NV097_SET_DIFFUSE_COLOR4I` packing ABGR with a channel reversal at the blit,
and packing RGBA with no reversal, predict **identical** screen pixels
throughout this scene: the blend is per channel, the checkerboard destination is
channel-symmetric, and the constant colour is grey. The pair is degenerate here
and cannot be settled from these captures — nor does it need to be, since both
give the same prediction. Stacks A and C also run in opposite band order; they
keep separate colour lists and no band index is carried between them.

## Two things this corrects, and one it leaves open

`blend-fifth-quad.md` describes the residual as a "fifth quad", one 256x64
region, and reads it as a draw-state bug. Two corrections, both measured:

- The region is **stack C's blit at cols 560-623** — `DrawColorAndAlphaStack`,
  the one stack that blends all four channels — not a fifth quad of a
  five-quad draw. `TestDetailed` draws twelve quads in three stacks, not five.
- It is **not confined to the unsigned equations, and not a small residual**:
  our renders differ from silicon there on **1,567 of 1,568** captures,
  including 1,119 of the 1,120 unsigned ones, for 53,292,672 differing channels
  on the unsigned set alone. The single exception is `0_ADD_1`.

Stack C is therefore dominated by a separate defect (#50) and is worthless as
evidence about blending. It is reported here and deliberately not attributed.
That doc's central claim survives and is strengthened: the blend arithmetic is
right, and stacks A and B are now bit-exact on 1,120 unsigned captures rather
than exonerated by argument.

What remains open is stack C, which is #50's, not #43's.

## Is #43 safe to implement

Yes, on the semantics. The rule is now fitted on 176,160,768 channels across
448 captures at four destination values and the full source range, on a harness
whose control is exact on 440,401,920 channels, with every near-neighbour rival
rejected and the layout pinned per capture. There is no residual left for a
correction term to hide in.

The prize, restricted to regions where our render is provably comparable —
stacks A and B, bit-exact on all 1,120 unsigned captures — is **91,557,488
differing channels across the 448 signed captures.** Fixing #43 closes all of
them, because the model that predicts them is the golden itself.

Two things an implementer should know before starting:

- Fixing #43 will **not** make these 448 captures exact, because stack C will
  still be wrong. #50 has to land too. Scoring #43's fix on whole-capture
  exactness will read as no progress; score stacks A and B.
- The implementation question is untouched by this measurement and is the real
  cost. Vulkan cannot express the rule as a blend op: a fixed-point colour
  attachment clamps the source to [0,1] before blending, destroying the
  negative half that makes these equations different from plain add. The three
  candidate shapes — a float intermediate target, shader-side blending via
  framebuffer fetch, and a per-channel-per-sign multi-pass needing no extension
  — are set out in `signed-blend-equations.md`. All three are far larger than a
  `pgraph_blend_equation_vk_map` entry, and choosing between them wants a count
  of how often games use these equations, which nobody has measured.

## Reproducing

    docs/testing/blend_detailed_oracle.py --control     # 1,120 unsigned, must be exact
    docs/testing/blend_detailed_oracle.py --stack-a     # the verdict, per equation and factor pair
    docs/testing/blend_detailed_oracle.py --falsify     # rivals must be rejected
    docs/testing/blend_detailed_oracle.py --layout      # goldens pinned to one of 24 orders
    docs/testing/blend_detailed_oracle.py --fifth-quad ~/hakux-work/res_oldblend

Runs on goldens alone except the last. No device.
