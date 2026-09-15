# Prediction: the hardware fills line joins and we leave a notch

Registered 2026-09-15 on `1ddd53a1`, before measuring.

## Why this and not something else

Three hypotheses are already dead, each on its own measurement: the driver
clamp (painted count rises monotonically with no plateau), the per-primitive
concentration (every primitive carries the same ratio), and the square pen
(clean segments give a thickness ratio of exactly 1.000 at 3.3, 10.1, 19.6 and
77.7 degrees, where it predicted 1.057 to 1.278).

**Line thickness is now measured correct at every angle the instrument can read
cleanly, and at 90 degrees on two independent vertical edges.** Yet the frame
still paints ~10% fewer pixels than the golden. If the segments are right, the
difference has to be somewhere other than along a segment.

The contaminated rows from the square-pen pass point at one place: they cluster
where segments MEET, the golden reads far wider there (17.00 against our 7.75 at
one W=8 corner, 8.50 against 5.50 at another), and **our own thickness dips
BELOW the requested width at those corners**. A reading below W on a width-W
line is what a notch looks like.

## The hypothesis

GL draws each wide line as an independent quad and does not join them. The
hardware fills the wedge where two wide segments meet. So every corner in the
frame is a small patch of pixels the golden has and we do not.

## The instrument, with its control built in

A paired design on the `TRIANGLES` primitive, which has known vertices and is
sparse:

- **TEST discs** centred on each of the 6 vertices.
- **CONTROL discs** of the same radius centred at segment midpoints, far from
  any vertex.

Count painted pixels in each disc, ours and golden.

## Predictions

**P1 (the control).** Mid-segment discs give ours/golden ~ 1.000. This must
hold or the instrument is measuring something other than what I think, exactly
as the LINE_LOOP pass failed. **If P1 fails, nothing else in this measurement is
reportable.**

**P2 (the test).** Vertex discs give golden > ours.

**P3 (the scaling).** The vertex deficit grows with requested width, because a
wedge's area grows with W^2 while a segment's grows with W. At W=4 versus W=8
the per-corner deficit should grow by roughly 4x, not 2x.

## What kills it

Vertex discs matching at ~1.000 (P2 fails) means joins are not it, and the
deficit is somewhere I have not looked -- endpoints/caps and the POINTS
primitive being the obvious remaining places. A vertex deficit that grows
LINEARLY with width would kill P3 and point at caps rather than wedges.

## Not assumed

That this is fixable in `gl/draw.c`. GL has no line-join mode; matching the
hardware would mean drawing wide lines as geometry rather than as GL lines,
which is a rasteriser-level change. `roundScreenCoords` in `glsl/vsh.c` is
rasteriser-wide and needs the owner. The deliverable here is the rule and its
evidence.

---

## Outcome: THE CONTROL FAILED. Nothing here is reportable, and two of my instruments now contradict each other.

| W | control (mid-segment) ours/gold | test (vertex) ours/gold |
|---:|---:|---:|
| 4 | **0.863** | 0.872 |
| 8 | **0.868** | 0.880 |
| 16 | **0.698** | 0.907 |

P1 required the mid-segment discs to read ~1.000. They read 0.86 and worse. This
file said before the measurement that "if P1 fails, nothing else in this
measurement is reportable", so **P2 and P3 are not read and the joins hypothesis
is neither supported nor refuted here.** The vertex numbers are in the table only
so that nobody re-derives them and believes them.

## The contradiction, which is the actual finding

`2026-09-15-line-width-square-pen.md` measured line thickness at segment
midpoints by walking the normal, and got **ours/golden = 1.000 exactly** on every
clean segment, at 3.3, 10.1, 19.6 and 77.7 degrees and at two widths.

This measurement counts painted pixels in a disc centred on the *same* segment
midpoints and gets **0.86**.

Both claim to measure the same thing at the same place. They cannot both be
right. Per this lane's own rule -- a measurement that disagrees with the
arithmetic is the instrument until proven otherwise -- **at least one of these
two instruments is broken, and no further hypothesis should be built on either
until it is known which.**

Candidate explanations, none tested:

- The normal walk measures a CONTIGUOUS run from the midpoint and stops at the
  first unpainted sample. The disc counts every painted pixel within the radius.
  If the golden has painted pixels near the line that are not contiguous with
  its core -- a separate nearby feature, or a fringe with a gap -- the disc sees
  them and the walk does not.
- The walk samples on a 0.25 grid with integer rounding, so it can miss a
  single-pixel difference at an edge that the disc counts in full.
- The disc radius is `1.2 * W + 3`, which at W=16 is 22.2 px; the segments may
  simply not be long enough to isolate, and the W=16 control has n=1.

## What this costs and what it is worth

It costs the joins hypothesis, which remains untested. It is worth more than a
result would have been: three hypotheses have been killed on measurements from
the walk instrument, and if the walk is the broken one then **the square-pen
falsification is itself in doubt** and would have to be redone. That is exactly
the kind of thing a control is for, and exactly why the control was registered
before the numbers were seen.

Next: reconcile the two instruments on a single segment, by hand, pixel by
pixel. Not another hypothesis.

---

## Reconciled: the DISC is the broken instrument. The walk stands.

Dumping the actual pixels along the normal at the 77.7-degree segment's
midpoint, W=8 -- the same place both instruments read:

    ours  ..........oooooooo...........
    gold  ..........GGGGGGGG..........G

**Eight contiguous painted pixels, in the same position, on both sides.** The
walk instrument is correct: the thickness is identical. The single trailing `G`
at offset +14 is a different feature 14 pixels away, not this line's edge.

The disc at the same point reads ours 194, gold 225 -- 31 gold-only pixels. Their
offsets from the midpoint are scattered, in vertically adjacent pairs:
(-6,8) (-6,9), (-5,4) (-5,5), (-3,-4) (-3,-3), (-2,-9) (-2,-8), (1,10) (1,11),
(2,6) (2,7). **Those are not along this line's edges.** They are a neighbouring
segment passing within the 12.6px radius, which the golden paints and we paint
differently or not at all.

So the disc is contaminated by neighbouring geometry, exactly as the LINE_LOOP
walk was in the previous pass. Its control "failure" was the contamination, not
a real mid-segment deficit.

### Consequences

- **The square-pen falsification stands.** It rests on the walk, and the walk is
  vindicated here against a direct pixel dump.
- **The joins hypothesis is still untested.** A disc cannot test it at these
  radii because nothing in this frame is isolated by 12 pixels, let alone 22.
- **The `1.000` thickness results and the `0.86` frame ratio are both correct
  and not in conflict** -- they measure different things. Thickness along a
  segment is exact; the frame paints fewer pixels. The difference is therefore
  in pixels that are NOT along a segment's normal at its midpoint.

### The clue worth keeping

The gold-only pixels arrive in vertically adjacent PAIRS at scattered positions.
That is what a neighbouring near-vertical line one pixel wider, or one pixel
displaced, would produce. It is consistent with the odd-width one-pixel offset
already established on the vertical edges -- but consistent is not evidence, and
this is a note for the next instrument rather than a finding.

### Method note, general

Two instruments disagreeing is not a reason to pick the one you like. Dumping
the raw pixels at the disputed point cost one command and settled it outright.
Do that first next time, before writing up either as a result.
