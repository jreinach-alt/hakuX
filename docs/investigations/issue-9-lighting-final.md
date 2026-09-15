# Issue #9 closed: the lighting arithmetic is correct, and what is left is three other issues

Measured 2026-09-12 on Adreno, APK `a56132dc295d`, **one disc per suite**.
137 captures across the eight suites #9 names.

## The numbers

| suite | caps | exact | differing px | one-step | **>1 step** |
|---|---:|---:|---:|---:|---:|
| `Lighting_spotlight` | 24 | 0 | 566,800 | 490,302 | 76,498 |
| `Lighting_accumulation` | 10 | 0 | 163,560 | 151,208 | 12,352 |
| `Lighting_range` | 3 | 0 | 10,364 | 7,638 | 2,726 |
| `Lighting_control` | 32 | 0 | 227,642 | 198,720 | 28,922 |
| **`Lighting_Two_Sided`** | 1 | **1** | **0** | 0 | **0** |
| `Material_color_source` | 28 | 0 | 124,424 | 100,352 | 24,072 |
| `Specular` | 22 | 0 | 436,923 | 227,781 | 209,142 |
| `Specular_back` | 17 | 0 | 233,308 | 93,504 | 139,804 |
| **total** | **137** | **1** | **1,763,021** | **1,269,505 (72%)** | **493,516** |

## Why this closes

Eight commits landed against it, each with its own before/after: the spot and
specular factors through the lighting unit's rational function, the colour
material terms, the specular fold when specular is disabled, two-sided
lighting, the unnormalised infinite light direction, 13-bit fractions on the
registers and vertex colours, `xf_s2lt` round-to-nearest, and
`LIGHTING_ENABLE` gating the colour outputs.

The evidence that the *arithmetic* is right rather than merely improved:

* `Lighting_Two_Sided` is **bit-identical to hardware**.
* `Specular_back::ControlFlagsNoLight_FF` is **306 px** from its golden.
* **72% of what remains is one step.** A rounding floor is not a lighting rule.

## Where the 493,516 structural pixels went

**#53 — six `_VS` captures, 318,962 px, 64.6% of the structural residual.** A
vertex program with `LIGHTING_ENABLE`. The programmable path emits the constant
term and no light loop, which predicts a same-disc A/B in both directions:
lighting-on-no-lights improves (94,510 → 25,446 on `Specular_back`) because
the constant is the whole answer, and lighting-on-with-lights regresses
(94,510 → 102,240) because a constant with no light contributions is further
off than the raw program colour. Net −60,460 px, so the commit stays.

And the obvious fix is measurably wrong before any code: silicon's own `_FF`
and `_VS` goldens differ by **88,451** and **99,652** px, so the `_VS` output is
not the fixed-function output, and our FF render sits 92,939 / 101,884 px from
the `_VS` golden — about where we already are.

**#38 — the one-step class, 1,269,505 px**, and **boundary-shift, 719,120
channels**. The first is the unit's truncating arithmetic plus host alpha-blend
rounding; the second is `DrawCheckerboardUnproject`'s texel ties, an
interpolator floor. On `Material_color_source` the boundary-shift accounts for
the >1-step part exactly, 72,216 against 72,216.

## Three method notes, each of which nearly produced a wrong number today

**Only same-disc arms are comparable.** `Specular` reads 436,923 px here
against 436,049 in the #19 sweep, which looks like a regression and is not a
comparison: that sweep ran a shared 23-suite disc and this is one disc per
suite. Earlier today the same mistake made me revert a working change, on a
capture that was exact when run alone.

**The exclusive `class` column is too coarse for a close/no-close question.**
`classify_residuals.py` labels a capture `structural` if *any* channel exceeds
one step, so a capture 90% one-step lands there — 113 of 136 captures read
`structural` while 72% of the pixels are one step. Use the channel-level split.

**One-step and boundary-shift overlap** — a band can differ by one step — so
they cannot be added or subtracted. Doing it produced negative residuals, which
is how I noticed rather than published.

## What was tried and should not be retried

Four precision models, all measured on the desktop lane, all worse in total
than the committed state, with `Lighting_spotlight` losing 16–53k px every
time: full Celsius LT arithmetic; the same with the spot factor in float32; LT
for the specular evaluator only; float32 with only the transform vectors
rounded. The reading that survives is that rounding the *registers and vertex
colours* to the unit's format is right, and rounding the *transform stage's
vectors* is not — so either NV2A's lighting runs at higher precision than the
NV10 model for those vectors, or its half-vector path differs. That is #38's
question now.
