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
new PR (#607).

### Gate 4: the pair

The pair: base `0-0-x-0-1790657057-litcompile569-206765` (bf1ecde346) and fix
`...-1790657061-litcompile569-206870` (87ceac5569). Nova, 440 s, perflog, MAX regimen, battery
39% at start.
- **Both arms were cold** (shader cache cleared) and never thermally paused. The GPU clock was
  615-680 MHz in both, median 680, with no throttling.
- **The route drew different fights.** Both arms picked Kasumi in Story mode.
  - Base fought Bayman, lost, and continued.
  - Fix fought Helena, then Lei Fang.
  - Both arms reached the fight during the menu presses, so `mark play` (at 23:41:54 on base,
    00:46:45 on fix) falls mid-fight. fbwin's rule places no fight load on either arm.
- **Creates:** 155 on base and 110 on fix (-29%). That is outside V's ±25%, so the per-create
  legs stand and the totals are reported only.
- **The fix arm's adb link dropped at 00:48:51,** 60 s before its end, at 36% battery (the
  known Nova link drop). All the compile data is before the drop. `title_verdict.py` voids
  the arm ("not-foreground: unreadable"), so the fix has no j_per_frame from it.

`doa_soak_judge.py` (registered legs):

| leg | reading | verdict |
|---|---|---|
| L1 (whole run, per create) | fix 180.9 ms/create against model 155.4 (base 359.1): ratio 1.16; base/fix **1.98x** | PASS |
| L2 (fight load, placed from the frames) | base 23:40:03-:23 (character select -> Bayman intro -> GET READY) 7,987 ms; fix 00:44:38-:56 (select -> intro -> fight) 4,855 ms; model 3,786: ratio **1.28** | PASS, on the line |
| L2, narrower placement (to :20 / :52) | 7,045 against 4,455, model 3,348: ratio 1.33 | FAIL |
| L3 (gs, fs per create) | 1.12, 1.12 | PASS |
| L4 (VS per create, 4.8-8.1x) | **3.48x** | FAIL |
| E (GPU Tot ms/frame, play, dpm == 0) | 26.8 -> 21.2 (-20.9%) | falls: see below |

- **L2 is not decided by this pair.** The two loads fetch different fighters (Bayman against
  Helena). Where the span ends moves the ratio across the 1.30 bound.
- **The matched read replaces it** (`doa_matched.py`, written after the run). It pairs the
  windows whose `kd` vector and create count are the same in both arms, i.e. the same load:

| | base | fix | base/fix |
|---|---|---|---|
| 15 matched windows, 72 creates each (base 72 of 155, fix 72 of 110) | | | |
| pipeline create ms | 25,758 | 12,029 | **2.14x** |
| the model's fix (base - 0.840 x base VS) | | 12,086 | **fix/model 1.00** |
| VS stage ms | 16,271 | 3,957 | **4.11x** |
| GS stage ms | 5,722 | 5,661 | 0.99 |
| the title-to-menu load (26 creates) | 12,233 | 4,903 | 2.49x (VS 4.55x) |
| unlit windows (boot 12 creates, 1-create unlit) | 1,205 / 126 / 150 | 1,203 / 125 / 150 | 1.00 |

- **On the same content, the registered model predicts the fix's create time exactly (1.00).**
  B1 halves DOA's pipeline creation time on the device: 2.14x on matched loads, 1.98x per create
  over the run.
- **L4 fails anyway: the device's VS stage gains 4.1x, not the host's 6.3x.** The pipeline
  total still meets the model because the time outside the three stages also shrank. Over the
  matched creates, dpc - (vs + gs + fs) is about 3.8 s on base and 2.4 s on fix. The feedback
  API's stage split is not the host's split. The registered text named only the other failure
  (L4 pass, L1 fail). This one is not a gap outside the VS stage; it is how the stage time is
  attributed.

### E: GPU time per frame, fps and energy (the addendum)

`doa_energy.py` / `doa_gpu_segments.py` (written after the run). Scenes are placed from the
route frames, and only windows with no pipeline miss are counted:

| scene | fps base -> fix | GPU ms/frame | net W (batt + USB) | J/frame |
|---|---|---|---|---|
| menus (profile -> character select; same content in both arms) | 58.3 -> 60.0 (at the cap) | 14.7 -> 10.9 (**0.74**) | 8.46 -> 7.39 (1 sample each) | 0.145 -> 0.123 (0.85) |
| first fight (Bayman / Helena, same stage, pause menus included) | 34.7 -> 44.2 (**1.27x**) | 27.4 -> 22.3 (**0.81**) | 7.41 -> 8.06 (4/4) | 0.214 -> 0.182 (**0.85**) |
| whole run to the fix's link drop | 36.6 -> 46.6 | 26.8 -> 21.4 (0.80) | 7.43 -> 8.02 | 0.203 -> 0.172 (0.85) |

- **The fight is GPU-bound in both arms:** fps is about 1000 / GPU ms (27.4 ms -> 36 fps cap,
  34.7 read; 22.3 -> 45, 44.2 read). A cut in GPU time per frame becomes frame rate.
- **The registered E reading expected ±10%.** It reads -19% to -26%: "the rewrite also cuts GPU
  time per frame and is an energy lever". Energy per frame falls 15%. Power rises, because the
  fix draws more frames per second.
- **Only `vsh-ff.c` differs between the refs** (`git diff --stat bf1ecde346 87ceac5569 -- .
  ':!docs'`).
- **Why this is not yet a claim:** it is one run per arm, and the fight is a different opponent
  in each arm. The menus are the same content, but n = 13 and 10.
- **Mechanism, host** (Turnip A740 drm-shim, `IR3_SHADER_DEBUG=vs`, gate 2's catalogue, where
  the FS keeps the lit colours):

| VS (A -> B) | instr | nops | cat0 (flow + nop) | cat2 + cat3 ALU | full regs | max_waves |
|---|---|---|---|---|---|---|
| ff_lit2 (+basic) | 4692 -> 2930 | 1584 -> 347 | 1841 -> 368 | 2608 -> 2488 | 16 -> 19 | 12 -> 10 |
| ff_skin_texgen (+basic) | 9224 -> 5101 | 3281 -> ~400 | 3825 -> 427 | 4923 -> 4539 | 24 -> 24 | 8 -> 8 |

  - B1 keeps the ALU and removes about 230-400 branch instructions and most of the scheduling
    nops.
  - Per vertex, the old forms pay a branch and its nop padding at every special case. The new
    forms select.
  - The cost is 3 more registers on `ff_lit2`.
  - A static count is not a dynamic path, so this makes the device reading plausible; it does not
    prove it.
- **DOA's own manifest cannot show this on the host.** Its pairing (one DOA FS + the triangle
  GS) reads only 2 varyings, so link-time DCE strips the lighting from the final ISA. A and B come
  out identical: 872-931 instructions, 12 regs. The compile-time gap survives because Turnip's NIR
  loop runs before the link.
- **Earlier DOA soaks with perflog** (`doa_gpu_history.py`: 22 runs, all pre-B1) are no baseline.
  Other builds and routes read 13-60 ms and 13-33 fps.

### Replication, registered before it ran

`docs/testing/predictions/litcompile569-doa-gpu-rep.json`: the same refs, order reversed (fix
first). The judge is `doa_gpu_history.py`, unchanged from the registering commit.
- **R1:** this pair's fight Tot fix/base <= 0.90 (refuted if >= 0.95).
- **R2:** fps >= 1.10.
- **R3:** pooled with gate 4's 0.82, mean <= 0.90.

### State at the end of session 3 (2026-09-29 ~01:15 PDT): waiting

- **Gate 4 is read and posted on #569.** PR #607 carries it.
- **The replication is queued on the Nova,** 53rd-54th of 57, study priority:
  - fix `1790668953-litcompile569-2678297` first;
  - base `1790668956-litcompile569-2678738` second.
- **When both are DONE:**
  1. Run `doa_gpu_history.py <base> <fix>` and score R1-R3.
  2. Name each arm's opponent from its route frames.
  3. If the pair also drew one opponent each, rerun `doa_energy.py` with scene spans from its
     frames.
  4. Post the verdict on #569 and PR #607.
  5. Mark #607 ready once CI is green.
  - If R1 is refuted, B1 is a compile-stall fix only. Say that, and drop the energy framing.

## 8. Session 4 (2026-09-29, attempt 3 resumed): the replication pair

### Why session 3 did not finish

It ended on purpose, waiting on the replication pair (section 7). The resume brief named the
gate-4 pair again, and that pair was already read. The replication came back without a scorable
fix arm:
- **The fix arm `1-1790668953-litcompile569-2678297` is VOID.** hostops voided it: the Nova's USB
  link dropped at 09:11 PDT, and the soak aborted `not-foreground` at 312 of 440 s. Battery was
  53%, so this was not the low-battery link drop.
- **The hostops re-run `1-1790698600-litcompile569-3098546` had no route:** its `route_name` and
  `route` were empty. With no input the game never reached a fight and never wrote `mark play`,
  so the judge reads 0 lines from it. It cannot be a replication arm.
- The base arm, `1-1790668956-litcompile569-2678738`, is valid: cache cleared, 447 s, no
  thermal pause, and the GPU at 615-680 MHz.

### The provisional reading (the voided arm; NOT the registered verdict)

`doa_gpu_history.py`, unchanged, run on base against the voided fix arm:

| arm | fight lines | fight Tot ms | fps | opponent (route frames) |
|---|---|---|---|---|
| base bf1ecde346 | 112 | 24.4 | 36.3 | Gen Fu |
| fix 87ceac5569 (VOID, 312 s) | 20 | 20.4 | 43.7 | Bayman |
| fix/base | | **0.84** | **1.20** | |

- **It would pass R1 (<= 0.90), R2 (>= 1.10) and R3** (pooled with gate 4's 0.82, the mean is
  0.83).
- It is not scored, for three reasons:
  - the arm is void;
  - it has exactly V's minimum of 20 fight lines;
  - the opponents differ again. Both fights are on the same stage, the clock tower.
- The fix arm's GPU clock ranged 401-680 MHz, against 615-680 on base. A lower clock slows the
  fix, so it cuts against the fix's reading, not in its favour.
- **An unregistered cross-pair match:** gate 4's base also fought Bayman (27.4 ms). Against this
  fix's Bayman fight (20.4 ms) that is 0.74. It comes from different sessions, so it is
  reported, not scored.

### State at the end of session 4: waiting

- **The fix arm is re-queued with the survey route:** `1790721747-litcompile569-271619`, Nova,
  plain tier, 30th of 33. The route text is byte-identical to the base arm's.
- **When it is DONE:** run `doa_gpu_history.py <base 2678738> <fix 271619>`, score R1-R3, name
  the opponent, post on #569 and PR #607, and mark #607 ready.
- **If it voids again,** score R1-R3 on the voided arm above as the registered V permits (it
  has 20 lines), and say so.

## 9. Session 5 (2026-09-29 16:26 PDT, attempt 4): the queue was wiped

### Why session 4 did not finish

It ended on purpose, waiting on the re-queued fix arm `1790721747-litcompile569-271619`. That
request never ran. The Nova's per-run battery admission skipped it at 35-36% (need 38.1) until
16:15 PDT. Between 16:23 and 16:26 PDT, every queued request (32 at the 16:15 recovery
manifest) and every historical result dir left `$DISPATCH_DIR/queue` and `$DISPATCH_DIR/results`.
The dispatcher log has no line for it. The hostops waiters read "not in queue/running" as
"finished" and resumed eight lanes, this one included, at 16:25-16:26. The resume brief's
table names the gate-4 pair, which section 7 had already read.

- **Lost with the wipe:** the replication base arm `1-1790668956-litcompile569-2678738` (its
  judge output survives only as a scratch reading, section 8) and the voided fix arm.
- **Not lost:** gate 4's pair. Both dirs were copied into the worktree's scratch before it was
  read, and section 7's numbers stand.

### Re-queued

The registered replication (`litcompile569-doa-gpu-rep.json`, unchanged, same refs, fix first),
both arms fresh on the Nova, survey route (text identical to gate 4's request.json):
- fix 87ceac5569: `1790724513-litcompile569-1351153`;
- base bf1ecde346: `1790724517-litcompile569-1352783`.

That is 2 x (440 + 90) s = 17.7 min of device time, inside the pilot budget. **When both are
DONE:** follow section 7's list (score R1-R3 with `doa_gpu_history.py`, name the opponents,
post on #569 and #607, mark #607 ready). Section 8's provisional 0.84 is not a pair, and is not
pooled into R3.

## 10. Session 6 (2026-09-29 17:49 PDT): the second re-queue was wiped too

### Why session 5 did not finish

It ended on purpose, waiting on the re-queued pair (section 9). Neither arm ran:
- **hostops confirmed the cause** from `dispatch/logs/dispatcher.log`. The dispatch wipe had a
  second pass.
  - `selftest.d/50-arms-requeue.sh` and `51-dispatch-hardening.sh` ran against the live
    `DISPATCH_DIR` from PR #622's branch.
  - The fix arm (`1351153`) was only ever battery-skipped on the Nova.
  - The base arm (`1352783`) was admitted on the Thor and then removed before anything
    claimed it.
- **The fix is PR #624** (lane.dispatchguard): those fragments now refuse a live
  `DISPATCH_DIR`. It folded at 2026-09-30 00:40 UTC.
- **The resume brief's table names the gate-4 pair** (`206765`, `206870`). Section 7
  already read that pair.

### Queued a third time

The pair is back in the queue, queued at 00:41 UTC (after #624 folded):
- fix 87ceac5569: `1790728885-litcompile569-2295720`, first;
- base bf1ecde346: `1790728890-litcompile569-2296232`.

Both run on the Nova, at study priority, on the survey route. The route text is
byte-identical to the replication base arm's `request.json`. I did not queue a duplicate.

Both handhelds are held for the owner's top-up (`lanelocal-topup`). The holds release
themselves, so nothing runs until the Nova is back.

**When both are DONE:** follow section 7's list. If the pair is lost a third time with #624
in, that is a different bug: report it on #607 with dispatcher.log evidence.

## 11. Session 7 (2026-10-01 21:00 PDT, attempt 2 after the suspension): the replication is read

### Why session 6 did not finish

It ended on purpose, waiting on the third re-queue (section 10). That pair ran on the Nova on
2026-09-30, fix 04:29-04:37 UTC and base 05:16-05:24 UTC. Both runs are DONE. The lane was not
resumed to read them. GitHub suspended the harness account on 2026-09-29 around 21:00 PDT, and
only the lanes named in the offline protocol ran. This session follows that protocol: there
is no PR #607 to update. The PR is `docs/lanes/litcompile569/PR.md`, and the issue post is
`OUTBOX.md`.

### The pair

- fix 87ceac5569: `1-1790728885-litcompile569-2295720`, first;
- base bf1ecde346: `1-1790728890-litcompile569-2296232`, second.

Both were copied to the worktree's scratch before reading.

### V (validity): holds

- **Both caches were cleared.** `result.json` reads `shader_cache=cleared`.
- **Neither arm paused.** No `pause` flag and no active pause cdev in either `thermal.jsonl`.
- **Both arms have enough fight lines:** 75 on base and 66 on fix, against V's minimum of 20.
- **The GPU ran at 615-680 MHz during play in both arms.** Base read 401 MHz once, at the
  idle `cool` sample before the start; it was 615-680 from then on.
- **The thermal profiles matched:** xo 31 -> 51 C on base, 31 -> 54 C on fix.
- **Both arms were on USB charge** (500 mA input) at 35-39% battery.

### The registered judge (`doa_gpu_history.py`, unchanged since 1d46b29c8f)

| arm | n | Tot ms | fps | fight lines | fight Tot ms | fight fps |
|---|---|---|---|---|---|---|
| base bf1ecde346 | 89 | 28.0 | 31.8 | 75 | 28.6 | 31.1 |
| fix 87ceac5569 | 106 | 20.4 | 39.9 | 66 | 26.4 | 35.0 |

| leg | reading | verdict |
|---|---|---|
| R1: fight Tot fix/base <= 0.90 (refuted at >= 0.95) | 26.4 / 28.6 = **0.923** | **not decided** (inside the 0.90-0.95 band) |
| R2: fight fps fix/base >= 1.10 | 35.0 / 31.1 = **1.125** | PASS |
| R3: mean of the two pairs' ratios <= 0.90 | (0.821 + 0.923) / 2 = **0.872** | PASS |

- **R1 is not refuted.** The registered text says the gate-4 0.82 "was content, not B1" only at
  >= 0.95. This pair reads 0.92, which the registration names as "not decided".

### The opponents differ again (route frames)

Each arm played two fights after `mark play`.

| | base | fix |
|---|---|---|
| fight 1 (clock tower, Kasumi) | Bass, 05:20:59-:21:40, lost -> CONTINUE | Bayman, 04:33:23-:45, lost -> title |
| fight 2 (Ryu, wooden Japanese interior) | Gen Fu, 05:23:00-:24:25 | Ayane, 04:34:45-:36:25 |

- The two arms played a different share of each fight.
  - Fix spent 22 s in fight 1 and about 100 s in fight 2.
  - Base spent about 41 s in fight 1 and 85 s in fight 2.
- The pooled fight median therefore mixes a different blend of the two scenes in each arm.
  Fight 2 is the heavier scene: 46 ms on base. Fix has 34 of its lines there, and base has 17.
- **That blend pulls the pooled ratio towards 1.** Each scene, on its own, reads lower than
  the pool.

### Per scene (`doa_gpu_segments.py` / `doa_energy.py`, spans placed from the frames, dpm == 0)

| scene | fps b -> f | GPU ms/frame b -> f | net W b -> f (samples) | J/frame b -> f |
|---|---|---|---|---|
| clock tower fight | 31.9 -> 45.1 (1.41x) | 28.6 -> 20.4 (**0.71**) | 7.88 -> 9.08 (2/1) | 0.247 -> 0.201 (**0.81**) |
| Ryu fight | 20.7 -> 33.3 (1.61x) | 46.2 -> 28.1 (**0.61**) | 6.94 -> 9.11 (3/3) | 0.335 -> 0.273 (**0.82**) |

`title_verdict.py` (on the copies) over the whole run:
- **J per frame:** 0.309 on base, 0.268 on fix (0.87).
- **fps_ok:** 0.37 on base, 0.72 on fix.
- **Net W:** 7.68 on base, 9.20 on fix.
- Both arms FAIL on `reached_gameplay: unconfirmed (generic route)` and `hang=True`. That is the
  survey route's verdict, the same for both arms. It is not a B1 effect.

- **This replicates gate 4's direction on every reading.** Both pairs, and every scene in each
  pair, read the fix faster in GPU time per frame. The readings:
  - gate 4's menus 0.74 and its fight 0.81;
  - this pair's scenes 0.71 and 0.61;
  - the pooled registered medians 0.82 and 0.92.
- **Energy per frame falls in every scene,** by 13-19%. Power rises because the fix draws more
  frames per second.
- **What is still not shown is a same-content pair.** Three pairs on the survey route have
  drawn six different fights. The registered single-pair leg R1 lands in its undecided band.
  R3 passes.
- **What the claim is now:** B1 cuts GPU time per frame in DOA's fights by roughly 10-40%,
  depending on the scene and the blend. Its sign held on every reading across two pairs. Its
  size is not pinned down. It is an energy lever as well as a compile-stall fix. That claim
  rests on R2 and R3 passing with R1 undecided, not on R1.

### State at the end of session 7: ready

- PR.md is `State: ready`. It carries gate 4 (section 7) and this replication. The branch
  changes no emulator code: B1 itself folded as #580.
- `OUTBOX.md` holds the #569 post.
- No device run is queued. A same-content pair would need a route that fixes both fighters and
  the stage, such as Versus mode. That is a new registration, and it is left to whoever picks
  up the energy question. It is not this lane's.

## 5. For the next lane

- **Do not run another survey-route pair to settle B1's GPU-per-frame size.** Three pairs drew
  six different fights. A pair that settles it fixes both fighters and the stage, and holds the
  same time in each.

- **Gate 4 (device) is read** (section 7). B1 halves DOA's pipeline creation on the Nova: 2.14x
  on matched loads, with the model at 1.00. The GPU-per-frame replication is section 11.
- **Do not write `a ? f(x) : y` or `a && (b == c)` in a generated helper.** glslang branches on
  both. Use `mix()` and named bools.
- **B2 (`geom.c`'s wedge) is now the larger per-pipeline cost** on a lit pipeline too: ~150 ms
  of a ~500 ms lit pipeline.
