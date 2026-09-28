# lane.shaderplan569 -- #569: shader compile stalls, research and a ranked plan

Base master 01e62d8d1c. Analysis only: no code, no board files, no device runs. Draft in
progress; sections marked TODO are waiting on the research agents.

## 2. hakuX's path for a new combination (read from the code at 01e62d8d1c)

Default mode: `async_compile` off (`SettingsActivity.kt:69`, `xemu_android.cpp:959`).

| step | where | thread | parallel? | cost |
|---|---|---|---|---|
| 1. ShaderState build + dirty check | `glsl/psh.c`, `glsl/vsh.c` state fill; `pgraph_vk_bind_shaders` (`vk/shaders.c:1437`) | PFIFO | no | unmeasured; per draw only when a watched register moved |
| 2. ShaderState hash, LRU lookup | `pgraph_glsl_hash_shader_state` (`vk/shaders.c:1263`), `fast_hash` | PFIFO | no | unmeasured, small (a hash of one struct) |
| 3. module key hash, LRU lookup | `hash_shader_module_key` (`vk/shaders.c:770`) | PFIFO | no | as 2 |
| 4. GLSL text generation | `pgraph_glsl_gen_vsh/psh/geom` via `shader_module_compile_sync` (`vk/shaders.c:1066`) | PFIFO (async: the one worker) | no | unmeasured; runs even on a SPIR-V cache hit, because the SPIR-V cache is keyed on the GLSL text's hash (`vk/glsl.c:450`) |
| 5. GLSL -> SPIR-V (glslang, `validate=true`, optimizer at its default) | `pgraph_vk_compile_glsl_to_spv` (`vk/glsl.c:195`), skipped on a `spv_cache/<hash>.spv` hit | PFIFO (async: the worker) | no | **bounded: under 1%** of the stalled PFIFO thread. doa413c s3 record: 63 samples reach glslang out of 13,230 (`docs/lanes/doa413c/NOTES.md:195-203`) |
| 6. `vkCreateShaderModule` + SPIR-V reflection | `vk/glsl.c:285`, `:343` | PFIFO (async: the worker) | no | inside the same <1% [inferred: Turnip does no compile at module creation] |
| 7. pipeline key build + hash + LRU | `init_pipeline_key`, `fast_hash` (`vk/draw.c:2267-2281`) | PFIFO | no | unmeasured, small |
| 8. `vkCreatePipelineLayout` | `vk/draw.c:2767` | PFIFO | no | unmeasured; one per pipeline miss, never cached [read] |
| 9. **`vkCreateGraphicsPipelines`: Turnip SPIR-V -> NIR -> ir3** | `vk/draw.c:2837` sync; `compile_worker.c:131` async | PFIFO (async: the worker, with PFIFO spinning in `g_usleep(100)` at `vk/draw.c:4349`) | no | **measured share: 96% of a thread 97-98% on-CPU** during the cold stall (`tu_spirv_to_nir` 65%, `tu_shader_create` 21%, `link_opts` 10%; doa413c NOTES:195-199). **Per pipeline: upper bounds only**, 414-485 ms (title-stage load), <= 780 ms (fight load), <= 1.24 s (mid-fight) (pipeline413 NOTES:168-175). Wall ms inside the call: **unmeasured** (pipeline413 §9) |
| 10. pipeline cache save | `maybe_save_pipeline_cache` (`vk/draw.c:1500`): `vkGetPipelineCacheData` + write the whole file, at most once per 30 s, on the PFIFO thread after a sync miss | PFIFO | no | unmeasured |
| 11. module key persist | `shader_module_key_persist` (`vk/shaders.c:1049`): open, append one key, close | PFIFO / worker | no | unmeasured, small |

What nothing measures: steps 1-4, 7, 8, 10 individually; the wall ms of step 9 per pipeline; the
SPIR-V size of the shaders that cost 0.4-1.2 s; which key fields differ between a missed key and
its nearest cached neighbour.

### Readings from the code that matter for the plan

- **One compile worker.** `compile_worker.c:199` starts one `pgraph.vk.compile` thread. It is
  used only in async mode. Nothing pins it; `XEMU_OPT_THREAD_AFFINITY` is 0 by default
  (`pfifo.c:32-33`, `xemu_android.cpp:1024-1025`), so no hakuX thread is pinned.
- **The startup warm-up warms the cheap half.** `shader_cache_init` (`vk/shaders.c:1204-1236`)
  replays `shader_module_keys.bin` into the module LRU: GLSL + glslang + `vkCreateShaderModule`,
  steps 4-6, <1% of the stall. It creates no pipeline, so step 9, the 96%, still happens at the
  first draw unless `vk_pipeline_cache.bin` already holds that pipeline's ir3 binaries. With async
  off, the warm-up runs synchronously on the init thread (the LRU init hook compiles inline), and
  `wait_idle` sees an empty queue.
- **Async mode never saves the pipeline cache during play.** The worker's `process_pipeline_job`
  (`compile_worker.c:63-142`) does not call `maybe_save_pipeline_cache`; only the sync path does
  (`vk/draw.c:2848`, `:2043`). The only other save is `finalize_pipeline_cache` at renderer
  teardown (`vk/draw.c:1514`). Whether teardown runs before `SDL_main`'s `_exit`
  (`xemu_android.cpp:1387`), and whether it runs at all when Android kills the process, is **not
  read here**. If it does not, an async user's ir3 work is never kept.
- **Async mode as built does not take the 96% off the draw path.** A draw whose modules are
  pending is skipped (`vk/draw.c:4333-4341`); the pipeline job is enqueued only once the modules
  are ready (`vk/draw.c:2313-2319`); the next draw then waits for it (`:4342-4351`). doa413c
  NOTES:311-315 reached the same reading. lane.async413 (PR #567) registered it as leg M before
  any run; no result yet.
- **Both caches are keyed on everything that can change a shader.** `ProgrammableVshState` holds
  the whole vertex program (`glsl/vsh.h:36-39`), `PshState` all 8 combiner stages
  (`glsl/psh.h:38-132`). A few floats ride the keys too (`point_size`, `point_params` when
  enabled, `aa_offset_x`, and `border_*_size` for border-source textures only;
  `glsl/vsh.c:116-125`, `glsl/psh.c:491-527`). Whether any of them splits DOA's keys is
  unmeasured: pipeline413's dsm/dpm of 0.73-1.0 says the misses are new *shaders*, not new
  blend/depth combinations.

## 3. Known issues and fixes (sweep)

TODO: table from the sweep.

## 6. The visual-cost question: "permanently missing textures"

**Where the claim comes from.** `git blame` puts the comment at `vk/draw.c:4343-4348` in
9a138b24a2 (rfandango, 2026-04-08), a commit titled "android: remove Rust/Cargo dependency for
XISO converter". The same commit split the async path: before it, a pending pipeline was skipped
like a pending module; after it, a pending pipeline is waited for. The commit message does not
mention the change, and nothing in the commit (no test, no log, no capture) measures the
missing-texture case. It is a claim carried by a comment.

TODO: upstream, mechanism, async413.
