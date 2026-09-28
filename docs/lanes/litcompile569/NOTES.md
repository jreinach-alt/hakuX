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

## 5. For the next lane

- **Gate 4 (device) waits on P1** (PR #574, lane.shaderfb569: `dpc_ms` per stage). The leg
  is: the fight load's `dpc_ms` falls by (2.5-2.7x factor) x (the lit share of the stall),
  within 30%. The lit share is lane.local's, from the DOA shader-key pull.
- **Do not write `a ? f(x) : y` or `a && (b == c)` in a generated helper.** glslang branches on
  both. Use `mix()` and named bools.
- **B2 (`geom.c`'s wedge) is now the larger per-pipeline cost** on a lit pipeline too: ~150 ms
  of a ~500 ms lit pipeline.
