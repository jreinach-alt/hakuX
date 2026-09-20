# #112 item 1: "the rounding threshold is 9/16" names two models, and the goldens already kill one

Written 2026-09-19 by `lane.cloud-112`, ahead of hardware, from the twelve
`Viewport` goldens already on disk. Nothing here needed a device and nothing
here is new measurement: it is arithmetic over
[`viewport-9-16-boundary.md`](viewport-9-16-boundary.md)'s tables.

The prediction this derivation binds is
[`docs/testing/predictions/2026-09-19-viewport-substep-threshold.md`](../testing/predictions/2026-09-19-viewport-substep-threshold.md).

## The two readings

This tree snaps the post-viewport-offset screen coordinate with
`trunc(pos * 16.0) / 16.0` (`hw/xbox/nv2a/pgraph/glsl/vsh.c:548`) and samples
at the pixel centre. Call that **T**. #112 quotes a hardware source saying the
rounding threshold is **9/16**, and that sentence can mean either of two
entirely different things:

- **R -- a rounding threshold.** The coordinate carries more than four
  fractional bits internally and is reduced to four, rounding *up* when the
  discarded remainder is at least 9/16 **of a 1/16 step**:
  `k = floor(pos*16); snap = (k + (frac >= 9/16)) / 16`. T is R with the
  threshold at 1.
- **S9 -- a sample position.** The fill rule tests coverage at `n + 9/16`
  rather than at the pixel centre `n + 1/2`. The snap stays a truncation.

They are not variants of one idea. R changes *where the edge is*; S9 changes
*where the rasteriser looks*. Only one number is shared, and #49's captures
separate them completely.

## What a capture can see at all

For a left edge that lands at `n + s` after snapping, the first covered pixel
is `ceil(n + s - 1/2)`, so **coverage changes only when `s` crosses 1/2**. On
a 1/16 grid the only crossing available is `s = 8/16 -> 9/16`. Therefore:

> A capture can distinguish two snap rules **only** at an offset whose
> `floor(offset * 16) mod 16` is 8. Everywhere else the two rules differ by at
> most one 1/16 step that no pixel centre lies inside, and the frame is
> bit-identical.

That single line is what makes the rest of this cheap.

## R is invisible in all twelve existing captures

The sweep offsets (`docs/testing/probe_viewport_ff_extents.py:61`) are 0,
±17/32, +9/16, −7/16 and ±1, each with a scale-0 and (for five) a scale-2.0
twin. Their sub-step remainders are:

| offset | `offset*16` | remainder of a step | T snap | R snap |
|---|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |
| +17/32 | +8.5 | 1/2 | +8/16 | +8/16 |
| **+9/16** | **+9.0** | **0** | **+9/16** | **+9/16** |
| −17/32 | −8.5 | 1/2 | −9/16 | −9/16 |
| **−7/16** | **−7.0** | **0** | **−7/16** | **−7/16** |
| ±1 | ±16 | 0 | ±1 | ±1 |

Every remainder is 0 or 1/2, and 1/2 < 9/16, so **R and T produce the same
snap on every vertex of every one of the twelve captures**, at both scales.
Not "agree to within a pixel" -- the same value, bit for bit.

This also disposes of the sentence in #112 that the 9/16 threshold "must then
be reconciled with the 820,000-pixel regression". It need not. That regression
was **round-half-up**, threshold **8/16**, which does move ten of the twelve
(it rounds 17/32 up to 9/16 where hardware keeps 8/16). R's threshold is
9/16, above 1/2, so R costs exactly **zero** of those 820,000 px. The two are
different constants and only one of them has ever been measured against.

## S9 is refuted by the goldens, offline

S9 moves coverage wherever the snapped edge's position **within its own
pixel** is exactly `9/16` -- `ceil(x - 1/2)` and `ceil(x - 9/16)` differ iff
`frac(x)` lies in `(1/2, 9/16]`, and on a 1/16 grid the only value in that
half-open interval is `9/16` itself. On this sweep that is `+9/16` (edge at
`n + 9/16`) and `−7/16` (edge at `n − 7/16`, whose fractional position is also
`9/16`) -- which,
on this sweep, is the two grid-exact offsets and nothing else:

| offset | T first covered | **S9** first covered | differ |
|---|---:|---:|---|
| 0, ±17/32, ±1 | n, n, n±1 | same | . |
| **+9/16** | n+1 (`HIGH`) | **n (`LOW`)** | yes |
| **−7/16** | n (`HIGH`) | **n−1 (`LOW`)** | yes |

So S9 renders every vertex `LOW` in both failing captures. Gold does not:
`viewport-9-16-boundary.md`'s per-vertex table has **x = 120 and x = 220 HIGH**
and the other seven `LOW`, in the same quad, at the same y and w. S9 fixes five
vertices and breaks two.

S9 is therefore the same prediction as the "tiny negative pre-snap bias" that
document already priced -- both make +9/16 render as offset 0 does and −7/16 as
−17/32 does -- so **S9's residual is already computed: 428 + 460 = 888 px**,
against 1,396 today. A different mechanism reaching the identical frame. It
needs no hardware and it is not the answer, for the reason the investigation
gave in general form: every rule on the coordinate is invariant under integer
translation, and gold resolves `120 + 9/16` and `320 + 9/16` in opposite
directions.

**Both readings of "9/16" fail to predict #49's two captures**, R by predicting
exactly what we render today (all nine `HIGH`) and S9 by predicting all nine
`LOW`. #112's claim that a real 9/16 threshold "predicts both failing
captures" is false under either reading. #49's residual stays where
`viewport-9-16-boundary.md` put it: one step upstream, in the
reciprocal-versus-divide of the fixed-function transform.

## What hardware can still settle, stated as a quantity

Write **θ** for the threshold in units of one 1/16 step: the snap rounds up
when the discarded remainder is ≥ θ. T is θ = 1, R is θ = 9/16, round-half-up
is θ = 1/2.

The goldens already bracket it. `+17/32` has remainder exactly 1/2 and renders
`LOW` on silicon, so **θ > 1/2** -- a bound from this suite's own goldens, and
a separate observation from the ~820,000 px that θ = 1/2 costs across
`Blend_tests`, `Specular`, `Specular_back`, `Material_color_source` and
`Lighting_spotlight`. Two independent measurements agreeing, not one restated:
none of those 820,000 px is a `Viewport` pixel, and the bound stands without
them. Nothing in the corpus constrains θ from
below any further, because no capture in it has a remainder strictly between
1/2 and 1.

So the hardware run is a **measurement of θ over (1/2, 1]**, not a choice
between two stories, and the offsets that carry information are exactly:

> `offset ∈ [k + 0.53515625, k + 0.5625)` and
> `offset ∈ [k − 0.46484375, k − 0.4375)` for integer k.

Two windows, each 1/32 wide, each ending at one of #49's two failing offsets.
That is why those two captures sit where they do and still cannot see this:
they are the *top edge* of the window, where every θ agrees again.

## Margin, and the one thing that could spoil it

The sub-step probe asks about differences of 1/256 px, so it is fair to ask
whether the transform's own last bit swamps it. `viewport-9-16-boundary.md`
gives two figures: the true vertices sit "within a few ULP of n" (~1e-4 px at
a coordinate near 320), while its CPU replication's own fp32 unproject
contributes 0.005-0.010 px where it dominates -- and that document concludes
the replication is wrong exactly there, so the second figure bounds the model
rather than the silicon.

The prediction therefore places its primary discriminator at the **midpoint**
of the window, offset `+0.548828125` (= 281/512, remainder 25/32 of a step),
which is `7/512 = 0.01367 px` from θ = 9/16 and the same distance from θ = 1.
That clears the realistic error by two orders of magnitude and the pessimistic
bound by 1.4x. If the pessimistic figure is the right one the capture says so
directly -- the five x vertices split `HIGH`/`LOW` within one frame -- and that
split is itself the measurement #49 is missing. Both outcomes pay.
