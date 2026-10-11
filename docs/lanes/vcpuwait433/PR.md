# vcpuwait433: a guest read of the PFIFO USER registers no longer waits out a GPU batch (Tron 2.0's intro vCPU sleep)
State: ready

Lane: vcpuwait433       Issue: #433
Base: master @ a143aa5db8 (merged into the branch at 05f5cbf201; earlier 6c828f9860, cfa37a359e; first base 9550493846)
Files: hw/xbox/nv2a/user.c, hw/xbox/nv2a/pfifo.c, docs/testing/predictions/vcpuwait433-pixels.json, docs/testing/predictions/vcpuwait433-tron.json, docs/testing/predictions/vcpuwait433-tron-firstrun.json, docs/testing/predictions/vcpuwait433-tron-anystate.json, docs/lanes/vcpuwait433/PR.md, docs/lanes/vcpuwait433/NOTES.md, docs/lanes/vcpuwait433/OUTBOX.md, docs/lanes/vcpuwait433/capture_offcpu.sh, docs/lanes/vcpuwait433/waitsite.py, docs/lanes/vcpuwait433/decompose.py, docs/lanes/vcpuwait433/tron-newgame.route, docs/lanes/vcpuwait433/tron-newgame-returning.route, docs/lanes/vcpuwait433/tron-newgame-firstrun.route, docs/lanes/vcpuwait433/tron-newgame-anystate.route, docs/lanes/vcpuwait433/levelcheck.py, docs/lanes/vcpuwait433/userread-lockless.diff, docs/lanes/vcpuwait433/selftest_userread.sh
Prediction: docs/testing/predictions/vcpuwait433-tron-anystate.json @ 7906cac1bcb687d71eb4bea21ac4ae762bf0f19f3479569a25171dfb7fa736d1 (B 1791044179-vcpuwait433-2251972: V PASS, M FAIL, O1 FAIL, O2 FAIL); docs/testing/predictions/vcpuwait433-pixels.json @ 51885311070260918a53796ec4038db00d1a3a6173d5c3867df6ca9ca62045a9 (PASS); docs/testing/predictions/vcpuwait433-tron-firstrun.json @ 7c92e808e99436d2d5320c5d05aa093aab66ead111349362cfad85c135fa0b9b (VOID on leg V); docs/testing/predictions/vcpuwait433-tron.json @ 020b10df7f6e66dee2854093439e952d76b833a59b65f676926452534ead8d77 (superseded by -anystate, never queued: request.sh refuses its returning route)
Needs device: yes (Thor: 2 pixel arms + head runs; Nova: 4 runs, one past the brief's 3)    Needs NDK: yes

**What it changes.** In Tron 2.0's slow intro window (tron2, 60 s at 27.9 fps), 65.2% of the vCPU's attributed off-CPU time was `pfifo.lock` in USER MMIO, and 95.5% of that was `user_read`: a guest load of DMA_GET, DMA_PUT or REF. The holder was the PFIFO thread, asleep in the `pgraph_vk_finish(STALLED)` that `pgraph_process_pending_reports` runs with pfifo.lock held when DMA_GET == DMA_PUT. While it sleeps, the word the guest is waiting to read does not change. The fix (012fa08a94; user.c 25+/14-, pfifo.c 1 line) follows #474's pattern: `user_read` takes no lock and uses acquire loads. `user_write` keeps the lock and stores with release. `pfifo_run_pusher` publishes DMA_GET with a release store.

**What is measured.**

| leg | run(s) | result |
|---|---|---|
| pixels (Thor, 3 surface-coherence suites) | B 1-1791035760-vcpuwait433-4105238 / A 1-1791035764-vcpuwait433-4105418 | **PASS**: 45/45 captures byte-identical |
| Tron intro A/B (Nova) | B 1791044179-vcpuwait433-2251972 against A 1-1790994313-uberdefault569-990012 | **V PASS** (menu-down frame on New Game, intro frames, all goldens, mode=3, PLC wiped, 261 rows). **M FAIL:** slow-row vCPU sleep 9.29 ms/frame against A's 9.80; the bar was <= 7.0. **O1/O2 FAIL:** share 0.71 (A 0.82, within near30's 0.50-0.73 single-soak spread), all-row fps 35.87 (A 35.58) |
| Tron intro A/B, first try | B 1-1791039792-vcpuwait433-947718 | VOID on leg V: Auto Load took it into the level. Descriptive in-level read: share 0.91, vCPU sleep 6.93 ms/frame, 12 min clean |

So the fix is correct and pixel-inert, and it has run 24 min of Tron on the Nova without a BugCheck or hang. **It does not remove the vCPU's intro sleep.** The slow-row sleep fell 0.5 ms, not the ~3 ms tron2 attributed to the read. v_run is flat (31.30 -> 31.43), so the time did not turn into spin. The vCPU sleeps at a second site. The likeliest by mechanism (unmeasured) is the guest's DMA_PUT store: `user_write` still takes pfifo.lock, which the stalled finish holds.

**Why fold an inert change.** It is correct and costs nothing at run time, and the next step needs it. A capture of this sleep on a build that still has the locked read rediscovers tron2's 65% site and hides the layer beneath.

**Harness defects found (OUTBOX 08:04, 09:25):** (1) the dispatcher ran a stale snapshot without savestate433. That was resolved by 09:13. (2) Tron 2.0 has no `targets.toml` row, so request.sh refuses its returning route. This is filed as a NEW ISSUE in OUTBOX. The workaround is `# state: any`.

Local checks (no CI offline), at this head:
- `bash docs/lanes/vcpuwait433/selftest_userread.sh`: PASS. It compiles the real user.c with `-Wall -Werror`. With the fix, reads return in 0 ms while pfifo.lock is held for 400 ms, and a write still waits. The pre-fix user.c blocks 400 ms on each read (the falsifier).
- `docs/testing/preflight.sh --allow-tracker` at this head: passed (psh_differ, aci_vmstate, nv2a index, territory, coverage and board files ok).
- NDK build: 012fa08a94 built and ran in pixel arm B, 947718 and 2251972 (apk b43d7cbb8930). Earlier head runs 1316447 (ac52966d30) and 1774257 (4f74f7512a) each matched pixel arm B on all 45 rows. The final-head run (Thor, the same 3 suites, requester vcpuwait433) is queued right after this commit, with `--ref` set to this commit. Nothing is committed after it, so its ref is the branch head.

| Next | P | win | cost |
|---|---|---|---|
| **A. BF2 gameplay off-CPU capture** on master with this fix (capture_offcpu.sh, fail-closed gate) | 0.6 that one site holds >= 50% (the method named Tron's intro owner; Tron's sleep proved layered) | names the owner of 21 ms of a 64 ms gameplay frame, in a title below the bar | 1 host capture + a BF2 in-level gate |
| B. Tron in-level capture | 0.85 that it names the owner | ~7 ms of a 34 ms gameplay frame; Tron already clears 0.90 | 1 host capture |
| C. Tron intro capture on this build | 0.85 that it names the second site | decides D; knowledge about a cutscene | 1 host capture |
| D. Release pfifo.lock across the stalled finish | 0.25 (the next layer is unmeasured; renderer-state risk) | <= ~3 ms of a 42 ms cutscene frame | grant vk/reports.c, build, goldens, Nova arm |

A ranks first by P x win. C goes first only if D is chosen, because C decides D.

Release note (other): a game's CPU no longer waits for the GPU to finish a frame before it can read the GPU's command-queue position. No frame-rate change was measured: Tron 2.0's intro and gameplay run as before.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
