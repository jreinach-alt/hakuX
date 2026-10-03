## #433 -- 2026-10-02 18:20 PDT

[lane.vcpuwait433] HOST REQUEST for lane.local: one held Nova session, the off-CPU capture that names Tron 2.0's vCPU wait (step 1 of this lane's brief). About 10 minutes of device time; it counts as 1 of this lane's 3 Nova runs.

Run it from a checkout of `origin/lane/vcpuwait433`, on the host, in a detached shell:

    DEV=nova bash docs/lanes/vcpuwait433/capture_offcpu.sh tron1 "Tron 2.0 - Killer App (USA, Europe).iso"

What it does:
- It takes `hold/nova` with tag `lane.vcpuwait433`, then waits for the running request to finish (`hold.sh wait-idle`).
- It installs `dispatch/builds/16f09aa346.apk`, the plain build of near30's Tron soaks, and plays near30's `tron-newgame.route` with `PERF_REGIMEN=default`.
- At `mark gameplay` + 10 s it records `simpleperf --trace-offcpu` for 60 s (cpu-clock, dwarf call graphs, 1000 Hz). If the off-CPU event will not open, it retries up to 3 times, 15 s apart.
- It writes to `perf/2026-10-02-vcpuwait433/tron1/`: `tron1.data`, `logcat.txt`, `soak.log`.
- On every exit path it stops the app, clears the shader caches and releases the hold.

Needs: Nova battery at 20% or more, `perf_event_paranoid` <= 1. The script logs both.

Expected result, written before the run: one site holds >= 70% of the vCPU's attributed off-CPU time. My priors on which: the BQL 0.35, pfifo.lock in `user_write` 0.20, a surface download on guest access 0.10; no site >= 50% 0.25. If no site reaches 50%, I stop and report the split (the brief says so).

How I read it: `python3 docs/lanes/vcpuwait433/waitsite.py perf/2026-10-02-vcpuwait433/tron1/tron1.data`. On slowdown462's `doa3.data` the same reader gives `pgraph.lock` 89.7%, the #474 answer. When the capture exists, please resume this lane with an addendum that says so.

One correction for near30's notes: "read-downloads (~0.15 ms) measured out" used `[tlb68] rdus`. That field times `tlb_reset_dirty`, not the vCPU's wait for a GPU surface download (`surface_access_callback`). That wait is still a candidate, and this trace measures it.

[lane.vcpuwait433] waiting: on this host capture (`perf/2026-10-02-vcpuwait433/tron1/tron1.data`). The lane is parked until it exists. Nothing else is queued.

## #433 -- 2026-10-02 19:00 PDT

[lane.vcpuwait433] tron1 read: **void for the question.** The route ended in Tron's Options > Display menu at 59 fps, not in the level. The Nova's hdd.img has no Tron save any more: on Single Player (route-frame 185013) Auto Load and Load Game are greyed and the cursor starts on New Game. The route's one DOWN was written for a disk that had a save. Here it skipped to Light Cycles, and the START/A loop walked out to Options. decompose.py on the run's logcat: 56 rows, 59.9 fps, 0 below the bar, v_blk 0.52 ms/frame (near30's slow window: 10).

The trace is still a usable fast-window **control**. The vCPU was off-CPU 3.2% of 60 s, 0.53 ms/frame, which matches v_blk. 69% of the attributed time is BQL in `cpu_exec_loop`: about 1,000 short (15 us) interrupt-entry waits a second. 14% is pgraph.lock. That BQL row, about 0.3 ms/frame, is the baseline the slow-window capture is compared against.

Fixed for run 2 (commit below on lane/vcpuwait433):
- `tron-newgame.route` v5 has no DOWN. A picks the top enabled entry: New Game with no save, Auto Load with one. Both reach the level.
- `capture_offcpu.sh` waits after mark + 10 s for a guest second below 40 fps (cap 90 s) before recording, and logs which way it started. Soak 510 s.

Next, ranked by P x win:
- **A. Re-run the capture (run 2 of 3).** P 0.6 that it names a site: 0.8 it reaches the level (the frames show the no-save state; New Game is near30's path) x 0.8 slow window (4 of near30's 5 New Game soaks) x 0.95. Win: names the wait behind up to 10 ms of a 43 ms Tron frame, the precondition for step 2. Cost: 1 run, ~12 min of Nova.
- B. BF2 capture instead. P 0.4: no slow-window route evidence under this script. Win: 21 ms of a 64 ms frame. Run 3 if A misses the level again.

HOST REQUEST for lane.local: run 2 of 3, same command as run 1 but with a new name, from a checkout of `origin/lane/vcpuwait433` at the commit that carries this entry, or later:

    DEV=nova bash docs/lanes/vcpuwait433/capture_offcpu.sh tron2 "Tron 2.0 - Killer App (USA, Europe).iso"

Expected, written before the run: the record starts on the gate (the CAP line says `slow gate: last pace second N fps` with N < 40), and decompose.py on tron2 shows at least half its rows below 28.5 fps with v_blk >= 6 ms/frame. Then one site holds >= 50% of the attributed off-CPU time. Priors unchanged: BQL 0.35, pfifo.lock 0.20, surface download 0.10, none 0.25. Please keep the script's stdout (the CAP lines) next to the output, e.g. `> .../tron2/cap.log`.

[lane.vcpuwait433] waiting: on host capture run 2 (`perf/2026-10-02-vcpuwait433/tron2/tron2.data`). Nothing else is queued.
