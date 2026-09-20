# lane.drvab77 -- does the stipple rate move with the GPU driver?

Issue: #77 (Galleon deck/ground stipple, 10-14 stipple frames per 100)
Base: master (post PR #165, lane.diagsoak77's frame-dump correlation)
Files: none. This lane edits no in-repo source file; it runs existing tools
against device soaks and posts a reading. Do not touch
hw/xbox/nv2a/pgraph/vk/draw.c or vk/blit.c -- reading them for the next
lane's benefit is fine, editing them is the follow-up this lane must NOT do.

## What's already done, and why this is not that

lane.diagsoak77 (PR #165, merged) built and validated `stipple_classify.py`
(docs/lanes/diagsoak77/), which replaces `galleon_flash_rate.py`'s default
bar -- that bar manufactures a false 13.3-per-100 reading on a smooth,
non-hatched sequence, which is exactly the failure mode a driver A/B must not
inherit. It also established that an unattended soak reliably reaches a
demo-cave scene (t ~165s+) that shows the artifact at a *measured*, gameplay
comparable rate: 6.6 to 16.4 per 100 across four same-driver arms. That
scene, and that classifier, did not exist the last time anyone asked whether
the driver matters.

The driver question WAS asked before either existed: four arms at
`c866527e03`, T30/T26/stock, 180s each. It came back void -- V0 (does the
artifact even fire) failed on both Turnip arms, because those soaks did not
reach a scene with enough texture detail under the old bar. That result is
about the old instrument and the old soak length, not about the driver, and
nv2a_issues.toml's issue.77 blocked_on field says so explicitly. This lane is
the same question asked with the instrument that now works.

## Goal

Using `~/hakux-work/drv/swap_driver.sh` (arms `t30`, `t26`, `stock`; restores
T30 on exit) and a `request.sh --title` soak long enough to reach the
demo-cave scene (diagsoak77's arms used `600,after165,cap200` -- reuse that
spec unless the dump shows a reason not to), take at least two runs per
driver arm (single-run claims on this issue have already produced one
withdrawn conclusion -- see #77's own history) and score each with
`stipple_classify.py`, not the old default-`k` tool. Compare the per-100
stipple rate across the three drivers.

## Falsifier

Pre-register, before any run: if the three drivers' rate ranges overlap
(each arm's runs land inside the same band the same-driver replicates
already span -- 6.6 to 16.4 per 100 is the existing same-driver spread).
that is a null result and refutes driver-dependence, not a failed lane. A
result counts as implicating the driver only if one arm's range sits
clearly outside that same-driver spread across at least two runs of that
arm -- one outlying run is exactly the trap #77's history has already fallen
into once.

## Done when

Rate table (driver x run x rate) posted to #77, verdict stated as one of:
driver-dependent (name which arm and by how much), or refuted at the stated
sensitivity -- plus the run/session ids so the numbers can be re-derived. Do
not chase the content/mip-level hypothesis diagsoak77 named as the next
instrument after this -- that needs a code change and is a separate,
not-yet-dispatched follow-up.
