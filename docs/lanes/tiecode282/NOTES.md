# lane.tiecode282: the weight-binade v-tie rule, implemented (#282, #283)

Base: master @ 7a2036020d, merged up to e673558587 at 1462da29d2. Code:
`18dc4f11e2` (the rule), `8e649f05e9` (the power-of-two gate). Predictions:
`docs/testing/predictions/tiecode282-binade.json` (arm 1, refused, section 6),
`docs/testing/predictions/tiecode282-pow2.json` and
`docs/lanes/tiecode282/tiecode282-trt.json` (arm 2, section 7).

## 0. Why attempt 1 did not finish

Attempt 1 ended correctly on a `waiting:` for the arms job, and the arms job
did run the pair. Its verdict (2026-09-26 03:09 PDT) was **REFUSED**, and
nothing resumed the lane for that. The prediction recorded a disc composition
with `skip_tests: Texture render target::RenderTextureLoop`. `arms.sh`'s
`suites_for()` reads `disc.suites` only and never passes `skip_tests` to the
request, so arm A ran a different composition from the registered one, and
the judge refused the absolutes. **Harness defect:** `arms.sh` cannot run a
prediction that needs `skip_tests`, and `ab_run.sh` has no flag for it
either; only `request.sh --skip-tests` carries it. Both result directories
were complete and comparable, so attempt 2 read them without the prediction
(section 6).

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

Verdict: REFUSED on composition (section 0). Read unjudged in section 6: a
must_not_move leg moved (Pixel_shader, Texture_3D_as_2D), so the scoping was
refuted and narrowed. The arm-2 legs are in section 7.

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

## 6. Arm 1, read without its prediction (7a2036020d vs 18dc4f11e2)

Results `1790415048-arms-tiecode282-base-2121181` / `-fix-2121581`, 405
captures each, progress-log proof on both, one disc (the 24 suites, with
RenderTextureLoop). `ab_compare.py --a --b` with no expect file:
**139 better, 8 worse, 258 same; exact 111 -> 163 (+52); 4 regressed from exact.**

| suite | caps | better | worse | differing A -> B |
|---|---|---|---|---|
| Volume_texture | 20 | 18 | 0 | 34,727 -> **0** (all 20 exact) |
| Material_color_source | 28 | 28 | 0 | 24,072 -> **0** |
| Lighting_spotlight | 24 | 24 | 0 | 166,198 -> 97,090 |
| Lighting_control | 32 | 16 | 0 | 56,804 -> 28,960 |
| Lighting_accumulation | 10 | 10 | 0 | 32,412 -> 20,102 |
| Lighting_range | 3 | 3 | 0 | 9,968 -> 7,592 |
| Specular / Specular_back | 39 | 33 | 0 | 452,606 -> 427,317 |
| Combiner | 8 | 3 | 0 | 24,901 -> 8,195 |
| Texture_palette | 2 | 2 | 0 | 10,488 -> **0** |
| Texture_border_color | 1 | 1 | 0 | 6,284 -> 1,324 |
| Texture_border | 18 | 1 (2D) | 0 | 20,868 -> 20,837 |
| **Pixel_shader** | 8 | 0 | **6** | 102,866 -> 190,420 |
| **Texture_3D_as_2D** | 2 | 0 | **2** | 3,037 -> 5,709 |
| Texture_render_target | 41 | 0 | 0 | 3,209,634 both (poisoned by RenderTextureLoop) |

Texture_signed_component_tests/txt_A8R8G8B8_ADD moved 12,544 px at the same
score. Everything else on the must_not_move list was byte-identical.

**What the wrong-way movers share.** `scratch/where.py`, arm A vs arm B vs
golden, per capture:
- Pixel_shader StageDependentAlphaRed/GreenBlue, DotZW: 256 x 256 quad, a
  256-texel texture (1:1). Moved: every column, rows 113-240, the upper half,
  which is where the rule says "down". Arm A was exact, so silicon puts all of
  those ties **up**. DotST moves every other row (a 2:1 map). BumpEnvMap and
  BumpEnvMapLuminance use 128 and 64 px quads.
- Texture_3D_as_2D: only the 64 x 64 reference quads (x 33-95) moved. The
  256 x 256 main draw has no ties.
- Texture_signed: 256 x 256 quads.
- The draws the rule got right: 640 x 480 (checkerboard), 285.625 (TRT BiTri),
  135 x 80 (Volume texture) and **96 x 96 over 128 texels (Texture_palette,
  made exact)**. So w = 1 against w = 7 or 8 is not the split: Palette is w = 1
  and the rule holds on it. The texture filter is not the split either,
  because every draw here uses the nxdk default (BOX/BOX, `0x1012000`).

Every wrong-way triangle has power-of-two legs, and every right-way triangle
has legs that are not powers of two. A reading consistent with the rule: with
dyadic legs the weights at pixel centres are exact, so no rounding exists for
the binades to steer, and the tie takes silicon's plain "up". The power-of-two
triangles are all square, so the data does not say whether one leg or both
must be dyadic. The gate (`8e649f05e9`) takes the rule only when **neither**
leg is a power of two, which is the narrowest scope the three geometries and
Palette support.

## 7. Arm 2 legs (a e673558587 = master, b 1462da29d2 = gate + master merge)

`docs/testing/predictions/tiecode282-pow2.json` (the arms job; 23 suites, no
skip):

| leg | kind | predicted | refutes |
|---|---|---|---|
| Pixel_shader/StageDependentAlphaRed, GreenBlue, DotST, BumpEnvMap | expect | 0 (back to exact) | the gate does not reach the 1:1 and 2:1 draws |
| Pixel_shader/*, Texture_3D_as_2D/*, Texture_signed_component_tests/* | must_not_move | byte-identical to master | same |
| Volume_texture/Y16, R16B16, A8R8G8B8 | expect | 0 | the gate took Volume's 135 x 80 quads |
| Texture_palette/PaletteSwapping, XemuHighPaletteBug | expect | 0 | the gate is wider than "a power-of-two leg" (96 x 96) |
| Material_color_source/FromMaterial, Lighting_range/Directional | expect | 0 | the gate took the checkerboard |
| the checkerboard suites, Texture_border(_color), Texture_palette, Volume_texture | must_not_regress | | any capture worse |
| Texture_BRDF, _format, _DXT, _Matrix, _perspective, _2D_as_cubemap, Point_params, Bump_env_lum | must_not_move | byte-identical | |

`docs/lanes/tiecode282/tiecode282-trt.json` (queued by hand with
`request.sh --skip-tests "Texture render target::RenderTextureLoop"`; kept out
of `predictions/` so that `arms.sh` does not queue it on the poisoned
composition): TexFmt_A8R8G8B8 = 0, and Texture_render_target/* must not
regress.

PR #367 (y16bump10, fold-ready) is not merged into this branch. It merges
cleanly with this head in psh.c and psh.h, and only the generated
`nv2a_index.json` conflicts, which whichever PR folds second regenerates.
Merging its branch would have put its diff in this PR and mixed its effect
into arm 2.

## Do not repeat (attempt 2)

- Do not register a prediction that needs `skip_tests` in
  `docs/testing/predictions/`. The arms job drops the skip, and the judge
  refuses the verdict ~90 device-minutes later.
- Do not widen the rule to power-of-two triangles. Arm 1 measured silicon
  "up" on every tie row of five such draws.

## Why attempt 2 did not finish

It ended correctly on a `waiting:` for arm 2 and the hand-queued TRT pair. All
four result directories were DONE when attempt 3 started. The arms job posted
no verdict for `tiecode282-pow2.json` (label `none`), so attempt 3 judged it
by hand.

## 7a. Arm 2 results (judged by hand, 2026-09-26)

`ab_compare.py --expect docs/testing/predictions/tiecode282-pow2.json` on
`1790419344-arms-tiecode282-base-4178057` / `-fix-4178393`: **PASS, 375 of 375
checks.** 139 better, **0 worse**, 225 same; exact 110 -> 166 (+56); none
regressed from exact.

| suite | caps | better | worse | differing A -> B |
|---|---|---|---|---|
| Volume_texture | 20 | 18 | 0 | 34,727 -> **0** |
| Material_color_source | 28 | 28 | 0 | 24,072 -> **0** |
| Texture_palette | 2 | 2 | 0 | 10,488 -> **0** |
| Lighting_spotlight | 24 | 24 | 0 | 166,198 -> 97,090 |
| Lighting_control | 32 | 16 | 0 | 56,804 -> 28,960 |
| Lighting_accumulation | 10 | 10 | 0 | 32,412 -> 20,102 |
| Lighting_range | 3 | 3 | 0 | 9,968 -> 7,592 |
| Specular / Specular_back | 39 | 33 | 0 | 452,606 -> 427,317 |
| Combiner | 8 | 3 | 0 | 24,901 -> 8,195 |
| Texture_border_color | 1 | 1 | 0 | 6,284 -> 716 |
| Texture_border | 18 | 1 | 0 | 20,868 -> 20,837 |
| Pixel_shader, Texture_3D_as_2D, Texture_signed, and the other must_not_move suites | | 0 | 0 | unchanged |

The power-of-two gate removed all 8 wrong-way movers from arm 1 and kept every
gain.

TRT pair (`1790419139-tiecode282-trt-base-4031902` /
`1790419143-tiecode282-trt-fix-4032233`, judged against
`tiecode282-trt.json`, bound at queue time): **PASS, 41 of 41 checks.** 28
better, 0 worse; exact 12 -> **40 of 40**; 1,473 -> 0 px. Every full-gradient
TexFmt_* capture is now exact, including the Index8, YUV and 16-bit ones.

## 8. Arm 3: the merge replicate (a 6c25a829ef = master, b adb573c270)

Master gained #367 (y16bump10, psh.c bump paths) and #274 (vk/draw.c uniform
refresh). The merge was clean except the generated `nv2a_index.json`, rebuilt
with the fold pins (tests 6743b6ab16) and `check` clean. The brief asks for
the arm to be re-run on the merged head before ready.

- `docs/testing/predictions/tiecode282-merge.json`: arm 2's legs unchanged
  (11 expect, 11 must_not_move, 12 must_not_regress, same 23-suite disc). The
  arms job queues it.
- `docs/lanes/tiecode282/tiecode282-trt-merge.json`: all 28 TexFmt_* captures
  that arm 2 took to exact are expected at 0, and Texture_render_target/* must
  not regress. Queued by hand with `request.sh --skip-tests`, because #386
  (arms.sh carries `skip_tests`) has not folded.
- Both were written by `register_merge.py`, which copies the legs from arm 2's
  files so they cannot drift.

A leg that passed in arm 2 and fails here is an interaction with the merged
code, not a new reading of the rule.

## Waiting (2026-09-26, attempt 3)

On things outside this session: the `[job.arms]` verdict for
`tiecode282-merge.json`, dispatch requests
`1790424878-tiecode282-trtm-base-759654` / `1790424878-tiecode282-trtm-fix-760263`
(judge with `ab_compare.py --expect docs/lanes/tiecode282/tiecode282-trt-merge.json`),
and CI on the head. If all pass: post both verdicts, then `gh pr ready 379`,
which releases psh.c and psh.h. Preflight on 6a18634f4c: every gate is ok
except `coverage`, which flags board rows #278 and #276. Those are the board's.

## Waiting (2026-09-26, attempt 2, superseded by attempt 3)

On three things outside this session:
- the arms job's `[job.arms]` verdict for `tiecode282-pow2.json` (a e673558587, b 1462da29d2);
- dispatch requests `1790419139-tiecode282-trt-base-4031902` and
  `1790419143-tiecode282-trt-fix-4032233`, judged with
  `ab_compare.py --a <base> --b <fix> --expect docs/lanes/tiecode282/tiecode282-trt.json`;
- CI on the head.

If all pass: post both verdicts and fill in section 7's result, then mark the PR
ready and release psh.c and psh.h. If Pixel_shader or 3D_as_2D still move, the
gate did not reach them, so read which leg length they have. If Palette,
Volume or the checkerboard lose their gains, the gate is too wide.
