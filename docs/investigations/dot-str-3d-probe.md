# What actually reaches the DOT_STR_3D sampler, measured on Adreno

Run 2026-09-12 on the device, `ref ec13c70e60` (a temporary probe, tagged
`probe-51-ec13c70e` and deliberately never on the branch). Issue #51.

## Why a probe was needed

The goldens can only show *which texel was fetched*, and the two candidate
mechanisms predicted the same texel, so no capture of the real fetch could
separate them:

* **Saturation** — the dot products run far outside `[0,1]` and every axis
  saturates, landing on a corner. Falsified beforehand by arithmetic: `pT1..3`
  are rows of the *inverse* fixed-function composite, bounding `|dot|` at
  0.00299, 0.00299 and 9.37e-7.
* **Projective divide** — the test sets `SetTexCoord1/2/3(..., 0.f)` so `w` is
  zero, and the dot modes take `pT.xyz` raw where every other consumer divides
  by `pT.w`. A divide would send every component to ±inf with the numerator's
  sign, making magnitude irrelevant by construction.

The probe replaced the fetch with a readout: `R = sign(dot_{i-2})`,
`G = sign(dot_{i-1})`, `B` a magnitude **bucket** (255 not finite, 200 >= 1,
150 >= 0.01, 100 >= 0.001, 50 > 0, 0 exactly zero). Bucketed because the
predicted 0.003 as a raw channel is 0.76/255 — a confirmation and a null result
would both have rendered black.

## The text overlay is a confound, and it is now pinned

`B = 255` looked like "not finite" and is not: on the three unsigned captures
the count matches the golden's `#FFFFFF` population **exactly**.

| capture | probe `B=255` | golden `#FFFFFF` |
|---|---:|---:|
| `DotSTR3D_0to1` | 1,042 | 1,042 |
| `DotSTR3D_HiLo_1` | 1,170 | 1,170 |
| `DotSTR3D_HiLoHemi` | 1,376 | 1,376 |

Those are the on-screen text pixels, which the harness draws white after the
quad. On the signed captures white is also a corner colour, so the golden count
is much larger (15,220) while the probe still reports only the text
(1,042 / 1,332 / 1,206).

**So no pixel is non-finite.** The projective-divide candidate is refuted *for
our pipeline*.

## The magnitude is exactly what the matrix rows predict

Every cube pixel lands in bucket **100**, `|dot|` in `[0.001, 0.01)`. On
`DotSTR3D_HiLo_1` that is all 56,909 of them. The arithmetic falsification was
right, measured on device rather than argued.

## The signs already partition the cube the way the goldens do

Classifying cube pixels by `(sign(dot_{i-2}), sign(dot_{i-1}))` and comparing
the four populations against the golden's four corner populations — sorted,
because the sign-to-corner assignment is what is in question, text excluded
from both:

| capture | ours (sorted) | golden (sorted) | diffs |
|---|---|---|---|
| `-1to1` | 14563, 14261, 14176, 13549 | 14562, 14446, 14178, 13723 | +1, −185, −2, −174 |
| `-1to1D3D` | 15262, 14594, 13722, 13034 | 15262, 14832, 13722, 13093 | 0, −238, 0, −59 |
| `-1to1GL` | 14458, 14436, 14074, 13734 | 14527, 14457, 14076, 13849 | −69, −21, −2, −115 |

Two populations are exact and two are within 2 px on `-1to1D3D`. Our sums fall
short of 56,909 by 360 / 297 / 207, which is exactly the bucket-0 population
(`|dot|` identically zero) excluded from the classification.

On the three unsigned captures only `(1,1)` and `(1,0)` occur — `sign(dot_{i-2})`
is uniformly non-negative, which is what the unsigned dotmaps guarantee and
what makes the two `x = 63` corners forbidden. The prediction that
`#FF0000 = 0` there is confirmed at the mechanism level, not just in the
output.

## What this means for #51

`hw/xbox/nv2a/pgraph/vk/texture.c:1308-1310` creates the sampler with
`VK_SAMPLER_ADDRESS_MODE_REPEAT` on all three axes. With a coordinate of
±0.003, `+0.003` addresses texel 0 and `−0.003` **wraps to 0.997**, addressing
the far texel. So (INFERRED from the measured magnitude plus the measured
address mode) our fetch is *already* selecting a corner by sign — by wrapping
rather than by saturating, arriving at the same observable rule from the other
direction. That is consistent with the population table above: if we were
sampling a volume interior, those four populations would not land within 238 px
of the golden's corner populations.

**So the entry's framing — "its coordinate range is wrong", 494,852 structural
channels — overstates the defect.** What is left is the sign-to-corner
*assignment* and a boundary population of roughly 60–240 px per capture where
`|dot|` is at or near zero. Those are different sizes of problem and different
fixes.

MEASURED here: the magnitudes, the absence of non-finite values, the text
identification, the four sign populations, the sampler's address mode.
INFERRED: that wrapping is the route by which our corner is chosen, and
therefore that the remaining error is an assignment rather than a range. The
next check is cheap and settles it — compare the sign-to-corner map
capture-by-capture rather than as sorted populations.

Nothing about hardware's own route is settled by this. The projective divide
remains a live description of *silicon*; it is only refuted as a description of
what our shader computes.
