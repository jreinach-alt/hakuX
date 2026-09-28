# lane.async413 -- #413: does async shader compilation remove DOA's compile stalls?

Base master 01e62d8d1c. Fix d1e5278311: the `async_compile` default flipped to true in
`xemu_android.cpp:959` (native) and `SettingsActivity.kt:69` / `:543` (UI). Nothing else.

## 1. What the code says before any run

With `async_compile` on:

- **The shader modules go to a worker.** `shader_cache_entry_init` (`vk/shaders.c:961`) enqueues
  GLSL generation, glslang and `vkCreateShaderModule` on the single `pgraph.vk.compile` thread
  (`vk/compile_worker.c:199`, one FIFO). The draw is skipped until they are ready
  (`vk/draw.c:4333-4341`).
- **The pipeline is created on the same worker, and the draw waits for it.** `create_pipeline`
  (`vk/draw.c:2772`) enqueues the `vkCreateGraphicsPipelines` job behind whatever the worker holds.
  The draw then spins in `while (pending) g_usleep(100)` (`vk/draw.c:4342-4351`).
- **On Turnip, pipeline creation is where the compile happens.** doa413c profiled the cold fight
  load (`docs/lanes/doa413c/NOTES.md` s.5, s.9). 96% of the stalled PFIFO thread's samples were
  under `tu_spirv_to_nir`, `tu_shader_create` and `link_opts`, all inside
  `vkCreateGraphicsPipelines`. About 1% were glslang.

So **model M** (doa413c s.9) predicts that async compile moves about 1% of the stall off the draw
thread and still waits for the other 99%. The flip gaps barely shrink. The experiment tests that:
the brief's S leg is the claim the flip must meet to ship, and M's own leg is its falsifier.

**What the remaining pipeline-creation wait could still cost:** under M, all of the Turnip
compile. That is at least 9.8 s of the 12.3 s title-stage gap (doa413c's cold-minus-warm) and
most of the fight load's 21 s. If M is wrong the other way, the wait is only the pipeline's
share of each compile, but the worker is still serial. N new pipelines in one frame then cost
the sum of their creations in that frame, plus any module jobs queued ahead of them in the FIFO.

**Counters in a B run:** `dpm` is not counted on an async enqueue (pipeline413 s.1), so the
reader locates the stalls by `dsm`, which `shaders.c:954` counts before the async branch.

## 2. Instrument: `asyncwin.py`

`docs/lanes/async413/asyncwin.py <result dir>` (`--selftest` passes). It joins each `[shd413]`
window (60 flips, `dt_ms`, `dsm`) with the `hakuX-pace` line of the same frame count (`max=`,
the longest single flip gap). It then finds:

- **T**, the title-screen stage load: the window where the shader-module miss total first reaches
  its value at 50 s plus 15. It is read over windows T-1..T+3.
- **FL**, menu -> first fight: from the first window after `mark play` with dsm >= 5 to the
  steady fight, which is the first 3 windows with dsm 0 and dt >= 4 s.
- **H**, any window in the steady fight with dsm >= 3.
- **F**, the steady fight's median dt per 60 flips.

`frozen_ms` is the sum of a span's per-window longest gaps of 1 s or more. That is a lower bound
on the time the screen stood still.

On pipeline413's cold 440 s run (`1-1790579572-pipeline413-1715785`), the same route and the
async-off code:

| stall | longest flip gap | frozen | longest window | dsm |
|---|---|---|---|---|
| T (80 s) | 12298 ms | 12298 ms | 13751 ms | 25 |
| FL (355 s, 54.9 s span) | 7605 ms | 21168 ms | 9322 ms | 36 |
| H (440 s) | 4183 ms | -- | 15238 ms | 8 |
| F | -- | -- | median 5314 ms per 60 flips = 11.3 fps | 0 |

The 180 s pilot (`1-1790571190-pipeline413-3895602`) reads a T gap of 12185 ms.

## 3. Pre-registration (committed before any device run)

- `docs/testing/predictions/async413-doa.json`: DOA Ultimate, Nova, survey, 440 s, 2 runs per
  arm, A = 01e62d8d1c, B = d1e5278311. Legs:
  - **VOID:** each run must show `shader_cache: cleared`, the Nova, and `async compile: OFF` (A)
    or `ON` (B).
  - **S-T:** each B run's T gap is <= 0.5x the A mean. It fails in M's world.
  - **S-FL:** each B run's FL frozen_ms is <= 0.5x the A mean.
  - **S-H:** read only if both arms hitch.
  - **M:** the B/A ratio is >= 0.8. M is refuted at <= 0.5, and 0.5-0.8 is partial.
  - **V:** content present in A and absent in B at the same screen for >= 2 consecutive shots,
    in both B runs. Pop-in at a single shot is recorded, not failed.
  - **F:** the steady fight's dt is within 10% of A. It fails fast if draws are being skipped
    for good.
- `docs/testing/predictions/async413-blinx.json`: Blinx, Nova, survey, 240 s, 1 run per arm, V
  only. It covers the blurred title-screen background, the menus and the level HUD.

The arms job skips soak predictions, so I queue them with `request.sh --title`. They run in the
order fix, base, fix, base, so every run follows a different apk and starts cold.

## 4. Runs

Device time: 4 x (440 + 90) + 2 x (240 + 90) = 2780 s, or 46 min. That is over the 30-minute
pilot line, so the pilot is the first pair (B1, A1: 1060 s). The rest is queued once its frames
and logcat show T located, the cold cache, and the async line read.

- 2026-09-28 18:12Z (11:12 PDT): pilot queued. B1 = `1-1790618748-async413-847565` (fix
  d1e5278311), A1 = `1-1790618752-async413-854601` (base 01e62d8d1c). Both are Nova, survey,
  440 s, `--expect async413-doa.json`. In the Nova queue a Kabuki run from another lane
  (idlehaltdefault) sits between them, so each follows a different apk. The Nova is on its
  battery hold until the owner's ~18:00 PDT top-up. The session ended **waiting** on these two
  ids.
- **On resume:** run `asyncwin.py` on both. Check the VOID gates (`cleared`, nova, the
  `async compile:` line) and read the frames. Write `$DISPATCH_DIR/pilots/async413.ok` (with
  python3) with the verdict. Then queue B2, A2 (DOA) and B, A (Blinx, 240 s,
  `--expect async413-blinx.json`), fix first each time. If the pilot pair already puts M's
  ratio >= 0.8 on T and FL, S cannot pass. Queue the rest anyway, because V and F still need
  two runs, but say so on the PR.
