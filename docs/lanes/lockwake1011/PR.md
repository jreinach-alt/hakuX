lockwake1011: NFS Most Wanted's cold race start, which pfifo.lock site holds the guest's last 2.2 ms, and a lock-free wake (#433, 0.5)
State: draft

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
- Cold `lockw` came in 0.65-0.8 below section 9's 2.19 / 2.35 (outside the brief's 0.3). The cold frame did not
  move. NOTES.md says so.

Decision (NOTES.md section 2): `HAKUX_LOCKFREE_WAKE=1`, default off. The PFIFO thread parks on a QemuEvent and a
posted store wakes it without pfifo.lock.

Built and checked at 39c6dacc5e (NOTES.md section 2): `selftest_wake.sh` passes in all three modes and its
falsifiers fail, the NDK compile adds no warning, and check_android_guards.py is ok.

A/B registered 2026-10-11T11:17:26Z (`lockwake1011-lockfree_wake.json`; reader `wakeread.py`). It is one binary at
39c6dacc5e with 3 runs per arm, queued A B B A A B. A is the stacked configuration and B adds
`HAKUX_LOCKFREE_WAKE=1`. K requires cold B <= 34.5 and B - A <= -0.5.

Release note (none): instrumentation, and an opt-in switch that is off by default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
