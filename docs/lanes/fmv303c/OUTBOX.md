## #303 -- 2026-10-04 13:10 PDT

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
