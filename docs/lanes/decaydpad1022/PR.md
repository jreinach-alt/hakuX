# decaydpad1022: the classifier floor falls over an unknown stretch, and the d-pad is pressed while it does (#433)

State: ready

Lane: decaydpad1022            Issue: #433 (0.5)
Base: master @ a28a108880
Files: docs/lanes/decaydpad1022/PR.md, docs/testing/titles/classify.py,
docs/testing/titles/drive-profiles/generic.toml, docs/testing/titles/drive.py,
docs/testing/titles/pathclass_selftest.py
Prediction: none: harness-only; no fps or pixel claim about hakuX itself. The behavioural claims (a screen
  pathclass is unsure of is named within a few captures instead of waiting; the d-pad is sent while it is
  unsure; neither ever names a screen as gameplay on a score the held-out set has not seen right) are
  checked by the selftests and mutants below and, on the device, by a rerun of 007: Everything or Nothing
Needs device: yes, for the proof run only
Needs NDK: no

Follows loadstuck1021 (folded a28a108880). Built in the interactive session from two owner directions on
2026-10-22, after the 007 and Def Jam pilot runs:

> the threshold you're using before declaring things unknown is way too high ... Let's have that threshold
> lower over time, but, it should be a pretty steep drop off, maybe 3-5 steps.
>
> Does it take 6 to 15 seconds for the classifier to return a result? Sitting at a screen for 45 seconds not
> pressing anything seems unlikely to meaningfully change what is on the screen ... while it is in the decay
> loop, it should use the dpad in an order, say, up, down, left, right. And use that to evaluate what's going
> on. Sitting there and waiting is counterproductive.

## What was built

**The gap.** 007 reached level-1 gameplay in ~140 s, and pathclass read a clear HUD frame `unknown` (0.48-0.70,
under the 0.85 gameplay floor); the driver held the play input and nothing named the screen.
The classifier answers every 1.3-2.7 s (measured capture gap, median 2.7 s on 007, 1.3 s on Def Jam) and a frame
that does not change scores the same each time, so a long `unknown` was spent waiting on a number that was not
going to move.

**1. The floors fall (`classify.py`, `generic.toml`).** `classifier_decay_menu` and `classifier_decay_gameplay`
(lists, 3-5 entries, never rising, never above the profile's own floor; `check_profile` refuses anything else).
Capture k of a stretch that stayed under its floor is judged at `list[k-1]`, the last entry holds
(`decay_floor`). Shipped:

- menu-class answers: 0.70, then `[0.55, 0.45, 0.40, 0.35]`;
- gameplay answers: 0.85, then `[0.75, 0.65, 0.60, 0.60]`.

The floor stays down until pathclass is sure at its own floor again (`low_run` in `drive.py`), so a screen named
at 0.5 does not flip back to `unknown` on the next capture. An answer accepted below the full floor carries a
`decayed` marker; a press that is resolved while one is in force is judged by the picture (`settle_explore`),
not by the state change, because the bar fell and the screen did not.

**The guard (`classify.DECAY_PLAY_MASS = 0.1`).** A non-gameplay answer below its full floor is refused while the
top-3 still gives `gameplay` 0.1 or more (the lean's own START limit, `drive.LEAN_PLAY_START`; a selftest holds
them equal). Without it, each of the 0.55-0.35 menu rows carries one errant press on a true gameplay frame (a
Buffy `controller_prompt`); with it, none does.

**Where the floors stop.** Measured on the held-out set (117 scored frames, menu_seen=True, guard in force):

| menu floor | acted | right | errant on gameplay | wrong, other truth |
|---|---|---|---|---|
| 0.70 (today) | 49 | 49 | 0 | 0 |
| 0.55 | 61 | 61 | 0 | 0 |
| 0.45 | 64 | 64 | 0 | 0 |
| 0.40 | 67 | 66 | 0 | 1 |
| 0.35 | 69 | 68 | 0 | 1 |
| 0.30 | 73 | 68 | 0 | 5 |

so the menu list stops at 0.35. Gameplay: no gameplay answer exists under 0.55 on that set and the false claims
start at 0.75 (see Known limits), so that list stops at 0.60.

**2. The d-pad while it waits (`drive.py`, `[drive] dpad_probe = 1`).** An `unknown` stretch used to start with
one `wait (unknown, confirming)` capture (the free look) and then the ladder's A. It now starts with
`DPAD_ROTATION = UP, DOWN, LEFT, RIGHT`, one flick per capture, sent as hat flicks (hakuX's d-pad buttons do nothing; `HAT` maps them to HATY/HATX min/max). Order inside
the `unknown` branch of `act()`:

1. the free look: the first UP flick (a fresh stretch);
2. what this title already learned for this screen (`learned.suggest`, min_rank 2);
3. the lean (pathclass's own action when the top-3 leans menu);
4. the global learned answers;
5. the rest of the rotation;
6. the exploration ladder (`A`, `START` only with a pause crop, `X`, `Y`, `DOWN`, `LX:min`, `R1`, `L1`, `B`).

Informed presses (2-4) still beat the blind rotation; the rotation replaces what used to be the wait. Each flick
is an `input ... dpad probe k/4, floor step n` line in logcat (so `playprobe_report.py` ties an fps dip to it).
A d-pad press followed by a named screen is learned `changed`, never `advanced` (a cursor moved; the screen did
not progress), so it is not replayed as the way forward. The four results (which flicks moved the picture) are
logged as `dpad-probe t=...: 2/4 moved the picture (UP changed DOWN changed LEFT none RIGHT none); floor step n`
and kept in `route-solution.json` `dpad_probes`: **recorded, not acted on**.

A screen that leans play never gets a flick: it goes to the play probe (held inputs), as before. A flick in live
play moves a camera or a weapon.

## Selftests

`pathclass_selftest.py` (standalone) `decay_tests()` (new) and edits to the older tests. Each check has a mutant
that must fail the same check:

- **Schedule:** step 0 is the profile's floor, step k is `steps[k-1]`, the last entry holds, no list raises a
  floor above its own; the shipped lists are 3-5 steps and stop at the measured limits.
- **0.5 menu answer:** `unknown` for two captures, named on the third, and it stays named. Mutants: floor never
  falls (never named); floor resets on a decayed acceptance (flip-flops main_menu/unknown).
- **Gameplay:** 0.80 named on the second capture; 0.5 never named however long it lasts.
- **Rotation:** UP, DOWN, LEFT, RIGHT in that order as HATY min/max, HATX min/max; the ladder's A after them; a
  stretch nothing resolves ends on the budget, never a Fail. Mutant: `dpad_probe = 0`.
- **Verdict:** 2 of 4 moved the picture, logged and kept. Mutant: verdict not written. Each flick an `input` line.
- **Learning:** UP followed by a named screen is `changed`, not `advanced` (mutant: no downgrade); A pressed on a
  static unknown and then named because the floor fell is learned `none` (mutant: `decayed` not marked, learns
  `advanced`).
- **Order:** the look flick first, then a learned answer (mutant: learned ignored goes on to DOWN), then the
  lean's own DOWN before LEFT and RIGHT; a play-leaning unknown is probed, never flicked (control: a 0.5 answer
  that leans nowhere does get the rotation).
- **Guard:** 0.5 menu with gameplay 0.2 in its top-3 stays unknown, with 0.05 it is named; mutant: no guard.
- **Loading overstay:** past `loading_stuck_s` the rotation runs, then the A that ends it.
- **A hand-tuned profile** (no lists, `dpad_probe` 0) behaves exactly as before. Bad lists are refused.
- **Older tests, adjusted, not weakened:** the lean tests pin `dpad_probe = 0` (they are about the lean; the
  combination has its own check above); the AvP replay gets its stalled title screen three more times so START
  has a capture to go out on after the look flick; the Simpsons "no START before play" check now flags START sent
  by the exploration ladder (the title policy's START on a named `title` is by design).

## Known limits

- **Gameplay false claims at 0.75-0.60.** The held-out set has three: PGR attract 0.78, Burnout replay 0.72,
  ToeJam attract 0.65 (all moving attract/replay pictures); a fourth, a Burnout Game Over overlay at 0.57, is
  under the list's last step. A false `play` marks a route done when it is not. `classifier_decay_gameplay =
  [0.85]` gives the claim back its old floor; the owner chose lower floors, this is their price.
- **The guard cannot see an overlay on live play that reads as a menu with no gameplay in the top-3.** Simpsons
  Hit & Run's tutorial dialog reads `controller_prompt` 0.46-0.56 (gameplay far down); `controller_prompt` is the
  `title` role, so under the fallen floor it gets a START, which pauses. In the replay the next frames return to
  play. (The frame before it, 124911, `gameplay` 0.69, is real gameplay: Homer on the lawn with the first hint;
  the run now marks play at 10.3 s.)
- **The d-pad verdict is recorded, not acted on.** Nothing yet uses "UP and DOWN move the picture" to drive a
  menu; that is the next step once real runs show what the verdicts look like.
- **`black` and `boot` have no overstay and no rotation.** Def Jam sat 578 s on a LOADING splash the harness
  called `black`/`boot`; that is a separate fix (a Fail on long `black`/`boot`, and whether the rotation should
  run there).
- **The sim answers are stubs.** The floor sweep is real (held-out frames through the real pathclass), the
  selftests drive stubs; the device proof is what ties it together.

## Full selftest run

`bash docs/testing/jobs/selftest.sh` in the lane tree: **3863 passed, 0 failed, all 160 fragments**, exit 0.
The standalone `python3 docs/testing/titles/pathclass_selftest.py` (included in the run above, rerun by itself
after the last comment edits): 88 ok, 0 failure(s). Territory row `[lane.decaydpad1022]` pushed to origin/board
(5b268b2eea), `check_territory.py` ok, every file released at ready.

## Proposed device proof (not part of the fold)

007: Everything or Nothing (45410042) on the Nova, through the dispatcher, no route (the auto route attaches).
It passes if: `dpad-probe` lines appear whenever a stretch of `unknown` runs longer than a capture or two, no
stretch of `unknown` outlasts about five captures except on a screen pathclass is honestly unsure of, the level-1
HUD is named `play` (not held as `unknown`), and `playprobe_report.py <result dir>` ties every below-bar play
second to an input or says there is none. A menu-heavy title next (a Def Jam or Simpsons-class title with a
dialog), to read the verdicts.
