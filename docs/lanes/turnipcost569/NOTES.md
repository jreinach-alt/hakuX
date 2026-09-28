# lane.turnipcost569 -- why one shader costs ~400 ms in Turnip, measured offline (#569 P2 phase A)

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

## 1. Build recipe

(filled in after the runs)
