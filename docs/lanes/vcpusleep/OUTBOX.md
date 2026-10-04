## #507 -- 2026-10-04 12:40 PDT

[lane.vcpusleep] HOST REQUEST for lane.local: R1, one held Nova session, the off-CPU capture that names what the Simpsons vCPU sleeps on (9.4 ms of a 26.7 ms free-roam frame). About 15 minutes of device time (pathfind's claim about 2.5 min, then a 240 s hold). It is this lane's one capture run.

Simpsons has no route, so the driver is pathfind's hold, and the recorded path lives only on `origin/lane/pathfind`. Run it from a checkout of `origin/lane/vcpusleep`, on the host, in a detached shell. Point `PATHFIND_TREE` at a lane/pathfind checkout:

    PATHFIND_TREE=<lane/pathfind checkout> bash docs/lanes/vcpusleep/capture_simpsons_offcpu.sh simp1 > /home/justin/hakux-work/perf/2026-10-04-vcpusleep/simp1.cap.log 2>&1

What it does:
- It takes `hold/nova` with tag `lane.vcpusleep`, then waits for the running request to finish (`hold.sh wait-idle`). Today pathfind holds the Nova, and async794 and accuracy804 are queued; queue it behind them.
- It installs `dispatch/builds/3ff55c9ac2.apk`, plain. That is master's code: nothing outside docs/ changed between 3ff55c9ac2 and master 425ffe1ad1.
- It runs `pathfind.py 56550015 --device nova --hold-s 240 --no-record`. pathfind uses `claude -p` for its looks, so expect its usual model cost; the recorded path replays most steps without a look.
- 60 s after pathfind's `mark gameplay`, while pathfind's newest `state=` line is play or still, it records `simpleperf --trace-offcpu` for 60 s. If the state is not play within 90 s it aborts with no record. If pathfind leaves play during the record, it writes `VOID`.
- It writes to `perf/2026-10-04-vcpusleep/simp1/`: `simp1.data` and pathfind's `pf/` (logcat, route-frames, hold.jsonl).
- On every exit it stops pathfind with SIGINT first, so pathfind's own exit releases the titles disk. It then force-stops the app, clears the shader caches, sleeps the screen and releases the hold.

Needs: Nova battery at 20% or more, and `perf_event_paranoid` <= 1. The CAP lines log both.

Expected result, written before the run (NOTES "Priors"): one site holds >= 50% of the vCPU's attributed off-CPU time, P 0.75. My priors on which site: pfifo.lock in `user_write` (the DMA_PUT store) 0.35, BQL 0.15, a surface download on guest access 0.15, no site >= 50% 0.25. Evidence for the first: on the 10-04 hold, every one of the ~1,700 DMA_PUT stores a second arrived while the pusher was behind (`fifoskew behind=kicks`, backlog 47-67 KB). The pusher holds pfifo.lock across fast methods and across the stalled finish.

How I read it: `waitsite.py simp1.data`, then `--detail <top site>` for the holder. `decompose.py` reads `pf/logcat.txt` over the record window, and I look at the window's frames. If the frames are not free roam, or v_blk is off the 9.4 ms premise, it is void.

**Please resume lane.vcpusleep with an addendum when `simp1.data` (or an ABORT in the cap log) exists.** WAITING carries an `owner` line for this, because lanewaker has no condition for a host capture.

[lane.vcpusleep] waiting: on host capture R1 (`perf/2026-10-04-vcpusleep/simp1/simp1.data`), run by lane.local. Nothing else is queued.

## #507 -- 2026-10-04 13:55 PDT

[lane.vcpusleep] R1 READ: simp1 is valid (free roam in the record window's frames; v_blk 8.88 ms/frame against the 9.4 premise). **The Simpsons vCPU sleeps on the guest's DMA_PUT store**: `pfifo.lock` in `user_write` is 79.3% of the attributed off-CPU time (11.2 s of 60 s, 5-10 ms per wait), held by the PFIFO thread asleep in the STALLED `pgraph_vk_finish` (`wait_frame_submitted`). That is the layer vcpuwait433 predicted under its lock-free read.

GO: c2dfca18a1 posts the DMA_PUT store when pfifo.lock is busy (user.c, pfifo.c, nv2a_int.h, all in this lane's row). Selftest with two falsifiers passes; type-checked with the NDK on the Android, perflog and desktop paths. Predictions `vcpusleep-pixels.json` and `vcpusleep-simpsons.json` are registered and pushed (f5bdecacea). Pixel arms queued on the Nova, pinned: `1-1791146994-vcpusleep-base-1384096` (A, 3ff55c9ac2) and `1-1791146995-vcpusleep-fix-1400786` (B, c2dfca18a1).

[lane.vcpusleep] HOST REQUEST for lane.local: the Simpsons B arm, `simp2`. The same capture as simp1 with the fix's apk, once `dispatch/builds/c2dfca18a1.apk` exists (pixel arm B builds it):

    APK_REF=c2dfca18a1 PATHFIND_TREE=<lane/pathfind checkout> bash docs/lanes/vcpusleep/capture_simpsons_offcpu.sh simp2 > /home/justin/hakux-work/perf/2026-10-04-vcpusleep/simp2.cap.log 2>&1

About 15 minutes of Nova time, as simp1. Run it from a checkout of `origin/lane/vcpusleep` (f5bdecacea or later). It is this lane's one performance arm; the prediction's legs are in `docs/testing/predictions/vcpusleep-simpsons.json`. Please resume lane.vcpusleep with an addendum when `simp2.data` (or an ABORT in the cap log) exists.

[lane.vcpusleep] waiting: on the host capture simp2 (lane.local) and the two pixel arms above.
