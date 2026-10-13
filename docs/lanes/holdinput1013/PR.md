# pathfind: a drive hold proves its gas, gets a stuck vehicle out, acts on an on-screen prompt, and tries every unstick rung; the verdict does not read a parked vehicle as travel (#433, 0.5)

State: draft

Lane: holdinput1013            Issue: #433
Base: master @ d2bcaacd22
Files: docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py, docs/lanes/holdinput1013/fixtures/4x4evo2/*, docs/lanes/holdinput1013/fixtures/promptrung/*
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

## Part B -- COMPLETE (4cd1307df7)
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
061 reverse rung 2; 062 `abort=True` -- exactly where recovery now gets a try instead of ending the hold. This
replay is now `driverecover-4x4evo2` in `pathfind_selftest.py`, using fixture copies under
`docs/lanes/holdinput1013/fixtures/4x4evo2/`; `drive_recover`'s three branches (prompt, BACK/Y, pause-menu) are
each a direct `FakeAgent`/`FakeModel` unit test (`driverecover-prompt`, `driverecover-pause`,
`driverecover-unsafe`). The pre-existing `holdstill` test (asserting the reverse rung fires before the unlock
ladder for `genre=="drive"`) still passes unchanged -- Part B only touches the `sd_watch` abort path, not the
still-window rotation.

## Part C -- COMPLETE (next commit)
Darkwatch: on-screen button-prompt detection (X = melee a door lock) now fires before the shooter genre's
unstick ladder gets a rung. Added `Agent.prompt_rung()`, wired into `hold_play()`'s `sd_watch` non-abort
branch -- the opposite side of Part B's injection point: this fires on the *first* stuck sample, before any
ladder rung, not after the ladder is exhausted. One model look for a named on-screen prompt; if it names a
target direction the model's own stick is sent first, then the button. Gated by `prompt_tried` (once per
stuck episode, same pattern as `drive_recovered`); unlike `drive_recover`, not gated by genre or by `TITLE_HOLD`
(`th`) -- a button prompt is model-read evidence of what the screen is asking for right now, not a per-title
guess, so it should fire even when a title has its own fallback walk. Checked the shared flat canned-answer
queue in `pathfind_selftest.py`'s dry mode doesn't break `sdstuck` (the only leg with real `stuckdetect`): confirmed
safe because `prompt_tried` limits the new call to one per stuck episode and `sdstuck`'s 16 `PAUSED` answers are
content-identical, so a one-position shift changes nothing -- verified by running the full suite.

Two real fixture frames: `fixtures/promptrung/darkwatch-038-hold.jpg` (the melee prompt, positive) and
`fixtures/promptrung/n-4947001F-099-hold-noprompt.jpg` (a plain still-recovered shooter frame with no prompt,
negative), both copied from existing read-only run folders. Three new selftest legs: `promptrung-darkwatch`,
`promptrung-noprompt`, `promptrung-turn`. Full suite re-run clean after the change (`pathfind_selftest: all
ok`, 0 FAIL).

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
