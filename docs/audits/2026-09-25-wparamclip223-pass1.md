# Audit pass 1: PR #250, lane wparamclip223 (#223, external wedge)

Auditor: job.cloud, 2026-09-25. Head audited: `3c3f845719`. What I read: the
full diff against `origin/master`. Outside the diff I also read each consumer
the new geometry-shader path reaches:

- `emit_vertex()` and the varying header (`glsl/common.c`
  `pgraph_glsl_get_vtx_header`);
- the vertex-shader position epilogue (`vsh-ff.c`, `vsh-prog.c`,
  `clampAwayZeroInf`);
- the fragment depth reconstruction (`psh.c`, which is built from
  `gl_FragCoord.xy` and the flat `vtxPos0..2`);
- the provoking-vertex notes in `prim_rewrite.c`.

**Verdict: no HIGH and no MEDIUM, but four LOWs.** The Vulkan arm passes, and
nothing in this pass needs a device. Pass 2 only has to confirm that each LOW
was either answered or deliberately left.

The geometry code has not changed since the arm's b_ref. `git diff 537ffb91ed
3c3f845719 -- hw/` touches only `vk/draw.c` and `vk/surface.c`, and both of
those come from master merges. The `[job.arms]` PASS on
`wparamclip223-wedge-grid.json` (451/451 checks, Thor, 18:40Z) therefore
measures the geometry shader that is at head.

## What was checked and holds

- **Every output is written.** `emit_wedge_vertex()` writes each varying that
  the header declares: D0/D1/B0/B1, Fog, FogSpecial, T0-T3, vtxPos0-2, triMZ
  and vtxPointSize. It also writes `gl_PointSize` except on GLES, which is the
  same exclusion `emit_vertex()` makes.
- **One weight set is enough.** `common.c` gives every *interpolated* varying
  the same qualifier. Colours take `smooth_s` when smooth, and Fog, T0-T3 and
  PointSize take `smooth_s` always. So `lam` under NOPERSPECTIVE and `al/S`
  otherwise is right for all of them. The flat ones are copied as
  `emit_vertex()` copies them:
  - colours come from `v[0]` under flat shading;
  - `vtxFogSpecial` comes from `v[0]`, which is what a first-provoking host
    takes from the original triangle;
  - vtxPos0-2 and triMZ come from `pz`.
- **The perspective weights are non-negative.** Inside the wedge lam_N <= 0
  and w_N < 0, so lam_N / w_N >= 0. The other two weights are >= 0 as well.
  The interpolated colours therefore stay a convex combination.
  - Under NOPERSPECTIVE, `lam` extrapolates (lam_1 + lam_2 = mu >= 1). That
    is the same affine field the host produced for the clipped triangle
    before, so it is not a change.
- **Depth is unaffected by the synthetic W'.** `psh.c` rebuilds depth from
  `gl_FragCoord.xy` and the flat `vtxPos*`. Nothing reads `gl_FragCoord.w`.
  Rasterised z is the triangle's own plane, because z/w is affine in screen:
  Z = dot(lam, zq). So host z-clipping of the wedge is the same clipping it
  applied to the original triangle, on both the GL spelling
  (`2z - w`) and the Vulkan one.
- **Winding and culling match the host.** Worked example: N at the origin,
  P1 = (1,0), P2 = (0,1), K > 1.
  - The polygon (P1, KP1, KP2, P2) is CCW.
  - The strip order 0, 3, 1, 2 gives (P0,P3,P1), and cross = -(K-1) < 0.
  - The odd triangle (P1,P3,P2) gives cross = -K^2 + K < 0.
  - Both are CW. That is the sign of the homogeneous determinant with one
    negative w, which is what the host's clipped polygon has.
  - `gl_FrontFacing`, and so the B0/B1 selection, is preserved.
  - Sutherland-Hodgman keeps the cyclic order, so any clipped np keeps this
    winding.
- **The lambda_N labelling is consistent.** `area = cross(q1-q0, q2-q0)`
  equals `cross(P1-N, P2-N)` for each n in {0,1,2}, because the cross product
  is invariant under cyclic rotation. So `1 - cross(P1-k,P2-k)/area` is mu at
  corner k.
- **mu is bounded correctly.** mu is affine in screen, so its maximum over
  the surface rectangle is at a corner. The trapezoid out to K = 2*max(mu, 1)
  therefore covers every on-screen part of the wedge. When the wedge is
  entirely off-screen, np reaches 0: nothing is emitted and the function
  returns true. That is correct, because nothing of it is visible.
- **The vertex bound holds.** A convex quad clipped by four half-planes has
  at most 8 vertices. The `nq < 8` guards cannot truncate a convex input, and
  the quad is a trapezoid.
  - Vulkan: 8 is below the 18 that `vk/instance.c` checks.
  - GL/GLES: the vertex needs roughly 53 components, and 8 x 53 = 424, well
    under the 1024 minimum.
- **The fallback is total.** A NaN or Inf in q, zq, the area, K, a far
  corner, S, Z or A returns false before `EmitVertex`, and the caller then
  emits the triangle as before.
  - `clampAwayZeroInf` sends -0.0 to -2^-64, so `lessThan(w, 0)` counts it as
    negative. That is the W_param `w-0.00` case, and it is intended.
  - w is never 0 or Inf after the vertex shader, so the division that makes q
    only goes non-finite through xy.
- **The grid gate is sound.** Zero area is tested on `pz[i].xy` (v_vtxPos,
  the truncated screen position) with `kahan_det`. That is the fix for the
  first arm's `w_gaps` leak. Both zero-area tests have to pass, so the gate
  only narrows the path.
- **`dump.c`.** The four new cases name real `GeomState` fields and
  `cylinder_wrap` values. They are not wired into CI (nothing under
  `.github/` references `geom_dump`), so they cannot break a build.

## Findings

### L1 (LOW): on GLES without the noperspective extension, the wedge gets a third interpolation answer

`emit_wedge()` chooses its weights at generation time, from
`state->noperspective`. On GLES, `NOPERSPECTIVE` expands to *nothing* unless
the device has `GL_NV_shader_noperspective_interpolation`
(`common.c:115-119`). The contract written there is that the GLES branch
"degrades ... exactly [to] what it was before".

**Failure scenario:** an Android GLES build on a GPU without the NV extension,
with texture perspective off (CONTROL_0 bit clear), drawing a filled triangle
with one negative w.

1. The wedge vertices carry affine `lam`-weighted values.
2. The varyings are declared `smooth`, so the host interpolates those values
   perspective-correctly under W' = smin/S.
3. Interior texels therefore match neither silicon (affine) nor the previous
   degraded answer (the triangle's own perspective field).

The blast radius is small. It needs GLES, no extension, perspective off and
one negative w. The previous answer was also wrong, and no arm runs GLES.

**Remedy, if wanted:** pick the weight expression in GLSL rather than in C.
Emit `#if defined(GL_NV_shader_noperspective_interpolation) || !defined(GL_ES)`
around the `lam` choice when `opts.gles` is set, so the wedge degrades
exactly as the varyings do.

### L2 (LOW): max_vertices goes from 3 to 8 on the hottest shader in the emulator, with no frame-time measurement

Every filled-triangle draw in every title now runs a geometry shader declared
with `max_vertices = 8` instead of 3. The per-triangle ALU for the common case
is small, because the early return fires when the count of negative w is not
1. But on several mobile GPUs the declared output size, not the emitted size,
sets how much output storage each geometry-shader invocation reserves. That
limits occupancy. Adreno is the device class this project ships on.
`NOTES.md` has no frame-time or throughput number for the change.

**Failure scenario:** a geometry-heavy title on the Thor loses frame rate on
every draw, including draws that never contain a negative w. No capture would
show this, because the goldens score pixels, not time.

**Remedy, if wanted:** one before/after frame-time sample on a heavy scene.
If the cost is real, compile two filled-triangle variants and select by a
cheap guest-side predicate. That is out of scope for this lane.

### L3 (LOW): `vtxFogSpecial` provoking source differs from `emit_vertex()` on Android GLES

`emit_wedge_vertex()` pins `vtxFogSpecial = v_vtxFogSpecial[0]`.
`emit_vertex()` writes `v_vtxFogSpecial[index]`, and the host takes the flat
value from its provoking output vertex. That vertex is index 0 on Vulkan and
desktop GL, which are first-vertex. On Android GLES it is index 2, because
`gl/draw.c`'s `glProvokingVertex` sits under `#ifndef __ANDROID__` (see
`prim_rewrite.c:146-155`).

**Failure scenario:** on Android GLES, when `vtxFogSpecial` differs across a
triangle's vertices, a one-negative-w triangle now takes it from v0 where its
neighbours take it from v2.

This is arguably the more correct answer, since v0 is the guest's provoking
vertex after the rewrite. It is recorded so that the difference is a known
one and not a surprise.

### L4 (LOW): seams along the N->P ray edges are not bit-shared between neighbouring wedges

The P1-P2 edge is copied exactly, as the comment says. The ray edges are not.
Two triangles that share the edge N-P1, each with N as their only negative
vertex (for example a fan around a vertex behind the camera), each build
`N + K*(P1-N)` with their own K. After the Sutherland-Hodgman cut at a
surface edge, the two far points differ by float rounding, so the shared ray
edge is two lines a few ulps apart.

**Failure scenario:** in a mesh crossing the camera plane, an occasional
pixel along that ray is dropped or drawn twice. At NDC error of about 1e-7
over about 1000 px of edge, the expectation is well under one pixel per edge,
and subpixel snapping usually merges the two far points. The host clipper
gave no watertightness guarantee here either.

**Remedy, if wanted:** none needed now. If a seam ever shows up, derive the
far point from the shared edge alone, for example K taken from a function of
(N, P1) and not of the whole triangle.

## Not findings (scope, recorded for pass 2)

- Two-negative-w triangles and the flat-quad adjacency path (#235) are
  deliberately left on the host clipper. The code comment and NOTES both say
  so, and the ff quads already match silicon.
- GL and GLES are verified by compilation only (geom_dump under the NDK's
  glslc). The arm is Vulkan. That matches the lane's stated scope.

## For pass 2

There is no HIGH or MEDIUM scenario to re-fire. For each of L1-L4, pass 2
should record one of two things: that it was answered (a commit), or that it
was left deliberately (a line in `docs/lanes/wparamclip223/NOTES.md`). No
device run is needed.
