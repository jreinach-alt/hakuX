## #303 -- 2026-10-04 12:35 PDT

[lane.fmv303c] The owner lifted the 0.5 park, so the surface write-back arm is
running. origin/master is merged at cf328d86f7, and the probe now also covers
master's deferred-download path. The prediction
`docs/testing/predictions/fmv303c-wb-probe.json` is registered on that ref.
Two Thor soaks are queued: 1791142591-lane.fmv303c-697274 and
1791142595-lane.fmv303c-698913 (Spikeout, 150 s, `HAKUX_FMV303_PROBE=1`).
Predicted: EXONERATED, P about 0.65.

Territory: before folding, this lane needs a shared grant of
`hw/xbox/nv2a/pgraph/vk/surface.c`, which lane.async794 holds. The hunk is
already on the branch and is gated on the env variable. If the arm reads HIT,
the fix is a second hunk in the same file.

## #303 -- 2026-10-04 12:40 PDT

[lane.fmv303c] Both Thor runs (1791142591-lane.fmv303c-697274,
1791142595-lane.fmv303c-698913) were refused before start with
`display-covered: ... primaryScreenTopLayout (com.odin.dualscreen.assistant,
BOOT_PROGRESS)`. This is the AYN dual-screen overlay from 09-27
(`dual_screen_display_mode=2`). It is probably left over from the owner's
Spikeout hand test today. For hostops / lane.local: please clear it with
`device_reality.sh --fix` on the idle Thor, which restores mode 0. Until
then, every Thor soak is refused. The lane re-queues the two runs after
13:40 PDT.
