# lane.shaderprebuild569 -- #569 P3: pre-build known pipelines on idle cores; save the pipeline cache during play

Brief: P3 of `docs/lanes/shaderplan569/NOTES.md` section 7 (items 1-5 here; item 6, shipped
per-title key sets, is the second PR, designed in section 6 below). Base: master @ 2c59b7bbba.
Code: 54865a3521.

## 1. Item 5 first: is the pipeline cache saved on Android? Yes, in sync mode

The plan's check ("grep a soak's logcat for 'Saved pipeline cache'") cannot work: that line is
`VK_LOG`, which is compiled out on Android (`vk/debug.h:27-31`, `VK_LOG_VERBOSE 0`). The
`[shd413]` line carries the same facts: `L=Y|N` (the cache file was loaded at init) and `W=<n>`
(saves so far).

Read over every soak and arm logcat in `dispatch/results` that has `[shd413]` (224 logcats,
2026-09-28 to 09-30):

- `W` climbs in every one of them. The default (sync) mode saves during play, from
  `maybe_save_pipeline_cache` after a miss, at most every 30 s.
- A run on the same apk after another loads the file (`L=Y`); the first run after an apk
  change starts `L=N`, because the dispatcher clears the caches then (`dispatcher.sh:296-331`).
- The loaded cache works. Arctic Thunder on the Nova (lane.tcg424flip, ref 7bcd6e6e2b): cold
  run 1691697 spent 4,661 ms in 43 draw-path creates; the next three launches on the same apk
  (1692424, 1692530, 1692609) spent 1, 1 and 2 ms on the same 43.
- Turnip never sets `VK_PIPELINE_CREATION_FEEDBACK_APPLICATION_PIPELINE_CACHE_HIT_BIT`:
  `dfbh=0` in every window of every run, warm or cold. A cache hit shows only as time.

So the premise "on Android every session may start cold" is **refuted for sync mode**, the
default. What is true:

- **Async mode** never saves from the worker. It saves only when a clear pipeline misses (the
  one sync create left in async mode, `vk/draw.c` create_clear_pipeline) or at teardown.
- **The last minutes of a session can be lost.** A sync save needs another miss 30 s after the
  previous save. Pipelines created in the last half-minute before the app is killed are not
  saved unless teardown runs, and the dispatcher ends a soak with `am force-stop`.
- **A second play is warm only while the cache file is valid.** Three things invalidate it:
  - a driver-identity change (`renderer.c` wiped all three caches);
  - a key-layout change;
  - any update that changes the GLSL generators. The SPIR-V changes, so every Turnip cache key
    misses.

  That last is every nightly that touches `glsl/`. The pre-build is what survives it: it
  regenerates GLSL from the keys.

## 2. What was built (54865a3521)

| item | what | where |
|---|---|---|
| 1 pool | `HAKUX_COMPILE_WORKERS` threads (1-4, default 3), one queue. A pipeline job is taken first, then module jobs, then LTO. Workers sleep on the condvar. `wait_idle` counts finished jobs (queued + running), not dequeued ones. The async draw path waits for a pending pipeline on a condvar instead of `g_usleep(100)` | `compile_worker.c`, one line in `draw.c` |
| 2 records | Every monolithic draw pipeline appends a record to `pipeline_keys/<title id>.bin`: the hashes of its three module keys (`shader_module_keys.bin` holds the keys) plus its create state with no handles. That state is vertex input, topology, rasterizer and depth-stencil from `flags` on, blend, dynamic states, push-constant ranges and `RenderPassState`. Records are deduplicated by content hash. The title id is default.xbe's certificate id, read from the disc at renderer init (a C copy of `ReadDiscTitleId`, `xemu_android.cpp:795`, which does not export it) | `compile_worker.c`; call sites in `draw.c` `create_pipeline` (sync and async) |
| 3 pre-build | At renderer init, after the module warm-up and `init_pipelines`, the title's records are resolved. Each module comes from the module cache the warm-up filled, as a copy of its SPIR-V made into the batch's own `VkShaderModule`. Each render pass is made before PFIFO draws. The records are queued in first-seen order. Workers build each pipeline into the `VkPipelineCache` and destroy it. Pre-build jobs run behind every draw-path job, on all workers in sync mode and on workers - 1 in async mode. They bypass `pgraph_vk_create_graphics_pipeline_fb`, so `[shd413]` `dpc_ms` stays the draw path's own time. A queued job whose pipeline the draw path already built this run is dropped (`met=`). At most 2048 records per launch. `HAKUX_PREBUILD=0` turns it off (records are still written) | `compile_worker.c`, `renderer.c` start/stop, `shaders.c` exports, `draw.c` `pgraph_vk_prebuild_render_pass` |
| 4 driver change | A driver-only identity change wipes `vk_pipeline_cache.bin` alone. `spv_cache/`, `shader_module_keys.bin` and `pipeline_keys/` are wiped only when the key layout changes | `renderer.c` |
| 5 saves | The draw thread and the workers only mark the cache dirty. A worker writes it when the VM has stopped (`runstate_is_running()` false: the Android app's `nativePauseEmulation` -> `vm_stop`), when no new pipeline has come for 3 s and the last save is 10 s old, when the last save is 30 s old, and after a pre-build. While dirty, a worker wakes once a second. The save is no longer on the PFIFO thread. | `compile_worker.c`, `draw.c` `maybe_save_pipeline_cache` |

Why the runstate is polled, not a change-state handler: renderer init runs on the PFIFO thread
(`pfifo.c:2108` -> `pgraph_init_thread`), outside the BQL that
`qemu_add_vm_change_state_handler` needs. Taking the BQL there at boot risks a deadlock that I
did not rule out.

Thread safety, checked by reading:
- `shader_module_key_persist` now appends under a mutex. One key is larger than stdio's buffer,
  so two workers' appends could interleave.
- `ShaderModuleInfo.refcnt` is a plain int (`vk/glsl.c:500-512`), so no pre-build job touches a
  render-thread module.
- `ensure_spv_cache_dir`'s static is set on the init thread (`init_clear_shaders`) before any
  worker runs.
- `vkGetPipelineCacheData` and `vkCreateGraphicsPipelines` on one cache need no external
  synchronisation.

Instrument, all on `hakuX-perf`:
- `[pb569] start title= records= jobs= unresolved= modules= workers= pb_workers= enabled= setup_ms=`
- `[pb569] done jobs= ok= fail= met= create_ms= wall_ms=`
- `[pb569] rec known|new us= known= known_ms= new= new_ms=`: one line per draw-path create. Known
  means the record was in the title's file at launch or was met earlier this run. `us` is the
  create's wall time.
- `[plc569] save=<reason> n= ms=`
- `[pb569] HAKUX_PLC_WIPE=1: vk_pipeline_cache.bin removed|absent`

Checks run here (no device):
- NDK clang type-check of the five changed C files with the shared tree's compile lines
  (`typecheck.py`, copied from lane.uberspike569): rc 0 each. The only warnings are in lines
  that predate this branch.
- `pbjudge.py --selftest`: ok. It covers both sides of every threshold and the three VOID cases.

## 3. Legs (registered before any run)

The plan's W1-W4, on the Nova, DOA first and then Kabuki. The dispatcher's cache handling gives
the two-launch session with no held device. Each launch is one soak request, and both are on
one ref.

- **L1:** the apk's first run, so the dispatcher clears the caches (cold). The title's records
  are written.
- **L2:** the same apk's next run, so the dispatcher keeps the caches (`shader_cache: kept`).

Both run with `--env HAKUX_PLC_WIPE=1`. So L2 starts with the keys and records but no pipeline
cache file: that is W4's falsifier in every L2. W1 as the plan wrote it (with the file) is what
master already does (section 1). It cannot tell the pre-build apart, so it is not run
separately.

Judge: `pbjudge.py --l1 <dir> --l2 <dir> --boot-mark booted --load-mark play` (DOA);
`--boot-mark gameplay` (Kabuki). Readings and factors are in its docstring, fixed before any
run.

| leg | registered | fails in the world where |
|---|---|---|
| V | L1 cleared, L2 kept; L2's wipe line says removed; L1 `records=0`; L2 `records >= 20`, unresolved <= 10%; >= 20 [shd413] windows; boot mark in both; >= 20 known (L2) and new (L1) creates after it | not a verdict: VOID, re-queue |
| W4 | L2's mean known create after the boot mark <= 0.10 x L1's mean new create after it | the pre-build builds under a different driver cache key than the draw path (layout, render pass, module or state mismatch), or has not reached them |
| W1 | L2 pc_ms <= 0.25 x L1's (whole run) | W4's world, or L2 meets many pipelines L1 never did |
| W1b (DOA) | L2's first load after `mark play`: dpc_ms <= 0.25 x L1's | the same, inside the fight load |
| W2 | L2's `[pb569] done` before its boot mark | the pre-build is too slow for the boot (Kabuki: ~836 records at ~168 ms / 3 workers is ~47 s against `mark gameplay` at ~223 s) |
| W3 | L2's median gfps before the boot mark >= 0.90 x L1's | the pool's cores are taken from the vCPU or PFIFO during the intro |

Cold references (lane.uberspike569's arm A, same route and seconds, GPL 0):
- DOA `1-1790730667-uberspike569-2559714`: 148 creates, 26.2 s. First load after play: 2.9 s
  (15 misses). `mark booted` at 64.7 s, with 13 misses before it. Median gfps before it: 59.
- Kabuki `1-1790730670-uberspike569-2559946`: 836 creates, 140.4 s. `mark gameplay` at 223 s.

## 4. Runs

(none yet)

## 5. Coordination

lane.uberspike569's `lane/uberspike569-gpl` (PR.md ready, not folded at 2c59b7bbba) changes the
same worker loop, `CompileJob` enum, shutdown and `renderer.h` structs. This branch keeps its
state in an opaque `CompilePool` behind one pointer in `r->compile_worker`, adds no job type,
and leaves the GPL/uber code alone. Whichever folds second merges the worker loop by hand: their
new `switch` cases go into this loop's `job` branch unchanged.

## 6. Item 6 design (the second PR, `lane/shaderprebuild569-sets`; not built here)

- **Format.** A shipped set is this PR's per-title record file, plus the module keys its records
  reference, in one asset, `android/app/src/main/assets/pipeline_sets/<title id>.bin`:
  - a header: magic, version, `sizeof(PrebuildRecord)`, `sizeof(ShaderModuleCacheKey)`, and the
    `shader_state_layout` fingerprint from `renderer.c`;
  - the keys;
  - the records.

  A set whose fingerprint or sizes differ from the build's is skipped whole, so a layout change
  can never feed garbage keys to the generators (the #235 abort).
- **Harvest.** From our own route soaks: a dispatcher option pulls `files/pipeline_keys/*.bin`
  and `files/shader_module_keys.bin` after a soak (a `--pull` of the app's private files needs
  `run-as`; that is `dispatcher.sh`'s owner's change). A host script cuts, per title, the
  records and the keys they reference, and merges over runs. Records that are different
  pipelines stay. The route soaks already cover 145+ titles.
- **Use.** At renderer init, if the title has a shipped set, its keys are warmed and its records
  queued after the learned ones. Learned records already in the file are dropped by content
  hash.
- **Size.** 808 B per record (arm64, computed from the struct), and a few KB per vertex key. DOA's set is about 148 records (0.12
  MB) plus its keys (under 1 MB). Measure it on the first harvest before shipping 145.
- **Leg.** One cold first-launch soak (every cache cleared, no learned records) with the set
  shipped meets W4 against a cold L1 without it.
- **Caveat.** A set is keyed to the GLSL generator only through the keys: the GLSL is
  regenerated, so a generator change needs no new harvest. A `ShaderState` layout change needs
  one. The fingerprint check makes that a skip, not a crash.

## Do not repeat

- Do not grep a soak logcat for "Saved pipeline cache": `VK_LOG` is compiled out on Android.
  Read `[shd413]` `L=` and `W=`, or `[plc569]`.
- Do not read `dfbh` (the creation-feedback cache-hit bit) as a cache-hit count: Turnip never
  sets it (0 in every run, warm or cold).
- A plan leg "launch 2 is warm with the cache file" is met by master already (section 1). Only
  the wiped-file launch (W4) says anything about a pre-build.
