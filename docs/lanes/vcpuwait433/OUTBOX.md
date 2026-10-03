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

## #433 -- 2026-10-02 21:10 PDT

[lane.vcpuwait433] **The wait is named: `pfifo.lock` in `user_read`.** Run 3 is not needed for the capture.

tron2 was not void for this question. Its gate printed "60 fps" because of a parse bug, not because the window was fast. `hakuX-pace` writes a line every 60 frames, and the gate took the f difference between two lines as fps, which is always 60. decompose.py on tron2's record window: median 27 fps, 22 of 36 rows below 28.5, v_blk 7.8 ms/frame (9.2 in the slow rows). That cinematic is near30's slow window: its New Game soaks were slow in minutes 0-2 after `mark gameplay`, which is the ~4.5 min in-engine intro, and tron2's slow rows read F 45, v_blk 9.9. Those are the brief's 43 and 10. In-level (Auto Load), the sleep is smaller, about 6.5 ms of 33.

What tron2 shows: the vCPU is off-CPU 18.1% of 60 s (6.5 ms/frame). 65.2% of the attributed time is `pfifo.lock` in USER MMIO, and 95.5% of that is `user_read`, a guest load of DMA_GET, DMA_PUT or REF. That is about 4.0 ms per frame. The largest named holder is the PFIFO thread asleep in `wait_frame_submitted <- pgraph_vk_finish(STALLED) <- pgraph_vk_process_pending_reports`, which `pfifo_thread` calls with pfifo.lock held (40% of the wait time). That finish runs only when DMA_GET == DMA_PUT, so the guest waits out a GPU-side batch to read a word that is already final. No golden can depend on that.

The fix is `docs/lanes/vcpuwait433/userread-lockless.diff` (25+/14-): `user_read` takes no lock and uses acquire loads, and the DMA_PUT/GET/REF stores, including the pusher's GET advance, become release stores. It applies to master 9550493846. It has not been compiled, because this worktree has no build tree.

Next, ranked by P x win (full table in NOTES.md section 4):
- **A. Arm the lock-free read.** P 0.4 that Tron's slow-window fps rises >= 5%. For: the value read is final, and the renderer is idle 18 of 45 ms, so the pipeline waits on the guest. Against: 60% of the hold time has no named holder, and the freed sleep may become guest spin. Win: up to 4.0 ms of a 36 ms frame (27.9 -> at most 31.4 fps); BF2 unknown. Cost: a grant, 1 build, 2 Nova runs (Tron, BF2).
- B. Release pfifo.lock across the stalled finish instead. P 0.3: wider, but it exposes renderer state to the display thread.
- C. In-level capture (run 3). P 0.85 that it names the owner, but it is knowledge only, and A's arm answers the same question.
- D. Per-tid holder pass on tron2.data (offline). It re-scores A's P; I can run it while the grant is pending.

Capture fixes for whoever runs one next: it now prepares Tron's golden profile (`returning`) and fails closed. It records only after `levelcheck.py` sees Tron's HUD in at least 4 of the last 6 route frames with a moving view, and 5 pace lines in a row are in [18, 40) fps. Otherwise it logs ABORT and does not record. A replay on past runs: OPEN on the Auto Load run 2186958 at mark+28 s, ABORT on tron1 (menu) and tron2 (credits).

**GRANT REQUEST for lane.local:** add `hw/xbox/nv2a/user.c` and `hw/xbox/nv2a/pfifo.c` to lane.vcpuwait433's territory, for the patch above. The pfifo.c change is one line (pfifo.c:2071). With the grant, the next session applies the patch, builds, registers the Tron + BF2 prediction (draft in NOTES.md section 4) on the new refs, and queues the arm.

[lane.vcpuwait433] waiting: on that grant. Nothing is queued on a device.

## #433 -- 2026-10-02 21:25 PDT

[lane.vcpuwait433] D (the offline per-tid holder pass) is done. During the vCPU's pfifo.lock waits, the PFIFO thread (one tid) is asleep in the stalled finish (`wait_frame_submitted`) 40% of the time, asleep with an unsampled chain 47%, and on-CPU 6%, mostly the same finish's staged-download copies. So for at least 86% of the wait the pusher is not advancing DMA_GET, and the word the guest waits to read never changes during the wait. The display thread holds the lock for a minor 11% (`pgraph_vk_get_framebuffer_surface`). A's P goes from 0.4 to 0.45 (0.9 that the site's sleep goes). The remaining risk is that the guest then waits on GPU results in RAM, which would turn the freed sleep into spin.

[lane.vcpuwait433] waiting: on the grant for `hw/xbox/nv2a/user.c` and `hw/xbox/nv2a/pfifo.c` (entry above). Nothing is queued on a device.

## #433 -- 2026-10-03 06:57 PDT

[lane.vcpuwait433] **The lock-free `user_read` is on the branch (012fa08a94). The pixel arms are queued. The Tron arm waits for savestate433 to fold.**

- **Fix:** `userread-lockless.diff`, applied unchanged on top of master 5661db4f2b. `user_read` takes no pfifo.lock and uses acquire loads of DMA_PUT/GET/REF. `user_write` keeps the lock and stores with release. The pusher publishes DMA_GET with release.
- **Selftest** (`docs/lanes/vcpuwait433/selftest_userread.sh`): PASS. It compiles the real user.c with `-Wall -Werror` against a stub header. With the fix, a read returns in 0 ms while another thread holds pfifo.lock for 400 ms, and a write still waits (402 ms). The pre-fix user.c blocks 400 ms on every read, so the test can tell the two apart.
- **Pixel arms (Thor, pinned, release tier):** B `1-1791035760-vcpuwait433-4105238`, A `1-1791035764-vcpuwait433-4105418`. The suites are DMA corruption around surfaces, Texture render target and Texture render update in place, where the guest consumes GPU-written memory right after the FIFO drains. Prediction `vcpuwait433-pixels.json`: nothing moves.
- **Tron A/B:** A is already on disk. uberdefault569's Tron B rerun `990012` is master's code with the ubershader on, run on the golden profile. With that profile its route's DOWN lands on **New Game**, so it played the intro, the brief's slow window: share 0.82, slow rows v_blk 9.80 ms/frame. B is the same request at 012fa08a94 on the same route text with `# state: returning` (`tron-newgame-returning.route`). Prediction `vcpuwait433-tron.json`: M slow-row v_blk <= 7.0 (P 0.85); O1 share >= 0.87 and fps +5% (P 0.45); O2 share >= 0.90 (P 0.3).
- **Why the Tron run is not queued:** `titlestate.py show --device nova` (06:52) has Tron at **d2aff0a53543, the first-run state**. There the DOWN goes to Light Cycles, the same void as tron1. Until savestate433 folds, the dispatcher keeps whatever the disk holds and nothing enforces `# state:`. Queuing now would void for a known cause.

Next, by P x win:
- **A. Tron arm on the Nova once savestate433 folds** (M 0.85, O1 0.45, O2 0.3). Win: up to ~4 ms of a 42 ms slow frame, share 0.82 -> 0.87-0.90. Cost: 1 Nova run, the lane's 3rd.
- B. Release pfifo.lock across the stalled finish. P 0.3. It also frees the DMA_PUT store (4.5% of the site) but exposes renderer state. It needs a vk/reports.c grant.
- C. If M passes and O1 fails, capture B to see where the freed time goes. P 0.8 that it names it. 1 run beyond the brief's 3.

[lane.vcpuwait433] waiting: on the Thor pixel arms 4105238/4105418, and on savestate433's fold. lane.local, please resume me when savestate433 is on master: I merge master, queue the Tron B run, and read all three.

## #433 -- 2026-10-03 07:05 PDT

[lane.vcpuwait433] **Pixel leg PASS.** Thor arms B `1-1791035760-vcpuwait433-4105238` (012fa08a94, the lock-free read) and A `1-1791035764-vcpuwait433-4105418` (ef511dbd19, master), judged with ab_compare against the pre-registered `vcpuwait433-pixels.json`: 45 of 45 captures byte-identical (DMA corruption around surfaces 3, Texture render target 41, Texture render update in place 1; exact 5 -> 5). B's run is also the fix's first NDK build. No golden in those suites needed the old hold.

[lane.vcpuwait433] waiting: on savestate433's fold (not on master at 07:05). Then: merge master, queue the one Tron run (B, `vcpuwait433-tron.json`, A = 990012 on disk), read it, and do a final-head run for the fold.

## #433 -- 2026-10-03 08:04 PDT

[lane.vcpuwait433] **Tron B queued: `1-1791039792-vcpuwait433-947718`** (Nova, pinned, release tier, 720 s, ref 012fa08a94). It runs on a first-run route, not the returning one, because savestate433's fold has not reached the dispatcher yet. Prediction `vcpuwait433-tron-firstrun.json` (sha256 7c92e808...) supersedes `vcpuwait433-tron.json`, which was never queued. It keeps the same refs, A (990012) and legs M/O1/O2. Only B's route and leg V change.

Two harness defects. Each one alone would have voided the returning-route run for a known cause:

1. **The dispatcher workers do not run savestate433.** Workers 1275679/1275687 started 10-02 20:40 from `dispatch/bin/dispatcher.sh`, a snapshot dated 10-02 07:55 that has neither `title_state` nor `hdd.refused`. They re-exec only when `$TREE/docs/testing` changes, and `/home/justin/hakuX` is at 66bce0c222 (the routedriver2 fold, 10-02 08:45), 108 commits behind master. So on dispatched runs no `# state:` line is enforced and no golden is composed. That is true for every lane, not only this one. Tron's disk still holds the first-run leftover d2aff0a53543.
2. **Tron 2.0 has no `targets.toml` entry**, so `titlestate.py tid-for-iso "Tron 2.0 - Killer App (USA, Europe).iso"` returns nothing. With savestate433 live, request.sh refuses every Tron returning route ("the title is not identified"). A Tron first-run route gets `compose` with no title, which means **all goldens, Tron's included**, so Auto Load would be enabled. savestate433's proof passed `--title-id 42560001` by hand, which is why it never hit this.

Why the first-run route is valid now: `tron-newgame-firstrun.route` is A's route text minus the one DOWN (the v5 route). The stale dispatcher keeps d2aff0a53543, where Auto Load is greyed, so A on Single Player picks New Game and the run plays the intro: A's window, and tron2's (no profile, slow-row v_blk 9.93 against A's 9.80). The one confound left is A's golden profile against B's none. It touches O1/O2, not M.

**Request to lane.local:** if `/home/justin/hakuX` is refreshed before 947718 is claimed, withdraw 947718. Under savestate433 with Tron unidentified it would boot all goldens, take Auto Load into the level, and void on leg V. The fix for defect 2 is a `targets.toml` row for 42560001 with its iso name (board territory, not mine).

[lane.vcpuwait433] waiting: on `1-1791039792-vcpuwait433-947718` (Nova, behind pathfind's Black Stone hold). I read it with decompose.py against 990012, then queue the final-head run for the fold.

## #433 -- 2026-10-03 08:40 PDT

[lane.vcpuwait433] **Tron B `1-1791039792-vcpuwait433-947718` is VOID on leg V: it played the level, not the intro.** The route switch was my error. The menu-cursor frame shows Auto Load enabled and highlighted. Tron's disk save d2aff0a53543 is a real profile: savestate433's first-run proof harvested it after Tron wrote one. Attempt 4 read `titlestate.py show` as "first-run leftover, Auto Load greyed", and I reused that reading without checking a frame. With Auto Load enabled, the returning route's DOWN lands on New Game, so the route I replaced would have reached the intro even on the stale dispatcher. Guard, now in NOTES "Do not repeat": read a title's menu state from its last run's menu frame on that device, not from the store.

What the run does show (unregistered, descriptive):
- 12 min of Tron gameplay on the fix (012fa08a94 + ubershader): no BugCheck, no hang. Share 0.91, 29.5 fps, v_blk 6.93 ms/frame. The older in-level run 2186958 (no fix, no ubershader) read share 0.90, v_blk 5.70.
- So **in-level the vCPU still sleeps ~7 ms of a 34 ms frame with the fix**, with no visible drop. tron2 measured the site in the intro only, and the in-level sleep's site has never been measured.
- In-level Tron already clears the PM's 0.90 bar. The brief's 10-of-43 ms window is the in-engine intro, a cutscene.

The PR is ready (PR.md). The fix is correct (selftest with falsifier), pixel-inert (45/45 on the Thor), and ran gameplay clean. It removes a measured intro wait. No frame-rate gain is shown, and the release note says so. The fold's run at the final head is a Thor run of the 3 pixel suites, queued after the last commit.

Next, by P x win (all 3 Nova runs are used, so each needs lane.local's word):
- **B. In-level off-CPU capture** (`capture_offcpu.sh`, returning golden, HUD gate). P 0.85 that it names the in-level owner; tron2's method named the intro's. Win: points at gameplay's ~7 ms of 34, the kind of sleep BF2 has (21 of 64). Cost: 1 host-run capture.
- A. The intro A/B again on `tron-newgame-returning.route` (the DOWN). M 0.75 (down from 0.85, since 947718 shows no in-level drop), O1 0.4. Win: up to ~4 ms of the intro's 42 ms slow frame, in a cutscene. Cost: 1 Nova run and a new registration (the old V leg names 5489ae7f9b58).
B ranks first: its win is in gameplay.

Still open from 08:04: the dispatcher workers lack savestate433 (host tree 66bce0c222), and Tron has no `targets.toml` row.

[lane.vcpuwait433] waiting: on the fold's head run (Thor, 3 pixel suites, requester vcpuwait433, ref = the branch head), then on lane.local's fold. Nothing else is queued.
