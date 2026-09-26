# cull13 -- #13 class A: cull line-mode triangles by source face

Base: master @ 02374a6847 (after the fold of PR #379).  Hunk: d750443b2a.
Prediction: `docs/testing/predictions/cull13-linemode-cull.json`, registered
before any device run (`register.sh`, prose in `prediction.txt`).

## What changed

- `glsl/geom.h`: `GeomState` gains `line_cull_face` (CULLCTRL when CULLENABLE
  is set, else 0) and `line_front_ccw` (SETUPRASTER_FRONTFACE).
- `glsl/geom.c`, `pgraph_glsl_set_geom_state()`: fills them only when the
  OUTPUT primitive is `PRIM_TYPE_TRIANGLES` under `POLY_MODE_LINE`.  Every
  other draw keeps 0, so line primitives and fill mode generate the same GLSL
  text as before (the struct grows, so their keys still differ from old ones).
- `glsl/geom.c`, `pgraph_glsl_gen_geom()`: the line-mode triangle body, when
  culling is on, computes `face = kahan_det` of the source triangle's edges
  from `v_vtxPos` and returns before the three `emit_line()` calls if the
  face is culled.  With culling off the body is the old string verbatim.
- `vk/renderer.c`: `SHADER_STATE_LAYOUT_VERSION` 4 -> 5.  GeomState goes from
  24 to 28 bytes, but whether ShaderState's size changes depends on
  PshState's alignment, which I did not establish; a bump is correct either
  way.  No other open PR bumped it (checked 2026-09-26).
- `vk/draw.c` is NOT edited (lane.remote's).  Its comment at the widened-draw
  cull clear ("Silicon does not cull lines") still states the premise this
  refutes for line-mode triangles; the clear itself stays right, because the
  footprint's own winding means nothing.  Whoever next edits that hunk should
  point the comment at geom.c.

## The sign, derived rather than fitted

- Vulkan has no y flip here: `gl_Position = oPos` with ndc y = 2 y/H - 1, and
  a positive-height viewport, so guest screen y runs down as the framebuffer's
  does.  `v_vtxPos.xy` is the guest screen position (vsh-prog.c: rounded
  before the NDC map), finite for Front_face's w = 0 / INFINITY vertices.
- Vulkan's area is minus the edge cross product, and `vk/draw.c` maps
  FRONTFACE set -> `VK_FRONT_FACE_COUNTER_CLOCKWISE`.  So "CCW" is
  `face < 0`, front is `ccw == line_front_ccw`.  The FrontFace_FM_* captures
  are not in #13's residual, so that mapping matches silicon in fill mode.
- Zero area -> CCW (`!(face > 0)`), from the goldens: both zero-area
  triangles are culled and drawn with the CCW quad in all 12.  `kahan_det` on
  1/16-grid differences returns an exact 0 for collinear points.
- NaN face culls nothing (old behaviour); FRONT_AND_BACK culls everything.
- Strip parity: `prim_rewrite.c` reflects odd strip triangles `(v1, v0, v2)`
  and only rotates list/fan ones, so every triangle reaching the shader winds
  as the guest's did.  Guard: Shade_model/ProgLM_TriStrip_*.

## Checked offline

`check.sh` builds `cull_dump.c` against `docs/testing/geom_dump`'s objects and
compiles all 32 variants (Vulkan and GL, cull 0-3, CW/CCW, flat/smooth) with
the NDK's glslc: 32 of 32 compile.  No desktop build (known gap, AGENTS.md).
`preflight.sh --allow-tracker` passes; the nv2a index was regenerated against
the fold-pins test trees (the provenance master uses), and only this hunk's
sites changed.

## Arm

Waiting (2026-09-26): the arms job queues the committed prediction
(refs 02374a6847 / d750443b2a) and posts a `[job.arms]` verdict on PR #403.
On resume: cite that verdict here and in the PR, then mark ready if it holds;
if it fails, read which leg (see "WORLD IN WHICH THIS FAILS" in
`prediction.txt`) before touching the sign.

## Do not repeat

- QUADS / QUAD_STRIP / POLYGON under line mode reach geom.c as LINES; this
  hunk cannot cull them.  Carrying the polygon's winding through the rewrite
  is a separate design, and no capture scores it today.
