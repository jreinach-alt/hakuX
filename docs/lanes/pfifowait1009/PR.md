# pfifowait1009: stop holding pfifo.lock across the report-processing fence waits (#433, 0.5)

State: ready (FAIL -- fix measured unsafe on both legs, stays default-off; see NOTES.md sections 7-8)

Lane: pfifowait1009          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 4fbff52ae9 (merged into this branch)
Files: docs/lanes/pfifowait1009/NOTES.md, docs/lanes/pfifowait1009/PR.md, docs/lanes/pfifowait1009/WAITING, hw/xbox/nv2a/pgraph/vk/reports.c, docs/testing/titles/routes/amped2.route, docs/testing/predictions/pfifowait1009-pgraph-inert.json, docs/testing/predictions/pfifowait1009-amped2-soak.json
Prediction: pfifowait1009-pgraph-inert.json (a_ref=b_ref=221a22f5a8, disc 27 suites) -- FAIL, 16/1060 must_not_move violations, 2 reproducible (Stencil, confirmed with a runs=3 determinism check). pfifowait1009-amped2-soak.json (a_ref=b_ref=221a22f5a8, HAKUX_FRAMETRACE=1 vs +HAKUX_PFIFOWAIT=1, runs_per_arm 2) -- Miss (H1: no measurable pfifo.lock wait to shrink on this route revision) plus a correctness-flagged H2 failure (pgraph.lock wait roughly doubles) and P1 failure (fps falls, not rises, at matched work in the slow bins). Both registered before any scored arm, both now read in full.
Needs device: yes (Nova only, used)    Needs NDK: no

Release note (performance|stability|rendering|other|none): none -- opt-in switch HAKUX_PFIFOWAIT, off by default, and stays off: the measured result is a regression, not a win, so the switch does not flip and nothing changes for a player.

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
(NOTES.md section 4).

Six scored requests (brief step 5), all read against their pre-registered
predictions, plus a follow-up determinism check (two more requests, not
scored, `--no-expect`) to separate a real regression from single-run
device noise:

- **pgraph 27-suite disc A/B: FAIL.** 16/1060 captures moved. Most are
  small (1-800 px) `Vertex_shader_rounding_tests` movers, plausibly
  single-run noise. **`Stencil`'s 7 movers are not**: all 7 go from
  bit-exact to exactly 30,000 differing pixels, same magnitude, nothing
  else differing. A `--runs 3` determinism check on just those two
  suites confirms 2 of them are self-consistent on both arms (A: 0 px, 3
  runs in a row; B: 30,000 px, 3 runs in a row) -- reproducible, not
  noise. The lock-release bracket corrupts real GPU-visible state; see
  NOTES.md section 7a.
- **amped2 soak A/B (x2 runs/arm): Miss, plus a correctness flag.**
  `pfifo.lock` wait (the brief's `lw`) is ~0 on both arms on this route
  revision -- there is no large wait here for the fix to shrink (W1's
  premise does not hold on Amped 2 as currently routed). Worse:
  `pgraph.lock` wait -- a lock the fix's own code never touches, and
  which NOTES.md section 2's analysis said is never co-held at this call
  site -- roughly doubles with the flag on, at every matched work bin
  (`workbin.py`), and fps falls rather than rises in the slow bins the
  brief named as the problem (21-27+ ms/frame work). This is the
  prediction's own named vcpusleep-shape failure (wait relieved
  elsewhere, contention reappears downstream, fps down), worse than a
  plain Miss because H2 flags it as a correctness concern in the
  prediction text itself. NOTES.md section 7b.

**Conclusion (NOTES.md section 8): `HAKUX_PFIFOWAIT=1` stays default-off.**
It is measured unsafe (a real pixel regression) and does not move the
metric it was built to move (fps in slow windows, down not up) on the
title the brief named. Root-cause hypotheses for the Stencil regression
and the pgraph.lock growth, unconfirmed and not spent on more device
time since the ship/no-ship question is already answered: NOTES.md
section 7c.

NFS Most Wanted (second title) was deliberately not queued: the fix
already failed decisively on title 1 on both legs, so a second title's
pair cannot change the ship/no-ship answer and would be device time
spent ahead of a decision the data cannot still swing (NOTES.md section
7d).

This PR is the negative result and the registered evidence for it, kept
on this branch (switch default-off, no behavior change for any player)
for whichever lane next picks up #433's candidate list.
