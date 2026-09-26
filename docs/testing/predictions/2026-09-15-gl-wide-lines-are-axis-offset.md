# Prediction: GL aliased wide lines are axis-offset copies, and that is the whole defect

Registered 2026-09-15, before measuring the angle sweep.

## Where this came from

The replication of `d913c9dd` (see
`2026-09-15-cross-width-colour-replication.md`) produced two numbers that were
not what it was looking for. On clean segments at W=32 the perpendicular run
through our line was 32, 32, 31 and 32 px at 170.5, 77.5, 76.8 and 90 degrees --
but **23 px at 45.4 degrees**. And the cross-width colour spread was ~0.5, ~0.78,
~0.78 and **0.0** colour-steps per pixel of width at those same four angles.

Both numbers fit one rule, and it is not the rule `d913c9dd` proposed.

## The mechanism

`glsl/geom.c` emits `layout(line_strip) out` -- we do **not** expand wide lines
into geometry ourselves. `gl/draw.c:394` hands the width to `glLineWidth` and the
GL implementation rasterises it.

The OpenGL specification defines a non-antialiased wide line as the width-1 line
**replicated with an integer offset along the minor screen axis**: offset in y
for an x-major line, in x for a y-major line. It is not a perpendicular-width
rectangle. The Xbox hardware draws a true perpendicular-width line.

Two consequences follow, both purely geometric:

**A. Perpendicular thickness is short by the major-axis cosine.** A GL wide line
of width W covers `W * max(|cos t|, |sin t|)` perpendicular pixels. That is W at
0 and 90 degrees and `0.707 * W` at 45 -- a 29% shortfall that vanishes as the
line approaches either axis.

**B. Colour shears across the width.** All the offset copies share the same
major-axis coordinate, so iso-colour lines in our output are axis-aligned rather
than perpendicular to the line. Walking perpendicular therefore crosses colour
bands: the along-line parameter shifts by `W * min(|cos t|, |sin t|)` across the
full width. Zero on an axis, maximal at 45.

## Predictions

**P1 -- thickness.** Perpendicular thickness ours/golden equals
`max(|cos t|, |sin t|)` within +/-0.06 across the angle range, and the golden's
own thickness stays flat at ~W. Specifically at ~45 degrees the ratio is ~0.71,
not ~1.0.

**P2 -- colour shear.** Cross-width colour spread divided by (along-line colour
gradient x W) equals `min(|cos t|, |sin t|)` within +/-0.15, and the golden's
spread stays near zero at every angle.

**P3 -- both scale linearly in W** and both are zero for axis-aligned lines at
every W.

## What kills it

- A thickness ratio near 1.0 at 45 degrees. The GL-spec model predicts its
  largest, most visible effect there; if the shortfall is not there, the model is
  wrong and the 23 px reading was an artefact of one segment.
- A thickness ratio that does not track `max(|cos|,|sin|)` -- for instance a
  constant ratio at every angle, which would mean a plain scale factor (already
  refuted once, in `d902a5cd`, and it would have to be reinstated).
- Colour spread that does not vanish on axis-aligned lines, which would mean
  the shear is not from axis offsetting.

## Controls

**C1 -- per-sample clearance.** The earlier run's clearance metric excluded
segments sharing an endpoint, which is wrong for a wide line: near a segment's
ends the adjacent edge is well within W/2. Every sample here requires distance
>= W/2 + 4 to **every** other segment, adjacent ones included. This is the
control that the previous instrument lacked and that invalidated `d913c9dd`'s
one measured segment.

**C2 -- the golden is the control for the instrument.** If the perpendicular
walk were straying, it would stray in the golden too. A golden thickness that
stays flat at ~W across the whole angle range while ours dips at 45 is
self-validating; a golden that wanders means the walk is wrong.

## What it would mean

This is a geometry defect with an exact closed form, not a colour one, and the
colour difference is a **consequence** of it rather than a separate mechanism.
It also explains why "thickness is exact at every angle" was measured and
believed: the four angles sampled were 3.3, 10.1, 19.6 and 77.7 degrees, whose
`max(|cos|,|sin|)` are 0.998, 0.985, 0.942 and 0.977. **45 degrees was never
sampled**, and it is the only place the effect is large.

---

## Outcome: CONFIRMED. P1 exactly, P2 directionally, P3 fully.

**P1 -- thickness. Confirmed, and tighter than the tolerance asked for.** At
W = 8, 16, 32, 48, across all seven primitives and 25 distinct angle/primitive
combinations from 0° to 44.6° off-axis:

    per-cell    N= 31   mean( ours/W - max(|cos|,|sin|) ) = +0.0014  sd 0.0295  max|err| 0.101
    per-sample  N=275   mean( ours/W - max(|cos|,|sin|) ) = +0.0006  sd 0.0432  max|err| 0.181

The prediction allowed +/-0.06 and the realised per-cell sd is 0.030, smaller
than one pixel of quantisation at these widths; per sample it is 0.043, still
inside. Against the constant-ratio null models:

    ours/W = 1.00 constant:  sd 0.1146   max|err| 0.375
    ours/W = 0.90 constant:  sd 0.1146   max|err| 0.275

At ~45 degrees ours is **0.688-0.750 of W** where the golden is **1.062-1.125**.
The kill condition -- "a thickness ratio near 1.0 at 45 degrees" -- is not met,
and neither is "a constant ratio at every angle".

**C2 self-validated.** The golden's thickness is 1.063 x W on average
(sd 0.065, range 1.000 to 1.250) with no angle dependence across the entire
range. A straying walk would have strayed in the golden too.

**P2 -- colour shear. Confirmed in form, ~20% under in magnitude.**

| sample set | n | ours | golden |
|---|---:|---:|---:|
| axis-aligned, `min(\|cos\|,\|sin\|) < 0.05` | 56 | mean **0.62**, max 2 | mean 0.62, max 3 |
| near 45°, `min(\|cos\|,\|sin\|) > 0.60` | 55 | mean **24.40**, max 65 | mean 3.11, max 8 |

Ours and the golden are indistinguishable on axis-aligned lines -- means equal to
two decimal places -- which is the prediction's zero case and the sharpest part
of it. Over 152 samples where the closed form predicts more than 2 steps,
`observed / predicted` is **0.866 (sd 0.170)**.

The prediction allowed +/-0.15 on that ratio. **The mean meets it (0.866 is 13%
under) and the per-sample scatter does not (sd 0.170).** So P2 is confirmed in
its zero case and its trend, met on the mean, and missed on the scatter.
Recorded as the weaker of the two results rather than rounded up.

**P3 -- linear in W. Confirmed.** The thickness ratio holds at all four widths
(so the absolute shortfall grows linearly), and the colour spread at
`QUADS`@170.5 runs 0, 4, 7, 17 at W = 1, 8, 16, 32 while the golden stays flat.

## What is now established

Our wide lines are `W * max(|cos t|, |sin t|)` perpendicular pixels instead of W,
and their colour is banded on the screen axis instead of perpendicular to the
line. Both are zero on axis-aligned lines, both are extremal at 45 degrees, and
both scale linearly in W. One defect, closed form, seven primitives, four widths.

## What is not

The attribution to the GL specification's aliased wide-line rule is an inference
from agreement with that rule, not from reading the driver. The measurement
stands on its own; the explanation is the one that fits it.
