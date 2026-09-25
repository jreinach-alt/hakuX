# lane.shadeflat224 -- #224 family A: flat quads on silicon's diagonal, v3 still flat

Brief: implement the fix `docs/lanes/shade224/NOTES.md` section 4 specifies
(PR #232), and run the arm it names.

**Status: patch committed (3ce8778094), prediction registered
(`docs/testing/predictions/shadeflat224-flatdiag.json`, a_ref a6bb4a13d4 =
master at branch time, b_ref 3ce8778094). Waiting on the device arm.**

## 1. What changed

In Flat mode `rewrite_quads()` split on v1-v3 and `rewrite_quad_strip()` on
v0-v3, so v3 was in both triangles. Silicon uses the Smooth diagonal in Flat
mode as well, and still colours from v3. A triangle list cannot have both,
because (v0, v1, v2) does not contain v3.

A flat, **filled** QUADS/QUAD_STRIP draw is now emitted as
triangles-with-adjacency, `(a, v3, b, v3, c, v3)`:

| file | change |
|---|---|
| `vsh_regs.h` | new `PRIM_TYPE_TRIANGLES_ADJACENCY`, never a guest mode |
| `prim_rewrite.[ch]` | `flat_quad_adjacency()`, `pgraph_prim_rewrite_get_draw_mode()`, `emit_tri_adj()`, adjacency branches in both quad rewriters, `max_output_indices()` doubles per-triangle count, `needs_rewrite(ADJ)` false, `PrimAssemblyState::no_adjacency` |
| `glsl/geom.c` | `layout(triangles_adjacency) in`, draws slots 0/2/4, flat varyings **and vtxFogSpecial** from slot 1, `calc_triz(0, 2, 4)`; geom state uses the draw mode |
| `vk/draw.c` | `TRIANGLE_LIST_WITH_ADJACENCY`; draw queue's `verts_per_prim` = 6 |
| `vk/shaders.c` | cached-state refresh uses the draw mode (it overwrote `geom.primitive_mode` with the plain output mode, which would have undone the whole change on the fast path) |
| `gl/shaders.c`, `gl/renderer.h` | `GL_TRIANGLES_ADJACENCY` (value-guarded define for GLES 3.0/3.1 headers) |
| `gl/draw.c` | `no_adjacency` when there is no geometry stage; `gl_draw_mode()` draws `GL_TRIANGLES` then |
| `docs/testing/geom_dump/dump.c` | adjacency cases for vk, GL, GLES 3.20 |
| `docs/testing/nv2a_index.json` | regenerated for the line moves (951 symbols / 2841 sites, unchanged) |

`pgraph_prim_rewrite_get_output_mode()` is kept as the topology class and
maps ADJ -> TRIANGLES, so `psh.c`'s stipple test is unchanged. The Vulkan
draw-queue flush sets `pg->primitive_mode` to the binding's mode, so
`get_draw_mode(ADJ)` returns ADJ.

POLY_MODE_LINE (`rewrite_*_line`) and POLY_MODE_POINT keep what they had.

### Target availability (the brief's stop condition): available everywhere a geometry shader runs

- **Vulkan (every device arm, Adreno/Turnip included):** list-with-adjacency
  needs only the `geometryShader` feature, which `vk/instance.c:842` already
  requires. `primitiveRestartEnable` is `VK_FALSE`, so no restart feature
  is needed. No dynamic topology is used.
- **Desktop GL:** core since 3.2, and this renderer always attaches a geometry
  shader.
- **GLES (Android GL renderer):** core in 3.2, `_EXT` in GL_EXT_geometry_shader.
  It is available exactly when `r->geometry_shaders_supported`. Without it
  `gl/shaders.c` attaches no geometry stage. The draw then falls back to the
  old v3 diagonal (`no_adjacency`), which has the old texture fault and
  nothing worse. That renderer already has worse flat-shading faults with no
  geometry shader (see the comment in `generate_shaders()`).

So adjacency is not missing on any target. The one target without it is also
without the geometry shader, and that renderer is already degraded.

## 2. Offline checks

- All 62 nv2a translation units compile with `-fsyntax-only` against the
  desktop build's flags. No new warnings.
- `geom_dump`: `quad_flat_adjacency_vk` compiles with the NDK's
  `glslc -fshader-stage=geom --target-env=vulkan1.0`. `_gl` and `_gles320`
  compile for `--target-env=opengl -fauto-map-locations`, as do the existing
  GL controls. Without `-fauto-map-locations` the existing GL shaders fail too,
  on SPIR-V's location rule.
- Rewrite unit check (scratch harness linking `prim_rewrite.c`, output
  verbatim):

  ```
  quads flat fill       draw=ADJ n=24: 0 3 1 3 2 3 0 3 2 3 3 3 | 4 7 5 7 6 7 4 7 6 7 7 7
  quads smooth fill     draw=TRI n=12: 0 1 2 0 2 3 | 4 5 6 4 6 7
  quads flat noadj      n=12: 3 0 1 3 1 2 | ...     (old path)
  quads flat point      draw=TRI n=12: 3 0 1 3 1 2 | ... (old path)
  quads flat line       draw=LINES (rewrite_quads_line, unchanged)
  qstrip flat fill      draw=ADJ n=24: 0 3 1 3 2 3 2 3 1 3 3 3 | ...
  qstrip smooth fill    draw=TRI n=12: 0 1 2 2 1 3 | ...
  ```

  Slots 0/2/4 are the Smooth split vertex for vertex, and slots 1/3/5 are v3.

## 3. The arm

`docs/testing/predictions/shadeflat224-flatdiag.json`. Disc: the 13
`nv2a_index.py blast` suites that have goldens (`Surface as vertex array` has
none), which includes #194's 2D_Lines, Edge_flag, Front_face, Line_width and
W_param.

- **must_move:** the 12 `*Tex` Quad/QuadStrip Flat captures, as
  `expect_counts better = 12, worse = 0`. `ab_compare`'s `expect` is exact
  equality, so the magnitude is prose, and I check it here by hand. Each
  capture should fall to at most its Smooth sibling + 200. Baseline, from
  `1789968297-arms-primpv13-fix-2094234` (binary identical to master for
  this suite, per shade224 section 0):

  | capture (First = Last) | now | bound |
  |---|---:|---:|
  | W_FixedTex_QuadStrip_Flat | 98,922 | <= 214 |
  | W_FixedTex_Quad_Flat | 42,185 | <= 224 |
  | FixedTex_QuadStrip_Flat | 43,456 | <= 206 |
  | ProgTex_QuadStrip_Flat | 43,453 | <= 315 |
  | ProgTex_Quad_Flat | 4,778 | <= 229 |
  | FixedTex_Quad_Flat | 4,313 | <= 304 |

- **must_not_move (bit-identical score):** the 12 untextured Flat quads that
  pin v3 as the colour source. This is tighter than shade224's +-300,
  because on a convex quad both diagonals tile the same pixels with the same
  flat colour. Also every Smooth, Tri*, Poly and ProgLM_* capture, and
  every other suite. Only `shade_model_tests.cpp` sets FLAT, and
  `test_suite.cpp` resets SMOOTH before each test. The prediction names the
  patch change that would move each leg.
- **Stability:** four primpv13 arms (two refs, two runs each) reproduce every
  row of those 7 suites exactly at each ref. The six other suites have no
  multi-run record here, so rerun a lone move in one of them before reading
  it.

## 4. Verdict

**Waiting (2026-09-25).** The prediction is committed and pushed with its refs,
so the host's arms job queues it. The signal that resolves the wait is the
`[job.arms]` verdict comment on PR #235. On resume:

1. Read the verdict. Then check the magnitude table in section 3 by hand
   against the b arm's `scores1.tsv`, because `ab_compare` cannot state
   "<= Smooth sibling + 200".
2. If the 12 do not move at all, suspect wiring before the model: is the
   pipeline's topology ADJ, and did the geometry shader compile? A failed
   Vulkan compile draws nothing, so the untextured Flat quads would jump
   too. Look for the arm's logcat shader-compile errors.
3. Record it here, then mark the PR ready.

Preflight passes on 574bb4f7d3. The nv2a index was regenerated: line moves
only, with the tests tree at the committed provenance.

## 5. Do not repeat

- A plain revert of the flat branch fixes the texture and breaks the v3
  colour. See shade224 section 4.
- `get_output_mode()` has four callers. Changing what it returns for flat
  quads would have broken `psh.c`'s stipple test (`== PRIM_TYPE_TRIANGLES`).
  Hence the separate `get_draw_mode()`.
- `vk/shaders.c`'s cached-state fast path re-derives `geom.primitive_mode`
  on every primitive change. Miss it, and the shader and the index stream
  disagree about adjacency on the second draw.
