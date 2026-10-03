# vcpuwait433: a guest read of the PFIFO USER registers no longer waits out a GPU batch (Tron 2.0's intro vCPU sleep)
State: ready

Lane: vcpuwait433       Issue: #433
Base: master @ 6c828f9860 (merged into the branch at 26eb8db032; earlier cfa37a359e at 4148fd3831; first base 9550493846)
Files: hw/xbox/nv2a/user.c, hw/xbox/nv2a/pfifo.c, docs/testing/predictions/vcpuwait433-pixels.json, docs/testing/predictions/vcpuwait433-tron.json, docs/testing/predictions/vcpuwait433-tron-firstrun.json, docs/lanes/vcpuwait433/PR.md, docs/lanes/vcpuwait433/NOTES.md, docs/lanes/vcpuwait433/OUTBOX.md, docs/lanes/vcpuwait433/capture_offcpu.sh, docs/lanes/vcpuwait433/waitsite.py, docs/lanes/vcpuwait433/decompose.py, docs/lanes/vcpuwait433/tron-newgame.route, docs/lanes/vcpuwait433/tron-newgame-returning.route, docs/lanes/vcpuwait433/tron-newgame-firstrun.route, docs/lanes/vcpuwait433/levelcheck.py, docs/lanes/vcpuwait433/userread-lockless.diff, docs/lanes/vcpuwait433/selftest_userread.sh
Prediction: docs/testing/predictions/vcpuwait433-pixels.json @ 51885311070260918a53796ec4038db00d1a3a6173d5c3867df6ca9ca62045a9 (PASS); docs/testing/predictions/vcpuwait433-tron-firstrun.json @ 7c92e808e99436d2d5320c5d05aa093aab66ead111349362cfad85c135fa0b9b (VOID on leg V); docs/testing/predictions/vcpuwait433-tron.json @ 020b10df7f6e66dee2854093439e952d76b833a59b65f676926452534ead8d77 (superseded, never queued)
Needs device: yes (Thor: 2 pixel arms + the head run; Nova: 3 of 3 runs used)    Needs NDK: yes

**What it changes.** In Tron 2.0's slow intro window (tron2, 60 s at 27.9 fps), 65.2% of the vCPU's attributed off-CPU time is `pfifo.lock` in USER MMIO, and 95.5% of that is `user_read`, a guest load of DMA_GET, DMA_PUT or REF. The holder is the PFIFO thread, asleep in the `pgraph_vk_finish(STALLED)` that `pgraph_process_pending_reports` runs with pfifo.lock held when DMA_GET == DMA_PUT. During that time the word the guest is waiting to read does not change. The fix (012fa08a94, user.c 25+/14-, pfifo.c 1 line): `user_read` takes no lock and uses acquire loads. `user_write` keeps the lock and stores with release. `pfifo_run_pusher` publishes DMA_GET with a release store. This is #474's pattern.

**What is measured.**

| leg | run(s) | result |
|---|---|---|
| pixels (Thor, 3 surface-coherence suites) | B 1-1791035760-vcpuwait433-4105238 / A 1-1791035764-vcpuwait433-4105418 | **PASS**: 45/45 captures byte-identical |
| Tron intro A/B (Nova) | B 1-1791039792-vcpuwait433-947718 against A 990012 | **VOID on leg V.** Tron's disk held a profile (d2aff0a53543, Auto Load enabled). The first-run route's A took Auto Load into the level, not the intro. I chose that route by misreading `titlestate.py show`; the returning route's DOWN would have landed on New Game |
| Tron in-level (same run, unregistered) | 947718 against 2186958 (older build, no ubershader) | 12 min of gameplay, no BugCheck or hang. Share 0.91 (2186958: 0.90). v_blk 6.93 ms/frame (5.70): no drop in the in-level sleep is visible. The in-level site was never measured |

So the fix is correct and pixel-inert, and it removes a measured intro wait. **No frame-rate gain is shown.** In-level Tron already clears the 0.90 bar.

**Harness defects found (OUTBOX 08:04):**
1. The dispatcher workers run a 10-02 snapshot, re-made only from `/home/justin/hakuX` (66bce0c222, 108 commits behind master). savestate433's state step is not live on dispatched runs.
2. Tron 2.0 has no `targets.toml` row. Under savestate433, its returning route is refused, and its first-run route boots all goldens.

Local checks (no CI offline):
- `bash docs/lanes/vcpuwait433/selftest_userread.sh`: PASS at this head. It compiles the real user.c with `-Wall -Werror`. With the fix, reads return in 0 ms while pfifo.lock is held for 400 ms, and a write still waits. The pre-fix user.c blocks 400 ms on each read.
- `docs/testing/preflight.sh --allow-tracker` at this head: passed (psh_differ, aci_vmstate, nv2a index, territory and board files ok). The coverage gate did not run: gh is suspended.
- NDK build: 012fa08a94 built and ran in pixel arm B and in 947718 (apk b43d7cbb8930).
- The fold's run at this head: a Thor run of the 3 pixel suites, requester vcpuwait433, queued after this commit with `--ref` = this head. The previous head run (1-1791041533-vcpuwait433-1316447, ac52966d30) is DONE, and all 45 rows match pixel arm B. The head moved only for the master merge (clean) and NOTES.

| Next | P | win | cost |
|---|---|---|---|
| **B. In-level off-CPU capture** (capture_offcpu.sh, returning golden, HUD gate) | 0.85 that it names the in-level owner; tron2's method named the intro's | knowledge toward gameplay's ~7 ms of a 34 ms frame, the kind of sleep BF2 shows (21 of 64) | 1 host-run capture |
| A. The intro A/B again, on the returning route (with the DOWN) | M 0.75, O1 0.4. Down from 0.85: 947718 shows no in-level drop | up to ~4 ms of the intro's 42 ms slow frame, in a cutscene | 1 Nova run (the lane's 4th) and a new registration |

B ranks first: its win is in gameplay, and A's is in a cutscene.

Release note (other): a game's CPU no longer waits for the GPU to finish a frame before it can read the GPU's command-queue position. No frame-rate change is measured yet: Tron 2.0 gameplay is unchanged, and the intro scene it targets is not yet measured.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
