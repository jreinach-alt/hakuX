# `Blend surface`'s destination-alpha tests: what they are not

Measured 2026-09-12. Issue #48. No fix landed; the value here is that three
plausible causes are eliminated with numbers and the fourth is named.

## The state, measured rather than assumed

Logged once per distinct combination at the dynamic blend path
(`vkCmdSetColorBlendEquationEXT` — the static pipeline path in `draw.c` is
**dead on this device**, which cost one build to discover: patching it changed
nothing at all, 0 better and 0 worse, totals identical to the pixel).

| test | `sf` | `df` | `eqn` | `blend_en` | `tex_en` | `ctl0` | surface |
|---|---|---|---|---|---|---|---|
| `DstAlpha_X_ORGB8` | 6 | 0 | ADD | 1 | **0x0** | 3f110700 | 0x05 |
| `DstAlpha_ARGB8` | 6 | 0 | ADD | 1 | **0x0** | 3f110700 | 0x08 |

`sf=6/df=0` is `DST_ALPHA`/`ZERO`, so **`result = S × Ad`** and the destination
contributes nothing — which is why the failing region is one uniform value
rather than a gradient.

The two rows are identical in every field except the destination format, and
`tex_en=0x0` means the source is **not sampled**. So `S` is the same for both,
and since `A8R8G8B8` is exact, `S = 108`.

## What the goldens give, at fixed coordinates

| test | golden at (120,100) | ours |
|---|---|---|
| `DstAlpha_ARGB8` | 85 — the background | **85, exact** |
| `DstAlpha_X_ORGB8` | **255** | 108 |
| `DstAlpha_X_ZRGB8` | **85** — the background | 108 |

**No factor ≤ 1 takes 108 to 255.** So the `O` variant's white cannot come from
this blend at all. It comes from the other draw the log shows into the same
surface: `sf=4 df=5 blend_en=0` — blending *disabled*, writing `S` straight.

Two draws land on that region, one with blend off and one with blend on, and
hardware's surviving value is the blend-disabled one where ours is the blended
one. **That is the defect**, and it is not about destination alpha.

## Eliminated, with numbers

| candidate | why not |
|---|---|
| the `Z` variant forces alpha to zero | its golden is 85, *identical to `A8R8G8B8`'s*, and we are exact there with the stored alpha. Forcing zero made those captures **worse** — 6 better, 7 worse over the suite |
| the source is a sampled texture | `tex_en=0x0` on the draw |
| the source differs between formats | every logged field but the format is identical |
| the static pipeline path | patched it; 0 better, 0 worse, identical to the pixel |

## What the `O` variant does need

`Ad = 1.0`, derived: `result = S × Ad`, hardware 255 where ours is `S`. That
substitution is correct and **moves no number on its own**, because it
multiplies an `S` that is already wrong. It is written up here rather than
committed for that reason.

`X1A7R8G8B8` needs nothing: its seven-bit alpha is real data.

## Probably the same defect as the fifth quad

The remote lane's reading of the test source is that `DrawQuad` draws every
swatch **twice**, differing in both write mask and blend enable, and their
`Blend tests` residual is one 256×64 strip where the wrong member of such a
pair survives. Same shape, different suite. If they are one defect, a fix for
either should move both — and these eight captures are a much cheaper test case
than 1,568.

Hypothesis, not a finding.

## Two method errors this cost, both worth more than the attempt

**Reverting on a contaminated number.** `DstAlpha_ARGB8` went 0 → 98,304 in a
shared-disc run and I read it as a regression caused by my change. It is
**exact when run alone** with that change in place — the predicate never
matches `A8R8G8B8`. `score_sweep.py` prints a warning about shared discs on
every one of those runs, and the isolation harness that settles it in two
minutes was built the night before.

**Sampling the golden in a window defined by our own error.** I characterised
hardware by reading golden values *where we differ*, so when our output changed
the sampled pixels changed with it — which produced "hardware is white for both
variants" and erased the entire `O`/`Z` distinction. Fixed coordinates give 255
and 85. The earlier version of this mistake was a point standing in for a
region; this one is a region standing in for a *fixed* region, which is harder
to see and identically wrong.
