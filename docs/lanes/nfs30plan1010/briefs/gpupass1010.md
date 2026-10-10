# lane.gpupass1010 -- NFS Most Wanted's GPU frame: render mode A/B and the cold-start pass count (#433, 0.5)

Sonnet (measurement with one table-row change, per the 10-10 model table). Issue: none (dispatched directly by
lane.local, #433 umbrella; step 5 of docs/lanes/nfs30plan1010/PLAN.md). Nova only.

**Dispatch condition.** After texscan1010 and reportasync1010 have landed (or their switches are on one base), or
earlier if either lane's A/B shows the GPU on the critical path (period moving less than the CPU-side wait removed,
with GPU busy near the period). Before that the GPU is not on NFS's path and this lane's result cannot move the
frame.

## Why
- At the race start the GPU is busy 21.7 ms/frame cold, 12.8 warm, with 69 render passes per frame cold (26.5 warm),
  24.9 pass pairs, 20 MB of GMEM load and 20 MB of store, at a constant 615 MHz (lane.nfs30plan1010's `XFR rpc`
  census, runs `1-1791649387`/`1-1791649388`, NOTES 5.5). Today it is not on the path: the PFIFO thread's 56-62 ms
  cold frame waits on it only at three sync points. After steps 1-2 the GPU runs in parallel and the frame is
  max(PFIFO on-CPU ~24-25 cold, GPU 21.7) + the VBLANK grid: the GPU is the second-largest term and on heavier
  tracks (night, rain, more traffic) it can be the largest.
- The corpus (lane.gmem474, rendermode474, flip474): GMEM mode runs the draw stream twice (X/R ~1). Sysmem cut GPU
  time 60.0 -> 28.6 ms on DOA and 40.1 -> 21.5 on AUF, pixels PASS 1059, and is the default for those two titles via
  `kTitleRenderModes` (android/app/src/main/cpp/xemu_android.cpp:796-810). `TU_AUTOTUNE_ALGO=profiled` did as well.
  Kabuki did not win (X/R 0.77 remains). No lane measured NFS's X/R, passes or GPU ms under sysmem.

## The job
1. **One A/B, no code beyond a table row:** NFS MW's title id in `kTitleRenderModes` as sysmem vs the default,
   plain build + `HAKUX_GPUXFR=1` for the pass census, 2 runs per arm, route `nfs-mw-quickrace`, 12 starts. Read:
   GPU busy ms/frame, X/R, render passes per frame, cold start vs warm, and the countdown period and v2/v3/v4
   histogram (`docs/lanes/nfs30plan1010/phaseread.py`, `ftwin.py` if frametrace is on).
2. **Register the prediction first**, docs/testing/predictions/gpupass1010-*.json: GPU ms cold 21.7 -> <= 14 if NFS
   behaves like AUF; X/R -> ~0; period unchanged unless the GPU was the path (say which you expect from the base you
   run on). The falsifier for "GPU is not on the path" is a period that moves with GPU ms.
3. **Pass census after texscan1010:** the cold start's 2.6x pass count is the cube-face traffic (each face download
   ends a pass). With the GPU-side copy the breaks may remain (the copy still needs the surface out of its pass).
   Report passes per frame on vs off `HAKUX_TEXSCAN` from the census; if the breaks stay, name the site for a
   follow-up (not this lane).
4. **Pixel check:** rendermode474's suites on vs off for the NFS row (render mode is a driver tiling choice; expect
   byte-identical).
5. **PR.md:** `State: ready`; the tables; `Needs device: yes (Nova, used)`; `Release note (performance): ...` or
   `none`; whether the NFS row should stay.

## Rules
- Territory: android/app/src/main/cpp/xemu_android.cpp (`kTitleRenderModes` row only), docs/lanes/gpupass1010/**,
  docs/testing/predictions/gpupass1010-*.json. Ask for any other file by name on the board.
- No clock, governor or performance-mode remedy. `TU_AUTOTUNE_ALGO` is a tiling choice, not a clock; render mode is
  the remedy class rendermode474 landed.
- Titles run on the Nova only. Use pad.sh for input (RT is the gas), never `adb shell input keyevent`.
- Perf claims come from this lane's runs only; cite the run id for every figure.
- A measured scene needs a moving player: confirm it from the `s*-g11.png` frames, not the HUD clock.
- Device budget: this is at most four runs of 500 s. Batch them in one enqueue.
- No `gh`. Never `pkill -f` or `pgrep -f`.
- This is a headless session, and it ends when the turn ends. Never end a turn "waiting for a background task". With
  runs pending, commit and push `docs/lanes/gpupass1010/WAITING`, one `run <request-id>` line each; lanewaker
  resumes you when they are DONE.
