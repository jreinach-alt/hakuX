# vcpuwait433: a guest read of the PFIFO USER registers no longer waits out a GPU batch (Tron 2.0's slow-frame vCPU sleep)
State: draft

Lane: vcpuwait433       Issue: #433
Base: master @ 5661db4f2b (merged into the branch at ef511dbd19; first base 9550493846)
Files: hw/xbox/nv2a/user.c, hw/xbox/nv2a/pfifo.c, docs/testing/predictions/vcpuwait433-pixels.json, docs/testing/predictions/vcpuwait433-tron.json, docs/lanes/vcpuwait433/PR.md, docs/lanes/vcpuwait433/NOTES.md, docs/lanes/vcpuwait433/OUTBOX.md, docs/lanes/vcpuwait433/capture_offcpu.sh, docs/lanes/vcpuwait433/waitsite.py, docs/lanes/vcpuwait433/decompose.py, docs/lanes/vcpuwait433/tron-newgame.route, docs/lanes/vcpuwait433/tron-newgame-returning.route, docs/lanes/vcpuwait433/levelcheck.py, docs/lanes/vcpuwait433/userread-lockless.diff, docs/lanes/vcpuwait433/selftest_userread.sh
Prediction: docs/testing/predictions/vcpuwait433-pixels.json @ 51885311070260918a53796ec4038db00d1a3a6173d5c3867df6ca9ca62045a9; docs/testing/predictions/vcpuwait433-tron.json @ 020b10df7f6e66dee2854093439e952d76b833a59b65f676926452534ead8d77
Needs device: yes (Thor: 2 pixel arms; Nova: 3rd of 3 runs, Tron)    Needs NDK: yes

[lane.vcpuwait433] waiting: on (1) the Thor pixel arms 1-1791035760-vcpuwait433-4105238 (B) and 1-1791035764-vcpuwait433-4105418 (A), and (2) savestate433's fold. Only after that fold is the Tron arm's `# state: returning` enforced. Tron's disk now holds the first-run state, in which the arm's route would void. Once savestate433 is on master: merge master, queue the Tron B run (prediction vcpuwait433-tron.json), then read all three.

**The site.** In Tron 2.0's slow window (the New Game intro; tron2, 60 s at 27.9 fps), 65.2% of the vCPU's attributed off-CPU time is `pfifo.lock` in USER MMIO, and 95.5% of that is `user_read`, a guest load of DMA_GET, DMA_PUT or REF. In a 60-fps menu the same site is under 3%. The holder is the PFIFO thread. It calls `pgraph_process_pending_reports` with pfifo.lock held, and when DMA_GET == DMA_PUT that call does `pgraph_vk_finish(STALLED)`, which sleeps until the render thread submits. The per-tid pass puts the PFIFO thread asleep for >= 86% of the vCPU's waits. The word the guest is waiting to read does not change in that time.

**The fix** (012fa08a94, user.c 25+/14-, pfifo.c 1 line). `user_read` takes no lock and uses acquire loads of DMA_PUT/GET/REF. `user_write` keeps the lock and stores with release, and `pfifo_run_pusher` publishes DMA_GET with a release store. Each word has one writer on the other side, so acquire/release gives the read the ordering the lock did. This is #474's pattern: MMIO no longer waits behind a GPU-paced hold.

**A/B design.** The A for Tron is already on disk. uberdefault569's Tron B rerun (990012) is master's emulator code with the ubershader on, run on the golden profile. With that profile, its route's DOWN lands on New Game and the run plays the intro. Its numbers: share 0.82; slow rows F 42.2, v_blk 9.80 ms/frame (tron2 9.93, near30 ~10). B repeats the request at 012fa08a94 on the same route text, which declares `# state: returning`. Legs: M (mechanism) slow-row v_blk <= 7.0, P 0.85; O1 share >= 0.87 and fps +5%, P 0.45; O2 share >= 0.90, P 0.3.

Local checks (no CI offline):
- `bash docs/lanes/vcpuwait433/selftest_userread.sh`: PASS. It compiles the real user.c with `-Wall -Werror` (real atomic.h, nv2a_regs.h, stub nv2a_int.h). With the fix, the three reads return in 0 ms while pfifo.lock is held for 400 ms; a write still waits 402 ms; the PUT store is visible to the next read; the pfifo.c GET store is a release store. The pre-fix user.c blocks 400-405 ms on each read, which is the harness's falsifier.
- `docs/testing/preflight.sh --allow-tracker` at ab8b4646be: passed (territory ok, board files ok, nv2a index ok). The coverage gate did not run: gh is suspended.
- NDK build: none yet. The arms build 012fa08a94.

| Next | P | win | cost |
|---|---|---|---|
| **A. Tron arm (Nova), after savestate433 folds** | M 0.85; O1 0.45; O2 0.3. For: the read no longer waits (selftest), and tron2 put 65% of the window's sleep there. Against: the guest may then wait on GPU output in RAM, which turns freed sleep into spin | up to ~4 ms of a 42 ms slow frame; share 0.82 -> 0.87-0.90 | 1 Nova run |
| B. Release pfifo.lock across the STALLED finish | 0.3: also covers the DMA_PUT store (4.5%), but exposes renderer state to the display thread | <= A + 4.5% | grant (vk/reports.c), build, goldens, arm |
| C. If M passes and O1 fails: capture B | 0.8 that it names where the freed time goes | picks between B and a report-path fix | 1 run beyond the brief's 3 |

Release note (performance): in Tron 2.0's in-engine scenes, and in any game whose CPU polls the GPU's command-queue position, the CPU no longer stalls while the GPU finishes a frame (measured gain pending the Tron arm).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
