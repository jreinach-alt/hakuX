# lane.shaderplan569 -- #569: shader compile stalls, research and a ranked plan

Base master 01e62d8d1c. Analysis only: no code, no board files, no device runs. Every number
names its source; **[inferred]** marks a number this lane computed or reasoned rather than read.
Web research used WebFetch only (WebSearch was denied to the research agents). Sources that
refused and were not routed around: dolphin-emu.org (403), phoronix.com (403),
gitlab.freedesktop.org (bot wall), wiki.rpcs3.net (403), yuzu-emu.org, and the yuzu mirror (451).

## 0. The owner's questions, answered

- **Does this warrant a research dispatch?** Yes. It changed the plan. The stall is not "compile"
  in general: 96% of it is Turnip's SPIR-V -> NIR -> ir3 inside `vkCreateGraphicsPipelines`, on
  the PFIFO thread, one pipeline at a time (doa413c). Three things follow:
  - The existing startup warm-up re-does the other 1%.
  - The `async_compile` setting as built still waits for the 96%.
  - Nobody knows why one of our shaders costs ~400 ms in Turnip. A driver engineer's expectation
    is 10-100x less (section 4, R1').
- **How does native hardware handle it?** It doesn't compile. A new vertex program is up to 136
  four-dword slots written through `SET_TRANSFORM_PROGRAM` (about 562 dwords for a full program),
  and a full combiner setup is about 51 dwords of register writes (section 1). The GPU executes
  that state directly. Changing it costs the game the pushbuffer bandwidth and nothing more.
- **How is hakuX different?** A modern GPU cannot execute NV2A state, so every new combination is
  translated: state -> GLSL -> SPIR-V -> Turnip NIR -> ir3 -> Adreno ISA -> pipeline, at first
  use, on the thread that feeds the GPU (section 2). The guest then waits on the GPU and idles
  (doa413c: 91% of the vCPU is the kernel idle loop). Nothing else runs: one core compiles, one
  spins on nothing, and 5-6 sit idle [inferred].
- **Known issues and fixes not yet dispatched?** Yes, several (section 3):
  - never dispatched: pipeline413 §9's create-call timer, the worker pool, pipeline (not module)
    warm-up, GPL, and the glslang and disk-I/O trims;
  - found here: async mode never saves the pipeline cache during play; the teardown save is
    probably unreachable on Android; a driver-identity change wipes driver-independent SPIR-V and
    the key list; `wait_idle` counts dequeues, not completions.
  - Upstream xemu has no async, skip or ubershader path. Issue #2631 "Async Shader" is open with
    no maintainer response.
- **Would an Adreno expert find more?** It did (section 4). The useful new items:
  - `VkPipelineCreationFeedback` as the instrument;
  - the question of whether Turnip recompiles an unchanged partner stage, which decides GPL;
  - core placement off the in-order A510s, subject to the Thor's cpu3-7 thermal pause;
  - the driver-change wipe;
  - the `env_vars` preference, which lets a run set `IR3_SHADER_DEBUG` / `TU_DEBUG` with no
    rebuild.

  One of its conclusions is contradicted by our own profile ("the time must be outside ir3"); it
  is kept and answered in the section.
- **Per-title optimisations?** Yes, in one form: per-title **shader-key sets**, learned on a
  device and shipped from our own route soaks, pre-built on idle cores while the title boots (P3).
  Per-title settings beyond that: nothing yet shows a title the general fixes would miss.
- **Pre-compile / predictive work on idle cores?** Yes; this is the top of the plan (P3).
  - The prediction that works is "what this title compiled before". It is known before the title
    boots, and DOA takes ~58 s to reach `mark booted`.
  - Pre-building DOA's 180 s route on 4 workers is <= 9-15 s [computed from upper bounds].
  - Predicting from state writes gives near-zero lead: NV2A sets state immediately before the
    draw.
- **"Don't wait for the shader" costs visual accuracy: confirmed, and is it noticeable?**
  - **Confirmed as a mechanism, unmeasured in hakuX** (section 6). Skipping a draw removes that
    geometry for every frame its compile takes (<= 0.4-1.2 s per pipeline here, upper bounds).
  - For draws that build a texture once, the loss can be permanent. Dolphin's reviewers warned of
    exactly that, and Eden, Azahar and Vita3K each exempt draws of 6 or fewer vertices from
    skipping for that reason.
  - The hakuX comment claiming it was added with no measurement.
  - Whether a player notices is what async413's V leg (frames) will show; it has not run yet (the
    Nova is on a battery hold).
  - This plan does not make skipping a default (P4 is the owner's call). The top items neither
    stall nor drop.

**Ranked plan, top:** P1 measure the create call per stage (`VkPipelineCreationFeedback`, one
cold DOA soak) -> P2 find out why a shader costs ~400 ms in Turnip, offline on the host with
Mesa's tools, then make the generators cheaper -> P3 pre-build pipelines from learned and shipped
key sets on a 3-4 worker pool while the title boots. Then P4 (bounded-wait skip, owner's
decision), P5 (GPL, gated on P1), P6 (ubershader spike). Details in section 7.

## 1. Native hardware: state, not programs

- **Vertex programs.**
  - 136 instruction slots of 16 bytes (4 dwords) each, and 192 constant registers
    (https://xboxdevwiki.net/NV2A/Vertex_Shader).
  - The upload methods are `SET_TRANSFORM_PROGRAM_LOAD` (0x1E9C) to set the slot, then
    `SET_TRANSFORM_PROGRAM` (0xB00, a 32-dword method range) for the words, and
    `SET_TRANSFORM_PROGRAM_START` (0x1EA0).
  - Constants go through `SET_TRANSFORM_CONSTANT_LOAD` (0x1EA4) and `SET_TRANSFORM_CONSTANT`
    (0xB80, 32 dwords).
  - Offsets:
    https://raw.githubusercontent.com/xemu-project/xemu/master/hw/xbox/nv2a/nv2a_regs.h. Method
    ranges:
    https://raw.githubusercontent.com/xemu-project/xemu/master/hw/xbox/nv2a/pgraph/methods.h.inc.
  - A full 136-slot program is 544 data dwords in 17 bursts, about 562 dwords with headers; a
    20-instruction program is `_LOAD` plus 3 bursts [inferred from the ranges].
- **Register combiners and texture shaders.** Plain register writes:
  - `SET_COMBINER_ALPHA_ICW` / `COLOR_ICW` / `ALPHA_OCW` / `COLOR_OCW` / `FACTOR0` / `FACTOR1`, each
    an 8-entry range for the 8 general stages;
  - `SPECULAR_FOG_CW0/1` for the final combiner, and `COMBINER_CONTROL`;
  - `SET_SHADER_STAGE_PROGRAM` selects one of 19 texture-shader modes per stage
    (https://xboxdevwiki.net/NV2A/Pixel_Combiner).

  A complete combiner program is about 51 dwords [inferred].
- **What it costs a game:** the pushbuffer words. xemu's model stores the program words into
  `program_data` and the combiner words into registers, with nothing compiled
  (https://raw.githubusercontent.com/xemu-project/xemu/master/hw/xbox/nv2a/pgraph/pgraph.c). No
  NVIDIA primary document was found. "No compile on hardware" rests on the chip's documented
  programming model as xemu implements it, and on the fact that the NV2A executes vertex-program
  microcode and combiner state directly.
- **What this means for hakuX:** games change this state freely, because it is free for them. A
  scene load that sets 20 new programs or combiner setups paid a few kilobytes on the Xbox. It
  pays 20 compiles here.

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

Sources: `origin/board:nv2a_issues.toml` (wave 277), `docs/lanes/**/NOTES.md`,
`docs/audits/`, `docs/investigations/`, upstream xemu. "Never dispatched" means that no tracker
row, territory row or open PR claims it.

| item | source | status |
|---|---|---|
| Mechanism: synchronous Turnip compile on PFIFO, ~76% of the cold stall | doa413c NOTES:221-235 (PR #536) | merged (measurement) |
| `[shd413]` hit/miss instrument and the price table | pipeline413 (PR #541) | merged |
| The create-call timer (`dpc_ms`) | pipeline413 §9 | **never dispatched**. `pipeline_create_us` is absent from `hw/`. Superseded here by P1 |
| The `shader_compile` phase timer reads `Shd 0.0` over a 14 s stall | doa413c NOTES:207-209 | open, unexplained. P1 replaces the timer rather than explaining it |
| Skip a pending pipeline in async mode | doa413c step 2, pipeline413 §8 option 2 | **never dispatched** (P4) |
| More compile workers | doa413c step 3, option 3 | **never dispatched** (P3) |
| Fewer pipelines / `VK_EXT_graphics_pipeline_library` | doa413c step 4; `docs/investigations/perf-architecture.md:386-397` | **never dispatched** (P5) |
| Turn `async_compile` on by default | lane.async413, PR #567 | **in flight**. Registered S/M/V/F legs, waiting on the Nova's battery hold. Its own leg M predicts no gain, and this lane's code reading agrees (section 2) |
| Module warm-up re-does glslang, not Turnip | `vk/shaders.c:1204-1236` (read) | **new here**, in no NOTES (P3) |
| Async mode never saves the pipeline cache during play; the teardown save is reached only via `nv2a_exitfn` | `compile_worker.c:63-142`, `vk/draw.c:1514`, `pgraph.c:1610-1615` (read) | **new here**. Android reachability unverified (P3 item 5) |
| A driver-identity change wipes `spv_cache/` and `shader_module_keys.bin`, which do not depend on the driver | `vk/renderer.c:125-146` (read; expert R5) | **new here** (P3 item 4) |
| `wait_idle` counts dequeues, so warm-up can report done while the last compile runs | `compile_worker.c:164`, `:218` (read; expert R2) | **new here** (P3 item 1) |
| glslang `validate=true` in release | `vk/glsl.c:249` (read; expert R4) | **new here**, small (under 1% share) |
| `specular_power` fields split shader keys | `docs/investigations/sweeps/sweep-shaders.md:418-423` | **stale**: the field no longer exists under `hw/xbox/nv2a` |
| GTA spikes of 0.7-1.9 s beside compiles (`Shd` 253 / 37.9 / 118 ms) | slowdown462 NOTES:594-602 | measured, not settled. P3 applies to GTA the same way |
| #428 vCPU on the prime core | tracker, PR #437 | closed, **refuted** (-21.5% pinned). Constrains pool placement: leave cpu7 to the scheduler |
| #507 Thor pauses cpu3-7 when hot | tracker | open. Constrains the pool |
| Upstream xemu #768: GL shader disk cache | https://github.com/xemu-project/xemu/pull/768 | merged 2022-09-10 |
| Upstream #2324: cache shader modules (GL and VK) | https://github.com/xemu-project/xemu/pull/2324 | merged 2025-07-03 |
| Upstream #2932: driver version in cache validation | https://github.com/xemu-project/xemu/pull/2932 | merged 2026-07-27 |
| Upstream #2993: persist pipeline and SPIR-V caches | https://github.com/xemu-project/xemu/pull/2993 | open. On desktop (M3 Ultra), 106 SPIR-V compiles (299 ms) -> 0 and pipeline creation 258 -> 46 ms. hakuX already has both caches |
| Upstream #2746: lmdb shader cache | https://github.com/xemu-project/xemu/pull/2746 | open |
| Upstream issue #2631 "Async Shader" (#2787, Ninja Gaiden Black stutter, closed as its duplicate) | https://github.com/xemu-project/xemu/issues/2631 | open, no maintainer comment. Upstream has no async, skip or ubershader path |

No tracker row exists for pipeline pre-build, key sets, the worker pool, GPL, ubershaders or
the create-call timer; they live only as options inside #413 and #569.

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
| **(d) ubershader (Dolphin hybrid)** | an interpreter vertex + fragment shader driven by uniforms, drawn while the specialised pipeline compiles, then swapped | removes the whole excess on a cold cache, the only option that does so **with no dropped draw**: <= 10.8 / 14.8 / 9.9 s | none if exact; any divergence from the specialised shader shows as a pop when it swaps in | a new generator next to `glsl/psh.c` (4,610 lines of specialised semantics to mirror) and `glsl/vsh-prog.c`; `draw.c` (pacing) | **very high** / high: exactness against the goldens is the whole difficulty. Fps cost on the Adreno 740 is an estimate: fragment 3-6x ALU plus register pressure (expert R11, (C)); at the NV2A's 640x480 the A740 has room [inferred, unmeasured]. Precedent: Dolphin's exclusive mode costs "a large performance hit" and hybrid is "not guaranteed stutter-free" (PR #5702); PCSX2's uber/hybrid is an open WIP, "very slow on some systems/games", 20-40 s to precompile (https://github.com/PCSX2/pcsx2/pull/14737) |
| **(e) fewer pipelines** | GPL (four libraries, fast link), more dynamic state, one pipeline layout, dedup float fields out of the key | dedup: <= (dpm - dsm) x cost = **1.5 s / 0 / 0** (pipeline413 §8). GPL: 1/2-2/3 of each miss's ir3 work **if** Turnip recompiles unchanged partner stages (unverified; P1 decides) | none (fast-linked pipelines may run marginally slower until an LTO swap) | `draw.c` (pacing), `compile_worker.c`, `instance.c` (free), `shaders.c` (forza414) | GPL high / medium; dynamic state low / low. Turnip GPL: "Initial implementation" in Mesa 22.3.0 (https://docs.mesa3d.org/relnotes/22.3.0.html), an LTO leak fix in 23.0.0 (https://docs.mesa3d.org/relnotes/23.0.0.html); https://mesamatrix.net/ lists it as not supported on tu. Read `vulkaninfo` on the device first. Dolphin's dynamic vertex loader (PR #10781) "completely eliminates pipeline compiles" on Metal by moving vertex fetch into the shader |
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

**Upstream.** xemu has no async-compile, skip or ubershader path. Issue #2631 is open with no
maintainer comment (https://github.com/xemu-project/xemu/issues/2631), and no xemu discussion of
"screens drawn once" was found. The comment is hakuX's own.

**The mechanism is real elsewhere, and other emulators guard against it:**

- **Dolphin**, PR #6443 ("skip" mode, merged 2018-03-26,
  https://github.com/dolphin-emu/dolphin/pull/6443). Reviewers warned of "missing objects,
  flickering, or broken effects", and of permanent glitches from EFB copies (render-to-texture)
  that are not redrawn every frame. It shipped as an opt-in radio button with a warning. Dolphin's
  answer was hybrid ubershaders (PR #5702, https://github.com/dolphin-emu/dolphin/pull/5702).
- **Eden** (yuzu lineage) skips a draw whose pipeline is not built, except draws of 6 or fewer
  indices or vertices, which compile synchronously. The source comment reads: "we can assume these
  are full screen quads. Usually these shaders are only used once for building textures so we can
  assume they can't be built async"
  (https://git.eden-emu.dev/eden-emu/eden/raw/branch/master/src/video_core/renderer_vulkan/vk_pipeline_cache.cpp).
- **Azahar** (Citra line) has the same guard: `wait_built = !async_shaders || num_vertices <= 6`
  (https://raw.githubusercontent.com/azahar-emu/azahar/master/src/video_core/renderer_vulkan/vk_rasterizer.cpp).
  It also has a user-visible cost even with the guard: issue #1360, Fire Emblem Fates sprites
  flicker or vanish, closed "not planned"
  (https://github.com/azahar-emu/azahar/issues/1360).
- **Vita3K** refined full-surface draw detection (3, 4 or 6 vertices) alongside async pipelines
  (https://github.com/Vita3K/Vita3K/pull/3169). That this is the same guard is [inferred].
- **RPCS3's** own tooltip: async "nothing will be rendered for this shader until it has compiled…
  graphics pop-in"; synchronous "fixes missing graphics… but introduces severe stuttering"
  (https://raw.githubusercontent.com/RPCS3/rpcs3/master/rpcs3/rpcs3qt/tooltips.h). **Cemu's**:
  "objects not rendering for a short time"
  (https://raw.githubusercontent.com/cemu-project/Cemu/main/src/gui/wxgui/GeneralSettings2.cpp).

**How it would happen in hakuX.** A draw into a surface that the game renders once and then
samples or flips repeatedly, such as a composed menu background, a loading screen, or a
render-to-texture done at scene start. If that draw is skipped, nothing redraws it; the surface
keeps whatever it held. A draw into the back buffer redrawn every frame loses only the frames its
compile takes. That is 0.4-1.2 s per pipeline here (upper bounds), so it is a visible pop-in, not
a one-frame flicker.

**Answer.**
- "Permanently missing" is **plausible, and documented in other emulators, but unmeasured in
  hakuX**.
- "Missing for up to about a second per new pipeline" follows from the compile cost for every
  skipped draw.
- **As built, the setting skips only while glslang runs (<1% of the compile), so today's visual
  cost is small and so is its benefit.**
- What decides noticeability:
  1. async413's V leg on DOA and Blinx, frames compared A vs B after each load. It is registered
     and not yet run.
  2. If P4 is ever built, a counter of skipped draws per target surface, and of those surfaces
     later sampled or flipped without being redrawn, over a title sweep. That is the "drawn once"
     case, counted. A non-zero count on a surface that reaches the screen is a permanent loss.

  Both are cheaper than arguing it.
- If skipping ever ships as a default, it should carry the <= 6-vertex synchronous exception that
  three other emulators converged on, and the owner decides.

## 7. Ranked plan

Order of rank: what a player gains, and what it costs in pixels, per unit of work. Nothing here
drops a draw by default. Each item is one lane.

### P1. Measure the create call, per stage (instrument; unblocks P2 and P5)

- **What:** chain `VkPipelineCreationFeedback` (core in Vulkan 1.3) into both
  `vkCreateGraphicsPipelines` sites (`vk/draw.c:2837`, `compile_worker.c:131`) and accumulate:
  whole-pipeline duration (`dpc_ms`), per-stage duration, and per-stage
  `APPLICATION_PIPELINE_CACHE_HIT`. Add a glslang timer (`vk/glsl.c:456`), a timer on
  `save_pipeline_cache_to_disk`, and a key-diff class counter: for each shader-cache miss, which
  of {vertex program, fixed-function vsh, combiner stages, psh texture fields, float fields}
  differs from the previous binding. Print as fields on the `[shd413]` line.
- **Bound:** none itself. It turns pipeline413's upper bounds into measurements, and it decides
  P5.
- **Files:** `vk/draw.c` (pacing), `compile_worker.c`, `vk/glsl.c`, `pgraph/profile.c`
  (unclaimed), `hw/xbox/nv2a/debug.h` (lane.remote).
- **Prediction legs** (soak, hand-read; one cold DOA 440 s survey soak on the Nova):
  - **C1 (pipeline413 §9's falsifier):** the fight load's `dpc_ms` sum is within 20% of the
    14.8 s excess. Refuted: the stall's time is outside the create call, and every compile
    option's bound shrinks to `dpc_ms`.
  - **C2:** glslang ms <= 5% of `dpc_ms` (doa413c: under 1%).
  - **C3, decides P5:** of the stages in missed pipelines whose module was already used by an
    earlier pipeline, the share Turnip reports as a cache miss. >= 50%: Turnip recompiles
    unchanged partners, and GPL's bound is 1/2-2/3 of each miss. <= 10%: GPL buys little;
    drop P5.
  - **C4:** the key-diff classes of the fight load's misses (a reading, not a threshold).
- **Device:** yes, one soak. **Release note:** none.

### P2. Why one shader costs ~400 ms in Turnip, then cheaper shaders (option (h))

- **What.** Phase A is offline, with no device and no emulator code:
  1. Build Mesa 26.3's freedreno tools on the host. The device runs Turnip "T30", Mesa 26.3.0
     (`docs/investigations/adreno-driver-landscape.md:74`).
  2. Compile hakuX-generated SPIR-V for an a7xx GPU id, and time and profile the NIR/ir3 passes
     with full symbols. The device's call chains stop inside the driver (doa413c NOTES:196).
  3. Start from the pgraph test discs' shaders. Then do DOA's: its `spv_cache/*.spv` lives in the
     app's private directory, so getting it needs one device request that pulls it after a cold
     soak (a soak step or a dispatcher option; `dispatcher.sh` is lane.fanduty507's).

  Phase B: change the generators so Turnip does less work. Candidates to test first:
  - the glslang optimizer on or off (`vk/glsl.c:248`);
  - dynamic indexing into the 192-entry constant array (`c[A0+n]`, `glsl/vsh-prog.c:342`);
  - the constant-writer copy (`:866-875`);
  - psh's texture-mode code paths that `PshState` switches in.
- **Bound:** the excess is linear in per-shader cost (pipeline413 §8 row 4). Every other item's
  stall shrinks by the same factor. This is the only item that shortens a first-ever compile
  without an ubershader.
- **Files:** Phase A none (tools, `docs/lanes/<lane>/`). Phase B `glsl/psh.c`, `glsl/vsh-prog.c`
  (unclaimed), `glsl/vsh.c`, `glsl/vsh-ff.c`, `glsl/geom.c` (free), `vk/glsl.c`.
- **Legs:**
  - Phase A (offline, registered before the run): per-shader Turnip time on the host for the
    suite's shaders, and which passes dominate (a reading).
  - Phase B:
    - pixel-inert arms on every golden the generator change can reach (the full sweep for a
      psh/vsh change);
    - one cold DOA soak with `dpc_ms` (needs P1). Leg: fight-load `dpc_ms` drops by the factor
      Phase A measured, within 30%.
- **Device:** Phase A only for the SPIR-V pull. Phase B yes.

### P3. Pre-build pipelines on idle cores from learned and shipped key sets (options (a) + (c) + (g))

- **What:**
  1. A pool of 3-4 compile workers with pipeline jobs first and a condvar, not a `g_usleep(100)`
     spin. Let the scheduler place them (the Thor pauses cpu3-7 when hot, #507). `wait_idle`
     counts completions.
  2. Persist **pipeline** keys, next to `shader_module_keys.bin`.
  3. When a title boots, rebuild its known pipelines on the pool, in the background, into the
     VkPipelineCache. This regenerates GLSL from the keys, so it survives any generator change in
     an update.
  4. Keep `spv_cache/` and the key files across a driver-identity change (`renderer.c:125-146`).
     SPIR-V is driver-independent.
  5. Save the pipeline cache from the worker and on pause, not only at teardown. Async mode today
     never saves during play. The teardown save is reached only through `nv2a_exitfn`
     (`pgraph.c:1610-1615`), and whether that runs on Android at all is unverified: grep a soak's
     logcat for "Saved pipeline cache".
  6. Ship per-title key sets gathered from our own route soaks, keyed on the `ShaderState` layout
     hash, so a title's first play is pre-built too. The harness already plays 145+ titles.
- **Bound:** for every pipeline in the set, the stall drops to its warm floor. doa413c: 12.9 s
  cold vs 3.1 s warm on the fight load. Pre-build time for DOA's 180 s route (77 misses after
  boot, pipeline413 §4) at <= 485-780 ms each on 4 workers is **<= 9-15 s** [computed from upper
  bounds]. It fits inside the ~58 s from launch to `mark booted` (pipeline413 §7), on cores that
  are idle then. A shader outside the set: unchanged.
- **Visual:** none.
- **Files:** `compile_worker.c` (unclaimed), `vk/shaders.c`, `vk/renderer.c`, `vk/renderer.h`
  (forza414), `vk/draw.c` (pacing), plus a key-set asset under `android/app/src/main/assets/`.
- **Legs** (soak, hand-read; a held two-launch session like doa413c's `capture_stall.sh`, with
  caches cleared once before launch 1):
  - **W1:** launch 2's fight load and title-stage load are each within 1.5x of doa413c's warm
    3.1 s.
  - **W2:** launch 2 logs the pre-build finishing before `mark booted`.
  - **W3:** launch 2's windows before `mark booted` hold gfps within 10% of launch 1's. The
    pre-build must not slow the intro.
  - **W4, falsifier:** launch 2 with pre-build but a wiped `vk_pipeline_cache.bin` still meets W1.
    Refuted: the gain came from the old cache file, not the pre-build.
  - Shipped sets: one cold first-launch soak meets W1.
- **Device:** yes. **Release note (performance):** "a game you have played before (or one we ship
  a shader set for) no longer freezes the first time a scene loads after an update."

### P4. Async done without dropping: a bounded wait, then skip (option (f), owner's decision)

- **What:** with P3's pool in place, stop waiting forever on a pending pipeline
  (`vk/draw.c:4342-4351`). Wait up to a per-frame budget, then skip the draw. The budget and the
  default are the owner's call. The settings text already warns of "brief visual pop-in"
  (`strings.xml:201`).
- **Bound:** <= the whole excess (pipeline413 §8 option 2), or <= excess x (1 - 1/N) with the
  pool.
- **Visual:** missing geometry for the frames a compile takes. Section 6 says what decides
  whether that is visible.
- **Files:** `vk/draw.c` (pacing), `compile_worker.c`.
- **Legs:** async413's S and V legs re-run on this build.
- **Device:** yes. Rank this after async413's V result and the owner's decision, never as a
  default before both.

### P5. `VK_EXT_graphics_pipeline_library` (option (e)), gated on P1's C3

- **What:** four libraries, fast link without LTO, and one fixed pipeline layout with
  `INDEPENDENT_SETS` and the full push-constant range. Today a layout is created per miss
  (`vk/draw.c:2750-2768`). Optionally, an LTO rebuild in the background, swapped in when ready.
- **Bound:** 1/2-2/3 of each miss's Turnip work if C3 >= 50%; about 0 if C3 <= 10%.
- **Files:** `vk/draw.c` (pacing), `compile_worker.c`, `vk/instance.c` (free).
- **Legs:** pixel-inert arms (full sweep), plus a cold DOA soak with `dpc_ms` down by the C3
  share, within 30%.
- **Device:** yes.

### P6. Ubershader fallback (option (d)): a spike first

- **What:** Phase A covers the fragment side only. A uniform-driven interpreter of the combiner
  stages that `PshState` actually uses, scored against the pixel goldens and timed in fps on the
  Nova at native resolution. The vertex side stays specialised; the expert estimates an
  interpreter at 10x or more (R11).
- **Bound:** removes the remaining first-ever stall with no drop. Its value is what is left after
  P2 and P3: the first sight of a shader in a title we ship no set for.
- **Files:** a new generator beside `glsl/psh.c`, and `vk/draw.c` (pacing).
- **Legs:** pixel exactness against the goldens the spike covers, and fps within 10% on a fight.
- **Device:** yes. Effort very high; do not start before P2 and P3 report.

### Not recommended now

- **(b) predictive lookahead:** P3's key sets are the better predictor. The lookahead is a second
  decoder of every state method, and its window, the unconsumed pushbuffer, is unmeasured.
- **More dynamic state (e, the rest):** the misses are new shaders, not new blend or depth
  combinations (dsm/dpm 0.73-1.0).
- **(g) per-title settings beyond key sets:** nothing yet shows a title where the general fixes
  fall short.

## Do not repeat

- The startup "Shader module warm-up" is not a pipeline warm-up. It re-runs glslang, under 1% of
  the stall, and no ir3. Widening it as it is buys nothing.
- Turning `async_compile` on is not a stall fix as built. The draw still waits for Turnip (P4 is
  the change that would matter).
- Adding compile workers without something that submits misses early is worth ~0. Sync mode asks
  for one pipeline at a time.
- Do not price GPL before P1's per-stage cache-hit reading (C3).
- Do not read the expert's "ir3 should be 2-50 ms" as a measurement. It is an estimate, and our
  own profile says the time is in Turnip. The gap between the two is P2's question.
- The per-pipeline figures (414-485 ms, <= 780 ms, <= 1.24 s) are pipeline413's upper bounds, not
  compile times.
