# Prediction: reading FUNC_ADD_SIGNED off the single-blend swatches

Registered 2026-09-15 on `d7c5ec83`, before measuring.

## Why a second attempt

`2026-09-15-blend-signed-equations.md` established the defect -- `SADD` and
`SREVSUB` aliased to unsigned in `gl/constants.h:129` and `vk/constants.h:74` --
and failed to establish what they compute. Its follow-up instrument recovered the
blend operands from `ours_ADD = clamp(S+D)` and `ours_SUB = clamp(S-D)`, which
assumes one blend per pixel, and `TestSpot` draws some regions as nested quads.

**This also weakens that file's falsification, and the weakening is stated here
rather than left implicit.** P1 measured `golden == clamp(ours - 128)` over
*every* differing pixel. In nested regions no single-blend rule can hold, so 5.7%
is a contaminated lower bound, not a clean refutation. Roughly half of each cell
is single-blend, so a correct half-unit model should have scored near 50% rather
than 5.7% -- which is why the refutation is probably right -- but "probably right
for a reason I can state" is not the same as measured. **This measurement settles
it either way**, and if the half-unit model fits the clean data, the earlier
falsification is withdrawn.

## The geometry, from the test's source

`TestSpot` renders to a 512x512 target and composites it 1:1 at screen `(64, 64)`
(`RenderTexturedQuad(host_, CenterX(512), 64.f, 512, 512)`), clipped at the
480-row framebuffer, so target rows 0..415 are visible and all three cell rows
fit.

Fifteen `dst_factor` cells, 5 per row: `test_width = floor((512 - 16)/5) = 99`,
`test_height = floor((480 - (64+8))/3) = 136`, `color_swatch_size = floor(99/4) =
24`. Cell `i` is at `left = (i % 5) * 103`, `top = (i / 5) * 136`.

`DrawColorStack` occupies `x = left .. left+24` and four **non-overlapping**
24-pixel swatches from `top`, with diffuse colours, in order:

    0xDD00DD00   0xDDDD0000   0xDD0000DD   0xDDFFFFFF

over a `PrepareBlendBackground` checkerboard of `kColorSwatchBackground`
(`0x33333333`) and `kCheckerboardB` (`0xFF000000`) in 8-pixel checks -- so each
swatch spans **two different destination values**, which is a control built into
the test.

`DrawColorAndAlphaStack` (`x = left+24 .. left+48`) is likewise four
non-overlapping swatches. `DrawAlphaStack` (`x = left+48 .. left+99`) is
**concentric and nested** and is excluded.

That is 15 cells x 4 swatches x 2 background values = 120 exactly-known
single-blend regions per capture, 1,800 across the fifteen `sfactor` captures.

## The control that must pass FIRST

Recover `S` and `D` per pixel from the `ADD` and `SUB` **goldens**
(`S = (ADD+SUB)/2`, `D = (ADD-SUB)/2`), which is valid here precisely because
these regions are one blend deep. Then:

**C1.** `MIN` golden must equal `min(S, D)` and `MAX` golden must equal
`max(S, D)` over the same pixels, to within a step.

**C2.** `REVSUB` golden must equal `clamp(D - S)`.

**C3.** The recovered `S` must be constant within a swatch and the recovered `D`
must take exactly two values within a swatch, matching the checkerboard.

**If C1, C2 or C3 fails, the swatch localisation or the single-blend assumption
is wrong and NOTHING about `SADD` may be concluded from this run.** These are the
same class of check that the previous instrument lacked, and they are cheap
because the answers are already known.

## Predictions

**P1.** With C1-C3 passing, `SADD` golden is a function of `(S, D)` alone --
tabulating it against recovered `(S, D)` gives a single value per cell, not a
spread. This is the prediction the previous instrument failed outright (`S=64,
D=0` gave 4 and `S=96, D=64` gave 203).

**P2.** One of these closed forms fits `SADD` on at least 90% of clean pixels:

| # | form |
|---|---|
| A | `clamp(S + D)` -- the null, what we render now |
| B | `clamp(S + D - 128)` -- half-unit bias, the form P1 of the earlier file tested |
| C | `clamp(S + D - 127)` |
| D | `clamp(2*(S + D) - 255)` |
| E | `clamp(2*(S + D - 128))` |
| F | `clamp(S - D)` / `clamp(D - S)` -- the two aliases merely swapped |
| G | `clamp((S - 128) + (D - 128) + 128)` -- identical to B, listed to be explicit |

and the mirrored set for `SREVSUB`.

**P3.** Whatever fits is the same form at every one of the fifteen blend factors.
The baseline already shows the residual is flat across factors, so a form that
only fits some of them contradicts data already in hand.

## What kills it

- C1, C2 or C3 failing: this run establishes nothing and says so.
- P1 failing -- `SADD` golden not a function of `(S, D)`: then the signed
  equations depend on something beyond the two blend products, for instance the
  raw `src`/`dst` before the factors, or the destination alpha. That would be a
  real finding and would name the next instrument.
- P2 failing with P1 holding: the function is well-defined but is none of the
  obvious forms. The empirical table is then the deliverable, and it is published
  as a table rather than dressed up as a formula.

## Rule being followed

The table is the result. Forms are tested against it, not fitted to it, and any
form that survives has to survive at all fifteen factors. If none does, the
tabulated `f(S, D)` ships as-is -- an honest lookup beats an invented closed
form.

---

## Outcome: CONTROLS FAILED. Nothing is concluded about SADD — and an earlier claim of mine is void.

The swatches are exactly where the source says: `#spot_1_MAX` shows four 24-row
bands starting at screen `y=64`, `x=64..88`, in the right colour order, with the
8-pixel checkerboard alternation visible inside each. **Localisation is right.**

The controls still failed:

    C1  MIN    == min(S,D)      1030/3990 = 25.8%
    C1  MAX    == max(S,D)      1042/3990 = 26.1%
    C2  REVSUB == clamp(D-S)    1722/3990 = 43.2%

Per this file's own rule, that ends the run: **no statement about `SADD` may be
made from it, and none is.**

### Why, measured rather than guessed

Cell 0 of `#spot_1_MAX` has `sfactor = ONE` and `dfactor = ZERO`, so the render
target must hold `MAX(src*1, dst*0) = src` -- the source colour exactly. It does
not:

| swatch | expected | observed | ratio |
|---|---|---|---:|
| `0xDD00DD00` | (0, 221, 0) | (44, **192**, 44) | 0.8688 |
| `0xDDDD0000` | (221, 0, 0) | (**196**, 4, 4) | 0.8869 |
| `0xDD0000DD` | (0, 0, 221) | (44, 44, **192**) | 0.8688 |
| `0xDDFFFFFF` | (255, 255, 255) | (**221**, 221, 221) | 0.8667 |

Mean ratio **0.8707, sd 0.0073**, against **221/255 = 0.8667** -- and the white
swatch is exactly 0.8667 on all three channels. The small excess on the others is
the additive floor from compositing over the on-screen checkerboard.

221 is the swatches' **alpha** (`0xDD`). `TestSpot` renders to a 512x512 target
and composites it with `RenderTexturedQuad`, and **that composite scales RGB by
the target's alpha.**

### What that means for these captures

Every screen pixel is `T(blend_rgb(S, D))` where `T` folds in the **alpha** blend
result at the same pixel. The alpha channel is itself blended with the same
equation, and **our captures are RGB with alpha dropped**. So a `#spot_` capture
cannot determine the RGB blend semantics in isolation: there are two unknowns per
pixel and one observable.

That is a property of the substrate, not of this instrument, and it is why three
successive instruments have failed on it.

### The correction this forces

`2026-09-15-blend-signed-equations.md` reported P1 and P2 as **FALSIFIED** on
5.7% and 0.2% fits of `golden == clamp(ours -/+ 128)`, and P3 falsified because
the modal offset varied across factors.

**Those falsifications are void, and I am withdrawing them.** Both `golden` and
`ours` pass through the alpha-scaling composite, and the composite differs
between them -- for us `SADD` is `ADD` in the alpha channel too, for the hardware
it is not. So `golden == clamp(ours - 128)` could not have held **even if the
half-unit model were exactly right**. The measurement had no power to detect the
thing it was testing.

The half-unit model is therefore **untested**, not refuted. So is every other
closed form.

**What survives untouched** is the localisation, because it rests on *which*
captures differ and by how much, not on any model of what the equations compute:
91.3% of the suite is `SADD` and `SREVSUB`, the factor plays no part, `MAX` is
byte-exact in all fifteen, and `gl/constants.h:129` and `vk/constants.h:74` both
alias the signed pair to unsigned.

### What would actually work

- Captures that retain **alpha**. With RGBA the composite is invertible and the
  swatch instrument works as designed.
- The `TestDetailed` cases -- one `(equation, sfactor, dfactor)` per capture, a
  simpler layout -- which are in `interactive_only_tests_` and so are **not in
  our corpus**.
- Hardware documentation for `FUNC_ADD_SIGNED` / `FUNC_REVERSE_SUBTRACT_SIGNED`,
  which would answer it outright. This is asked on PR #45.

Stopping here rather than building a fourth instrument against a substrate that
has now defeated three. The defect is named, localised, quantified and reported;
the replacement value is not something these captures can yield.
