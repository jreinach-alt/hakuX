# Prediction: the cross-width colour drift replicates on other angles and primitives

Registered 2026-09-15 on `d913c9dd`, before measuring.

## The claim under test

`d913c9dd` reports a mechanism: the hardware gives a wide line **one colour
across its width** -- the vertex colour interpolated at that parametric position
ALONG the line -- while we expand the line into geometry and interpolate
**across the width** as well, so one edge drifts toward a different vertex's
colour.

It rests on **one segment of one primitive at two widths**. That is not enough to
edit a shader on, and `d913c9dd` says so. This replicates it.

It also has a specific way of being wrong that the original measurement did not
control for. The original walked a fixed distance across the width. If that walk
left our line -- onto a neighbouring segment, past a cap, or into background --
the far-edge value would be foreign to the line and the "drift" would be
contamination, which is exactly how the disc instrument failed in `cc41abef`.

## The instrument, and what is different about it

For a chosen segment, at parametric position `s` along it, walk perpendicular
from the centreline in both directions and **stop at background** (`0x202224`),
separately for ours and for the golden. Sample only the pixels painted in BOTH.
Report per-channel spread (max - min) across the width.

Segments are taken from the test's own source geometry
(`nxdk_pgraph_tests/src/tests/line_width_tests.cpp`) offset by `(160, 48)`, not
eyeballed from the image, and each is chosen for clearance from every
non-adjacent segment.

## Predictions

**P1 -- replication.** On a clean segment in a DIFFERENT primitive at a CLEARLY
DIFFERENT angle, at W=32: the golden's per-channel spread across the width is
small (<= 8 on every channel) and ours is large (>= 40 on at least one channel).

**P2 -- angle-independence.** It holds at a near-horizontal angle as well as a
near-vertical one. The mechanism is about the width direction, which exists at
every angle; if the drift only appears near one orientation it is not this
mechanism.

**P3 -- the drift grows with width.** The same segments at W=8 show the same
sign of effect at a smaller magnitude, and at W=1 there is no cross-width
variation at all because there is no width.

## Controls, declared in advance

**C1 -- run length.** The background-bounded run must be within +/-2 of the
requested width on BOTH sides. A sample that fails this has left the line and is
discarded, not interpreted.

**C2 -- W=1.** Ours must show near-zero spread across the width at W=1. A large
spread there means the walk is straying and every W=32 number is contaminated.

**C3 -- variation ALONG the line.** Both ours and the golden must vary along the
segment. If the golden is constant in both directions the segment is flat-shaded
for some other reason and proves nothing about the width direction.

## What kills it

- The golden's spread comparable to ours (within 2x) on the replication
  segments: the golden is not constant across the width in general, and
  `d913c9dd` measured an accident of one segment.
- Ours' spread small (< 16 on every channel) at W=32 on the replication
  segments: the drift is not a general property of our wide lines.
- C1 or C2 failing: the original instrument was straying, `d913c9dd`'s far-edge
  value `(255,112,194)` was a neighbouring primitive or the background, and the
  mechanism has no support at all. **This is the outcome I am most concerned
  about and the reason the controls are declared here rather than added after.**

## Why it matters

`d913c9dd` is the first positive result after eight refuted hypotheses, and the
fix it implies is in `glsl/geom.c`, which is `[free]` in `territory.toml` and
belongs to someone else. Handing a one-segment finding to another lane as a
mechanism would be handing over my own speculation. Either it replicates and the
handover is worth acting on, or it does not and I retract it before anyone
writes a shader against it.

---

## Outcome: the effect replicates, `d913c9dd`'s segment does not, and the mechanism is different

**C1 failed on `d913c9dd`'s own segment, and that is the headline.** The "clean
77.7-degree segment" is the `TRIANGLES` edge `(392.0, 150.5) -> (404.0, 95.7)`,
whose nearest non-adjacent neighbour is 23.2 px away. At W=32 the perpendicular
run stopping at background is **50 px on ours and 56 on the golden**, against a
true thickness near 31 and 34. The walk left the line and never reached
background, so the far-edge value `(255, 112, 194)` reported in `d913c9dd` is a
neighbouring primitive. **Those numbers are withdrawn.**

The control that caught it was declared in this file before the measurement ran,
which is the only reason it was caught rather than published a second time.

**P1 held** on three clean segments in two other primitives at W=32 --
per-channel spread ours vs golden: `QUADS` at 170.5° **17 vs 3**, `QUADS` at
77.5° **25 vs 3**, `POLYGON` at 76.8° **20-23 vs 3**.

**P2 held, and then over-held.** It replicates at near-horizontal (170.5°) as
well as near-vertical (76.8°, 77.5°) -- but `QUAD_STRIP` at exactly 90° gives
spread **0 on both sides at every width**. The effect is not merely
angle-independent-or-not; it is **zero on axis-aligned lines**, which no version
of "we interpolate across the width" predicts.

**P3 held.** Ours' spread at `QUADS`@170.5 s=0.50 runs 0, 4, 7, 17 at W = 1, 8,
16, 32 while the golden stays 0, 3, 3, 3. Linear in W for ours, flat for the
golden.

**C2 passed.** At W=1 ours' spread is (0,0,0) on every segment: the walk is not
straying.

**C3 passed.** Both vary along the line at every segment measured.

## And the numbers that were not being looked for

The perpendicular runs at W=32 were 32, 31, 32 and 32 px at 170.5, 77.5, 76.8
and 90 degrees -- and **23 px at 45.4 degrees**. `32 * cos(45.4°) = 22.8`. That,
with the zero-on-axis colour result, is one rule rather than two, and it is
tested in `2026-09-15-gl-wide-lines-are-axis-offset.md`, which supersedes this
file's framing of the mechanism.

The replication did its job in the way that matters least comfortably: it
confirmed the phenomenon, invalidated the evidence that had been published for
it, and pointed at a different cause.
