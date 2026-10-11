lockwake1011: NFS Most Wanted's cold race start, which pfifo.lock site holds the guest's last 2.2 ms, and a lock-free wake (#433, 0.5)
State: draft

Lane: lockwake1011      Issue: #433 (umbrella), none filed
Base: master @ 72b4b07b77 (+ lane/coldstart1010 @ 87c58dee10, merged)
Files: hw/xbox/nv2a/pfifo.c, hw/xbox/nv2a/user.c, hw/xbox/nv2a/nv2a_int.h, hw/xbox/nv2a/nv2a.c, hw/xbox/nv2a/debug.h, hw/xbox/nv2a/pgraph/profile.h, hw/xbox/nv2a/pgraph/profile.c, docs/lanes/lockwake1011/**, docs/testing/predictions/lockwake1011-*
Prediction: none yet (registered before the A/B is queued)
Needs device: yes (Nova)
Needs NDK: yes

Step 1 splits `lock_wait_ns` by site (`pfifo_post_kick`, and `user_write`'s locked branch by register) and
wraps both acquisitions in a frametrace wait. Step 2 builds the fix behind a default-off switch and A/Bs it.

Release note (none): instrumentation, and an opt-in switch that is off by default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
