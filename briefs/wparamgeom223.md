# #223: rescale extreme-w triangles in the geometry shader, so the host clipper draws silicon's external wedge

Lane: wparamgeom223            Issue: #223 (W param)
Base: origin/master, AFTER PR #235 folds. `glsl/geom.c` is lane.shadeflat224's
until then, and #235 adds a triangles-with-adjacency path to it. Build on top
of that path, not beside it.
Files: hw/xbox/nv2a/pgraph/glsl/geom.c, docs/testing/predictions/wparamgeom223-*.json,
docs/lanes/wparamgeom223/**
Needs device: yes (a Thor W_param arm). Needs NDK: no.

## Start from the analysis: `docs/lanes/wparam223/NOTES.md` (on master, PR #228)

- **About half of W_param is WASH** (max-channel |d| of 1-2): 2,653,711 of
  5,117,044 px, and `rcc_` is 99.87% wash. It is routed to #38, the one-step
  colour-difference issue. **Not this lane.**
- **The RCC/MUL leads are refuted by measurement** (section 2). Do not repeat
  them. #112 item 4's silicon values for them arrive separately (lane.toolsmith).
- **The structural residual is external triangles at extreme w** (section 4).
  - `ff_w_zero_inf` + `prog_w_zero_inf__bitri` total 2,210,752 px, of which
    1,658,611 are coverage.
  - Each such triangle has one negative-w vertex, and silicon draws it
    projectively as the external wedge.
  - We pass negative w to the host clipper, which gives the same wedge only
    while the arithmetic is well conditioned.

## The job: NOTES section 5, a per-primitive uniform positive scale

In `glsl/geom.c`, scale all three clip-space vertices of a triangle by one
positive factor, so that `sqrt(max|w| * min|w|) = 1`. Homogeneous invariance
leaves positions and every perspective-correct varying unchanged. The only
effect is to move |w| away from 2^-64, where the host clipper fails.

- It fixes tri2's small-magnitude cases, e.g. `{-2^-58, 2^-64} -> {-8, 1/8}`.
- It CANNOT fix a 2^128 ratio (tri1 in `w-0.00`). That needs the triangle
  clipped in the geometry shader itself. It's a possible second step, not this
  one.
- It reaches TRIANGLES only (`pgraph_glsl_need_geom`), not quads, so the
  `ff_..._quad` family is out of scope.

## The arm (NOTES section 5, register BEFORE building)

Run it on the Thor, W_param.
- **must_move:**
  - `prog_w_zero_inf__bitri_w-1.88e-37`: 143,546 -> < 5,000
  - `_w-3.76e-37`: 143,494 -> < 5,000
  - `_w-7.52e-37`: 4,768 -> < 1,000
- **must_not_move:**
  - `prog_w_zero_inf__bitri_w-0.00` (271,518: the ratio case the scale can't
    reach; it FAILS if the model is wrong about ratio vs magnitude);
  - the 20 `prog_w_zero_inf__quad` at 0;
  - the vertex-shader suites that pass today;
  - `nv2a_index.py blast hw/xbox/nv2a/pgraph/glsl/geom.c`, which covers #235's
    Shade_model Flat captures and #13's suites.

**The world in which must_move fails:** tri2's failure isn't magnitude-driven
at all (for example, an Adreno guard-band or binning effect keyed on screen
extent), and then the scale changes nothing. Say so if that is what you find.

**Before trusting the verdict:** check both arms' `scores1.tsv` status column
for `unreadable`, and `run1.log` for "PARTIAL COVERAGE" and UtilAcceptVsock.
An unreadable capture scores as 0 and reads as "repaired to exact", and that
voided an arm on this very suite tonight.

## Do not repeat (NOTES)

- the RCC/MUL leads;
- scoring a desktop capture against these goldens: llvmpipe, Adreno and
  silicon disagree here, because the host clipper decides;
- desktop Vulkan under WSLg, which hangs.

## Done when

The arm's verdict is on your PR and its status column checks out, NOTES
record the result, the PR has the lane template with its `Files:` line,
preflight passes, and the PR is marked ready.
