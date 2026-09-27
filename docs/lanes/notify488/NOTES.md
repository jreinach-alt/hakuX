# lane.notify488 -- NV097 NOTIFY notifiers, and semaphore releases without a download (#488)

Refs (all on `lane/notify488`, base master `db8cc66396`):

| ref | what |
|---|---|
| `dffb7a8a66` | **A.** Master plus a perflog-only `[notify488] sem_release N notify N` line (tag `hakuX-perf`, every 60 frames) and the `NV097_NOTIFY` define. A shipping build is master's code. |
| `46aff48301` | A plus the NOTIFY handler only. |
| `9f80bc887a` | **B.** The NOTIFY handler plus the semaphore change. |

Predictions, registered at 17:22Z before any device run:
`docs/testing/predictions/notify488-{timing,pgraph,doa-ab}.json`.

## 1. What the silicon does (read, then measured by lane.xbox)

**NOTIFY (NV097 method 0x104).**
- The parameter is the type: 0 = WRITE_ONLY, 1 = WRITE_THEN_AWAKEN (the second also raises the PGRAPH NOTIFY interrupt,
  `NV_PGRAPH_INTR_NOTIFY`, `nv2a_regs.h:192`). NV hardware delivers it when the *next* method completes, which is why
  pbkit-style code pushes NOTIFY then NO_OPERATION (`signal-timing462.patch`, `TestDone`).
- The notification is 16 bytes at offset 0 of the object bound by `SET_CONTEXT_DMA_NOTIFIES` (0x180): a 64-bit
  timestamp, info32, then info16 and status (status 0 = done).
- **The console's own files confirm the layout** (`docs/lanes/xbox/signal-timing/console/ST_Done_Tiny.txt`): slot 0
  (offset 0) is written on every rep and slot 1 (offset 16) never is; words 0-1 are PTIMER's nanosecond time -- the
  timestamp advances 0.9996 ns per ns of the performance counter across reps; the write lands 4.1 us after the kick,
  1.4 us after the semaphore release pushed ahead of it.
- pbkit's ISR handles `NV_PGRAPH_INTR_NOTIFY` (nxdk `pbkit.c:398-404`), so a guest that asks for the interrupt has a
  handler for it.

**How xemu/hakuX handled it.** It did not. `methods.h.inc` had no NV097 NOTIFY entry, so the method went to
`unhandled` (`pgraph.c`, the `kelvin_dispatch` case) and nothing was written: 0 of 900 on the Thor. No `NV_PGRAPH_NOTIFY`
register state exists in `nv2a_regs.h`. The only PGRAPH notification interrupt is NO_OPERATION's software-method trap
(`pgraph.c`, `DEF_METHOD(NV097, NO_OPERATION)`), which stalls the FIFO until the guest clears `INTR_ERROR`.

**Which titles send it.** Neither DOA nor AUF: `class 0x0097 method 0x0104` is absent from the `hakuX-unhandled` lines
of every DOA and AUF soak on disk (`1790491858-flip474-658414`, the aufire412 and slowdown462 soaks). The unhandled log
is once per (class, method) per boot, so one line would have shown it. The NOTIFY half cannot move those two titles.

**The semaphore release's download.** `DEF_METHOD(NV097, BACK_END_WRITE_SEMAPHORE_RELEASE)` has called
`surface_update(d, false, true, true)` before writing the value since the 2018 refactor (`584dbda1d6`, Matt Borgerson,
carried from espes' original). That was before xemu watched surface memory: a CPU read after the semaphore could only
see the rendering if the release downloaded it. The download is a GPU finish when the bound surface is draw-dirty,
which it always is after drawing: 13.8 ms after the last kick for 500 quads on the Thor, against 2.7 us on silicon.

**What a download at the release still guarantees today** (the risk list for removing it):
1. *CPU reads of the render target.* Now covered by the Vulkan surface watch: every draw-dirty active surface has a
   TCG access watch (`vk/surface.c`, `register_cpu_access_callback`), and a guest read or write of its VRAM downloads it
   first (`surface_access_callback`, which waits for `downloads_complete`). Draws still in the reorder window or draw
   queue are not yet marked dirty, so B flushes both at the release; that marks the surface dirty and arms the watch.
2. *Occlusion reports.* `GET_REPORT` results reach guest memory only in `pgraph_vk_finish`
   (`pgraph_vk_process_pending_reports_internal`, `vk/draw.c`, end of finish). A guest that reads a report after the
   semaphore (ZPass_pixel_count, and D3D's visibility tests) needs the finish before the value. **B keeps the old path
   whenever a GET_REPORT came since the last release** (`report_since_semaphore`).
3. *GPU reads (textures, blits) of a dirty surface.* Already handled by `download_surfaces_in_range_if_dirty`.
4. *Guest memory the draws read (vertex data, textures).* Copied to staging at method time; the flush keeps it so.

**Named risks that remain in B:**
- A CPU read of a surface *shelved while still dirty* after a release is not answered by the watch
  (`vk/surface.c`'s handoff note: `surface_access_callback` downloads active surfaces only). The old release had
  cleaned the bound surfaces before any later shelving.
- The watch's insert is asynchronous (`mem_access_callback_insert` via `async_safe_run_on_cpu`); a surface whose watch
  was suspended (after a CPU write while clean) and is re-armed by the flush could be read in the gap before the insert
  runs. `surface_watch_rearmed` checks writes in that gap by hash, not reads.
- GL and a build without TCG keep the download (no watch there).

**Which pgraph tests use these methods** (searched `/home/justin/nxdk_pgraph_tests`): only `texture_cpu_update_tests.cpp`
(release at :169) and `zpass_pixel_count_tests.cpp` (:170, :272, :385, :488) send the semaphore release; nothing but
lane.xbox's `signal_timing_tests.cpp` sends NV097 NOTIFY. pbkit sends neither (`pb_finished` uses a FIRE_INTERRUPT
software method). The harness reads captures back with `gpum_copy` (M2MF, `gpu_m2m.cpp:420`); hakuX implements no
M2MF class, so it falls back to a CPU memcpy through the same watch.

## 2. The change

- **NOTIFY** (`pgraph.c`, `DEF_METHOD(NV097, NOTIFY)`): writes the notification when NOTIFY itself is processed, all
  earlier methods having been processed: PTIMER time (the `ptimer.c` clock, `<< 5`, as `TIME_0`/`TIME_1` read it),
  info32 0, then status 0 after a write barrier. WRITE_THEN_AWAKEN sets TRAPPED_ADDR/DATA and `INTR_NOTIFY` and raises
  the IRQ, **without stalling the FIFO**: no measurement says silicon stalls, and a stall the guest never clears would
  hang it. It logs `[notify488] NOTIFY write-then-awaken seen` once (tag `hakuX`, which the dispatcher keeps).
  Deviation from silicon: the write is at NOTIFY, not after the next method. With NO_OPERATION next, no poller can tell.
- **Semaphore release**: under TCG on the Vulkan renderer, with no GET_REPORT since the last release, it flushes the
  reorder window and the draw queue and writes the value; otherwise it runs the old `surface_update` download. The two
  flush functions are declared locally in `pgraph.c` (the brief keeps `vk/surface.c` and `vk/renderer.c` out of reach, so
  no new renderer op).
- **Counter** (perflog builds only): `[notify488] sem_release N notify N` per 60 frames from the method histogram, on
  `hakuX-perf`. The histogram's own `hakuX-mhist` line has never reached a dispatcher logcat: the dispatcher's
  `LOGCAT_SPEC` (`dispatcher.sh:1386`) does not list that tag. Anyone adding a perflog line: use a listed tag.

## 3. How it was checked before any device

- Each ref type-checked with the NDK clang line from the shared tree's `compile_commands.json`
  (`tc.py`, with and without `-DNV2A_PERF_LOG=1`); `check_android_guards.py` ok; `preflight.sh --allow-tracker` passed
  after regenerating `nv2a_index.json` (local tests tree = the index's `tests_commit` `6743b6ab`, 104 suites kept).
- **Desktop: not run.** This host's desktop channel runs OpenGL only (no xvfb for Vulkan), and the semaphore change is
  Vulkan-gated, so a desktop GL A/B would show only the NOTIFY half. The pgraph correctness arm is the Nova disc
  (`notify488-pgraph.json`, 13 suites including the two that send releases).
- The timing judge (`timing_judge.py`) was run on the console's files: every B-only leg passes on silicon.

## 4. Runs

- **Pilot** (timing suite, B alone, Nova): `1-1790529854-notify488-2739010`, queued 2026-09-27 17:25Z behind 12
  requests. Judge: `timing_judge.py --pilot <id>`.
- **Next, after the pilot is read** (`pilots/notify488.ok` first; the rest exceeds 30 min): the timing A arm, then the
  DOA A/B (A1 B1 A2 B2), per the `queue_order` fields of the two hand-read predictions.
- **pgraph disc**: `notify488-pgraph.json` is on the branch, so the arms job queues its pair itself
  (`arms-notify488-base/fix`) and posts a `[job.arms]` verdict on PR #490.

Session 1 ended waiting on the pilot: a headless session cannot outwait a 12-deep queue.

## For the next lane

- Do not look for NOTIFY in DOA or AUF; they do not send it (section 1).
- A perflog line on a tag outside `dispatcher.sh`'s `LOGCAT_SPEC` is invisible in every result.
- Before removing any finish, list what the finish writes besides pixels: reports ride on it.
