# lane.shaderfb569 -- #569 P1: measure the pipeline create call, per stage

Base master 01e62d8d1c. Plan: `docs/lanes/shaderplan569/NOTES.md` §7 P1 (PR #570). PR #574.

## 1. The instrument (a073e39676, 84c865c37d)

Every graphics pipeline create now goes through `pgraph_vk_create_graphics_pipeline_fb()`
(`vk/compile_worker.c`, outside the `OPT_ASYNC_COMPILE` block). That covers the sync draw path
(`vk/draw.c`, `create_pipeline`), the clear path (`create_clear_pipeline`) and the async worker
(`process_pipeline_job`). The wrapper:

- times the call with `nv2a_clock_ns()`, giving `pipeline_create_us`, pipeline413 §9's
  accumulator;
- on a device reporting Vulkan >= 1.3, chains `VkPipelineCreationFeedbackCreateInfo` (core
  1.3, no feature bit) in front of the caller's `pNext`, and accumulates the whole-pipeline
  duration, the whole-pipeline cache hit, and the duration of each stage (vs/gs/fs);
- for draw pipelines (not clears, whose built-in modules are always "reused"), splits the
  stages by whether an earlier pipeline had already used the stage's `VkShaderModule`. For each
  side it counts the stages, the stages without `APPLICATION_PIPELINE_CACHE_HIT`, and their
  duration. That is C3, with a duration cross-check: a reported miss that costs ~0 ms is not a
  real recompile.

Module handles are remembered by value in a hash set and never forgotten. A module freed and
replaced by a new one with the same handle therefore reads as reused. Shader-module eviction is
rare enough that this is noise.

Also:
- `vk/glsl.c`: `glslang_us` around both `pgraph_vk_compile_glsl_to_spv` calls, and
  `shader_module_us` around the whole GLSL -> `VkShaderModule` (SPIR-V cache load and store,
  module creation, reflection). Both run on a module miss only.
- `vk/draw.c`: `plc_save_us` around `save_pipeline_cache_to_disk`.
- **Key-diff classes** (`nv2a_profile_shader_keydiff`, `pgraph/profile.c`). On a sync draw miss,
  just before the create, the new key's `ShaderState` is compared with the `ShaderState` of the
  pipeline bound before, as a class bitmask:
  - VP: vertex program words, or programmable <-> ff;
  - FF: fixed-function vsh, plus the vsh fields both paths share (lighting, material sources,
    fog, attrs);
  - CB: combiner stages and the final combiner;
  - TX: psh texture fields, the stage program included;
  - FL: floats (point size and params, aa offset, border sizes);
  - PO: the rest of `PshState`;
  - GE: `GeomState`;
  - NONE: identical, i.e. a miss on a non-shader field;
  - NOPREV: no comparable previous binding (none, the same node, or a clear pipeline).

  **Deviation from the brief:** the brief says "for each shader-cache miss". The only lent draw.c
  hunks are the create sites, and a shader-cache miss happens in `vk/shaders.c` (not lent). So
  this counts per pipeline miss. pipeline413's dsm/dpm is 0.73-1.0, so the two populations
  nearly coincide, and NONE counts the pipeline misses whose shader was unchanged.
- The `[shd413]` line keeps every existing field, in order, and appends:
  `pc_ms dpc_ms dpn dfb dfbh dfb_ms dvs_ms dgs_ms dfs_ms dsru dsrum dsru_ms dsnu dsnum dsnu_ms
  dgl_ms dsmod_ms dsv_ms kd=VP/FF/CB/TX/FL/PO/GE/NONE/NOPREV dins_us`. The meaning of each is in
  the comment above the emitter. `shdwin.py` (pipeline413) still parses the line; its regex is a
  search, not anchored at the end.
- **Overhead.** Everything added is on a miss path or wraps a create call. A pipeline hit, a
  shader hit and a SPIR-V hit run no new code. The instrument times its own bookkeeping (the
  lock, the hash set, the class compare) into `instr_ns`, printed as `dins_us`. So the brief's
  "a few clock reads per miss" is measured by leg O, not asserted.

`debug.h`: fields added to `ShaderPipelineStats` only. `vk/draw.c`: the two create sites, the
`save_pipeline_cache_to_disk` body, and two prototypes above it (the lent hunk). Nothing else.

### Checks run (no device)

- `syncheck.py`: `-fsyntax-only` on the four C files with the NDK clang and an arm64 release
  build's flags (`/home/justin/hakuX/android/app/.cxx/Release/135r5t6d/arm64-v8a`, `__ANDROID__`
  defined, so the `[shd413]` emitter and its format are checked by clang's `-Wformat`), and with
  the desktop gcc build's flags. 0 errors; every warning is in lines this lane did not touch.
- `keydiff_test.py`: builds `keydiff_test.c` against the real `ShaderState` with the classifier
  cut from `profile.c`. It has 19 cases, each changing a field in the middle of its class. PASSED.
  With `KD(TX, psh.dim_tex)` deleted, the test fails on `tex dim_tex[2]` (it lands in PO). The
  test can fail.
- `fbwin.py --selftest`: PASSED. It includes a decoy menu miss after `mark play`. With the
  quiet-run rule disabled, it fails 5 checks.
- `fbwin.py`'s fight-load rule was run on pipeline413's ring-out logcat
  (`1-1790579572-pipeline413-1715785`, padded with zero #569 fields). It picks 09:37:30-09:37:49:
  5 windows, dpm 19, own excess 14,932 ms. That is the span pipeline413 read from the frames
  (black screen -> `GET READY`, 19 misses, 14.8 s). A first rule ("first miss after `mark play`")
  picked the post-title menu miss at 09:37:00 and was replaced before registering.

## 2. Predictions (registered 2026-09-28, before any run)

- `docs/testing/predictions/shaderfb569-pixels-inert.json` (sha256 `e61d09cd5a0c...`): a
  01e62d8d1c, b 84c865c37d. The must-not-move set is the eight-suite set tbchurn424 used. The
  arms job queues it; its verdict comes back as a `[job.arms]` comment.
- `docs/testing/predictions/shaderfb569-doa-feedback.json` (sha256 `50023759ac46...`): the
  one-arm soak on cf5144dddb (the same hw/ as 84c865c37d, plus the reader). It uses a different
  ref from the arms' B, so its apk is not the one the arms may run first, and the dispatcher
  clears the shader cache for it. Legs: M0, C1 (vs 14.8 s) and C1' (vs this run's own excess),
  C2, C3 (with the duration cross-check), C4, and O (< 100 us of instrument time per create).

## 3. Runs

| id | what | state |
|---|---|---|
| `1790621694-shaderfb569-1529058` | cf5144dddb, Nova, DOA, survey, 440 s, cold | queued 2026-09-28 18:5xZ. The Nova is on its battery hold (lifts at >= 80%, after the owner's ~18:00 PDT top-up) |
| arms pair (arms job) | 01e62d8d1c vs 84c865c37d, 8 suites | queued by the arms job from the committed prediction |

**After the soak:** file a board request asking lane.local to pull the Nova's `files/spv_cache/`
(via `run-as`) for lane.turnipcost569 (P2).

## 4. Result

Pending.

## Do not repeat

- Do not define the fight load as "the first miss after `mark play`". On the survey route, the
  menus after the DOA2U title miss first (09:37:00 in pipeline413's run).
- `ab_compare --register` asks for the file to be committed before the arms land. The soak
  prediction is hand-written (a_ref == b_ref; the arms job skips it), so it is queued with
  `request.sh --expect`.
