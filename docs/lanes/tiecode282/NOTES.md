# lane.tiecode282: the weight-binade v-tie rule, implemented (#282, #283)

Base: master @ 7a2036020d. Code: `18dc4f11e2`. Prediction:
`docs/testing/predictions/tiecode282-binade.json`, registered before any build
or device run.

## 1. What was implemented

`hw/xbox/nv2a/pgraph/glsl/psh.c`, `append_texel_tie_rule()` and
`texel_tie_rule_stage()`, called at the end of `psh_convert()`. Each stage now
adds its own `texelTieBias<i>` instead of the shared constant. A stage the rule
does not reach gets `texelTieBias` itself, so nothing changes there.

A stage takes the rule when all of the following hold:

| condition | where it is checked | why |
|---|---|---|
| Vulkan renderer | generation time | `gl_FragCoord` shares `vtxPos`'s frame there, which the depth path already relies on. GL has not been checked. |
| fixed-function draw (`CSV0_D` mode 0, new `PshState::fixed_function`) | generation time | The VS-drawn checkerboards are all up (32,674 of 32,674, cloud-282). |
| smooth shading | generation time | A flat, last-provoking TRIANGLES draw is rotated by `prim_rewrite.c`, and the rule names vertices by their position in the triangle. |
| PROJECT2D on a 2D non-cube texture, or PROJECT3D on a 3D texture; not a shadow map, not the point-sprite stage | generation time | These are the sample sites the three geometries exercise. |
| v0, v1, v2 = UL, UR, LR of an axis-aligned right triangle | per fragment, exact compares on `vtxPos0..2` | This is the only vertex-role configuration measured. |
| equal w on all three vertices; texcoord q constant | per fragment | The interpolation is affine in all three geometries. |
| v constant along v0-v1 and rising toward v2 | per fragment, from `dFdx`/`dFdy` of t.y/t.w | Which vertex carries which v. Derivatives are used so no per-vertex texcoord varying is needed. |

Inside that configuration, l0 = (x1 - x)/(x1 - x0) and l2 = (y - y0)/(y2 - y0).
Every binade test is one of those differences multiplied by a power of two, so
it is exact on the 1/16 grid and the half-open ends fall where silicon's do. The
v half of the bias is negated iff

    l2 <= 1/2  and not (l0 in (1/4,1/2] and l2 in (1/4,1/2])

PROJECT3D on a 3D texture had no bias at all, which made our own Volume texture
tie direction noise (vol283r: 535 of our "down" picks, all wrong). It now takes
the bias as PROJECT2D does: u up, v per the rule. Without it the rule has no
sign to flip on that path.

**geom.c is not touched.** The brief expected per-vertex texcoords to be passed
flat from `geom.c`. The geometry stage's output is at exactly 48 components
(`PGRAPH_GEOM_VTX_COMPONENTS`), and one more vec4 per vertex would take
18 x 57 = 1,026 over the Vulkan minimum of 1,024 total output components. It
would also have collided with PRs #371 and #366, which both hold `geom.c`. The
screen derivatives give the same information in this configuration. The
derivatives are taken at the top of `main()`, before the clip code's `discard`.

`docs/testing/psh_differ/differ.c` probes the new field. `fixed_function=1`
changes the shader on the four textured baselines, and the emitted GLSL reads
as intended. The host has no GLSL compiler, so the device build is the compile
check.

## 2. What the evidence covers, and what it does not

- Covered: the checkerboard quad (w = 8, 640 x 480), Texture_render_target's
  BiTri (w = 7.1, 285.625 px), and Volume texture's four quads (w = 7,
  135 x 80). All three use T1 = (UL, UR, LR) with v = (0, 0, 1).
- Not covered, so it keeps "up": any other vertex order, T2 (UL, LR, LL),
  every u tie, projective interpolation, VS draws, and GL.
- **A known miss inside the configuration.** On checkerboard row 240, x = 480
  (l0 = 1/4 and l2 = 1/2, both exact), silicon is up on 3 of 3 captures and the
  published rule says down. Every other row at x = 480 is down, and x = 320
  (l0 = 1/2) is up, as the rule says. So at l2 = 1/2 exactly, l0 = 1/4 behaves
  as inside the band. I implemented the rule as published and did not patch
  that point: it is one pixel position with no second geometry behind it.
  The table is in section 5.

## 3. Coordination

- `psh.c`: PRs #367 (y16bump10) and #373 (fog278) also edit it, in
  `append_bump_channel` / `append_bump_coords` / `append_fog_factor`. They do
  not overlap this hunk. Before ready: merge master, or those branches if they
  have not folded, then re-run the arm.
- `psh.h`: #367 adds a field. The expected merge is a textual neighbour, not a
  semantic conflict.
- `stage_consumed_raw()` and the BRDF stage are untouched, as the brief
  requires (#315 lands there next).
- `docs/testing/nv2a_index.json` is regenerated because the new `CSV0_D` read
  is a new register site.

## 4. The legs (registered `tiecode282-binade.json`, a = 7a2036020d, b = 18dc4f11e2)

Disc: the nine checkerboard suites, Texture render target (RenderTextureLoop
skipped: in the 6-suite texvol283 arms it ran first and every TexFmt_* capture
then differed on the whole quad, 81,225 px), Volume texture, Texture BRDF,
Texture border, Texture format, Texture DXT, Texture signed component tests,
Texture Matrix, Texture perspective, Texture palette, Texture 3D as 2D,
Texture 2D as cubemap, Pixel shader, Point params, Bump env lum.

| leg | kind | predicted | fails if |
|---|---|---|---|
| Volume_texture/Y16 | expect | **0** | the rule is inert on 3D (2,605), only the bias acts (2,070), or the rule is wrong on a Y16 tie |
| Texture_render_target/TexFmt_A8R8G8B8 | expect | **0** (71 today on 1790359589: row 240, columns 392-462) | the rule is inert on 2D, or the composition does not reproduce the 71 baseline |
| 9 checkerboard suites, Texture_render_target/*, Volume_texture/* | must_not_regress | FF checkerboards better; VS ones unchanged; other TexFmt_* toward 0; Volume captures toward 0 | any capture worse |
| Texture_BRDF, Texture_format, Texture_DXT, Texture_signed_component_tests, Texture_Matrix, Texture_perspective, Texture_palette, Texture_3D_as_2D, Texture_2D_as_cubemap, Pixel_shader, Point_params, Bump_env_lum, Texture_border/3D_BorderTex_SZ_* | must_not_move | bit-identical | the configuration test reaches a draw the evidence does not cover. That refutes the scoping, not the rule. |

Left off the disc to save device time: Texture_shadow_comparator (288 captures;
shadow stages are excluded by construction) and Texture_cubemap (73; cube
stages are excluded by construction). The claim that they cannot move rests on
that construction, not on a measurement.

Verdict: pending, from the arms job's `[job.arms]` comment on PR #379.

## 5. Exact-binade columns on the checkerboard (goldens, FF v ties)

`golden down / total` per row, from `extract.py` over the three #314 result
directories.

| x | l0 | rows 135-225 (l2 in (1/4,1/2)) | row 120 (l2 = 1/4) | row 240 (l2 = 1/2) |
|---|---|---|---|---|
| 320 | 1/2 | up (0/19, 0/25, ...) | down 3/3 | up 0/2 |
| 480 | 1/4 | down (22/22, 25/25, ...) | down 3/3 | **up 0/3** (rule: down) |
| 481 | < 1/4 | down | down 3/3 | down 3/3 |

## Do not repeat

- Do not add a per-vertex texcoord varying to `geom.c` for this. It would push
  the geometry stage over the Vulkan minimum for total output components.
- Do not generalise to other vertex roles until a geometry that has them is
  scored (tie282c: "the odd vertex's weight is a hair low" predicts T2's u
  ties down, and silicon puts 99.80% of them up).
- Do not score Texture_render_target in a disc where RenderTextureLoop runs
  first. Every TexFmt_* capture after it differs on the whole quad.
