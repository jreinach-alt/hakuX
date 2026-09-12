# Fog_inf_coord is not a fog defect: it is three pixels of edge coverage

Measured 2026-09-12 on the scoreboard sweep, binary `fb4dfafc6d38`, one disc
per suite, `progress_log_proof` true. Six captures, 18 differing pixels in
total, `off_by_one` 0 on every row.

## The whole of it

Every one of the six captures differs at **exactly the same three pixels**:

| pixel | ours | golden |
|---|---|---|
| (333, 284) | the quad's colour | background `#303030` |
| (332, 286) | the quad's colour | background `#303030` |
| (315, 299) | background `#303030` | the quad's colour |

`AFF-linear-planar`, `AFF-linear_abs-planar` and `AFF-exp-planar` carry
`#FFFFFF` at those pixels; `AFF-exp2-planar`, `AFF-exp2_abs-planar` and
`AFF-exp_abs-planar` carry `#20207F`. So the **fog mode changes the colour of
those three pixels and never which pixels differ.**

That is the argument, and it is a strong one: if fog arithmetic were wrong, the
six modes would disagree by different amounts in different places, because
linear, exp, exp2 and their `_abs` variants are different functions. Instead
the fogged colour we produce is exactly the colour the golden has at the pixel
next door. What differs is **which pixels the primitive covers** — two we
cover that silicon does not, one silicon covers that we do not.

Coverage is not fog. This suite has no fog defect.

## What it is instead

Two pixels gained and one lost, on a diagonal edge, at fixed coordinates,
independent of the fragment shading. That is an edge-coverage tie: a vertex
whose transformed position lands close enough to a sample boundary that
hardware and host resolve it differently.

**#49 measured exactly this mechanism**, on a different suite, and measured it
to be a floor rather than a rule. There, both failing viewport offsets put the
post-offset coordinate exactly on a 1/16 grid line where the snap function is
the identity, so coverage was decided by the last bit of the transform above
it — and `vsh-ff.c:677` does `oPos.xy /= oPos.w`, a correctly-rounded fp32
divide, where the NV2A vertex ALU has no divide at all, only a
limited-precision reciprocal followed by a multiply whose ~2^-22 error is a few
ULP of a coordinate near 320. Note these three pixels sit at x = 315–333, i.e.
around 320.

#49 also established that no rule expressible in the snap function can fix it,
because every such rule is invariant under integer translation while hardware
resolves two vertices carrying the same fractional coordinate in **opposite**
directions.

MEASURED here: the three coordinates, their colours, their invariance across
all six fog modes, and `off_by_one` 0. INFERRED: that the cause is the same
transform-precision floor as #49. The inference is cheap to test — the
prediction is that these three pixels do not move for any change to fog, and do
move if the transform's reciprocal is ever modelled.

## Consequence for the backlog

`Fog_inf_coord` should not be counted against #8 (Fog). It is 18 pixels, it is
coverage, and on current evidence it is a precision floor shared with #49
rather than an independent defect. Anyone ranking fog work should drop it from
the list; anyone modelling the NV2A reciprocal gets it for free and should
expect exactly these three pixels to be among the first to move.
