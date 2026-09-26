# cloud-282b: an attribute-plane setup model for the texel-tie direction (#282)

Follow-up to `docs/lanes/cloud-282/` (PR #314). Desktop only, no device, no
`hw/` edit.

## Pre-registration (committed before the model was run)

**Geometry, from source.** Every FF checkerboard draw calls
`SetXDKDefaultViewportAndFixedFunctionMatrices()` and then
`DrawCheckerboardUnproject` (pbkitplusplus `nv2astate.cpp:931,1512`). The
camera is at z = -7 looking at the origin, and the helper unprojects the four
screen corners onto world z = 1. So every vertex has view depth 8 and
**w = 8 exactly at all four vertices**: 1/w is a constant plane and cannot
introduce a per-triangle error. The helper's screen x and y come back from a
float unproject and re-project, so each vertex lands at its integer corner
plus the 0.53125 viewport offset, **plus a float error of a few ulps**
(ulp(640) = 6.1e-5 px). 0.53125 is 8.5/16, the exact midpoint of the 1/16
grid, so the sign of that error decides a round-to-nearest snap and has no
effect on a truncating one.

**The model.** Per triangle: snapped vertex positions, plane coefficients
(dv/dx, dv/dy, and a reference vertex) computed from them, evaluated at the
pixel centre; a tie pixel goes down iff the evaluated v is below the exact
tie. The free choices are the snap rule and each vertex's error sign, the
reference vertex, and whether setup and evaluation are exact or float32.

**What a hit looks like, before running it.** The fit target is the sign
map in `cloud-282/NOTES.md`. A setup model explains the tie direction only
if, with its choices fixed on the part of the map outside the discriminating
region (rows 15-105, T2, and rows >= 255), it also predicts the
discriminating region it was not fitted on:

- the up band at x 320-479 on rows 135-240 inside T1, and
- the all-up cut between rows 240 and 255,

and scores **more than 95.2%** of the 284,681 FF+VS v <= 128 tie pixels
(the #314 fit), while keeping the controls: u ties up (>= 99.8%), v ties
v >= 136 up (>= 99.9%), VS draws up.

**Falsified** if no configuration in the family beats 95.2%, or if the
configurations that do beat it need the band itself to choose them (a fit,
not a model). The checkerboard suites are not independent geometry: every FF
draw has the same four vertices, so "held out by suite" would be the same
pixels scored twice. The held-out set here is the discriminating region.
