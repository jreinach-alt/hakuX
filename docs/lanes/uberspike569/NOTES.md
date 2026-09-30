# lane.uberspike569: P6, a Dolphin-style combiner ubershader, as a spike (#569)

Brief: `/home/justin/hakux-work/briefs/uberspike569.md`. Research: `docs/lanes/shaderplan569/NOTES.md`
option (d) and section 7's P6. PR #581.

Status (2026-09-29 PDT, attempt 3):
- **E on the device: PASS.** All 305 captures are byte-identical in both runs (section 6.1).
- **CB share, measured on the device:** forcing the families cut DOA's pipeline misses from 91 to 61
  on one route (section 6.2).
- **The device has GPL with fast linking** (8.4 item 1, read from the probe).
- **P: not read in this PR.** The Thor pilot pair was void (thermal pause). Pair 2's arm A ran on
  the Nova at 04:3x PDT; arm B (`1-1790671996-uberspike569-4116483`) is still in the Nova queue
  behind about 30 requests. The GPU cost of the uber stages is a registered leg of the build PR
  (lane/uberspike569-gpl), which reads arm B too when it lands.
- **Coverage (section 3):** DOA's 83 pixel-shader modules fall into 34 combiner families.
- **Addendum** (full uber pipeline, GPL): section 8. The answer is uber libraries under GPL.
- **Second addendum (2026-09-29 10:50 PDT), the build:** on a stacked branch,
  `lane/uberspike569-gpl`, on top of PR #594 (section 9). This PR is the spike, and it is done.

**Why attempt 2 did not finish.** It ended properly, with a `waiting:` comment (09:12 UTC) on three
things outside its session: CI, P pair 2 on the Nova, and the GPL probe. CI went green and the probe
and arm A ran on the Nova at about 04:30-04:50 PDT; arm B did not run, because the Nova queue filled
with critical-path requests ahead of it. The waiter resumed the lane with the brief's new build
addendum, which is why this is attempt 3 rather than a resume for a wait.

Verdict (section 7): the fragment-only hybrid as briefed is not supported, because the C leg kills
it.

**Why attempt 1 did not finish.** It ended properly, with a `waiting:` comment on PR #581 naming four
things outside its session: CI, the E arm, the P/C pilot soaks, and DOA's key file. All four
resolved overnight: the soaks ran on the Thor at 00:42-01:00 PDT, the E arm finished at about
01:50 PDT, and the key file landed in `$WORK/perf`. handback.sh then resumed the lane.

## 0. What was built

- `hw/xbox/nv2a/pgraph/glsl/psh-uber.{c,h}`: one interpreter fragment shader per FAMILY. A
  family is a `PshState` with its combiner registers (`combiner_control`, the 8 stages'
  rgb/alpha inputs and outputs, `final_inputs_0/1`) replaced by a fixed template program.
  - The generator does not re-implement psh.c. It asks `pgraph_glsl_gen_psh()` for the family's
    template shader and replaces only the combiner block (`// Stage 0` through the final
    combiner's `fragColor.a` line) with a call into the interpreter. It also adds one uniform
    member, `uvec4 ubComb[9]`, to the end of `PshUniforms`.
  - Everything else is psh.c's text, unmodified: the texture shader, fog, alpha test, clipping,
    depth output and the #43/#59/#285 epilogue.
  - `psh.c` is not edited, and its output is unchanged.
- `vk/shaders.c` and `vk/renderer.h`, under the switch only:
  - `pgraph_vk_bind_shaders()` binds a covered state's family, so every combiner program that
    shares the rest of the state shares one module and one pipeline (`init_pipeline_key` copies
    the binding's state; `draw.c` needed no edit).
  - The psh module key carries `bool uber`. It sits inside the key union's vsh-sized footprint,
    so the record size (2352 B, `host/keylayout.json`) and the persisted key file do not change.
    Uber keys are not persisted.
  - The uniform upload stages the live combiner registers into `ubComb` (inside the hashed
    layout, so a combiner change counts as a uniform change).
- **Switch:** `HAKUX_PSH_UBER=1` in the env_vars pref, read once; the build default is
  `HAKUX_PSH_UBER_DEFAULT` (0). It logs `psh-uber: ON ...` to stderr, and on Android also under
  `hakuX-perf`, because a title soak's logcat keeps that tag and drops `hakuX-vk`/`hakuX-stderr`.
  A default build with the variable unset logs nothing and never reaches the new code.
- **Coverage refusal:** a state whose final combiner is off (both final-input words zero).
  psh.c never writes `fragColor` there, so there is nothing defined to match.

## 1. State-space map: what the specialised generator branches on

From reading every use of each `PshState` field in `glsl/psh.c` (`psh_convert` and its helpers).

| field(s) | what psh.c does with it | as a uniform? |
|---|---|---|
| `combiner_control`, `rgb_inputs/outputs[8]`, `alpha_inputs/outputs[8]`, `final_inputs_0/1` | the combiner program: register reads, input mappings, products, dot, sum/mux, output mapping, writes | **yes, implemented** (`ubComb`) |
| `shader_stage_program` (4 x 5-bit texture modes) | picks each stage's sampler TYPE (2D, 3D, cube, `usampler2D` for shadow/X8Y24) and its fetch, bump, dot-product or clip-plane code | **no**: the declared sampler type must match the bound view type. Modes that share a sampler type (PROJECT2D, PASSTHRU, CLIPPLANE, BUMPENVMAP...) could share code behind a branch; not attempted |
| `other_stage_input` (dot mappings, `input_tex`) | which dot mapping function and which earlier stage a dependent stage reads | yes in principle (index/select), inside the dot-mode code |
| `dim_tex`, `tex_cubemap`, `shadow_map`, `tex_x8y24`, `tex_depth_float` | sampler type and the shadow/depth decode | **no** (sampler type) |
| `rect_tex`, `tex_aniso`, `conv_tex`, `snorm_tex`, `tex_signed`, `tex_hilo16`, `tex_bytes16`, `tex_y16`, `tex_comp0_const`, `addr_border`, `border_*_size` | per-stage fetch arithmetic: normalisation, probe loops, convolution taps, sign handling, border offsets (floats baked into the text) | mostly yes, at a cost in branches and gathers; the gather-based sign paths are the hardest |
| `alpha_test`, `alpha_func` | discard test against `alphaRef` (already a uniform) | yes, cheap |
| `fog_enable`, `fog_mode` | the fog factor formula | yes, cheap |
| `colorkey_mode`, `alphakill`, `compare_mode`, `shadow_depth_func` | discard/compare tests | yes |
| `window_clip_exclusive`, `window_clip_count`, `stipple` | clip and stipple discards | yes |
| `color_space_convert`, `point_sprite`, `fixed_function`, `two_side_light` | CSC after the texture shader, `pT3` source, the #282 tie-rule gate, front/back colour | yes |
| `smooth_shading`, `noperspective` | interpolation qualifiers on the inputs | **no**: qualifiers are declarations and must match the VS/GS |
| `depth_needed`, `depth_format`, `surface_zeta_format`, `depth_clipping`, `cull_near_far`, `z_perspective` | whether and how `gl_FragDepth` is written | `depth_needed` **no** (writing `gl_FragDepth` at all disables early depth); the rest yes |

This spike makes only the combiners uniform (the brief's first family width). Section 3's
coverage tool also prices a second width, L2 = L1 plus alpha test and fog.

## 2. The structural fact that bounds P6: the compile unit is the pipeline

lane.turnipcost569 (PR #573, folded) measured Turnip per stage on the host (A740 drm-shim):

| pipeline | cpu ms | VS | GS | FS |
|---|---|---|---|---|
| ff_unlit + basic | 241 | 29 | 160 | 6 |
| ff_lit2 + basic | 1401 | 931 | 172 | 7 |
| prog_pass + basic | 203 | 4 | 160 | 5 |
| fixed set of 15, median | 1108 | | | FS 3-9 |

**The fragment stage is 3-9 ms of a ~1.1 s pipeline.** So:

- A fragment-only ubershader cannot make a miss cheap by making its fragment shader cheap. It can
  only hide a miss by drawing through a pipeline that ALREADY EXISTS: same VS, same GS, same
  render state, same psh family, with only the combiner program changed (P1's key-diff class
  `CB`, PR #574).
- A miss that brings a new vertex shader, geometry shader, render state or texture-mode family
  needs a new uber pipeline too, and that costs what the specialised one costs, because the VS
  and GS dominate it.
- So P6's reach is the CB-only share of first-sight misses. P1's `[shd413]` key-diff classes
  measure exactly that on DOA; its soak `1790621694-shaderfb569-1529058` is queued behind the
  Nova's battery hold. Section 3 reads the module-level share from the key file.

## 3. Coverage against DOA's keys

Tool: `host/keys_coverage.py <shader_module_keys.bin>` (layout from `host/keyinfo.c`, this tree's
structs; `--selftest` passes on a 12-key fixture with a known answer).

Input: `$WORK/perf/2026-09-28-turnipcost569/nova/doa-cache.tar` (`files/shader_module_keys.bin`,
308,112 B = 131 records of 2352 B, which is this tree's record size). It holds 46 vertex, 2
geometry and 83 fragment modules.

| width | uniform fields | families | served by an existing family |
|---|---|---|---|
| L1 | the combiners | 34 | 49 of 83 (59.0%) |
| L2 | L1, plus alpha test and fog | 28 | 55 of 83 (66.3%) |

"Served" counts modules that are not the first of their family, so an existing family pipeline
could draw them. These are MODULE counts. They are not pipelines, and they are not first-sight
events in order.

The fields that split the 34 L1 families (the merge count if that field were a uniform too):
- `other_stage_input`: 8
- `fog_enable`: 4
- `tex_comp0_const`, `fixed_function`, `alphakill`: 2 each
- `rect_tex`, `alpha_test`, `alpha_func`: 1 each

The texture-shader modes (`shader_stage_program`) and the sampler types are the rest.

## 4. E, exactness, on the host (lavapipe)

`host/run_checks.sh` + `host/render_check.py`. 548 states: psh_differ's nine baselines, each with
its own program and 60 seeded random combiner programs (random stages, flags, registers,
mappings, dot/mux/sum, blue-to-alpha, reserved registers, read-only destinations).

| check | result |
|---|---|
| SPLICE: text outside the combiner block, specialised vs uber | **548 of 548 identical** (1 more state uncovered: final combiner off) |
| glslang, Vulkan 1.1, both shaders | 1096 of 1096 compile |
| render, same inputs, 64x64 RGBA32F, byte compare | see 4.1 |
| mutant (uber staged a wrong program) | 5 of 6 pairs DIFF, all 4096 px; the check can see a wrong program |

### 4.1 What differs, and why

First version (a single interpreter body): 479 of 548 pairs byte-identical, 69 differ. **Every
difference is 1-2 ulp**; 2 pairs reach the 8-bit result (9 px and 422 px of 4096). The logic is
right; the rounding is not the specialised shader's.

Reduced with `host/reduce.py` (greedy delta debugging over the 36 program words) to one stage:
`v1.rgb = clamp(((dot(0.5 - t3.aaa, pFog.aaa - 0.5) - 0.5) * 2.0))`, alpha = `-v1.b`. lavapipe's
NIR (`host/nirdump.sh`) shows why:

- With fog off, `pFog` is `vec4(fogColor.rgb, 1.0)`: a COMPILE-TIME constant in the specialised
  shader, so `pFog.aaa - 0.5` folds to 0.5.
- NIR then reassociates the dot's add chain with the later `- 0.5`:
  `(z*0.5 - 0.5) + y*0.5 + x*0.5`, which rounds differently from `dot(...) - 0.5`.
- The interpreter reads fog at run time, so nothing folds and nothing reassociates.

Values then land one ulp apart on (k + 0.5)/255, a rounding boundary: 0.605882287 (154.49999)
against 0.605882406 (154.50003). The BIAS and HALFBIAS mappings put combiner values on exactly
those boundaries, so one ulp is often one LSB.

**This is structural.** The specialised shader's compile-time constants (ZERO-register inputs,
`pFog` with fog off, mapping constants) and its CSE-visible equalities (`.aaa` lanes, a register
read twice) unlock NIR's inexact algebraic rewrites (reassociation, factoring, contraction). A
run-time interpreter can replay those only case by case.

Two fixes were tried against the reduced pair; neither moved it (same 885 px float, 422 px 8-bit):

1. Branching each stage half on its shape, so every product has the specialised shader's uses and
   contraction opportunities.
2. `ubDot()`, which hands the compiler `vec3(x)` where psh.c writes `.aaa`.

Both were later dropped: they changed no 8-bit result and cost 25-30x at compile (section 5.1).

Full re-run with both: 472 identical, 76 differ in float, **the same 2 in the 8-bit result**
(9 px and 422 px). Shape-matching does not reach the cause on lavapipe.

| baseline | pairs | identical | differ (float) | 8-bit differ | drew no pixel |
|---|---|---|---|---|---|
| basic | 61 | 58 | 3 | 0 | 27 |
| border | 61 | 41 | 20 | 1 | 0 |
| bumpenv | 61 | 48 | 13 | 1 | 0 |
| clipplane | 61 | 61 | 0 | 0 | **61** |
| misc | 61 | 40 | 21 | 0 | 0 |
| off | 60 | 57 | 3 | 0 | 0 |
| stages | 61 | 45 | 16 | 0 | 0 |
| surface | 61 | 61 | 0 | 0 | **51** |
| textures | 61 | 61 | 0 | 0 | **61** |

The three bold rows' "identical" is vacuous: every pixel was discarded in both shaders. `textures`
kills on stage 2's constant-zero alpha (alphakill on a stage that produces no texel), and
`clipplane`'s alternating compare modes cannot all hold. The random programs now clear both
(`uberhost.c`); see 4.2 for the re-run.

**The way to exactness, for a follow-up lane:** compile the combiner arithmetic EXACT on both paths
(SPIR-V `NoContraction`, GLSL `precise`). NIR then applies no inexact rewrite to either, and two
op-for-op identical expressions round identically. It changes the default path's output, so it is
out of this lane's scope. It needs its own pixel arm against the goldens, and its own fps cost.

## 5. C, the ubershader's own compile cost, on the host

`host/ccost.sh`: lane.turnipcost569's harness (in-tree `docs/lanes/turnipcost569/vkharness.c`),
its host Turnip (Mesa 26.3-devel, A740 drm-shim, NDEBUG -O2) and VS/GS SPIR-V, read-only; every
cache off. Five psh_differ baselines' own programs, specialised vs family ubershader, behind three
VS/GS pairs. One rep (rep 0 of 5; stopped there because the effect is two orders of magnitude and a
rep of the uber rows costs ~6 min). `host/build/ccost/ccost.tsv`, `ccost_summary.py`.

| pipeline | cpu ms spec | cpu ms uber | x | FS ms spec | FS ms uber | x |
|---|---|---|---|---|---|---|
| prog_pass+basic | 36 | 13316 | 367 | 20.2 | 11816 | 585 |
| prog_pass+border | 39 | 9073 | 234 | 20.6 | 7891 | 383 |
| prog_pass+bumpenv | 41 | 9331 | 230 | 23.2 | 8162 | 351 |
| prog_pass+stages8 | 47 | 10056 | 212 | 26.3 | 8807 | 335 |
| prog_pass+textures | 54 | 10983 | 203 | 29.8 | 9928 | 334 |
| ff_unlit+basic (GS) | 313 | 12681 | 41 | 98.7 | 11505 | 117 |
| ff_unlit+{border,bumpenv,stages8,textures} | 294-382 | 12153-15735 | 34-47 | 87-125 | 10732-13852 | 96-144 |
| ff_lit2+basic (GS) | 1198 | 12004 | 10 | 77.6 | 9672 | 125 |
| ff_lit2+{border,bumpenv,stages8,textures} | 955-1204 | 13180-13660 | 11-14 | 83-126 | 10964-11723 | 87-141 |

**The ubershader's fragment stage costs 8-14 s of Turnip CPU on this host, 90-590x the
specialised fragment stage, and 10-370x the whole specialised pipeline.** Per family and per
VS/GS/state combination, because the compile unit is the pipeline (section 2). The host is a
2015 i7 that other lanes load; turnipcost569 found its per-pipeline times the same order as the
device's, so on the Nova expect seconds, not milliseconds. That alone is fatal to the hybrid as
built: the stand-in costs 10x more to build than what it stands in for.

### 5.1 The cost is control flow, and it comes down 25-30x

`host/ccost_variants.sh`, prog_pass (no GS) so the fragment stage is nearly the whole pipeline,
2 reps, FS-stage ms (creation feedback), median:

| state | specialised | shape tree (first shipped) | v1: one stage body, switch register access | v3: array register file, arithmetic mappings |
|---|---|---|---|---|
| basic | 19.7 | 9422 | 4520 | 292 |
| stages8 | 19.2 | 8237 | 4896 | 345 |
| textures | 24.0 | 9840 | 4930 | 326 |
| border | 19.4 | 8050 | 4358 | 322 |
| bumpenv | 22.7 | 7835 | 4296 | 309 |

SPIR-V is 116-124 KB (shape tree), 49-56 KB (v1), 45-53 KB (v3), against 27-55 KB specialised: the
size barely moves between v1 and v3, the compile time moves 15x. What Turnip pays for is the
branch structure: `ubReg`'s 16-way switch and the mapping switches inlined eight times per stage,
and in the shape-tree design 82 leaves more.

**Exactness is the same.** v3 on the same 548 pairs (lavapipe): 444 identical, 104 differ in float,
the same 2 pairs in 8 bits (9 and 422 px), against 456 / 92 / 2 for the shape tree. The shape tree
bought nothing measurable and cost 25-30x at compile. **The generator now emits v3** (see the
comment block in `psh-uber.c`); section 5.2 re-measures it as shipped.

### 5.2 The shipped generator (lean interpreter), C on the host

`host/ccost.sh 3` against commit 2ca713adec's generator, 3 reps, medians
(`host/build/ccost/ccost.tsv`; run log `.cache/final_host.log`):

| pipeline | cpu ms spec | cpu ms uber | x | FS ms spec | FS ms uber | x |
|---|---|---|---|---|---|---|
| prog_pass + {basic, border, bumpenv, stages8, textures} | 37-43 | 420-465 | 10.5-11.9 | 20-24 | 338-373 | 15-17 |
| ff_unlit + GS + the same five | 247-321 | 840-938 | 2.7-3.7 | 84-100 | 567-690 | 6-7 |
| ff_lit2 + GS + the same five | 972-1517 | 1909-2275 | 1.3-2.3 | 90-125 | 577-717 | 5-7 |

With a GS in the pipeline the uber fragment stage costs more (0.57-0.72 s, against 0.34-0.37 s
behind prog_pass). Linking through a geometry stage keeps more of it live.

On the Nova, lane.shaderfb569's `dpc_ms` beside this table will give the host-to-device scale.
B's soak logs the glslang+module time per family (`psh-uber: family module`).

## 6. Legs registered, and device runs

| leg | what | registration | runs |
|---|---|---|---|
| E | twelve combiner suites, byte-identical, X vs the test variant, 2 runs per arm | `docs/testing/predictions/uberspike569-exact.json` (a 2ca713adec, b e677a46a66) | done on the Thor, **PASS** (6.1) |
| P, C | DOA1U (pilot pinned to the Thor; pair 2 on the Nova), survey route, 440 s, one binary (2ca713adec), B with `HAKUX_PSH_UBER=1`; fight fps B/A >= 0.90, plus family compile lines and pm/sm | `docs/testing/predictions/uberspike569-doa-soak.json` (hand-read, `soak_read.py --judge`) | pilot pair `1790629190-uberspike569-1700121` (A), `1790629194-uberspike569-1700918` (B), ran on the Thor, P void (6.2); pair 2 queued on the Nova |

**The test variant has all three mechanisms** (see the build-variant rule):
- **Artifact:** e677a46a66 is its own sha, so it builds its own APK.
- **Rebuild trigger:** the default is a `#define` in `psh-uber.h`, which the commit changes. The
  dispatcher builds per ref.
- **Runtime reader:** `psh-uber: ON` on `hakuX-stderr` and `hakuX-perf`, both in the pgraph
  `LOGCAT_SPEC`. The E prediction voids the arm without it.

Z (5f6cb7e69b) reverts the variant, so the branch head is default-off. X and Z have identical trees.

### 6.1 E on the device: every capture byte-identical

The arms are `1-1790629564-arms-uberspike569-base-1810388` (A, 2ca713adec) and
`1-1790629564-arms-uberspike569-fix-1810422` (B, e677a46a66). Both ran on the THOR (Adreno 740,
PurpleVK, a Turnip fork of Mesa 26.3-devel), with 2 runs each and 305 captures per run. The
comparison is `sha256` per capture file (`.cache/ecmp.py`).

| check | result |
|---|---|
| variant reached the binary | B, both runs: `psh-uber: ON ... (HAKUX_PSH_UBER=unset, build default 1)` on `hakuX-perf` and `hakuX-stderr`, and 242 `psh-uber: family module` lines. A: no `ON` line in either run |
| run 1, A vs B | **305 of 305 captures byte-identical** (only `pgraph_progress_log.txt` differs, which holds timestamps) |
| run 2, A vs B | 304 of 305 identical. `Texture_signed_component_tests::txt_A8R8G8B8_ADD` differs |
| that capture, per run | A run 1 = B run 1 = B run 2; **A run 2 is the odd one** (A's run 1 and run 2 differ, and B's two runs agree). So the difference is noise in the base arm, not a move |

**E passes: 305 of 305 captures are byte-identical wherever the base arm agrees with itself.** The
registered expectation was the ROUNDING world (some 1-LSB moves, as lavapipe showed in 4.1), so that
expectation was wrong. On the device's compiler (ir3/NIR on Turnip), the interpreter rounds the
same as the specialised shader on every capture in the twelve combiner suites. lavapipe's 2 of 548
random programs are still a warning for programs the suites do not draw. So `NoContraction` on both
paths remains the way to make "identical" a guarantee rather than an observation.

### 6.2 The P/C pilot pair (Thor): P void, and the CB share measured

| arm | result dir | env | fight fps | pipeline misses (`pm`) | shader modules missed (`sm`) |
|---|---|---|---|---|---|
| A | `1-1790629190-uberspike569-1700121` | - | 7.64 | **91** | 79 |
| B | `1-1790629194-uberspike569-1700918` | `HAKUX_PSH_UBER=1` | 7.70 | **61** | 50 |

- **The pair ran on the Thor, not the Nova.** The requests were pinned to `thor`. Both arms hit
  `thermal-pause-F8` (hottest zone 95 C): A by +260 s, B by +227 s. Both pauses came before or at
  the fight. So the fight fps is **void**. The Thor's paused-core fps is 5-7x lower
  (thermal-pause memory), and 7.6 fps is that regime.
- **Every miss happened before the pause** (A's last miss at 00:46:07, pause after 00:46:30; B's
  last at 00:55:25, pause by 00:56:37). So the miss counts and stall times are clean.
- **The CB share: 30 of A's 91 pipeline misses (33%) vanish when the combiner program is a
  uniform.** Those are misses whose pipeline differed from an earlier one only in the combiner
  program. This is the device's direct measure of the P6 hybrid's best case on this route.
- **What the forced mode says about the hybrid's foreground stall.** Forced, every family pipeline
  is built at first sight, which is exactly the hybrid's foreground cost (the specialised builds
  would run in the background). Per-second stall, as the worst frame in each second with a miss
  (`.cache/stalls.py`, a coarse proxy):

| arm | seconds with misses | misses | sum of worst frames |
|---|---|---|---|
| A (specialised) | 17 | 91 | 45.0 s (494 ms per miss) |
| B (families) | 14 | 61 | 36.0 s (591 ms per miss) |

- The family pipeline costs about 20% more per miss (591 against 494 ms, section 5.2's factor, on
  the device). It removes a third of the misses. **Net: about 20% less stall time on this route,
  not "no stall".**
- B's 19 family modules cost 1.9-86.9 ms each in glslang plus module creation (median 10.2 ms).
  That is not the pipeline compile, which sits inside the stall figures above.

**Pair 2** is on the Nova, queued 2026-09-29 01:53 PDT behind its charge hold:
- `1790671992-uberspike569-4114420` (A)
- `1790671996-uberspike569-4116483` (B, `HAKUX_PSH_UBER=1`)

The pilot verdict is in `pilots/uberspike569.ok`. Read the pair with `soak_read.py`, and check
the Nova's thermal line before trusting its fps.

As of attempt 3, arm A has run (`1-1790671992-uberspike569-4114420`, Nova) and arm B is queued. A
single arm is not a P reading, so P is carried to the build branch (section 9), which reads the
pair when B lands.

## 7. Verdict (host legs and device E measured; P pending on the Nova)

**The hybrid as briefed is not supported. C kills it, and section 2 says why structurally.**

- **The stand-in costs more to build than what it stands in for.** On Turnip the compile unit is
  the pipeline (VS + GS + FS + state). The lean uber fragment stage makes a realistic pipeline
  1.3-3.7x as expensive as the specialised one (host 0.84-2.3 s against 0.25-1.5 s). A miss whose
  uber pipeline does not yet exist stalls LONGER through the hybrid, not shorter. It pays the uber
  pipeline, then the specialised one in the background.
- **What it can hide:** only a miss that differs from an already-built uber pipeline in the
  combiner program alone (P1's key-diff class `CB`), within one VS/GS/render-state/texture-mode
  family. In each such group the first miss pays more; the rest are free. The value is
  (CB-only misses - groups) x `dpc`. P1's DOA soak (`1790621694-shaderfb569-1529058`) measures
  the CB share. The DOA key file (section 3) measures the module-level share. Neither exists on
  this host yet.
- **How many frames it would draw per hidden miss:** pipeline413 measured DOA's fight load as 19
  misses and 14.9 s of excess, about 0.78 s per miss. That is about 47 frames at 60 fps, or about
  12 at the fight's 15 fps, per miss while its specialised pipeline compiles. P1's `dpc_ms` gives
  the per-miss figure directly.
- **E (host):** the interpreter's LOGIC is exact (548 random programs; mutant caught). Its
  ROUNDING is not bit-identical. The specialised compiler folds constants and reassociates
  (section 4.1), leaving 1-LSB differences on rare boundary pixels: 2 of 548 programs, 431 of
  ~1.3 M drawn px. At a swap-in that is a pop of at most one LSB on those pixels.
- **E (device): PASS.** On the Thor's Turnip, all 305 captures of the twelve combiner suites are
  byte-identical (6.1). A swap-in would not pop on anything the suites draw.
- **CB share (device): 30 of 91 pipeline misses (33%)** on the DOA route. Each remaining miss costs
  about 20% more through a family pipeline, so the forced mode's stall time is 36 s against 45 s
  (6.2). The hybrid hides a third of the misses and makes the rest dearer. It does not reach a
  first draw with no stall.

**What survives, and what to do instead:**
- **A narrower ubershader does not help.** The cost is control flow (5.1), and the pipeline cost
  is dominated by the VS/GS it must be linked with. Fewer combiner features would shave part of
  0.3-0.7 s off a 1-2 s pipeline.
- **The one design where a fragment ubershader pays is with pipeline libraries (P5/GPL).** The
  uber fragment stage is compiled once per family as a fragment-shader library, and a first-sight
  pipeline becomes a link of an existing VS library with it. Section 8 measures it: on host Turnip
  a fast link costs ~0 ms.
- **Where key sets exist (P3), prebuild the specialised pipelines instead.** No interpreter, no pop.
- **Exactness, if a hybrid is built after all:** compile the combiner arithmetic exact
  (`NoContraction`) on BOTH paths (section 4.1). That is a default-path change with its own pixel
  arm.

## 8. Addendum: which design gives a first draw with no stall and no drop

The brief's addendum (lane.local, 2026-09-28 14:05 PDT) asked two questions, in order:
- (1) Does a full uber pipeline work, with vertex and geometry stages too?
- (2) Does GPL (P5) work, with the fragment ubershader as a prebuilt library linked per vertex
  stage?

**Answer: (1) alone does not, (2) alone does not, and the two together do.** The design is uber
LIBRARIES under GPL:
- one pre-rasterization library per vertex family (uber VS + GS);
- one fragment library per fragment family (uber FS);
- a first-sight pipeline is a fast link of libraries that already exist.

On host Turnip that link costs ~0 ms (8.2). The pieces below are measured on the host. The device
legs that remain are listed in 8.4.

### 8.1 Design 1, a full uber pipeline: C on the host, and the family count

**The prototype.** `host/uber_vs/gen_uber_vs.py` builds it, and `build.sh` compiles it to SPIR-V.
It takes the prologue of hakuX's generated vertex shader (the uniform block, the `lt*` lighting
helpers, the interface) and the MAC/ILU op helpers, and swaps `main()` for one of two paths:
- **vp:** the NV2A vertex-program interpreter. One loop runs over up to 136 microcode slots (the
  field table at `glsl/vsh-prog.c:49-88`), with the register file as arrays and one MAC switch and
  one ILU switch per slot.
- **ff:** fixed function, with the skinning count, texgen modes, texture-matrix enables, light
  types and fog generation all read from uniforms.
- `both` is one shader that branches on `vpMode`.

This prototype measures COST. It is not exact against `vsh.c`: material sources, point parameters
and the ring are left out.

**C, host Turnip.** `host/uber_vs/ccost_vs.sh 3`, 3 reps, median CPU ms. The result copy is
`results/addendum-ccost_vs.tsv`. The fragment stage is `basic`'s specialised shader (`fs_spec`)
or its family ubershader (`fs_uber`).

| pipeline | cpu ms | VS | FS | GS |
|---|---|---|---|---|
| specialised prog_skin4 (51-slot skinning program) + GS + fs_spec | 376 | 92 | 92 | 144 |
| specialised ff_unlit + GS + fs_spec | 314 | 16 | 106 | 158 |
| specialised ff_lit2 (2 lights) + GS + fs_spec | 1334 | 812 | 103 | 156 |
| **uber vp** + GS + fs_spec | 350 | **73** | 94 | 138 |
| **uber ff** + GS + fs_spec | 1151 | 754 | 119 | 147 |
| **uber both** + GS + fs_spec | 1224 | 870 | 92 | 142 |
| **uber both + GS + fs_uber (the full uber pipeline)** | **1955** | 997 | 655 | 122 |
| uber both + fs_uber, no GS | 1450 | 929 | 380 | - |

- **The vertex-program interpreter is cheap to compile:** 73 ms, less than the 51-slot
  specialised program (92 ms). A loop with a uniform trip count stays one body.
- **The fixed-function path costs what the specialised lit shader costs** (754 against 812 ms), and
  only after a fix. The first version took 2.7 s of VS: NIR unrolled the constant-bound 8-light loop
  and the 16 texgen switch copies (section 5.1's lesson again). Uniform trip counts
  (`ffNumLights`, `ffNumTexgen`) brought it down 3.6x. The remaining cost is the `lt*` soft-float
  lighting, the same code lane.litcompile569 is shrinking.
- **A full uber pipeline costs 1.5-2.0 s on the host**, which is 1.5-6x a specialised pipeline.
  Built on a miss, it stalls longer than the miss. **So design 1 alone fails the same way the
  fragment-only hybrid did (section 7).** The uber pipeline must exist BEFORE the miss.

**The family count on DOA's keys** (`host/keys_coverage.py`, now with an `LF` width and a vertex
read; `host/vshinfo.c` supplies the VshState layout):

| stage | modules | families at the full-uber width | what splits them |
|---|---|---|---|
| vertex | 46 (31 fixed-function, 9 programs of 2-30 slots) | 15 | **only `uniform_attrs`** (which attributes come from inline values). An interpreter can select that per attribute from a uniform mask, which leaves **1** |
| geometry | 2 | 2 | primitive and polygon mode |
| fragment | 83 | **11** (LF), 34 at L1 (what `psh-uber.c` builds) | sampler classes per stage, `dim_tex`, qualifiers, depth write |

LF assumes that the texture modes sharing a sampler class run behind a branch. That is not built,
so L1's 34 is what exists today.

**GPU cost, static only.** From ir3's statistics (`host/uber_vs/ir3stats.sh`,
`results/addendum-ir3stats.stats`):

| shader | instructions | full regs | max waves |
|---|---|---|---|
| vp interpreter | 1,503 (a loop body run once per slot) | 48 | 4 |
| specialised 51-slot program | 2,622 (straight-line) | 13 | 14 |

The interpreter also has 197 scratch-memory (cat6) instructions for the register arrays. Expect
several times the ALU per vertex, at under a third of the occupancy. That matches the expert's
"10x or more on vertex work" order.

**Not measured on the device.** The GPU cost needs the uber vertex stage wired into the emulator
(8.4). It is paid only for the frames between the fast link and the swap.

### 8.2 Design 2, GPL: library and link times on host Turnip

`host/gpl/gplharness.c` and `gpl.sh 3`, 3 reps, median CPU ms (`results/addendum-gpl.tsv`). Host
Turnip reports `GPL ext 1, feature 1, fastLinking 1, independentInterpolationDecoration 1`.

The columns:
- `mono`: the monolithic create.
- `pr`, `fs`: the pre-raster (VS+GS) and fragment libraries.
- `link`: the fast link of all four libraries. The vertex-input and fragment-output libraries cost
  0.0 ms and are not shown.
- `lto`: a LINK_TIME_OPTIMIZATION link of RETAIN libraries.

| pipeline | mono | pr | fs | **link** | lto |
|---|---|---|---|---|---|
| prog_pass + fs_spec | 39 | 4 | 97 | **0.0** | 17 |
| prog_pass + fs_uber | 478 | 4 | 627 | **0.0** | 338 |
| ff_unlit + GS + fs_spec | 305 | 221 | 95 | **0.0** | 220 |
| ff_unlit + GS + fs_uber | 869 | 206 | 629 | **0.0** | 698 |
| ff_lit2 + GS + fs_spec | 1305 | 1425 | 90 | **0.0** | 476 |
| ff_lit2 + GS + fs_uber | 1976 | 1404 | 620 | **0.0** | 1120 |
| prog_skin4 + GS + fs_spec | 364 | 253 | 100 | **0.0** | 290 |
| uber both + GS + fs_uber | 1999 | 1178 | 647 | **0.0** | 1044 |

- **A fast link is free** (under the 0.05 ms the print resolves). Turnip compiles each stage at
  library creation and links without recompiling.
- **Libraries split the cost by stage.** A miss that changes only the fragment state costs one
  fragment library: 90-100 ms specialised, against a 305-1976 ms monolithic create. A miss that
  changes only the vertex state costs one pre-raster library. That alone takes most of the stall
  off the CB, TX and FF-only misses. shaderfb569's C3 found 100% of reused-module stages recompiled
  by the monolithic path.
- **GPL alone does not reach "no stall".** A miss that brings a new VS still pays its pre-raster
  library (0.2-1.4 s). shaderfb569 C4 counts FF diffs in 98 of DOA's 164 misses.

### 8.3 The design that answers the addendum: uber libraries under GPL

- **Libraries, built ahead:** one uber pre-raster library per (vertex family, GS kind) and one
  uber fragment library per fragment family. Build them on background threads at boot, and keep
  them in the on-disk pipeline cache.
  - For DOA that is about 1 x 3 pre-raster libraries (no GS, and 2 GS kinds) at 1.2-1.7 s each,
    and 11 (LF) or 34 (L1) fragment libraries at 0.63 s each.
  - That is about 12 s (LF) or 26 s (L1) of host CPU once, spread over worker threads. From the
    second boot it is free, because the libraries come from the cache.
- **A first-sight pipeline:** fast-link the existing libraries:
  - the uber pre-raster library, or the specialised one if it is already built;
  - the uber fragment library, or the specialised one if it is already built;
  - the vertex-input and fragment-output libraries (0 ms each).
  
  **The draw happens this frame.** No stall, and no dropped draw.
- **In the background:** build the specialised libraries (only the stages that are new), then
  swap in. Either fast-link them, or LTO-link them for the best GPU code.
- **Where it can still stall:**
  - a family never seen before, in the first session of a title;
  - render state that GPL puts inside a library and the device cannot make dynamic.

  Both cases reduce to the vertex-input and fragment-output libraries (0 ms) plus the
  depth/stencil and multisample state held in the fragment library. EDS3 is already enabled on the
  device, and makes most of that dynamic.
- **Where it can pop:** at the swap.
  - Fragment: E shows none on the twelve suites (6.1).
  - Vertex: not measured.
  - A fast link does no cross-stage optimisation, so a specialised FS linked fast may not round
    like the monolithic one (section 4.1's mechanism, across stages). `NoContraction`/`precise` on
    both paths is the guarantee, and it is a default-path change with its own pixel arm.

### 8.4 What remains before building it, in order

1. **The device's driver has GPL.** It is PurpleVK, a Turnip fork of Mesa 26.3-devel
   (git-62ac221a33). Turnip has shipped GPL since Mesa 23.1, but the device must say so. The switch
   now logs `psh-uber: GPL ext= feature= fastLinking=` once (`vk/shaders.c`, under
   `HAKUX_PSH_UBER` only). A one-arm B soak on this branch's head reads it:
   `1-1790673060-uberspike569-277562` (4085a55165, DOA 90 s, Nova, ran 04:47 PDT).
   **Answer: yes.** `psh-uber: GPL ext=1 feature=1 fastLinking=1 independentInterpolation=1`.
   The same run's family modules cost 6.0-9.8 ms each on the Nova (glslang + module), and
   1.5-1.7 ms when a second instance reuses a warm glslang. lane.gpl569 read the same on the Thor.
2. **The device's fast-link time**, against its monolithic create. It needs GPL in the renderer,
   which is the build's first step.
3. **The GPU cost of the uber stages at DOA's loads**, forced (the addendum's measurement).
   - The fragment half is P, pair 2 on the Nova (6.2).
   - The vertex half needs an exact-enough uber vertex stage in the emulator
     (`glsl/vsh-uber.c`, spliced like `psh-uber.c`). That is the same wiring the build needs, so
     it is the build's first gate, not done in this spike.
   - The expected size: ir3's static stats (8.1) say several times the vertex ALU at under a third
     of the occupancy. It is paid only for the frames between a fast link and the swap, and a
     specialised fragment library takes about 0.1 s and a pre-raster library 0.2-1.4 s on the
     host. The probability that it kills the design is low, but it is the leg that could.
4. **Exactness:** `NoContraction` on both paths, and an arm against the goldens.

**The build, as files:**
- `glsl/vsh-uber.{c,h}`: the interpreter and the uniform fixed-function path, spliced into
  `vsh.c`'s own prologue and epilogue.
- `glsl/psh-uber.c`: as built, plus the LF width.
- `vk/pipeline.c` or `vk/draw.c`'s create sites: libraries and links. lane.shaderfb569 holds those
  create sites.
- `vk/shaders.c`: the family keys, library creation on worker threads, and the swap.
- `vk/instance.c`: enable `VK_EXT_graphics_pipeline_library`.

## 9. The build (second addendum): on `lane/uberspike569-gpl`

lane.local's addendum of 2026-09-29 10:50 PDT asks for the uber libraries on GPL: prebuilt uber
pre-raster and fragment libraries, fast-linked on a miss, with the specialised monolithic pipeline
built behind them and swapped in. It stacks on PR #594 (lane/gpl569), whose files it edits, so it
is its own PR on `lane/uberspike569-gpl`, and its notes are `docs/lanes/uberspike569/BUILD.md` on
that branch. This PR stays the spike.

### 9.1 Attempts 3 and 4

Attempt 3 built the ladder and ended as a wait on two smoke soaks (`[lane.uberspike569] waiting:`
on PR #618). Attempt 4 read them (clean, BUILD.md section 6), merged master and registered the build's
legs: `uberspike569-gpl-pixels.json` (E, the arms job) and `uberspike569-gpl-doa-soak.json` (N1-N3, G,
queued by hand). The results go in BUILD.md.

## Do not repeat

- Do not give an uber shader a constant-bound loop over lights or texgen slots. NIR unrolls it into
  N copies, and the fixed-function uber VS then took 2.7 s instead of 0.75 s (8.1).
- Do not judge an uber design by its monolithic create time alone. Under GPL the same shaders link
  in ~0 ms once their libraries exist (8.2).

- Do not build a Turnip ubershader out of switches. Register access and mapping by `switch`, inlined
  per input, cost 4-10 s per pipeline on the host; an array register file and arithmetic mappings
  cost 0.3-0.7 s for the same exactness (5.1).
- Do not judge an interpreter by "same ops, same order". The specialised compiler sees constants and equal
  operands the interpreter cannot, and rewrites inexactly on them (section 4.1).
- A render check whose inputs discard everything passes vacuously. The first run here had 217 of
  479 "ok" pairs with no drawn pixel (window clip regions covering the target under an exclusive
  clip; alpha refs above every alpha). `render_check.py` now prints drawn-pixel counts per
  baseline.

## The build (PR #618) is recorded in `BUILD.md`

Resume of 2026-09-29 16:10 PDT: attempt 4 ended as a wait on the DOA soak arms and the E pixel arm,
which had not run (all queued behind the Nova's release tier). This resume added the Kabuki
acceptance leg (BUILD.md section 7). Do not judge Kabuki's stall by "no flip gap over 5 s": master
already meets it since B1 (longest gap 4.4 s in K1); read create ms and the gap against an A arm.

Resume of 2026-09-29 16:25 PDT (attempt 6): attempt 5 ended as a wait, and before anything ran
the live dispatch queue and results were emptied (BUILD.md section 8). All seven device requests
were re-queued under new ids; E is now judged by this lane, not the arms job.

Resume of 2026-09-29 17:39 PDT (attempt 7): attempt 6 ended as a wait, but the same wipe took a
second pass and removed six of the seven re-queued requests. Only E's A arm ran. The cause is
PR #622's selftest fragments, and PR #624 fixes it. The lane waits for #624 to fold before it
re-queues the six (BUILD.md section 9).

Resume of 2026-09-29 18:10 PDT (attempt 8): attempt 7 ended as a wait on PR #624's fold, which is
what it should have done. #624 folded at 17:40 PDT. The lane merged origin/master (no emulator code,
so the refs and predictions stand) and queued the six lost requests a third time, with the soaks
hard-pinned to the Nova (BUILD.md section 10). Both devices are on the owner's top-up hold, so this
attempt also ends as a wait.

Resume of 2026-09-29 22:11 PDT (attempt 9): attempt 8 ended as a wait on the six requests it had
re-queued. It did not finish because none of them has run: at 22:11 all six are still in
`queue/`. The Nova is on the owner's top-up hold, and the Thor is out of service with a dead fan.
GitHub is suspended, so the lane now follows the offline protocol: `PR.md` and `OUTBOX.md` beside
this file stand in for PR #618 and the #569 post (BUILD.md section 11).
