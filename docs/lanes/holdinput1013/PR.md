# pathfind: a drive hold proves its gas, gets a stuck vehicle out, acts on an on-screen prompt, and tries every unstick rung; the verdict does not read a parked vehicle as travel (#433, 0.5)

State: draft

Lane: holdinput1013            Issue: #433
Base: master @ d2bcaacd22
Files: docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py, docs/lanes/holdinput1013/fixtures/4x4evo2/*
Prediction: none: analysis-only (test-harness input/measurement logic only, not emulator code; no pixel-moving claim)
Needs device: no    Needs NDK: no

Fixes five input-handling defects behind four failed/misjudged Nova hold runs on 2026-10-13 (ATV Quad Power
Racing 2, 4x4 Evo 2, Darkwatch, Genma Onimusha). Parts A-C and E are in `pathfind.py`; Part D is in
`hitch_report.py`. Landing in order, one commit per part.

## Part A -- COMPLETE (cd55eafedf)
ATV's probe accepted RT as gas (control 0.001, under input 0.094) when RT is actually the game's jump preload;
the speedometer never moved. Added `Agent.confirm_gas()`: tries RT, A, X, then the title's `TITLE_HOLD` gas
fallback, each checked against `gas_change()` (a band-masked `window_change` over the lower ~45% of the frame,
`GAS_MOVE_BAND`/`GAS_MOVE_BAR`) rather than accepting the probe's own control/under-input numbers. The drive
loop (`drive_tokens(gas)`) is now built from the confirmed candidate everywhere a drive loop is built,
including the still-window unstick rotation branch, which this session found was still hardcoded to
`HOLD_GENRES["drive"]` (RT) even after gas confirmation -- a requirement-3 gap the prior session's state had not
flagged; fixed in this same commit.

Measurements behind the fix (band change, `gas_change`): ATV RT 0.0226 (refused, correctly -- it's preload, not
gas); Auto Modellista RT stalled 0.0018; Panzer Elite RT 0.0591; RalliSport Challenge 2 RT 0.1246; Conflict
Desert Storm II RT 0.1656. Zero ledger-banked Playable runs are `genre=="drive"` today, so there was no banked
regression risk from tightening gas confirmation.

## Part B -- code complete, tests in progress (uncommitted)
4x4 Evo 2 drove nose-first into a tree, then fully submerged in a lake: 511 s of `stuck_abort` with both
`HOLD_UNSTICK["drive"]` reverse rungs tried and no recovery ever attempted. Added `Agent.drive_recover()`,
wired into `hold_play()`'s `sd_watch` abort branch (drive genre only, once per stuck episode, before the
title-hold fallback's own abort stands): one model look for an on-screen reset/respawn/recover prompt naming a
button, then `BACK`/`Y` alone, then -- last, because it risks the main menu -- the pause menu, opened with
`START` and read with a *second* model look before anything in it is pressed, so a wrong guess can never quit
to the main menu, exit to the dashboard, or load a different save. Each candidate is kept only if
`window_change` clears `HOLD_STILL`; a kept pause-menu restart counts as still-play. This can't live in
`stuckdetect.py`'s `HOLD_UNSTICK` ladder because that ladder is a static token list with no model-call hook.

Real-frame replay of 4x4 Evo 2's actual recorded hold frames through `StuckWatch("drive", ..., max_rungs=2)`
confirms the mechanism this fixes: frames 047-058 are the truck crashing into a tree then sinking (genuinely
changing, not yet "stuck" by `STUCK_MIN_SAMPLES`); frame 060 is the first stuck detection (reverse rung 1);
061 reverse rung 2; 062 `abort=True` -- exactly where recovery now gets a try instead of ending the hold.
Remaining before commit: port this replay into `pathfind_selftest.py` (fixture copies already staged under
`docs/lanes/holdinput1013/fixtures/4x4evo2/`), add a direct unit test of `drive_recover`'s three branches, and
confirm the existing `holdstill` test (which already asserts the reverse rung fires before the unlock ladder
for `genre=="drive"`) still passes unchanged -- that test is this fix's Forza regression coverage, since Part B
only touches the `sd_watch` path, not the still-window rotation.

## Part C -- not started
Darkwatch: on-screen button-prompt detection (X = melee) before the shooter genre's unstick rungs fire.

## Part D -- not started
`hitch_report.py`: a scored window whose scene never travels must fail like menu/pause/load. Prior analysis
(this lane, measurements in Part A's list plus route-frame series) found no tested measure at route-frame
cadence robustly separates ATV's parked-quad case from confirmed-real drives; this is a candidate "not
separable" finding, not yet finalized or written up with full supporting data.

## Part E -- COMPLETE (9fbdec7bea)
`StuckWatch` was built without `max_rungs`, defaulting to 3 and silently dropping the 4th rung of the 4-rung
`"attack"` ladder (Genma Onimusha: `STICK:down:2`+`A` never tried before `stuck_abort`). Fixed by passing
`max_rungs=len(sd_ladder)` from the genre's own `HOLD_UNSTICK` entry. New selftest walks every genre's full
ladder to `stuck_abort` and confirms a mutant reinstating the old default-3 cap drops attack's 4th rung.

## Part F
Will mark this `State: ready` once A-E (or D-as-not-separable) land, selftest passes clean on the merged tree.
