# hangplay1022: a dark screen that lasts is a hang, and a screen held as leaning play stays so (#433)

State: ready

Lane: hangplay1022            Issue: #433 (0.5)
Base: master @ d68c705bec
Files: docs/lanes/hangplay1022/PR.md, docs/testing/titles/drive-profiles/generic.toml,
docs/testing/titles/drive.py, docs/testing/titles/pathclass_selftest.py
Prediction: none: harness-only; no fps or pixel claim about hakuX itself. The behavioural claims (a `boot`/`black`
  stretch is waited out for 10 s, pressed after that and ROUTE FAIL at 30 s; a screen held as leaning play is not
  handed to the exploration ladder by a read that dips under the entry bar) are checked by the selftests and
  mutants below and, on the device, by a rerun of 007: Everything or Nothing and of Def Jam: Fight for NY
Needs device: yes, for the proof runs only
Needs NDK: no

Follows decaydpad1022 (folded d68c705bec). Two parts, both from the pilot and the proof run of 2026-10-22.

## A. Dark stretch = hang (owner 2026-10-22: "A black screen for 30 seconds sounds like a hang.")

**The gap.** `boot` and `black` were wait states with no limit. Def Jam: Fight for NY sat 578 s on its own
LOADING splash (guest spinning at one pc, `idle_us=0`, luma about 2), the harness called every capture
`boot`/`black`, pressed nothing, and the run ended "terminated", not Fail.

**What was built (`drive.py`, `[drive] dark_grace_s / dark_fail_s`, shipped in `generic.toml` as 10 / 30).**
`DARK = (boot, black)` is one stretch whichever name the luma check gives it (classify.py cannot alternate the
two without a named screen in between, but the clock does not rely on that). `enter()` starts the clock when the
screen goes dark and clears it when it does not. In `act()`, before the old `return "wait"`:

- under `dark_grace_s` (10 s): waited out, as before;
- from 10 s: `dark_press()` sends one rung of `EXPLORE_LADDER` per capture (`A` first; START only with a pause
  crop), spaced by `skip_settle_s`; the press is labelled `dark <n> s (<source>)` and nothing is learned from it
  (a black frame has no embedding to key on);
- at `dark_fail_s` (30 s): `Fail("dark for 31 s (black, luma 0.0): 10 presses sent and no picture came -- the game
  is hung, or draws something the luma check cannot tell from black")`, which `run()` turns into
  `ROUTE FAIL drive generic: black: dark for ...`.

`check_profile` refuses a grace at or over the fail time. `0/0` (the default for every hand-tuned profile) keeps
the old wait-for-ever behaviour, so no existing profile changes.

**Why 10 / 30.** Measured over the 45 runs in dispatch/results (the longest dark stretch of each): the 16 that
reached play never sat dark longer than 9.7 s; the two that did were Def Jam (577 s) and Bloody Roar (262 s on a
dark prompt, #1071). 007's own dark captures are 9.6 s of boot at start and a 3-capture `black` fade (about 5 s)
between the intro video and the level.

## B. Lean hysteresis (the 007 proof-run failure)

**The gap.** The 007 proof run (1-1792686890-decaydpad1022-3970029) reproduced the 2-3 fps defect (second
reproduction, see the unfiled board request) and **failed its own criterion**: 172 of 214 captures were
`unknown`, play was never marked and the exploration ladder pressed into live gameplay for about 400 s. The
`lean` (pathclass's top-3 giving the `play` family 0.45 or more) did work for the first 20 captures and the play
probe held R1; that hold moved the picture, the next read of the HUD fell under 0.45 (it had been 0.47-0.61), the
lean ended, and the entry bar was also the keeping bar, so the next capture went to the ladder.

**What was built (`drive.py`).** `Driver.play_lean` records that the last `unknown` capture leaned play. While it is
set, the lean is kept down to `LEAN_PLAY_KEEP = 0.25` of the top-3, unless another family holds
`LEAN_PLAY_YIELD = LEAN_MASS = 0.45` (then that family takes the screen). Entry is unchanged (0.45). The flag is
cleared on any state that is not `unknown`/`play`/`stalled`.

**Measured on the 117 held-out frames** (leansweep.py): a keep bar of 0.25 holds 13 frames as play where 0.45
held 12, and the non-gameplay frames leaning play go from 5 to 6, which is the price: one more screen is held
as play rather than pressed.

## Selftests

`pathclass_selftest.py` (standalone) `hangplay_tests()` (new, 17 checks), `probe_run(make_dev=)` for a device whose
picture goes dark or comes back by the route clock, `DarkDevice`, `FadingLeanStub`. Each check has a mutant that
must fail the same check:

- **Shipped profile:** 10 s grace, 30 s fail, grace above the 9.7 s measured.
- **Never draws:** first press at 10 s or later and it is `A`, none before; ROUTE FAIL at about 31 s naming dwell,
  luma and presses; presses labelled `dark`, nothing learned. Mutant: `dark_fail_s = 0` waits for ever, no presses.
- **6 s boot:** no dark press, no Fail. Mutant: grace 2 s presses.
- **A press that lifts it:** the run goes on; a second 20 s dark stretch at 80 s waits its own 10 s and is not a
  Fail. Mutant: the dark clock is never reset (the second stretch is a Fail).
- **`black` after a menu:** counted from the moment the picture went dark (Fail at about 51 s, not 30 s).
- **Profile:** a grace at or over `dark_fail_s` is refused; a fail time with no grace is valid.
- **Lean:** a screen held as leaning play at 0.5 stays so when the read falls to 0.30 (no ladder, no d-pad).
  Mutant: keep bar = entry bar presses the ladder. Control: the same 0.30 from the start is not a lean. A menu
  family holding 0.45 takes the screen (mutant: a held lean never yields). Gameplay at 0.15 is no longer held.
- The menu stub in the dark tests pins `menu_max_presses = 999`, so only the dark rule can end those runs.

## Known limits

- **The live pathclass scores are not logged.** `route-state.tsv` has no per-capture confidence (`cap_s` is the
  capture time), so the 007 explanation above is read from the earlier captures and the lean sweep, not from the
  post-182 s scores themselves. Backlog: log the top-3 per capture.
- **A dark prompt that `A` does not move fails at 30 s** (Bloody Roar, #1071: a small logo on black reads as
  dark). It now gets presses first; the real fix is the misclassification, not a longer wait.
- **Slow games and the play probe.** With the lean held, the play probe runs to its 3-round limit on a title at
  2-3 fps and fails "no input moved the picture" after about 114 s. That text is honest about the harness and
  misleading about the game. Backlog: report the game's gfps in the probe Fail text.
- **The 16 runs that reached play are the whole evidence for 10 s.** A real title that loads black for longer than
  30 s would now be Failed; every Fail names the dwell, so a miscalibration shows up in one run.
- **The sim answers are stubs;** the device proof ties it together.

## Full selftest run

`bash docs/testing/jobs/selftest.sh` in the lane tree: **3863 passed, 0 failed, all 160 fragments**, exit 0.
Standalone `python3 docs/testing/titles/pathclass_selftest.py`: 105 ok (88 before, 17 new), 0 failure(s).

## Proposed device proof (not part of the fold)

1. 007: Everything or Nothing (45410042), Nova, no route. Passes if the level-1 HUD stays `unknown` leaning play
   (`hold (unknown, leans play)` captures, no `explore` inputs after the lean starts) for the level, and
   `playprobe_report.py` ties the dips to inputs or says there is none. The play probe may Fail ("no input moved
   the picture") on a title at 2-3 fps; that is the limit above, not a new defect.
2. Def Jam: Fight for NY (45410049), Nova: expect `ROUTE FAIL ... dark for 3x s` at about 30 s after the splash
   goes dark, not a 578 s "terminated".
