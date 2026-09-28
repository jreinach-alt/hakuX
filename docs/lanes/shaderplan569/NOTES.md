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

## 4. Independent review: an Adreno/Turnip driver engineer

A subagent was briefed as a Snapdragon/Adreno driver engineer (Turnip/ir3 and Qualcomm's
driver). It got the measured facts (the 13.8 / 14.8 / 15.2 s stalls, dsm ~ dpm, upper-bound
prices, the three caches, the async setting) and the code paths, and not this lane's
conclusions. Its web access failed (Bash and WebSearch denied; gitlab.freedesktop.org
bot-walled), so it tagged every Turnip/ir3 statement **(B, unverified)**. The one URL it relied
on: https://docs.mesa3d.org/drivers/freedreno.html (the `TU_DEBUG` / `IR3_SHADER_DEBUG` option
names). Its findings, condensed, each with this lane's verdict:

| # | finding | verdict |
|---|---|---|
| R1 | **Measure per phase before building.** Timers around GLSL gen, glslang, SPIR-V write; chain `VkPipelineCreationFeedback` (core 1.3) into `vkCreateGraphicsPipelines` for per-stage driver time and the cache-hit bit; `IR3_SHADER_DEBUG=disasm` for instruction counts and private-memory use | **Agree.** Feedback is a better instrument than pipeline413 §9's clock pair: it separates a Turnip cache hit from a compile with no guesswork. |
| R1' | "ir3 should take 2-10 ms per fragment shader, 10-50 ms per vertex shader; the measured stall is 10-100x that, so look at glslang, fsync, whole-cache saves, or non-shader work" | **Disagree with the conclusion, agree with the surprise.** doa413c already profiled the stall: 96% of the PFIFO thread is inside Turnip (`tu_spirv_to_nir` 65%, `tu_shader_create` 21%, `link_opts` 10%), and glslang is 63 samples of 13,230. So the time IS in Turnip. If the expert's per-shader expectation is right, what that says is that **our generated shaders are pathological for NIR/ir3**, not that the time is elsewhere. That makes "why is one shader ~400 ms in Turnip" the most valuable unknown on the path (plan item P2). |
| R2 | Worker pool of 3-4 on cpu3-6 (A715/A710; keep cpu7 for the vCPU, avoid the in-order A510s), pipeline jobs ahead of module jobs, a condvar instead of the `usleep(100)` spin, `wait_idle` counting completions (it counts dequeues: `compile_worker.c:164`, `:218`, read) | **Agree**, with the thermal caveat it names: the Thor pauses cpu3-7 when hot (#507), so the pool must not assume those cores exist. |
| R3 | Take disk I/O off the compile path: `g_file_set_contents` per SPIR-V miss (`vk/glsl.c:438`), fopen/fclose per key (`vk/shaders.c:1058`), whole-cache serialise on the draw thread every 30 s (`vk/draw.c:1498-1511`) | **Agree, small.** Bounded by doa413c: all of libxemu's own samples in the stall are under 3%. Worth doing inside the pool change, not as its own lane. |
| R4 | glslang `validate=false` in release; measure `disable_optimizer` | **Agree it is cheap; disagree it matters for the stall** (<1% share, above). The optimizer question is really about Turnip's input: smaller, pre-optimised SPIR-V may make `tu_spirv_to_nir` cheaper. Fold into P2's measurement. |
| R5 | Keep `spv_cache/` and `shader_module_keys.bin` across a driver change (SPIR-V is driver-independent; `renderer.c:125-146` wipes all three, read); persist **pipeline** keys and pre-build pipelines in the background at boot | **Agree strongly.** This is the plan's P3. The expert found the second wipe path (driver identity) that this lane's brief did not name; the brief's (`dispatcher.sh:296-331`) is the test harness's. |
| R6 | `VK_EXT_graphics_pipeline_library` with four libraries, fast link without LTO, optional LTO swap in the background; needs one fixed pipeline layout with `INDEPENDENT_SETS` (today a layout is created per miss, sized by the uniform-attribute count: `vk/draw.c:2750-2768`, read) | **Agree, and the size of the win hangs on one unverified driver fact.** dsm/dpm of 0.73-1.0 means a missed pipeline brings about ONE new module; its other one or two stages already exist. If Turnip recompiles an unchanged stage whenever its partner changes (the expert's (B) claim: monolithic stage keys hash the whole pipeline), GPL removes 1/2 to 2/3 of each miss's ir3 work. If Turnip already caches stages independently, GPL removes nearly nothing. `VkPipelineCreationFeedback`'s per-stage cache-hit bit (R1) decides it on the first run, so P1 carries it and GPL is ranked after that reading. |
| R7 | More dynamic state (topology class, polygon mode, vertex input), load ops out of the key | **Agree it is low value for the cold stall:** the misses are new shaders. |
| R8 | `VK_EXT_shader_object`: check `vulkaninfo`; bigger rewrite than GPL; more draw-time CPU | **Agree.** PFIFO is the busy thread at play time (48%, `docs/investigations/frame-pacing-and-parallelism.md:97-105`), so more draw-time CPU is the wrong trade. |
| R9 | Move data-only fields out of `ShaderState` into uniforms | **Agree as a direction.** This lane found the float fields (`point_size`, `point_params`, `aa_offset_x`, `border_*`); none is shown to split DOA's keys. A key-diff counter (P1) is what would show it. |
| R10 | The 192-`vec4` local copy for constant-writing vertex programs (`glsl/vsh-prog.c:866-875`) forces private memory in ir3 | **Agree it is costly, disagree it is DOA's cause:** the copy is emitted only for programs that write a constant (#233; read at `:855-870`), which is rare. Check it in P2's disasm. |
| R11 | Ubershader as a fallback only; fragment side 3-6x ALU, vertex interpreter 10x+ (estimates) | **Agree**, see option (d). |
| R12 | Qualcomm's compiler is slower to compile than ir3 (B) | **Unverified.** Not needed for the plan. |

The expert also pointed at a zero-rebuild lever this lane had not: the `env_vars` preference is
`setenv`'d at startup (`xemu_android.cpp:796-806`, read), so `IR3_SHADER_DEBUG`, `TU_DEBUG` and
`MESA_SHADER_CACHE_DIR` can be set for a run without a new apk.

## 5. Options

Bounds are from pipeline413 §7-8 (upper bounds, excess / miss) and doa413c's cold/warm pair.
"Excess" per event: title-stage load 10.8-11.6 s (24-26 misses), menu -> fight load <= 14.8 s
(19 misses), mid-fight hitch <= 9.9 s (8 misses). Holders are from `origin/board:territory.toml`
(wave 277): `vk/draw.c` lane.pacing (after lane.forza414 released it); `vk/shaders.c`,
`vk/renderer.c`, `vk/renderer.h` lane.forza414; `hw/xbox/nv2a/debug.h` lane.remote;
`xemu_android.cpp` lines 955-965 and `SettingsActivity.kt` lent to lane.async413;
`vk/compile_worker.c`, `vk/glsl.c`, `pgraph/profile.c`, `glsl/psh.c`, `glsl/vsh-prog.c`
unclaimed; `vk/instance.c`, `glsl/vsh.c`, `glsl/vsh-ff.c`, `glsl/geom.c` in `[free]`.

**Idle capacity, what is known.** Gameplay thread loads: vCPU ~85%, PFIFO ~48%, render ~4%,
compile worker "small" (`docs/investigations/frame-pacing-and-parallelism.md:97-105`; that table
cites no result dir, so treat it as indicative). In DOA's cold stall: PFIFO 96.7-98.1% on-CPU,
vCPU 78-99% but 91% of it the guest's idle loop, every other thread under 10% (doa413c
NOTES:151-159, 192). So during a stall about two cores are busy, one of them doing nothing
useful, and five to six are idle [inferred: 8 cores minus the threads measured busy]. Where the
idle ones are: on the Thor, fast records put the vCPU on cpu7 92-99% and the other emulator
threads on cpu3-6 (gta482 NOTES:336-341); per-core busy % during play is **unmeasured** for
both handhelds. Constraint: the Thor's thermal mitigation pauses cpu3-7 a few minutes into a MAX
run (#507; gta482 NOTES:400-437), so a pool must work on cpu0-2 as well.

| | what | bound (DOA, per event) | visual effect | files (holder) | effort / risk |
|---|---|---|---|---|---|
| **(a) parallel compile on idle cores** | a pool of 3-4 workers, pipeline jobs first, condvar not spin, `wait_idle` counting completions | today, sync mode compiles on demand, one at a time, so a pool alone saves **~0**: nothing asks for the second pipeline until the first is built. With something that submits misses early ((b), (c), or a non-blocking pending path), it saves <= excess x (1 - 1/N): **8.7 / 11.1 / 7.4 s at N=4** (pipeline413 §8) | none by itself | `compile_worker.c` (unclaimed), `renderer.h` (forza414), `draw.c:4342-4352` (pacing) | small / low; thermal on the Thor |
| **(b) predictive compile** | compile a key before the draw that needs it | lead time from state writes alone is **near zero**: NV2A state methods sit just before their draw in the same pushbuffer run. The only lead is pushbuffer the puller has not reached: during DOA's stall a submission waited up to 425-444 ms from publication to consumption (`fifoskew` drain max, doa413c NOTES:64-68, :188). A lookahead that decodes that backlog into a shadow register file could find the next draws' keys and feed (a). Bound = (a)'s, only for misses inside the backlog; the backlog's draw count is unmeasured | none | `pfifo.c`/`pgraph.c` (a shadow decoder), `compile_worker.c`, the key builders in `glsl/*.c` | high / medium: a second decoder of every state method is a second copy that can drift from the first |
| **(c) warm pipelines, not modules; per-title key sets** | persist **pipeline** keys; at boot, build them on the pool into the VkPipelineCache in the background; keep `spv_cache/` and the key files across a driver change (`renderer.c:125-146` wipes them); save the pipeline cache from the worker and on pause, not only at teardown; optionally ship per-title key sets built from our own soaks | a replay of something already seen: **the load drops to its warm floor**. doa413c: 12.9 s cold vs 3.1 s warm, ~9.8 s saved on that load. First-ever sight of a shader: **0** | none | `shaders.c`, `renderer.c`, `renderer.h` (forza414), `draw.c` (pacing), `compile_worker.c` | medium / low; a pipeline key holds `VkRenderPass` handles, rebuilt from `RenderPassState` at boot |
| **(d) ubershader (Dolphin hybrid)** | an interpreter vertex + fragment shader driven by uniforms, drawn while the specialised pipeline compiles, then swapped | removes the whole excess on a cold cache, the only option that does so **with no dropped draw**: <= 10.8 / 14.8 / 9.9 s | none if exact; any divergence from the specialised shader shows as a pop when it swaps in | a new generator next to `glsl/psh.c` (4,610 lines of specialised semantics to mirror) and `glsl/vsh-prog.c`; `draw.c` (pacing) | **very high** / high: exactness against the goldens is the whole difficulty. Fps cost on the Adreno 740 is an estimate: fragment 3-6x ALU plus register pressure (expert R11, (C)); at the NV2A's 640x480 the A740 has room [inferred, unmeasured] |
| **(e) fewer pipelines** | GPL (four libraries, fast link), more dynamic state, one pipeline layout, dedup float fields out of the key | dedup: <= (dpm - dsm) x cost = **1.5 s / 0 / 0** (pipeline413 §8). GPL: 1/2-2/3 of each miss's ir3 work **if** Turnip recompiles unchanged partner stages (unverified; P1 decides) | none (fast-linked pipelines may run marginally slower until an LTO swap) | `draw.c` (pacing), `compile_worker.c`, `instance.c` (free), `shaders.c` (forza414) | GPL high / medium; dynamic state low / low |
| **(f) skip while compiling (the setting)** | as built: skips only while the cheap half runs, then waits on the Turnip half | as built: **<= ~1% of the stall** (glslang's share, doa413c). Extended to skip a pending *pipeline* too: <= the whole excess | missing geometry for the frames each compile takes (x 400-1240 ms per pipeline, upper bounds); whether any stays missing is section 6 | `draw.c` (pacing), `compile_worker.c` | small / the visual cost is the owner's decision |
| **(g) per-title** | per-title key sets (part of (c)); per-title `async_compile` already exists (`PerGameSettingsActivity.kt:104`) | as (c) / (f), per title | as (c) / (f) | as (c) | the general fixes above cover every title; per-title only for titles where (f)'s cost is shown invisible |
| **(h) cheaper shaders** (not in the brief; from section 2 and R1') | find why one shader costs ~400 ms in Turnip, then change the GLSL generators so Turnip's NIR passes do less | **scales every other bound**: the excess is linear in per-shader cost (pipeline413 §8 row 4). A 4x cheaper shader takes the fight load's <= 14.8 s to <= 3.7 s, with no other change | none if the generated code is equivalent (the goldens check it) | `glsl/psh.c`, `glsl/vsh-prog.c` (unclaimed), `glsl/vsh.c`, `vsh-ff.c`, `geom.c` (free), `vk/glsl.c` | unknown until measured / low for pixels (goldens) |

## 6. The visual-cost question: "permanently missing textures"

**Where the claim comes from.** `git blame` puts the comment at `vk/draw.c:4343-4348` in
9a138b24a2 (rfandango, 2026-04-08), a commit titled "android: remove Rust/Cargo dependency for
XISO converter". The same commit split the async path: before it, a pending pipeline was skipped
like a pending module; after it, a pending pipeline is waited for. The commit message does not
mention the change, and nothing in the commit (no test, no log, no capture) measures the
missing-texture case. It is a claim carried by a comment.

TODO: upstream, mechanism, async413.
