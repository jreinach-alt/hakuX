# pfifowait1009: stop holding pfifo.lock across the report-processing fence waits (#433, 0.5)

State: waiting (route proved pacing-robust both ways, scored A/B arms queued, not yet read -- see NOTES.md sections 4-5)

Lane: pfifowait1009          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ f9eabe4ebf (merged into this branch)
Files: docs/lanes/pfifowait1009/NOTES.md, docs/lanes/pfifowait1009/PR.md, docs/lanes/pfifowait1009/WAITING, hw/xbox/nv2a/pgraph/vk/reports.c, docs/testing/titles/routes/amped2.route, docs/testing/predictions/pfifowait1009-pgraph-inert.json, docs/testing/predictions/pfifowait1009-amped2-soak.json
Prediction: pfifowait1009-pgraph-inert.json (a_ref=b_ref=221a22f5a8, disc 27 suites), pfifowait1009-amped2-soak.json (a_ref=b_ref=221a22f5a8, HAKUX_FRAMETRACE=1 vs +HAKUX_PFIFOWAIT=1, runs_per_arm 2) -- both registered before any scored arm, both now queued, neither yet read
Needs device: yes (Nova only)    Needs NDK: no

Release note (performance|stability|rendering|other|none): none -- opt-in switch HAKUX_PFIFOWAIT, off by default; nothing changes for a player until an arm confirms the fix and the switch flips.

## What changed

`hw/xbox/nv2a/pgraph/vk/reports.c`, `pgraph_vk_process_pending_reports`:
when `HAKUX_PFIFOWAIT=1` (read once, default off), `pfifo.lock` is released
immediately before the single `pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED)`
call and retaken immediately after it returns. That one call is where both of
the brief's named GPU fence waits live (the frame-slot rotation wait inside
`pgraph_vk_finish`, and the #804 occlusion `vkWaitForFences`/
`vkGetQueryPoolResults` loop its `_internal` tail-call runs) -- bracketing the
whole call covers both without needing to locate each wait individually.
`pgraph.lock` is never held at this call site (confirmed by reading, not
assumed), so there is nothing of the brief's shape (b) to do here; shape (a),
scoped to this one call, is the fix. Full lock analysis, why this does not
need `#474`/`#796`'s flag+cond pattern, and the explicit guard against
vcpusleep's prior-art regression (wait relieved but fps flat/down): NOTES.md
section 2.

`docs/testing/titles/routes/amped2.route`: committed (did not exist on disk;
recovered per Addendum 1 from the request that originally generated it),
then made pacing-robust for the deterministic menu phase (steps 1-12,
settle waits widened 4x/floored at 20s after a `waitfor`-based attempt was
found not to reach a dispatched run at all -- `request.sh`/`route.sh`'s
`refs/` staging gap, NOTES.md section 1 "CORRECTION"). Steps 13-25 and the
genre loop are unchanged from the verbatim original; no device evidence
ties either of pmucounters' two void causes to that phase's timing
specifically, and a `waitfor`-based gameplay-HUD checkpoint does not
discriminate (NOTES.md section 1, "What I did NOT robustify").

## Measurements

Two pacing-robustness runs (brief step 4, not scored): baseline pacing
and the fix's own (different) pacing both complete the route end to end,
no `ROUTE FAIL`, no crash/ANR, player confirmed in motion in both
(NOTES.md section 4). Six scored requests queued (brief step 5): pgraph
27-suite disc A/B and amped2 soak A/B x2 runs, all against pre-registered
predictions -- not yet read, see WAITING.

NFS Most Wanted (second title, route read from `lane/perdraw1009`) is not
yet queued: needs its own prediction registered first; planned after this
batch reads.
