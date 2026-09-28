# lane.uberspike569: P6, a Dolphin-style combiner ubershader, as a spike (#569)

Brief: `/home/justin/hakux-work/briefs/uberspike569.md`. Research: `docs/lanes/shaderplan569/NOTES.md`
option (d) and section 7's P6. PR #581.

Status (2026-09-28): the host legs are measured. The device legs are registered and queued:
- E is queued by the arms job from the push.
- The P/C pilot soak pair is behind the Nova's battery hold.
- The DOA key file (section 3) has not been pulled yet.

Verdict so far (section 7): the hybrid as briefed is not supported. The C leg kills it.

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

**Pending.** DOA's `shader_module_keys.bin` was to be pulled to
`$WORK/perf/2026-09-28-turnipcost569/nova/doa-cache.tar`; on 2026-09-28 at the time of writing it
does not exist on this host (searched all of `~/hakux-work`). The read is one command once it
lands.

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
| E | twelve combiner suites, byte-identical, X vs the test variant, 2 runs per arm | `docs/testing/predictions/uberspike569-exact.json` (a 2ca713adec, b e677a46a66) | queued by the arms job from the push |
| P, C | DOA1U on the Nova, survey route, 440 s, one binary (2ca713adec), B with `HAKUX_PSH_UBER=1`; fight fps B/A >= 0.90, plus family compile lines and pm/sm | `docs/testing/predictions/uberspike569-doa-soak.json` (hand-read, `soak_read.py --judge`) | pilot pair `1790629190-uberspike569-1700121` (A), `1790629194-uberspike569-1700918` (B), behind the Nova's battery hold |

**The test variant has all three mechanisms** (see the build-variant rule):
- **Artifact:** e677a46a66 is its own sha, so it builds its own APK.
- **Rebuild trigger:** the default is a `#define` in `psh-uber.h`, which the commit changes. The
  dispatcher builds per ref.
- **Runtime reader:** `psh-uber: ON` on `hakuX-stderr` and `hakuX-perf`, both in the pgraph
  `LOGCAT_SPEC`. The E prediction voids the arm without it.

Z (5f6cb7e69b) reverts the variant, so the branch head is default-off. X and Z have identical trees.

**Next, after the pilot pair lands:** read it with
`soak_read.py --a <A dir> --b <B dir>`. If both reached the fight and the B arm shows the `ON`
line, write `$DISPATCH_DIR/pilots/uberspike569.ok` (with python3) and queue the second pair (the
same two commands, "pair 2 of 2"). Then judge all four with `--judge`.

## 7. Verdict (host legs measured; device E and P pending)

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
  ~1.3 M drawn px. At a swap-in that is a pop of at most one LSB on those pixels. The device arm
  decides whether ir3 does the same.

**What survives, and what to do instead:**
- **A narrower ubershader does not help.** The cost is control flow (5.1), and the pipeline cost
  is dominated by the VS/GS it must be linked with. Fewer combiner features would shave part of
  0.3-0.7 s off a 1-2 s pipeline.
- **The one design where a fragment ubershader pays is with pipeline libraries (P5/GPL).** The
  uber fragment stage is compiled once per family as a fragment-shader library, and a first-sight
  pipeline becomes a link of an existing VS library with it. Its value is bounded by how cheap
  Turnip's GPL link is (not measured here) and by the family count (section 3).
- **Where key sets exist (P3), prebuild the specialised pipelines instead.** No interpreter, no pop.
- **Exactness, if a hybrid is built after all:** compile the combiner arithmetic exact
  (`NoContraction`) on BOTH paths (section 4.1). That is a default-path change with its own pixel
  arm.

## Do not repeat

- Do not build a Turnip ubershader out of switches. Register access and mapping by `switch`, inlined
  per input, cost 4-10 s per pipeline on the host; an array register file and arithmetic mappings
  cost 0.3-0.7 s for the same exactness (5.1).
- Do not judge an interpreter by "same ops, same order". The specialised compiler sees constants and equal
  operands the interpreter cannot, and rewrites inexactly on them (section 4.1).
- A render check whose inputs discard everything passes vacuously. The first run here had 217 of
  479 "ok" pairs with no drawn pixel (window clip regions covering the target under an exclusive
  clip; alpha refs above every alpha). `render_check.py` now prints drawn-pixel counts per
  baseline.
