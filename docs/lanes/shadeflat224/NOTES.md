# lane.shadeflat224 -- #224 family A: flat quads on silicon's diagonal, v3 still flat

Brief: implement the fix `docs/lanes/shade224/NOTES.md` section 4 specifies
(PR #232), and run the arm it names.

**Status (attempt 2, 2026-09-25): the arm ran. Family A moved exactly as
registered, 12 better and 0 worse, every capture inside its bound. The arm's
FAIL comes from 56 W_param captures that were UNREADABLE in the B run, not
from 52 that got better. Every readable W_param capture is byte-identical
between the arms. See section 4. PR marked ready. The W_param legs are
unmeasured until the same registered arm is rerun.**

**Attempt 3 (2026-09-25): replicate registered, waiting on its arm.** The host
accepted the unreadable diagnosis (and withdrew its #223 heads-up), but the FAIL
and `regressed` stand because W_param's must_not_move legs have no valid
measurement. See section 4d.

Why attempt 1 did not finish: it did, as a wait. It pushed the registered
prediction, posted the wait and stopped. Attempt 2 is the handback on the
verdict.

Why attempt 2 did not finish: it diagnosed the FAIL correctly and marked the
PR ready, but it could not get the W_param legs a valid measurement. It asked
for a rerun of the same prediction, but this lane may not run `ab_run.sh`, and
the arms job will not re-queue a pair with one valid half, because its RAN
set counts the done halves. The rerun had no actor. Attempt 3 gives it one: a
new prediction file gets a new sha, and the arms job queues that.

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

`[job.arms] VERDICT: FAIL -- 53 of 461 checks violated`. Pair
`42c014b32fab...`: A = `1790327180-arms-shadeflat224-base-820902` (a6bb4a13d4),
B = `1790327180-arms-shadeflat224-fix-820924` (3ce8778094), both on thor
(bdc158a5), one run each. The prediction is PRE-REGISTERED and unedited.

### 4a. Family A: PASS, inside every registered bound

| capture (First = Last) | A | B | bound | ok |
|---|---:|---:|---:|---|
| W_FixedTex_QuadStrip_Flat | 98,922 | 14 | <= 214 | yes |
| W_FixedTex_Quad_Flat | 42,185 | 24 | <= 224 | yes |
| FixedTex_QuadStrip_Flat | 43,456 | 6 | <= 206 | yes |
| ProgTex_QuadStrip_Flat | 43,453 | 115 | <= 315 | yes |
| ProgTex_Quad_Flat | 4,778 | 29 | <= 229 | yes |
| FixedTex_Quad_Flat | 4,313 | 104 | <= 304 | yes |

Shade_model total: 3,757,098 -> 3,283,468 (-473,630). The registered value
was 3,282,884 +- 3,000. The 12 untextured Flat quads (the v3 colour pin) and
every other Shade_model capture did not move. Byte check: 68 captures differ.
These are the 12 above plus the 56 unreadable ones below, and nothing else.

### 4b. W_param: 0 real movers. The 52 "better" are unreadable captures scored as 0

The verdict lists 52 W_param captures as "better ... now exact". Every one of
them carries `[status ok -> unreadable]`. The chain:

- `score_sweep.py:147-161`: when a capture PNG will not open, the row is
  `status = unreadable, differing = 0`.
- `ab_compare` reads that 0 as a score, so a capture that could not be
  read becomes "repaired to exact".
- B's `scores1.tsv` has **56** W_param rows `unreadable` with `pixels = 0`,
  and A has none. That is the 52 "movers", plus the 4 the byte check called
  "same, 0 -> 0, PIXELS MOVED" (`prog_w_zero_inf__bitri_w{1,2,4}.00`,
  `_winf`, which were already 0 in A).
- B's own `run1.log` says so: `W_param 28/54 ... PARTIAL COVERAGE: W_param 54
  of 110`. A's says `32/110`. But `result.json`'s `captures_vs_goldens`
  records W_param as 110 of 110 and not partial, because it counts the
  unreadable rows as scored.
- Every **readable** B W_param capture (52 ok + 2 white-content) is
  byte-identical to A. Hashing 451 captures found 68 differing, and 12 + 56
  = 68.

Which ones were unreadable (B, in `scores1.tsv` order):

| group | unreadable in B | readable |
|---|---|---|
| `ff_w_zero_inf__bitri_*` | w-7.52e-37, w0.00, w0.25, w0.50, w1.00, w2.00, w4.00 (7) | 12 |
| `ff_w_zero_inf__quad_*` | w-0.25, w-0.96e-34, w-3.08e-33, w0.25 (4) | 16 |
| `prog_w_zero_inf__bitri_*` | all but w-0.00 (19) | 1 |
| `prog_w_zero_inf__quad_*` | none | 20 |
| `rcc_w_zero_inf__z*` | all 20 | 0 |
| `w_gaps`, `w_gaps_tex_persp`, `w_neg_strip*`, `w_pos_strip*` | all 6 | 0 |
| `ff_w_zero__*` | none | 4 |

Unreadable, and not re-rendered. A mechanism that changes pixels cannot
make a PNG fail to open. W_param never reaches the new path anyway:
`test_suite.cpp:177` resets `SET_SHADE_MODEL SMOOTH` before every test,
only `shade_model_tests.cpp` in `nxdk_pgraph_tests/src/tests` sets FLAT, and `flat_quad_adjacency()` requires
flat shading. The B guest also exited cleanly (`qemu_main returned 0`,
02:19:48, about 158 s against A's 166 s), and all 452 files were extracted.
So the files were truncated on the guest disk or during extraction, not lost
to a crash.
`unreadable` appears in 2 of every `scores*.tsv` under `dispatch/results`
(this run and one Depth_buffer row in `depth52-A`). The captures directory
has been pruned, so the truncated bytes cannot be examined now. Also,
`run1.log` for B says `ran 49s` and extracted 13.6 MiB against A's
`141s` / 17.6 MiB, which does not match B's own logcat timeline. I did not
resolve that.

**So #223's W_param residual is unchanged by this patch.** The
"5,117,044 -> 1,695,991 (-67%)" in the resume brief is 3.42M px of W_param
captures dropping out of the sum, not pixels fixed. #223 starts from A's
W_param numbers.

### 4c. What settles it, and what is wrong in the instrument

- **Rerun the same registered prediction on the same refs** (a6bb4a13d4 /
  3ce8778094, `--expect .../42c014b32fab....json`), preferably `--runs 2`.
  Do not re-register. The prediction already says W_param must not move,
  and it has not yet been measured. I tried to queue it with `ab_run.sh`.
  This session is not permitted to run it, so the host has to.
- Harness defects, for the host to brief, not for this lane's files:
  1. `ab_compare` scores an `unreadable` capture as differing = 0. An
     unreadable B capture should void its legs (not scored), not move them
     to exact.
  2. `result.json`'s `captures_vs_goldens` counts `unreadable` rows as
     scored, and `run1.log` does not.
  3. B's `run1.log` `ran 49s` against a ~158 s logcat lifetime.

### 4d. The replicate (attempt 3)

`docs/testing/predictions/shadeflat224-flatdiag-replicate.json`, sha256
`36509316d609...`. It is registered with `ab_compare.py --register` after
the last merge of `origin/master`. Its legs, `expect_counts`, disc and refs
(a6bb4a13d4 / 3ce8778094) are asserted equal to the original's field for
field. The only change is a replicate note at the head of the prose. It was
written before its arm ran, and it is not fitted to the first measurement:
W_param stays must_not_move, as it was.

When the verdict lands, read every mover's `[status]` tag before its "better"
or "worse". A PASS with W_param at 110 of 110 readable settles the legs. Any
`unreadable` row is a void leg again, not a result.

## 5. Do not repeat

- A plain revert of the flat branch fixes the texture and breaks the v3
  colour. See shade224 section 4.
- `get_output_mode()` has four callers. Changing what it returns for flat
  quads would have broken `psh.c`'s stipple test (`== PRIM_TYPE_TRIANGLES`).
  Hence the separate `get_draw_mode()`.
- `vk/shaders.c`'s cached-state fast path re-derives `geom.primitive_mode`
  on every primitive change. Miss it, and the shader and the index stream
  disagree about adjacency on the second draw.
- Do not read a verdict's "now exact" before its `[status ...]` tag. A
  move to `unreadable` is a capture that failed to open, scored as 0.
