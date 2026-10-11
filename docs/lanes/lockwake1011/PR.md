lockwake1011: NFS Most Wanted's cold race start, which pfifo.lock site holds the guest's last 2.2 ms, and a lock-free wake (#433, 0.5)
State: ready

Lane: lockwake1011      Issue: #433 (umbrella), none filed
Base: master @ b9212b3462 (coldstart1010 folded; merged into the lane at b110cb4e90)
Files: hw/xbox/nv2a/pfifo.c, hw/xbox/nv2a/user.c, hw/xbox/nv2a/nv2a_int.h, hw/xbox/nv2a/nv2a.c, hw/xbox/nv2a/debug.h, hw/xbox/nv2a/pgraph/profile.h, hw/xbox/nv2a/pgraph/profile.c, docs/lanes/lockwake1011/**, docs/testing/predictions/lockwake1011-*
Prediction: docs/testing/predictions/lockwake1011-lockfree_wake.json @ 83d720359997fcf9e6d79682047912da7bb6ccb9604f6691ef62c66c181f2ead
Needs device: yes (Nova)
Needs NDK: yes

Step 1 splits `lock_wait_ns` by site (`pfifo_post_kick`, and `user_write`'s locked branch by register) and
wraps both acquisitions in a frametrace wait. Step 2 builds the fix behind a default-off switch and A/Bs it.

Step 1 is built and checked (NOTES.md section 0): frametrace's selftest and this lane's `selftest_wake.sh` pass,
and the NDK compile under the dispatcher's flags is clean.

Census (NOTES.md section 1; 0-1791714330-lockwake1011-1625482 and 0-1791714331-lockwake1011-1625531, stacked
configuration plus `HAKUX_FRAMETRACE=1`, at ee62b4edb5, 12/12 marks each):

| ms per frame | cold | warm | post-GO |
|---|---|---|---|
| `lockw` | 1.53 / 1.57 | 0.64 / 0.81 | 0.31 / 0.19 |
| `kick` (`pfifo_post_kick`) | 1.53 / 1.57 | 0.64 / 0.81 | 0.31 / 0.19 |
| `put`, `get`, `ref`, `oth` | 0 | 0 | 0 |
| ended with the PFIFO thread parked | 1.49 / 1.57 | 0.63 / 0.80 | 0.30 / 0.19 |

- The whole wait is the posted store's wake to a parked PFIFO thread, in waits of 5.4-5.5 ms on 28 % of cold
  frames.
- The lock is held by a third thread: inferred to be the display refresh's `vkWaitForFences` under pfifo.lock in
  `pgraph_vk_get_framebuffer_surface()`.
- **Caveat on this table:** cold `lockw` came in 0.65-0.8 below section 9's 2.19 / 2.35. That is outside the
  brief's 0.3, so the instrument may have changed the regime, and two runs a side cannot rule it out. The cold frame
  did not move (census `P` 34.67 / 34.96 against 34.85 / 35.27).
  - The split was taken anyway (NOTES.md section 1). What is left, 1.55 ms a frame, is above the 1.0 stop line.
  - The 100 % share is one site in both runs, and a share does not depend on the level.
  - Read the levels in this table as the instrumented run's, not section 9's.

Decision (NOTES.md section 2): `HAKUX_LOCKFREE_WAKE=1`, default off. The PFIFO thread parks on a QemuEvent and a
posted store wakes it without pfifo.lock.

Built and checked at 39c6dacc5e (NOTES.md section 2): `selftest_wake.sh` passes in all three modes and its
falsifiers fail, the NDK compile adds no warning, and check_android_guards.py is ok.

A/B registered 2026-10-11T11:17:26Z (`lockwake1011-lockfree_wake.json`; reader `wakeread.py`). It is one binary at
39c6dacc5e with 3 runs per arm, queued A B B A A B. A is the stacked configuration and B adds
`HAKUX_LOCKFREE_WAKE=1`. K requires cold B <= 34.5 and B - A <= -0.5.

**A/B verdict: PASS, 5 of 5** (NOTES.md section 3; `ab_wakeread.txt`). All six runs are 12/12 marks, with
`[lockwake] on` on B only and a moving car in the g11 frames:

| ms per frame, mean of 3 | cold start 1 | warm countdown | post-GO |
|---|---|---|---|
| A (stacked configuration) | 34.54 (34.7 / 34.1 / 34.8) | 33.55 | 33.36 |
| B (+ `HAKUX_LOCKFREE_WAKE=1`) | **33.58** (33.8 / 33.5 / 33.4) | 33.56 | 33.37 |
| B - A | **-0.96** | +0.01 | +0.01 |

| leg | rule | verdict | predicted P |
|---|---|---|---|
| K | cold B <= 34.5 and B - A <= -0.5 | PASS (33.58, -0.96) | ~45 % |
| C | cold B - A <= -0.5 | PASS | ~55 % |
| W | warm B - A <= +0.2 | PASS (+0.01) | ~85 % |
| G | post-GO B - A <= +0.2 | PASS (+0.01) | ~90 % |
| M | every B run reaches 12 marks | PASS | ~95 % |

- Every B run is below every A run at the cold start. The point estimate was B 33.9 +- 0.8 and B - A -0.9.
- Cold B now equals warm B. The guest's pfifo.lock wait was the cold residual, and the wake did not leave the
  PFIFO thread's start as a bound. So OUTBOX.md's fence-wait release has no measured win left at this scene.
- The site table above is the instrumented runs' (see its caveat). The verdict does not rest on it: the A/B is a
  plain build and reads the frame.

Hang checks (NOTES.md section 4), B's env, 120 s each:
- Halo CE (0-1791717723-lockwake1011-2002180) ran into its attract demo at ~30 fps to the end.
- JSRF (0-1791717725-lockwake1011-2002610) ran in gameplay at 60 fps to the end.
- No crash or hang in either. JSRF's last capture is the soak's teardown (Android Settings), as on a switch-off
  fastpaths1010 run.

Next step (NOTES.md section 5), ranked by P x win:
1. A cross-title screen of `HAKUX_POSTED_PUT` + `HAKUX_LOCKFREE_WAKE` + `HAKUX_SUBMIT_FRAMES=3` for default-on.
   P 0.6. All three are default-off, so none of NFS MW's 37.93 -> 33.6 reaches a player yet.
2. The fence-wait release (OUTBOX.md). P 0.25. Census a title whose PFIFO thread is the bound first.
3. NFS MW's warm countdown against the floor: 0.18 ms, not worth device time now.

Release note (none): instrumentation, and an opt-in switch that is off by default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
