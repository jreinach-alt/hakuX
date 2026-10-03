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
