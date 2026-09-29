# lane.litcompile569 -- B1: the lighting unit's helpers, cheap to compile and bit-exact (#569)

P2 phase B1 of #569, as proposed in `docs/lanes/turnipcost569/NOTES.md` section 6 (PR #573).
The change is in `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`, `append_lighting_header()`.

## 0. Pre-registration (committed before the first timed run of the new forms)

### Gate 2: host compile time per lit pipeline

- **Harness:** lane.turnipcost569's, unchanged. Mesa Turnip `4c18636110f0` for an Adreno 740
  via drm-shim, NDEBUG -O2, and glslang `b5782e52` with the device's options. Its built Mesa
  and glslang are reused read-only. `compare.sh` interleaves A and B, 5 reps, thread CPU
  time.
- **A** = the harness variant `old_lt` (this directory's `old_lt.py`). It turns the new block
  off (`#if 0`), so the Vulkan build compiles the forms master ships. Before this commit it was
  checked to give SPIR-V **byte-identical** to master's for all 27 shaders of the catalogue.
- **B** = this branch.
  - The only SPIR-V that differs from A is the four lit fixed-function vertex shaders (`ff_lit2`
    and `ff_skin_texgen`, with and without the prefixed outputs).
  - Unlit, program, geometry and fragment shaders are byte-identical.
- **Measure:** the factor A/B for each lit `+gtri` pipeline of the fixed set: `ff_lit2` x 8
  pixel states, and `ff_skin_texgen`. The leg is their geometric mean.
- **Prediction:** the geomean is **>= 1.9x**. That is C7p's measured factor for `ltA3` alone
  (1.90-2.18x). It is bounded above by C7's float-arithmetic ceiling of 4.5-5.8x, because the
  exact forms keep all the integer work.
- **Reading, decided now:**
  - **>= 1.9x:** B1 holds on the host. The factor is the one the device leg (gate 4) scales.
  - **between 1.15x and 1.9x:** the rewrite of the other helpers costs back part of C7p's gain.
    It ships only if the arms pass. The NOTES say which helper form to revisit, from a
    per-helper probe.
  - **< 1.15x:** inside the harness's A/A noise (0.83-1.12x per pipeline). The leg is refuted.
- **Control:** the non-lit `+gtri` rows (`ff_unlit`, and the five `prog_*`) are byte-identical
  on both sides. Their A/B is the run's own A/A, and it must stay within 0.85-1.15x. If it does
  not, the run is noise-limited and is repeated.

### Gate 1 (CPU bit-exactness) -- done before this pre-registration, stated for the record

`lt_check.c` transcribes both the old forms (the `#else` branch) and the new forms to C, line
by line. It compares them:
- `ltR` over all 2^32 inputs;
- `ltMkU` over every sign, e in [-64, 320] and m in [0, 2^16);
- `ltM`, `ltsM`, `ltVM`, `ltA3`, `ltVA`, `ltsA` and `ltDp` over the special-value products,
  random words, and nearby-exponent inputs.

It also has 10 mutants, one or more per rewritten helper, and each must be caught. The 1 M run
gave **0 mismatches** and **10 of 10 mutants caught**. The 50 M run is in section 1.

### Gate 3: pixel-inert arms (registered at 19:56Z, before any device run)

`docs/testing/predictions/litcompile569-arms.json`.
- **Refs:** A is master `503b901ee4` and B is `fb80d7e793`, this branch merged with it. The two
  differ in `hw/` only by `vsh-ff.c`.
- **Disc:** the full sweep. That is all 100 golden suites, with `RenderTextureLoop` skipped, as
  `queue_full_sweep.sh` does.
- **Prediction:** no change anywhere. `must_not_move` names all 489 captures of the lighting
  set:
  - Lighting (Two_Sided, accumulation, control, normals, range, spotlight);
  - Material_alpha, Material_color and Material_color_source;
  - Shade_model, Specular and Specular_back;
  - the Fog family (Fog, Fog_gen, Fog_param, Fog_vsh), all rows. The Fog tests do not set the
    lighting state themselves, so "the lit rows" cannot be picked from the source. All rows is
    the stricter claim.
  - The set includes #224's: Shade_model's Fixed flat colours, Lighting_range/Directional and
    Lighting_accumulation/Directional-5.
- **World in which it fails:** a lit capture moves by one byte. Then the GPU evaluates some
  construct differently from the C transcription: `findMSB`, `mix` on uint or bool, shifts of
  23-31, or the vector `==`/`!=` reductions. The suite that moves names the helper.

## 1. Results

### Gate 1: CPU bit-exactness -- holds

`run_lt_check.sh 50`, 50 M random/nearby inputs plus the exhaustive and special sets:

| helper | inputs checked | mismatches |
|---|---|---|
| `ltMkU` (scalar) | 50,462,720 (every s, e in [-64, 320], m < 2^16) | 0 |
| `ltMkU` (vec3) | 591,360 | 0 |
| `ltM` / `ltsM` | 25,000,900 each | 0 |
| `ltVM` (per lane) | 112,581,000 | 0 |
| `ltA3` | 25,027,000 | 0 |
| `ltVA` (per lane, against `ltA3(a, b, 0)`) | 112,581,000 | 0 |
| `ltDp` | 37,527,000 | 0 |
| `ltsA` | 25,000,900 | 0 |
| `ltR` | **4,294,967,296 (all inputs)** | 0 |

**Mutants: 10 of 10 caught.** Each is one constant or one flag in a new helper:
- `ltMkU` (scalar and vec3);
- `ltMulV`'s exponent bias;
- `ltA3`'s alignment bias (C7p's own mutant);
- `ltVA`'s alignment;
- `ltsA`'s final shift;
- `ltR`'s underflow edge;
- a lane swap in `ltVM`;
- `ltDp` using the signed multiply;
- `ltsM` using the unsigned one.

The smallest catch is `ltMkU3`'s edge mutant: 1,532 mismatches in its own sweep and 2,678
through `ltVA`.

**What this does not check:** the GPU. The transcription reads each GLSL line as C. The arms
(gate 3) are the test of whether Turnip/ir3 evaluates `findMSB`, `mix` on uint/bool and the
vector reductions the same way.

**GLSL versions:**
- The helper block, as the generator emits it, compiles under `#version 300 es` and `#version
  400` (glslang `b5782e52`). Those take the `#else` forms, which are unchanged from master.
- Under 450, the whole catalogue compiles through the device's glslang options.

### Gate 2: host compile time -- holds, 2.5-2.7x per lit pipeline

`compare.sh <tag> old_lt:noopt base:noopt 5 '\+gtri'`, thread CPU ms, median of 5. Two
independent runs, loadavg ~4:

| pipeline (+GS +FS) | run 1 A -> B ms | A/B | run 2 A -> B ms | A/B |
|---|---|---|---|---|
| ff_lit2 + basic | 1568 -> 476 | 3.30x | 1302 -> 518 | 2.51x |
| ff_skin_texgen + basic | 1254 -> 594 | 2.11x | 1392 -> 557 | 2.50x |
| ff_lit2 + vcolor | 1509 -> 545 | 2.77x | 1360 -> 500 | 2.72x |
| ff_lit2 + game2 | 1764 -> 745 | 2.37x | 1464 -> 782 | 1.87x |
| ff_lit2 + aniso4 | 1508 -> 593 | 2.54x | 1272 -> 556 | 2.29x |
| ff_lit2 + dotprod | 1375 -> 592 | 2.32x | 1245 -> 504 | 2.47x |
| ff_lit2 + bumpenv | 1271 -> 390 | 3.26x | 1063 -> 339 | 3.13x |
| ff_lit2 + border | 1198 -> 393 | 3.05x | 950 -> 323 | 2.94x |
| ff_lit2 + stages8 | 1348 -> 530 | 2.54x | 1334 -> 509 | 2.62x |
| **lit geomean (the leg)** | | **2.67x** | | **2.54x** |
| control: ff_unlit, prog_* x 5 (byte-identical SPIR-V) | | 0.88-1.04x | | 0.95-1.08x |

- **The leg (>= 1.9x) holds in both runs.** The control stayed inside 0.85-1.15x.
- **The lit vertex stage** drops from 790-1340 ms to 96-450 ms, about 4-5x. The geometry stage
  (~150 ms) and the fragment stage are untouched, which is why the pipeline factor is lower than
  the stage factor. The geometry stage is B2's prize.
- **Ceiling not reached:** C7's float-arithmetic bound was 4.5-5.8x. The exact forms keep the
  integer work. The largest single item left in a lit VS is probably the ~40 inlined copies of
  `ltMulV` and `ltA3`, not control flow. That is a guess, not measured: no per-helper probe was
  run after the rewrite.
- The B VS time varies 96-450 ms for the same vertex shader across rows. The creation-feedback
  per-stage split moves with what `link_opts` does against each fragment shader. The pipeline
  total is the figure to read.

## 2. What the change is

`append_lighting_header()` now emits `#if __VERSION__ >= 450` / new forms / `#else` / the
forms master ships / `#endif`. Only the Vulkan path is `#version 450`.
- **Why the preprocessor and not `opts.gles`:** the generator entry points do not see the GLSL
  options. Threading them through would edit `vsh.c` and `vsh-ff.h` for no gain. Desktop GL is
  `#version 400`, which also lacks `mix` on uint/bool, so it must keep the old forms too. The
  version test gets both right.
- **What the new forms avoid:** glslang emits `?:` as a branch unless both arms are bare
  symbols or constants, and `&&`/`||` as a branch unless the right side is one comparison of
  leaves (`isTrivial`, `SPIRV/GlslangToSpv.cpp` at `b5782e52`). So every choice is a `mix()`
  (always `OpSelect`), and compound conditions are split into named bools.
- **The helpers:**
  - `ltMulV(vec3, vec3, bool signedInf)` is the one multiply. `ltM`, `ltsM` and `ltVM` are its
    `.x` or its whole vector.
  - `ltA3` is C7p, finishing in uint.
  - `ltVA` is `ltA3(a, b, 0)` in each lane.
  - `ltDp` is `ltA3` over one `ltVM`.
  - `ltsA`, `ltR` and `ltMkU` are straight-line.
- **Nothing else moves:** unlit, program, geometry and fragment SPIR-V are byte-identical to
  master's. The A side was checked byte-identical to master for all 27 shaders.

## 3. How to re-run

```
docs/lanes/litcompile569/run_lt_check.sh 50      # gate 1, ~9 min (ltR exhaustive x 11)
# gate 2: lane.turnipcost569's harness (docs/lanes/turnipcost569, section 2 of its NOTES),
# with this directory's old_lt.py copied into its gen/variants/, then
OUT=<scratch> docs/lanes/turnipcost569/compare.sh g2 old_lt:noopt base:noopt 5 '\+gtri'
```

The harness carves `hw/xbox/nv2a/pgraph/glsl/*.c` from the tree it sits in. Its built Mesa and
glslang are large (~10 min to build), so `mesa`, `mesa-build`, `glslang-noopt` and `vshinc` were
symlinked from lane.turnipcost569's `.scratch` rather than rebuilt.

## 4. State at the end of session 1 (2026-09-28): waiting

- **Waiting on gate 3:** the arms job's `[job.arms]` verdict on PR #580 for
  `litcompile569-arms.json` (full sweep, a=`503b901ee4`, b=`fb80d7e793`).
- **Waiting on CI:** CI for the PR head.
- **Next:**
  - If the verdict is PASS and CI is green, mark #580 ready.
  - If a lit capture moved, see the prediction's "world in which it fails" for which helper to
    suspect. Re-run `lt_check.c` with that helper's GPU semantics in mind.
  - Gate 4 follows P1 (#574) as its own post.

## 6. Session 2 (2026-09-28 21:30 PDT, attempt 2)

### Why session 1 did not finish

It ended on purpose, waiting (section 4) on two things outside it: the arms pair (about 90
min of Nova time behind other queued work) and CI. Its `waiting:` comment is on #580. #569's
`blocked:in-flight` label made `handback.sh` skip the lane, so the waiter unit resumed it
when the pair finished. At resume, CI was green on `856d9455cb` and both arms were DONE.
The arms job had not yet judged the pair.

### Gate 3: the arms pair, read per capture before the job's verdict

Base `1-1790625720-arms-litcompile569-base-3794892` (503b901ee4) and fix
`1-1790625721-...-fix-3795315` (fb80d7e793): Nova, 3,379 captures each, both from a cleared
cache (two apks).
- **All 489 registered lighting-set captures are byte-identical** (sha256 of each PNG).
- **13 other captures moved:**
  - 9 are Stencil_REPLACE/ZERO_*;
  - 4 are Vertex_shader_rounding_tests Geometry{Sub,Super}screen_*.
- **Both suites draw with `PassthroughVertexShader`, a vertex program.** Their pipelines have
  no fixed-function vertex shader, and B1 changes only lit fixed-function SPIR-V. The change
  cannot reach them.
- **10 of the 13 fix images also appear in runs of refs without B1** (flip474, zrtz272,
  notify488, dpforce345, buildflags427: 1-23 runs each). These captures are bistable noise.
  Stencil moves by whole 200x200 quads.
- The other 3 are new images from the same two suites.
- The prediction scores only `must_not_move` (the 489). The `[job.arms]` verdict is the
  record.

### DOA's own shaders, regenerated on the host (the lit share for gate 4)

`gendoa.c` + `build_gendoa.sh`: read lane.local's pull of P1's cold DOA
`shader_module_keys.bin` (131 raw `ShaderModuleCacheKey`s of 2,352 bytes; x86-64 and aarch64
agree on the layout) and regenerate every module with a given tree's generator.
- **Against P1's build (cf5144dddb):** all 44 vertex and 2 geometry modules are
  **byte-identical** to the device's `spv_cache` SPIR-V, including all 21 lit ones.
  - The 62 fragment modules differ (psh_differ's shim).
  - No file name matches, although the device names files by XXH3 of the GLSL. The SPIR-V
    identity is the stronger check. The name mismatch is not chased.
- **Master (bf1ecde346) against this branch:** exactly the 18 lit modules that carry the
  helpers change. Everything else is byte-identical, including master's newer `geom.c` on
  DOA's two geometry states.
- **Timed** with `doa_manifest.py` (VS + DOA's triangle GS + one DOA FS) on turnipcost569's
  harness, 5 interleaved reps, load ~1-3. Then `doa_share.py`:

| | A (master) | B (B1) | A/B |
|---|---|---|---|
| the 18 lit pipelines, each | 534-1558 ms | 224-338 ms | **2.18-4.96x** |
| their VS stage, each | 310-1187 ms | 61-114 ms | |
| 26 unchanged pipelines (A/A) | | | 0.93-1.13x |
| sum over 44 modules: pipeline | 20.7 s | 8.8 s | **2.36x** |
| sum over 44 modules: VS stage | 11.9 s | 1.9 s | **6.26x** |

- **Lit share, each module weighted once:** 81% of DOA's pipeline compile time and 96.7% of its
  VS stage time.
- The keys list modules, not how many pipelines used each module. The device leg settles the
  weighting.
- DOA's lit shaders gain more than the catalogue's (2.5-2.7x). Their A-side VS stages are
  larger, up to 1.19 s against the catalogue's 0.8-1.3 s pipelines.

### Gate 4: registered before any run

`docs/testing/predictions/litcompile569-doa-soak.json`, 04:43Z. Judge:
`doa_soak_judge.py <base> <fix>`.
- It was written before either arm ran.
- It was self-checked with P1's run as both arms: L3 passes, and L1, L2 and L4 fail, as a
  no-change pair must. It reproduces fbwin's 8,277 ms load.
- Its GPU leg was checked on a fixture (5.0 against 4.0 ms reads -20%).

The run: cold DOA survey soak, Nova, 440 s, `--perflog` (the only build that prints
`xemu-gpu` frame times; `[shd413]` is in every Android build). Base is master bf1ecde346,
queued first; fix is 87ceac5569.

**Model:** fix create time = base create time - (1 - 1/6.26) x base VS stage time.
- **L1:** whole run, per create, within 30%.
- **L2:** the fight load, within 30%.
- **L3:** gs/fs per create unchanged (0.75-1.33).
- **L4:** VS per create falls 4.8-8.1x.
- **E:** GPU `Tot` ms per frame in play windows with no misses. Expected within ±10%;
  `j_per_frame` is read beside it.

### State at the end of session 2 (2026-09-28 ~22:10 PDT)

- **Gates 1, 2, 2b and 3 are done.** 3 is `ab_compare` PASS, 489/489 on the host. CI is green
  on 3b151aeb2b. PR #580 is marked ready. The `[job.arms]` comment had not posted: the arms
  job's last tick was 19:39 PDT.
- **Gate 4 is queued** on the Nova, plain priority, 54th-55th of 59:
  - base `1790657057-litcompile569-206765`;
  - fix `1790657061-litcompile569-206870`.
- **When both are DONE:**
  1. Run `title_verdict.py` on a COPY of each result dir.
  2. Run `doa_soak_judge.py <base> <fix>`. Add `--base-span`/`--fix-span` from each arm's
     route frames if fbwin's rule finds no fight load.
  3. Post the legs on #569 as their own post, with GPU ms per frame and `j_per_frame`.
- If the thermal gate voids the pair, re-run it from a cool start.

## 7. Session 3 (2026-09-29, attempt 3): gate 4 read

### Why session 2 did not finish

It did not fail. It ended on purpose, waiting on the gate-4 soak pair, which was queued 54th-55th
of 59 on the Nova. PR #580 (gates 1-3) was marked ready and folded in the meantime. The pair
finished DONE, and `handback.sh` resumed the lane to read it. This session carries gate 4 on a
new PR.

## 5. For the next lane

- **Gate 4 (device) waits on P1** (PR #574, lane.shaderfb569: `dpc_ms` per stage). The leg
  is: the fight load's `dpc_ms` falls by (2.5-2.7x factor) x (the lit share of the stall),
  within 30%. The lit share is lane.local's, from the DOA shader-key pull.
- **Do not write `a ? f(x) : y` or `a && (b == c)` in a generated helper.** glslang branches on
  both. Use `mix()` and named bools.
- **B2 (`geom.c`'s wedge) is now the larger per-pipeline cost** on a lit pipeline too: ~150 ms
  of a ~500 ms lit pipeline.
