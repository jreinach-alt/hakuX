# Prediction: the line is in the right shape but the wrong place

Registered 2026-09-15 on `b932a902`, before measuring.

## The one hypothesis still standing

Six are refuted (`2026-09-15-line-joins.md` carries the ledger). What survives:
**a one-pixel position offset**, measured directly on two vertical edges --
at ODD widths our line starts one pixel left of the hardware's, at EVEN widths
they start identically, and the width itself is exact at every integer 1..48.

Everything else is consistent with it and nothing yet tests it along a segment:

- thickness at a segment midpoint is exact (raw pixel dump, 8 contiguous both);
- the frame still paints ~10% fewer pixels;
- the missing pixels sit ~W/2 from a segment -- at its EDGE -- and ~26px from
  any vertex, so they are spread along segments rather than at corners.

A line of the right thickness in the wrong place produces exactly that: every
cross-section the right size, edges displaced, and the displacement showing up
as missing pixels along the whole length.

## The instrument

Walk ALONG a segment. At each step, walk the normal and record the two EDGE
coordinates of the painted run -- not just its length -- in ours and in the
golden. Compare the edges, not the thickness.

**Per-sample control built in:** discard any sample where our own run length is
not within 1px of the requested width. That is the check that caught the
LINE_LOOP walk and the disc, and it must be applied per sample rather than in
aggregate.

## Predictions

**P1 (control).** On kept samples, our thickness equals the golden's. This is
already established at one point; here it must hold along the length. If it
fails, the instrument is contaminated and nothing else is read.

**P2.** The two edges are displaced by the SAME signed amount at each sample --
the run is translated, not stretched. A stretch (edges moving apart) would mean
a thickness difference and would contradict everything measured so far.

**P3.** The displacement is ~1px at ODD requested widths and ~0 at EVEN,
matching the vertical-edge result, and the sign is consistent along the segment.

## What kills it

Displacement ~0 at every width on a diagonal: the offset is vertical-only and
does not explain the residual. Displacement varying in sign or magnitude along
one segment: not a translation, and the "wrong place" story is wrong. Edges
moving apart rather than together: a thickness difference after all, which would
contradict the pixel dump and mean an instrument problem.

## Not assumed

That a confirmation licenses a fix. GL centres a wide line on the segment by its
own rule; matching a different centring convention is a rasteriser-level change,
`roundScreenCoords` in `glsl/vsh.c` is rasteriser-wide and needs the OWNER, and
the deliverable here is the rule and its evidence.

---

## Outcome: FALSIFIED. The offset is vertical-only, and the diagonal residual is sub-pixel.

Walking along the clean 77.7-degree segment, ~35 samples each, per-sample control
applied (discard where our own run is not within 1px of the requested width):

| W | kept | discarded | thickness ours / gold | near-edge shift | far-edge shift |
|---:|---:|---:|---|---:|---:|
| 3 | 34 | 2 | 2.75 / 3.00 | **+0.00** | **+0.00** |
| 4 | 33 | 3 | 3.75 / 4.00 | **+0.00** | **+0.00** |
| 7 | 30 | 6 | 6.75 / 7.12 | **+0.00** | **+0.00** |
| 8 | 31 | 5 | 8.00 / 8.00 | **+0.00** | **+0.00** |

**P3 falsified.** The displacement is 0.00 at every width, odd and even alike.
The one-pixel offset measured on the vertical edges is real there and **does not
generalise to a diagonal**. It cannot be the explanation for the residual.

**P2 not supported.** The per-sample near and far shifts are not equal to each
other, so what little difference exists is not a translation of the run.

**P1 marginal, and that is the instrument's floor.** Thickness medians differ by
0.25 to 0.37 at W=3, 4 and 7 and match exactly at W=8. The walk steps at 0.25px
with integer rounding, so a quarter-step median difference is at the resolution
limit; it means that at SOME samples along the segment the golden covers one more
pixel at an edge, and at others it does not.

## What that leaves, said plainly

Seven hypotheses are now refuted. The difference on a diagonal is **sub-pixel and
varies from sample to sample along one segment** -- not a width, not a position,
not a translation, not joins, not angle, not a clamp, not a per-primitive effect.

That is the signature of a **coverage / edge rule** difference, and it is the
class `classify_residuals.py` and `docs/investigations/edge-defect.md` already
document as "the same shape whatever produced them ... the precision floor of
interpolation, **not a rule to derive**".

**If that reading is right, most of `Line_width`'s 4,462,131 "actionable"
channels are not actionable** -- they are the documented floor wearing a
structural classification because the band is wide when the lines are wide. That
would be worth correcting in `corpus-residual-triage.md`, which ranks this suite
sixth on that number.

**It is a reading, not a measurement.** What is measured is the seven
refutations and the sub-pixel, sample-varying character of what remains.
Establishing the floor claim properly needs the boundary-shift classifier run per
capture on this suite with the band width scaled to the line width, which is a
different instrument from any used here and is not done.

## Method note

The per-sample control discarded 2 to 6 samples of ~36 in every arm. Without it
those would have entered the medians, and at these magnitudes a handful of
contaminated samples is the whole effect.
