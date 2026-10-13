## Why attempt 1 did not finish

Attempt 1 (session `holdinput1013.20261013T200229Z`, 243 turns, ended cleanly with
`stop_reason: end_turn`) wrote Part B's code and tests, fixed the `d["abort"]` ->
`d.get("abort")` `KeyError`, and launched the full `pathfind_selftest.py` rerun **in the
background** to confirm nothing regressed before committing -- then ended its turn with
that rerun still in flight. Per this repo's own rule for a headless lane session
("Never end a session waiting on your own background task" -- a `run_in_background`
job or detached process dies the moment the turn ends, and its result never arrives),
the rerun was killed with the session and Part B was never committed. Attempt 2 (this
session) re-ran the full suite in the foreground (it took ~9 minutes of real CPU time,
piped through a blocking `tail`, not nothing -- which is likely why attempt 1 reached
for background in the first place) and waited on it via a PID poll loop within the same
turn before doing anything else. It passed clean (`pathfind_selftest: all ok`, exit 0,
including the new `driverecover-*` and `maxrungs-*` legs), so Part B is committed as-is,
unchanged from attempt 1's code.

# lane.holdinput1013

Five input-handling defects behind four failed/misjudged Nova hold runs on 2026-10-13
(ATV Quad Power Racing 2, 4x4 Evo 2, Darkwatch, Genma Onimusha). None are emulator bugs --
all five are in `pathfind.py`'s own drive/stuck/input logic (Part D is in `hitch_report.py`).
Parts A-C and E land in `docs/testing/titles/pathfind.py`, one commit per part. Full
per-part detail is in `docs/lanes/holdinput1013/PR.md`; this file is what the next lane
(or a future me) should not have to rediscover.

## Part A -- a drive hold's gas must move the vehicle (COMPLETE, cd55eafedf)

ATV's probe sent `RT:1.5` and read it as accepted (control 0.001, under input 0.094) purely
from `probe_change`'s own control/under-input numbers -- but in this game RT is the jump
preload (rider crouches, PRELOAD gauge fills, speedometer stays 0), not the gas.

Fix: `Agent.confirm_gas()` tries RT, A, X, then the title's own `TITLE_HOLD` gas fallback,
and keeps the first one whose `gas_change()` (motion measured with the vehicle/HUD band
masked out, `GAS_MOVE_BAND`/`GAS_MOVE_BAR`) clears the bar -- not the probe's own
control/under-input accept. `drive_tokens(gas)` builds the drive loop from whichever
candidate is confirmed.

Band-change numbers behind `GAS_MOVE_BAR` (measured on real probe triplets, RT unless
noted):

| run | band change | read |
|---|---|---|
| ATV Quad Power Racing 2 | 0.0226 | refused (preload, not gas -- correct) |
| Auto Modellista | 0.0018 | refused (RT stalled) |
| Panzer Elite | 0.0591 | confirmed |
| RalliSport Challenge 2 | 0.1246 | confirmed |
| Conflict Desert Storm II | 0.1656 | confirmed |

Zero ledger-banked Playable runs are `genre=="drive"` today, so there was no banked-run
regression risk from tightening gas confirmation.

**A gap this session found and fixed in the same commit, not flagged by the prior
session's own state**: the still-window unstick rotation branch (the `rot`/`HOLD_UNSTICK`
cycling inside `hold_play()`, independent of the `StuckWatch` mechanism) was still building
its loop from the hardcoded `HOLD_GENRES["drive"]` (RT) even after `confirm_gas` had
confirmed a different button. Fixed: `loop = drive_tokens(gas) if genre == "drive" else
HOLD_GENRES[genre]`. Lesson: re-read the whole hold loop for every place a genre's drive
tokens are built, not just the one the brief names -- there were two independent
mechanisms (`StuckWatch`'s ladder and the still-window rotation) both hardcoding RT, and
the brief's repro only exercised one of them.

## Part B -- a stuck drive genre tries a recovery before giving up (COMPLETE)

4x4 Evo 2 drove nose-first into a tree, then fully submerged in a lake: 511 s of
`stuck_abort` with both `HOLD_UNSTICK["drive"]` reverse rungs tried and no recovery ever
attempted.

**Why this can't be a `HOLD_UNSTICK` ladder entry**: `stuck_step()` (in
`docs/lanes/stuckdetect1007/stuckdetect.py`, a different lane's territory) is a pure
static-token-list walker with no model-call hook. A reset/respawn prompt needs reading the
screen; a pause menu needs reading to find which entry does what. Neither fits the ladder.

Fix: `Agent.drive_recover(self, log, jpg)`, wired into `hold_play()`'s `sd_watch` abort
branch (drive genre only, once per stuck episode, gated by a `drive_recovered` flag reset
whenever the detector goes un-stuck again, and only when there's no `TITLE_HOLD` fallback
already standing in):
1. one model look for an on-screen reset/respawn/recover prompt naming a button
2. if no usable prompt: `BACK`, then `Y` (`DRIVE_RECOVER`), tried one at a time
3. last, because it risks the main menu: opens the pause menu with `START`, then a
   **second** model look reads it before anything is pressed, explicitly instructed to
   never name an input that quits to the main menu, exits to the dashboard, or loads a
   different save -- answer none for those instead. Only a model-named, non-"none"
   restart input is pressed; otherwise a plain `B` backs out without confirming anything.

Each candidate is kept only if `window_change` clears `HOLD_STILL`; a kept pause-menu
restart counts as still-play (not a Playable-ending state). Logged under `"recover_try"`
(not `"action"`), matching `confirm_gas`'s `"gas_try"` convention so hold-loop-only test
assertions on the `"action"` key don't pick up probe/recovery logging by accident.

**4x4 Evo 2 real-frame replay** (actual recorded hold frames, copied read-only into
`docs/lanes/holdinput1013/fixtures/4x4evo2/`, replayed through the real
`StuckWatch("drive", (), HOLD_UNSTICK["drive"], (), max_rungs=2)`):

| frame | stuck | abort | action |
|---|---|---|---|
| 047,051,054,056,058 | False | -- | -- (crash-into-tree-then-sink is still genuinely changing; `STUCK_MIN_SAMPLES` not yet met) |
| 060 | True | False | `LT+left:3 RT+right:3` (reverse rung 1) |
| 061 | True | False | `LT+right:3 RT+left:3` (reverse rung 2) |
| 062 | True | True | -- (`stuck_abort` -- this is exactly where `drive_recover` now gets a try instead of ending the hold) |

This is now a selftest leg (`driverecover-4x4evo2` in `pathfind_selftest.py`), reading the
fixture copies, not the external read-only run folder.

**Forza regression**: the brief asks to show the existing Forza case still takes the
reverse rung first. The pre-existing `holdstill` leg already asserts this for
`genre=="drive"` (the reverse rung fires before the unlock ladder) and is untouched by
Part B, since Part B only adds a branch inside the `StuckWatch`-abort handling, not the
still-window rotation path `holdstill` exercises. Confirmed unchanged by the full selftest
run after Part B landed (see below).

**`drive_recover`'s own branching** is covered directly (not through a full Sim/Agent run,
since the brief's literal test bar for Part B -- the replay above plus the Forza
regression -- only needs the static-ladder mechanism) via a minimal duck-typed
`FakeAgent`/`FakeModel` stub in `pathfind_selftest.py` (`driverecover-prompt`,
`driverecover-pause`, `driverecover-unsafe`): a named prompt succeeding on the first try;
no prompt, both `BACK`/`Y` failing, the pause menu read and its model-named restart input
succeeding; and nothing working at all, where the model explicitly answers
`restart_input: "none"` and `drive_recover` presses only a plain `B`, never an unconfirmed
input.

**A trap hit while writing the replay test**: `stuck_step()` returns `{"stuck": False,
"run": run}` with no `"abort"`/`"action"` keys when nothing is stuck -- the standalone
verification script used `d.get(...)` throughout, but the first pass of the selftest leg
indexed `d["abort"]` directly and raised `KeyError` on every non-stuck frame. Fixed to
`.get()`. Lesson: a standalone script's defensive `.get()` habit doesn't automatically
carry over when the same logic is transcribed into a permanent test -- re-check every
dict access against the function's own documented return shape, not just against what
happened to work in the one-off script.

## Part C -- on-screen button-prompt detection before the genre's unstick rungs (COMPLETE)

Darkwatch, `$R/n-43430016-1013r/`: from hold frame 026, every frame shows "USE (X) TO
MELEE ATTACK THE DOOR LOCK" (blue X glyph), but `HOLD_UNSTICK["shooter"]`'s two rungs
(strafe + fire) have no X -- `stuck_abort` at 432 s of play, failing on duration.

Fix: `Agent.prompt_rung()`, wired into `hold_play()`'s `sd_watch` non-abort branch
(the `else` that used to go straight to `self.send(d["action"])`), gated by a
`prompt_tried` flag reset the same place `drive_recovered` is (so it fires once per
still-window episode, before the first ladder rung, not once per rung): one model look
for an on-screen instruction naming a button (the prompt's text, and the glyph's
colour -- A green, B red, X blue, Y yellow); if the instruction needs the player to
face or aim at something first, the model also names a stick turn (`stick:left` etc.,
walk, or `rstick:left` etc., look/aim), sent via the real `self.send()` before each of
up to 3 presses. A prompt the rung cannot clear in 3 tries falls through to the
existing ladder for that stuck sample (`cleared` stays `False`, so `self.send(d["action"])`
still runs); not gated by genre or `th`, since an on-screen prompt can appear in any
genre's still window and `sd_watch`'s own ladder branch already runs unconditionally
of `th` (only Part B's drive-recovery branch is `th`-gated, because that one duplicates
a mechanism `TITLE_HOLD` can already have its own fallback for).

Logged under `"prompt_try"` (not `"action"`), matching `confirm_gas`/`drive_recover`'s
`"gas_try"`/`"recover_try"` convention.

**Why this can't reuse `drive_recover`'s own flow wholesale**: `drive_recover` fires
once, *after* the genre's static ladder is fully exhausted (last resort, Part B).
Part C's prompt is the *opposite* order -- tried *before* the ladder's first rung, on
the *first* stuck sample of an episode, since an on-screen prompt is an instruction,
not a fallback. Both share the same one-look-then-try-the-named-button shape, so
`prompt_rung` is still a short, separate method (not a flag passed into
`drive_recover`) -- the trigger condition and the thing it falls through to on failure
differ enough that sharing one function would need a branch at nearly every line.

**A reuse trap avoided**: the shared `self.sim` canned-answer queue in
`pathfind_selftest.py`'s dry-mode `Model.ask()` is a flat list popped in call order,
with no purpose-based routing. Before writing this, checked whether `prompt_rung`'s
new `model.ask(..., "prompt-rung", ...)` call (fired once per stuck episode, inside
the existing `sdstuck` selftest leg, which already runs the real `stuckdetect` module
against 16 canned `PAUSED` answers) would shift that queue and break `sdstuck`'s
assertions. It doesn't: `sdstuck`'s screen never changes, so there is exactly one
continuous stuck episode, `prompt_tried` gates `prompt_rung` to a single extra call
across the whole test, and all 16 `PAUSED` answers are identical in content, so a
one-answer shift changes nothing the test checks. Confirmed by running the full
selftest suite after wiring this in: `sdstuck` and every other leg still passes.

New selftest (`promptrung-*`) calls `pathfind.Agent.prompt_rung` directly (same
duck-typed-stub pattern as `driverecover-*`, extended with a `send()` stub) against two
real recorded frames, copied into `docs/lanes/holdinput1013/fixtures/promptrung/`:
Darkwatch's own hold frame 038 (the melee prompt) with a fixture model answer naming
X -- the rung presses X; and n-4947001F-1011's hold frame 099 (a shooter-genre run
that went still -- "scene unchanged for 4 consecutive samples" -- and recovered via
the ordinary ladder with no on-screen prompt anywhere in frame, the brief's asked-for
"hold that went still and recovered") with a fixture answer naming no prompt -- the
rung presses nothing, falling straight through. A third leg (`promptrung-turn`, extra
coverage beyond the brief's two-case bar) confirms a prompt whose answer needs a
target sends the model's own named stick turn before the button.

## Part D -- a scored window whose scene never travels must fail like menu/pause/load

Not started this session; carried forward from a prior session's analysis. Measured (see
Part A's table above, plus route-frame series over several runs' `route-frames/`
directories): no tested measure at route-frame cadence robustly separates ATV's
parked-quad case from confirmed-real drives -- window_change and scene_shift both move
on camera/physics jitter alone, with no clean threshold that fails ATV without also
failing at least one banked-real drive. This is a candidate "not separable" finding, not
yet finalized with full supporting numbers; if it stands, the right outcome may be to
document the limit in `hitch_report.py` rather than force a fragile threshold, per the
brief's allowance for an explicit negative result.

## Part E -- StuckWatch's max_rungs must match the genre's ladder (COMPLETE, 9fbdec7bea)

`StuckWatch` was built without `max_rungs`, defaulting to `stuck_step`'s own default of 3
-- silently dropping the 4th rung of the 4-rung `"attack"` ladder (Genma Onimusha:
`STICK:down:2`+`A` never tried before `stuck_abort`). Only `"attack"` was affected:
drive/shooter/bowl's ladders are all 2 rungs, never truncated by the old default.

Fix: `max_rungs=len(sd_ladder) if sd_ladder else 3` when constructing `sd_watch`.

New selftest (`maxrungs-*`) walks every genre's full `HOLD_UNSTICK` ladder to
`stuck_abort` directly against `stuckdetect.StuckWatch` (synthetic still signatures, no
Sim/Agent needed), confirms attack's 4th rung is `STICK:down:2`+`A`, and includes a
mutant (`max_rungs=3` as if the fix were reverted) that correctly drops attack's 4th rung
-- confirming the walk above would have caught the original bug.

## Outstanding

- Part B: commit once the full selftest suite passes clean (in progress as of this
  writing; the first full run after adding Part B's tests hit the `KeyError` above and is
  being rerun).
- Parts C and D: not started.
- Six scratch analysis scripts in this directory (`scratch_band.py`,
  `scratch_find_drive.py`, `scratch_find_genre.py`, `scratch_frac.py`,
  `scratch_ledger_genre.py`, `scratch_measure.py`) are the raw measurement tools behind
  Part A's table and Part D's "not separable" finding -- kept for now as working notes,
  not wired into the selftest suite; worth a decision before Part F whether any earn a
  permanent home or should be deleted.
