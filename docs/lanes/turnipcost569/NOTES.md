# lane.turnipcost569 -- why one shader costs ~400 ms in Turnip, measured offline (#569 P2 phase A)

**Outcome:**
- The host Turnip (Mesa 26.3-devel, Adreno 740 via drm-shim) takes **~0.9-1.1 s per realistic
  hakuX pipeline**, and its profile matches the device's.
- The time is not in the four features the plan named. It is in two exactness features:
  - **#224's bit-exact lighting arithmetic**, about 96% of a lit vertex shader, 4.5-5.8x per lit
    pipeline;
  - **#223's negative-w wedge in the triangle geometry stage**, about 97% of that stage, 2.6-11x
    per non-lit pipeline.
- An exact, loop-free rewrite of the heaviest lighting helper already halves a lit pipeline.
  That is Phase B's first lever (section 6).

Item P2 of `docs/lanes/shaderplan569/NOTES.md` section 7 (PR #570). Offline only: no device,
no emulator code. Everything built lives in the worktree's git-ignored `.scratch/`.

## 0. Pre-registration (committed before the first timed run on a hakuX shader)

The only compile timed before this commit is a two-line GLSL pair (`triv`, 0.4-1.6 ms), run to
check that the harness reaches Turnip and that no cache answers a repeat.

**Setup.** Mesa at `4c18636110f0` (main, 2026-09-25, 26.3.0-devel; the same tree as
`tools/turnip/build.sh`; T30 reports `git-62ac221a33`, which is not on Mesa main), built for
x86_64 with NDEBUG (T30 has no `nir_validate` symbol, so it is NDEBUG too), -O2, full debug
info. The freedreno noop drm-shim presents an Adreno 740 (`FD_GPU_ID=740`). `vkharness`
dlopens the ICD and times `vkCreateGraphicsPipelines` with no pipeline cache, the in-memory cache
off (`VK_ENABLE_PIPELINE_CACHE=false`) and the disk cache off, so every rep is cold. Shaders
come from hakuX's own generators (`hw/xbox/nv2a/pgraph/glsl/*.c`, carved as psh_differ does),
through glslang at the Android pin (`b5782e52`) with vk/glsl.c's options and resource limits.

**The fixed set:** the 15 `+gtri` pipelines of `gen/gen.c`'s manifest (8 vertex states x the
basic pixel shader, 7 more pixel states x `ff_lit2`), each VS' + GS(triangles) + FS, because
every filled-triangle draw on the Vulkan path carries a geometry stage
(`pgraph_glsl_need_geom`, `geom.c:81-94`). 5 reps each, median per pipeline.

**Host CPU:** i7-6700K, 4.0-4.2 GHz, one thread.

### Leg A: per-pipeline Turnip time on the host, and its scale to the device

- **Prediction:** the median over the fixed set of per-pipeline medians is in **[20, 200] ms**.
- Reading, decided now:
  - **>= 100 ms:** the host is within 4x of the device's ~400 ms. The cost is the shaders
    themselves, and a factor found here is expected to carry to the device.
  - **< 40 ms:** the device pays > 10x what this host pays for shaders of this kind. Then the
    gap is outside what the host reproduces (the core the PFIFO thread runs on, T30's own
    patches, DOA's shaders being unlike the catalogue, or pipeline413's bound being loose), and
    Phase B may not assume a host factor transfers.
  - in between: same order, stated with the scale below.
- The host-vs-device scale is stated from public single-thread figures, as a range, and marked
  as an estimate: it is a bound, not a measurement.

### Leg B: which passes dominate (a reading, not a threshold)

- The SIGPROF sampler's samples inside `vkCreateGraphicsPipelines` over the fixed set,
  symbolized against the host build, grouped inclusively: `vk_pipeline_shader_stage_to_nir`
  (spirv_to_nir), `ir3_optimize_loop` inside `tu_spirv_to_nir`, the rest of
  `tu_spirv_to_nir`, `tu_link_shaders`/`link_opts`, `ir3_compile_shader_nir` and below (the ir3
  backend), and the remainder.
- **Expectation:** `tu_spirv_to_nir` inclusive is >= 50% of the samples, as on the device (65%,
  doa413c NOTES:195-203), and the ir3 backend <= 35%. If the backend is > 50%, the host does
  not reproduce the device's profile shape, and the ranking below is read with that caveat.

### Leg C: generator features, cost with the feature on vs off (host, same harness)

Factor = Turnip time with the feature / without, on the pipelines that contain it. Each "off"
is an edit to the carved copy of the generator (`gen/variants/*.py`), never to the repo's
sources, and need not be pixel-correct: it is a cost probe.

| id | feature | "off" means | prediction |
|---|---|---|---|
| C1 | glslang optimizer | Android builds glslang with `ENABLE_OPT OFF` (`android/app/src/main/cpp/CMakeLists.txt:264`), so the device's optimizer is **already off**; the lever is turning it ON | Turnip time with SPIRV-Tools `-O` SPIR-V is >= 1.3x lower; spirv-opt's own time is reported beside it |
| C2 | dynamic `c[A0+n]` (`vsh-prog.c:342-344`) | the same index, static | < 1.1x on `prog_skin4_a0` |
| C3 | constant-writer copy (`vsh-prog.c:866-875`) | no `c_rw` copy (writes to a scratch vec4) | >= 1.3x on the `prog_aa_cwrite` pipeline |
| C4 | vsh-prog's NaN / zero-exact helpers (`_MUL` branches, `_PosNaN`, `_DotZeroForced`, `vsh-prog.c:639-711`) | plain `*`, `+`, `dot` | the largest vertex-side factor, >= 1.5x on the program pipelines |
| C5 | psh texture modes and stage count | ranking of the pixel states against `basic` | `stages8` and `border` are the costliest, each >= 2x `basic` |
| C6 | the geometry stage | VS + FS with no GS (and unprefixed VS) | the GS adds >= 30% per pipeline |

**Added after the base run (commit 7ba8c8d8ba's run), before either was run.** The base run
showed two costs the table above did not name, so two more probes, predictions written here
first:

| id | feature | "off" means | prediction |
|---|---|---|---|
| C7 | the fixed-function lighting unit's bit-exact arithmetic (`vsh-ff.c:128-283`, #224: `lt`, `ltMulCore`, `ltA3`, `ltsA`, `ltR`) | float32 arithmetic (the approximation #224 replaced; NOT pixel-inert) | lit pipelines' VS time drops >= 3x |
| C8 | the triangle geometry stage's negative-w wedge (`geom.c:436-449`, #223) | three plain emits, `max_vertices = 3` (NOT pixel-inert on the W_param goldens) | the GS stage's time drops >= 2x |

C7a, C7b (which lighting helper) and C7p (the exact prototype, section 5) were run after C7, as
follow-ups with no registered threshold. They are readings.

## 1. Results at a glance

1. **Leg A: prediction refuted, and the host is not faster.** The host median for the fixed set is
   **861-1108 ms per pipeline** (three runs), not [20, 200] ms. This is above the device's
   ~400 ms mean excess per miss. The registered reading ">= 100 ms" applies: the cost is the
   shaders themselves, and a factor measured here is expected to carry to the device.
2. **Leg B: the host reproduces the device's profile.** Across the whole set, `tu_spirv_to_nir`
   is 55.6%, `tu_shader_create` 29.1% and `link_opts` 13.7%. The device measured 65%, 21% and
   10%. Inside, `ir3_optimize_loop` is 73% inclusive and spirv_to_nir proper is only 1.8%.
   **A lit fixed-function pipeline matches the device almost exactly: 66.3%, 20.7% and
   12.5%.**
3. **Two generator features carry nearly all the cost, and neither was on the plan's list:**
   - The fixed-function lighting unit's bit-exact arithmetic (#224) is about 96% of a lit VS
     (976 -> 37 ms without it). It makes each lit pipeline 4.5-5.8x dearer.
   - The negative-w wedge in the triangle geometry stage (#223) is about 97% of that stage
     (~150 -> ~4 ms without it). The geometry stage is on every filled-triangle pipeline and
     makes a non-lit pipeline 2.6-11x dearer.
4. **The plan's four candidates are small or backwards:**
   - The glslang optimizer switch does nothing. Turning SPIRV-Tools on makes lit pipelines
     1.5-2.3x slower.
   - Removing `c[A0+n]` makes the vertex stage 1.7x cheaper, but the whole pipeline only 1.17x.
   - Removing the constant-writer copy does nothing measurable.
   - psh texture modes cost 3-10 ms per fragment shader: noise next to the VS and GS.
5. **The first Phase B lever is measured.** A loop-free, vectorised `ltA3` is bit-exact on the
   CPU (50 M triples, 0 mismatches; a one-constant mutant is caught). It makes lit pipelines
   **1.9-2.2x** cheaper on its own.

## 2. Build recipe (re-runnable; everything lands in the worktree's git-ignored `.scratch/`)

```
docs/lanes/turnipcost569/build_host_turnip.sh   # Mesa 4c18636110f0 + drm-shim, x86_64, NDEBUG -O2 -g (~10 min, 8 threads)
docs/lanes/turnipcost569/build_glslang.sh       # glslang b5782e52 twice: ENABLE_OPT OFF (device) and ON
docs/lanes/turnipcost569/compare.sh <tag> <A> <B> [reps] [row regex]
    # spec = <variant>:<noopt|opt>[:optsize]; e.g.
    #   compare.sh aa base:noopt base:noopt 5              (the A/A control)
    #   compare.sh c7 base:noopt c7_lt_plain:noopt 5 'ff_'
docs/lanes/turnipcost569/prof.py <icd.so> <tag.samples> --manifest <tag.manifest> [--only <row>]
docs/lanes/turnipcost569/gen/run_lta3_check.sh 50   # C7p's CPU bit-exactness check + mutant
```

- **Host tools** come from lane.turnipfork's setup (read only). They are its Mesa clone (shared
  clone into `.scratch/mesa`), its meson venv, its glslangValidator, and the nxdk
  bison/flex/ninja/m4 bundle (`BISON_PKGDATADIR`, `M4`, as in `tools/turnip/build.sh`).
  - No sudo is needed.
  - Meson options: `-Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm -Dtools=drm-shim
    -Dplatforms= -Dgallium-drivers=` with llvm, zstd, expat and xmlconfig off.
  - `-Dbuildtype=custom -Doptimization=2 -Ddebug=true -Db_ndebug=true`. With a custom
    buildtype, b_ndebug must be set explicitly, or asserts and NIR validation stay on.
- **Running:** `run_harness.sh` sets `LD_PRELOAD=libfreedreno_noop_drm_shim.so FD_GPU_ID=740
  VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true`.
  - `vkharness.c` dlopens the ICD. There is no loader.
  - It builds the hakuX pipeline layout: set 0 is four samplers, set 1 is two UBOs, and push
    ranges are as in `vk/draw.c:2727-2764`.
  - It times `vkCreateGraphicsPipelines`: wall time, thread CPU time, and
    `VkPipelineCreationFeedback` per stage.
  - Reps run round-robin. `compare.sh` puts A and B of each pipeline on adjacent lines, so both
    sides share the machine's load.
- **Shaders:** `gen/gen.c` links hakuX's real `glsl/{vsh,vsh-ff,vsh-prog,geom,psh,common}.c`.
  - The sources are carved by `gen/carve_all.py`, which extends psh_differ's `carve.py`.
  - It uses vk/shaders.c's GLSL options and vk/glsl.c's glslang call and resource limits
    (extracted verbatim at build time).
  - Each variant is an exact-match edit of the carved copies (`gen/variants/*.py`). An edit that
    does not match stops the build. The repo's sources are never touched.
  - Vertex programs are the pgraph and vsh test suites' own `.vshinc` builds, plus
    `gen/skin4_a0.vsh`, a 4-bone A0 palette skin assembled with nv2avsh.
- **Noise:** the host is a 4-core i7-6700K that other lanes load (loadavg 3-5 during these runs).
  - The A/A control (base vs base, interleaved) gives per-pipeline factors of **0.83-1.12x**
    and a fixed-set geomean of **1.01x**.
  - So a per-pipeline factor under ~1.15x is noise. Absolute ms drift about ±25% between runs.
- **Sampler:** ITIMER_PROF with `backtrace()`, symbolized from the host build's symbol table
  (C++ names demangled; inlined static functions fold into their callers).
  - It fires at the kernel tick (~4 ms), not the 200 us asked for, so per-pipeline profiles are
    a few hundred samples.
  - The whole-set profile is 22,218 samples.

## 3. Leg A: per-pipeline time on the host

Base run, `compare.sh aa_control` side A (thread CPU ms, median of 5). Stage columns are
creation-feedback medians.

| pipeline (VS' + GS + FS) | cpu ms | VS | GS | FS |
|---|---|---|---|---|
| ff_unlit + basic | 241 | 29 | 160 | 6 |
| ff_lit2 (2 lights, specular, fog) + basic | 1401 | 931 | 172 | 7 |
| ff_skin_texgen + basic | 1379 | 970 | 153 | 7 |
| prog_pass (passthrough.vshinc) + basic | 203 | 4 | 160 | 5 |
| prog_proj + basic | 247 | 26 | 175 | 7 |
| prog_ffapprox + basic | 274 | 41 | 180 | 7 |
| prog_skin4_a0 + basic | 289 | 85 | 151 | 6 |
| prog_aa_cwrite + basic | 81 | 12 | 48 | 3 |
| ff_lit2 + vcolor / game2 / aniso4 / dotprod | 1319-1557 | 874-1197 | 140-167 | 6-9 |
| ff_lit2 + bumpenv / border / stages8 | 1048-1318 | 685-858 | 140-157 | 7-9 |
| **fixed set (15), median** | **1108** | | | |
| same VS + FS, **no GS**: ff_unlit / ff_lit2 / prog_pass / prog_skin4_a0 | 34 / 1106 / 9 / 154 | | | |

- **The fixed set is 1108 ms here, 861 ms and 923 ms in the other two runs.** The leg predicted
  [20, 200] ms, so the prediction is **refuted**. The reading registered for >= 100 ms applies:
  the cost is in the shaders, the same order as the device's, and host factors are expected to
  carry.
- **Host-vs-device scale: unmeasured, not estimated.** The leg planned to state it from public
  single-thread figures, but WebSearch was not permitted in this session, and a remembered
  benchmark number would be a guess dressed as a source. What is known:
  - The host is above the device's ~400 ms mean. So either DOA's mix is lighter than this
    catalogue, or the device's core is faster than this 2015 desktop core per compile.
  - pipeline413's 400 ms is an upper bound per miss, not a per-pipeline measurement.
  - **What pins the scale:** P1's `dpc_ms` per stage (lane.shaderfb569) on the device, beside
    this harness on the same shaders. The keys-file pull requested below would give exactly
    those shaders.

## 4. Leg B: which passes dominate

Inclusive shares of the samples inside `vkCreateGraphicsPipelines`:

| group | whole set (22,218) | lit FF pipeline, no GS (1,774) | `prog_pass` + GS (217) | device, doa413c |
|---|---|---|---|---|
| `tu_spirv_to_nir` | 55.6% | **66.3%** | 24.9% | **65%** |
| `tu_shader_create` | 29.1% | **20.7%** | 60.8% | **21%** |
| `link_opts` | 13.7% | **12.5%** | 11.1% | **10%** |
| `ir3_optimize_loop` (called from all three) | 73.4% | 80.2% | 52.5% | (chains truncated) |
| spirv_to_nir proper (vtn) | 1.8% | 1.8% | 1.8% | |
| ir3 backend (`ir3_compile_shader_nir`) | 21.9% | 17.5% | 37.8% | |
| ir3 RA (+ `ir3_spill` 9.2% on the GS) | 5.3% | 1.9% | 18.9% | |

- The expectation held: `tu_spirv_to_nir` is >= 50% and the backend is <= 35% over the set.
- **Where the time goes:** the NIR optimisation loop over a very large, branchy program. The top
  pass-level frames are:
  - `nir_algebraic_impl` 13%, `nir_copy_prop_vars` 10%, `nir_opt_uub` 9%;
  - then `nir_lower_reg_intrinsics_to_ssa`, `nir_opt_cse`, `nir_lower_vars_to_ssa`.
  - Leaf self-time is spread thinly: `match_expression` 7%, CFG walking 4%, and
    ralloc/hash tables about 10%.
- **No single pass is the problem, and no Turnip flag fixes it.** The input is too big.
- **The geometry-stage pipeline is different.** Its backend is 38%, including register spilling,
  because the wedge's `P[8]`/`Q[8]`/`A[8]` arrays are indexed dynamically.
- **The lit-FF profile matches doa413c's device profile to within 1-2 points on all three
  frames.** The GS-dominated profile does not. That suggests (only suggests; it is a shape match,
  not a count) that DOA's stall is dominated by lit fixed-function vertex shaders. The keys-file
  pull settles it.

## 5. Leg C: generator features, ranked by cost

The factor is A (as shipped) / B (feature off), in interleaved thread CPU time, median of 5.

| rank | id | feature | stage factor | pipeline factor | prediction | verdict |
|---|---|---|---|---|---|---|
| 1 | C7 | FF lighting bit-exact arithmetic (#224) | lit VS **~25x** (976 -> 37 ms) | lit + GS **4.5-5.8x** (fixed-set lit rows geomean 4.54x); lit, no GS 20-22x | VS >= 3x | holds |
| 2 | C8 | triangle-GS negative-w wedge (#223) | GS **~35x** (~150 -> ~4 ms) | non-lit **2.6-10.9x**; lit 1.06-1.30x; fixed set geomean 2.08x | GS >= 2x | holds |
| 3 | C6 | the geometry stage itself | | +GS vs no GS: prog_pass 23x, ff_unlit 7x, skin4 1.9x, lit 1.1-1.3x | GS adds >= 30% | holds for every non-lit pipeline |
| 4 | C4 | vsh-prog NaN/zero-exact helpers | program VS **2.7-4x** | with GS 1.0-1.31x (geomean 1.14x) | pipeline >= 1.5x | refuted for pipelines (the GS hides it); holds for the stage |
| 5 | C2 | dynamic `c[A0+n]` | skin VS **1.7-2x** | 1.17x | < 1.1x | refuted: larger than predicted, still small beside 1-3 |
| 6 | C5 | psh texture modes / stages | FS 3-10 ms against VS/GS in the hundreds | | stages8, border >= 2x basic | refuted: stages8 1.3x, border 1.3x basic; FS is not a lever |
| 7 | C3 | constant-writer copy | aa_cwrite VS 1.13x | 0.93x | >= 1.3x | refuted: inside noise |
| - | C1 | glslang optimizer | see below | lit **0.43-0.76x** (slower); aa_cwrite no-GS 2.6x | >= 1.3x cheaper | refuted, and backwards |

**C1: the "optimizer" is not a lever as written.**
- `vk/glsl.c:248` leaves `disable_optimizer` false, but glslang runs SPIRV-Tools on GLSL input
  **only when `optimize_size` is set** (`SPIRV/GlslangToSpv.cpp:11551` at b5782e52). So the
  switch does nothing in any build.
- Android also builds glslang with `ENABLE_OPT OFF`. The ENABLE_OPT build with `disable_optimizer`
  false produced SPIR-V byte-identical to the device build's.
- With `optimize_size` on, Turnip took **longer**: lit pipelines 1.5-2.3x slower. SPIRV-Tools'
  inlining and scalar replacement hand NIR a larger, flatter program.
- glslang itself went from 292 to 454 ms over the 27 shaders.

**Inside C7 (follow-up readings):**
- `ltA3` alone as a plain add (C7a): lit VS **4.5x** (818 -> 181 ms), lit pipeline 2.5x.
  `ltA3` is the three-term aligned add, with two 3-iteration loops over local arrays and early
  returns inside loops.
- `ltMulCore` alone as a plain multiply (C7b): lit VS 1.6x.
- The rest (`lt`, `ltsA`, `ltR`) makes up the remainder.

**C7p, the exact prototype.** It is `gen/variants/c7p_lta3_vec.py`: `ltA3` written without loops
or early returns, as `uvec3`/`ivec3` operations with the NaN/Inf/zero cases as final selects and
`findMSB` in place of `ltMsb`.
- **Bit-exact on the CPU.** `gen/lta3_check.c` transcribes both GLSL functions to C and compares
  50,013,824 triples: random bit patterns, nearby-exponent triples, and all 24^3 special-value
  combinations. There are **0 mismatches**.
  - A mutant with the alignment bias 2 -> 3 is caught: 15,763 mismatches in 1 M.
  - Limit: this checks the transcription, not the GPU. Phase B's arms are the real test.
- **Cost:** lit pipelines **1.90-2.18x** cheaper with the GS, 2.4x without. The VS drops
  2.5-4.2x, and non-lit rows do not move (0.98-1.11x).

## 6. Phase B proposal

**B1 (first): rewrite the lighting unit's helpers for the compiler, keeping them bit-exact.**
- **File:** `vsh-ff.c:128-283`.
- **Change:**
  - `ltA3` as in C7p.
  - Then the same treatment for `ltMulCore`, `ltsA`, `ltR` and `ltMk`: straight-line code, and
    special cases as final selects rather than early returns.
  - `ltVM`, `ltVA` and `ltDp` get vector forms, one call where there are now three.
- **Expected factor on a lit pipeline:**
  - **>= 1.9x**, measured for `ltA3` alone.
  - The ceiling is **4.5-5.8x**: C7's float-arithmetic bound, less whatever the exact forms
    cannot shed.
  - On the device, the stall shrinks by the lit pipelines' share of it. That share is the
    keys-file pull's answer.
- **Gates, in order:**
  1. The CPU bit-exactness check (extend `gen/lta3_check.c` to every rewritten helper, with a
     mutant each).
  2. **Pixel-inert arms on every golden that draws with fixed-function lighting.** Register a
     prediction of no change, and read per-capture byte identity, not a count:
     - Lighting (all), Shade model, Material*, Specular, Two-sided lighting, Fog (lit rows),
       Lighting range/accumulation/normalization;
     - the #224 set (Shade model's nine colours, Lighting range Directional 203, Lighting
       accumulation Directional-5).
     - The full sweep is simpler and is what the plan asks of a vsh change.
  3. One cold DOA soak with P1's `dpc_ms`. The leg: the fight load's `dpc_ms` falls by the
     measured factor x the lit share, within 30%.
- **Release note:** performance.
- **GLES:** keep the old forms under `opts.gles` (C7p needs GLSL 4.50).

**B2 (second): make the triangle geometry stage's wedge cheap to compile.**
- **File:** `geom.c`, #223's `wedge_clip` / `emit_wedge`.
- **The prize:** ~150 ms of every filled-triangle pipeline. C8 bounds it at 35x on the stage and
  2.6-11x on non-lit pipelines.
- **Nothing here is prototyped.** The candidates are:
  - the four `wedge_clip` calls as one fixed-size, straight-line clip of a quadrilateral against
    the unit square, with no `P[8]`/`Q[8]` dynamic indexing (the source of the spilling);
  - the emit loop with static indices.
- **Gates:**
  - the W_param goldens (the 13 negative-w `prog_w_zero_inf__bitri` captures);
  - the full sweep, because every triangle draw passes through this stage.
- **Before B2 is worth it, check whether Turnip even recompiles an unchanged GS.** P1's leg C3
  measures whether Turnip reuses an unchanged partner stage across pipelines. If Turnip reuses
  the GS, B2's device factor is small.

**Not recommended:**
- the SPIRV-Tools optimizer (C1: slower);
- the constant-writer copy (C3: nothing);
- psh texture modes (C5: the FS is 1% of a pipeline);
- `c[A0+n]` (C2: 1.17x per pipeline, and it would need a correct static form, which does not
  exist for a palette skin).

## 7. Device data asked for

- **What:** `shader_module_keys.bin` and `spv_cache/` from the Nova after lane.shaderfb569's cold
  DOA soak. Board request `$DISPATCH_DIR/board-requests/turnipcost569.md`, for lane.local; no
  hold, no device time.
- **What it gives:** the file holds every `ShaderModuleCacheKey` DOA compiled
  (`vk/shaders.c:1049-1064`). `gen.c` can then regenerate DOA's exact GLSL: its lit / program /
  GS mix, and B1's and B2's factors on DOA's own shaders. The `.spv` files check that the host
  regeneration matches the device byte for byte.
- **Without it,** section 5 ranks features on a catalogue, not on DOA.

## 8. For the next lane: do not repeat

- **Do not flip `disable_optimizer`** expecting SPIRV-Tools: GLSL input needs `optimize_size`
  (section 5, C1). And optimized SPIR-V is slower for Turnip here.
- **Do not time single runs on this host.** Other lanes load it. Use `compare.sh`'s interleaved
  A/B and thread CPU time, and run an A/A control first: per-pipeline noise is ±15%.
- **Every filled-triangle pipeline has a geometry stage.** A catalogue of VS + FS pairs misses
  the ~150 ms that is often most of the pipeline.
- **meson `-Dbuildtype=custom` does not imply NDEBUG.** Set `-Db_ndebug=true`. T30 is NDEBUG.
- **The `tu_*` symbols are C++.** Demangle them, or every Turnip frame reads as "no group".
- **ITIMER_PROF fires at the kernel tick (~4 ms)** whatever interval is asked for.
- The Bash sandbox here rejects pipelines, `cd`+git, and running binaries from `.scratch`
  directly. Run tools through `bash <script>` or `python3`.
