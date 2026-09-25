# #224, family A: flat quads split on silicon's diagonal, with v3 still providing the flat values

Lane: shadeflat224            Issue: #224
Base: origin/master (fetch first).
Files: hw/xbox/nv2a/pgraph/prim_rewrite.c, hw/xbox/nv2a/pgraph/prim_rewrite.h,
hw/xbox/nv2a/pgraph/glsl/geom.c, hw/xbox/nv2a/pgraph/gl/draw.c,
hw/xbox/nv2a/pgraph/vk/draw.c, docs/testing/predictions/shadeflat224-*.json,
docs/lanes/shadeflat224/**
Needs device: yes (the arm). Needs NDK: no.

## The analysis is done. Read it first

lane.shade224 classified #224's whole residual. See PR #232, `fold-ready`, and
until it folds read it off `origin/lane/shade224`:
`docs/lanes/shade224/NOTES.md`, **section 4 specifies this fix**, plus
`shade_split.py` and `probe.py`. It re-derives #224 to the pixel (3,757,101).

| family | captures | px | this lane? |
|---|---|---:|---|
| **A. flat-quad diagonal** | *Tex x Quad/QuadStrip x Flat (12) | **474,214** | **yes** |
| B. FF lighting tie | Fixed/W_Fixed x Flat (18) | 884,185 | no: a 1-LSB rounding tie, (0,85,59) against silicon's (0,85,60) |
| C. Smooth interpolator wash | | 2,385,491 | no: routed to #223's wash (and #12/#58) |

## Family A's mechanism

`prim_rewrite.c:398-403` (`rewrite_quads()`) and `:473-478` (`rewrite_quad_strip()`)
split flat quads on v1-v3 / v0-v3, so v3 provokes both triangles. Silicon keeps
v0-v2 / v1-v2, and its Flat texture pattern is identical to that diagonal.

**A plain revert of the flat branch is WRONG.** It fixes the texture and breaks
the v3 colour, and the untextured Flat quads pin that colour to v3. So:

- emit silicon's diagonal as triangles-with-adjacency `(a, v3, b, v3, c, v3)`,
  so that v3 supplies the flat varyings without being a triangle vertex, and
  update `max_output_indices()`;
- in `glsl/geom.c`, add a `layout(triangles_adjacency) in` path that draws
  `gl_in[0,2,4]` with flat index 1;
- in `gl/draw.c` and `vk/draw.c`, map the new rewritten mode, wherever
  `PRIM_TYPE_TRIANGLES` maps to `GL_TRIANGLES` /
  `VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST`.

Check that adjacency topology is available on every target (GLES on Android,
Vulkan on Adreno, desktop GL). If it isn't on one, say so and stop. That is a
finding, not a failure.

## The arm, registered BEFORE any device run

The legs are in NOTES section 4:

- **must_move:** the 12 `*Tex` Quad/QuadStrip Flat captures, with direction and
  size;
- **must_not_move:** the untextured Flat quads that pin the v3 colour source,
  plus the rest of `nv2a_index.py blast` over your files. `prim_rewrite.c`
  also carries #13's provoking-vertex fix (PR #194, folded tonight), so its
  suites (2D_Lines, Edge_flag, Front_face, Line_width, W_param) are legs too.

Name, for each leg, the patch change that would move it.

## Done when

The arm's verdict is on your PR, NOTES record it, the PR carries the lane
template with its `Files:` line, preflight passes, and the PR is marked ready.
