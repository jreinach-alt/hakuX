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

Attempt 1 ended correctly, waiting on the arm (`[lane.cull13] waiting:` on
#403).  The arms job queued it as `1790435466-arms-cull13-{base-2947259,
fix-2947293}`, and both runs finished (`DONE`).  When handback resumed this
lane at 20:02Z, no `[job.arms]` verdict had been posted, so I judged the
two result dirs against the registered prediction myself:
`ab_compare.py --a <base> --b <fix> --expect
docs/testing/predictions/cull13-linemode-cull.json`.

**VERDICT: PASS, all 147 registered checks hold.**  better 12, worse 0,
same 401 of 413; exact 39 -> 43; regressed from exact 0.

| captures (x4 each: 0x00, 0x63, CW, CCW) | structural A -> B | bound |
|---|---|---|
| FrontFace_LM_*_CF_FaB | 3,911 -> 0 | <= 20 |
| the 3,030 rows (CW/0x00/0x63 CF_B, CCW CF_F) | 3,030 -> 688 | <= 720 |
| the 2,258 rows | 2,258 -> 689 | <= 720 |

The structural total dropped by 31,288, against cloud-13's 31,152 for
class A.  Shade_model (168), Line_width (61) and 3D_primitive (160) are
byte-identical across the arms: the only 12 captures that differ by byte
are the 12 movers.  There is one run per arm, but the result has no
counter-case: the "WORLD IN WHICH THIS FAILS" legs (FaB unmoved, the B/F
rows rising, a guard moving) all came out the other way.  What remains on
the 8 (688/689) is the tie-stroke and extent residual (B and D) that the
prediction said this hunk does not touch.  Front_face scored 24 of 36
goldens in both arms (the FM rows are a floor, and the same in both).

## Do not repeat

- QUADS / QUAD_STRIP / POLYGON under line mode reach geom.c as LINES; this
  hunk cannot cull them.  Carrying the polygon's winding through the rewrite
  is a separate design, and no capture scores it today.
