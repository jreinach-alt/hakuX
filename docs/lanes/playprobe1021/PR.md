# playprobe1021: the driver finds the input that makes the game move, and every input is attributable to an fps dip (#433)

State: ready

Lane: playprobe1021            Issue: #433 (0.5)
Base: master @ 6448c914e0
Files: docs/lanes/playprobe1021/PR.md, docs/testing/jobs/selftest.d/99-playprobe-report.sh,
docs/testing/titles/drive-profiles/generic.toml, docs/testing/titles/drive.py,
docs/testing/titles/pathclass_selftest.py, docs/testing/titles/pathknow/learned.py,
docs/testing/titles/playprobe_report.py
Prediction: none: harness-only; no fps or pixel claim about hakuX itself. The behavioural claim (a title whose
  play input is not on the stick and RT now gets moving, and the run says which input did it) is checked by the
  selftests and mutants below and, on the device, by a rerun of NFS Hot Pursuit 2 (proposed below)
Needs device: yes, for the proof run only
Needs NDK: no

Owner, 2026-10-21: "Yes let's build it. Item 3 is a moot point. Almost any game featuring computer controlled
opponents is likely not going to be idempotent. And, the game needs to hold 30 FPS regardless of the path chosen
when in gameplay. If falling into water craters the framerate, we need to know that." Built in the interactive
session. Follows routebuild1021 (folded 6448c914e0).

## What was built

**The gap.** The proof run of routebuild1021 got NFS Hot Pursuit 2 to its race start at 115 s with no model
call, then the car sat at 0 MPH for the rest of the soak. HP2's gas is A. The leans-play branch holds the stick
and RT and presses nothing, and the stall escape only runs for a confident `stalled`, so nothing ever pressed A.
A soak of a car that is not moving measures nothing.

**The probe (`drive.py`).** When the screen has not moved for `probe_idle_s` while the driver is in play, or
in an unknown screen that leans play, it holds candidate inputs one at a time on top of the play cycle:
`PROBE_LADDER` = A, X, Y, R1, L1, LY:max (a button by `pad hold`, `AXIS:value` by `pad axis`).

- A candidate is held until the picture moves on `probe_hits` (2) captures running, or `probe_hold_s` (5 s) is up.
  One moving capture is not motion: a camera cut or a button's flash would win.
- The winner stays held. When the screen goes still again, the winner is let go, a new round starts, and the old
  winner is tried last (it already stopped working once).
- Order within a round: what the learned table says moved a screen like this one (this title's records, then
  every title's, matched by embedding), then the profile's `input.probe` list, then the ladder.
- `probe_rounds` (3) rounds that find nothing FAIL the step: `ROUTE FAIL ... play probe: 3 rounds, nothing moved
  the screen (held A L1 R1 X Y LY:max)`. This replaces the 40 s `stall_fail_s` and the blind `stall_cycle` while
  the probe is on, so a stalled screen is searched instead of waited out.
- A probe-held axis is the probe's: `hold_play` no longer re-sends the cycle's value for it every capture.
- Nothing the probe holds stays down: leaving play, a Fail and the end of the run all release it.
- Never START (pauses live play), B (backs out of a menu the classifier may have miscalled), BACK or SELECT.
  `check_profile` refuses an `input.probe` that names one, as it does for `play_tap`.
- `probe_idle_s` defaults to 0 (off). `drive-profiles/generic.toml` turns it on at 8 s. A hand-tuned profile
  is unchanged.

**What it learns (`pathknow/learned.py`).** Every probe is a record of kind `play`: the screen's embedding, the
input, the outcome (`advanced` / `none`), the motion before the hold, the most motion under it, and how long it
was held. That is the (embedding, input, motion change) tuple the owner asked for. `suggest()` matches only its
own kind: a play screen's embedding sits near many menus' by chance, and `A` held for 5 s is not `A` pressed
once, so a play record can never be pressed as an explore answer. Records with no `kind` are `explore`, as before.
The run's `route-solution.json` also carries `play_probes`.

**Attribution (`drive.py`, `playprobe_report.py`).** Every input drive.py sends goes to logcat the moment before
it goes, tag `hakuX-route`, on the clock the `hakuX-perf gfps=` lines are on:

    input t=<route s> <what> why=<why>          a press, a hold change, a tap, a stall escape, a probe hold
    play-probe round N start idle=.. queue=..    a round begins
    play-probe won|missed <input> motion=.. before=.. held=.. round=.. t=..

`playprobe_report.py <result-dir|logcat.txt>` lays the dips against them. It reads only. It takes
title_verdict.py's own logcat parser, `gfps=` pattern and bar (`playable_fps` 30 x `fps_tolerance` 0.95 = 28.5)
and scores only the seconds the driver called `play`; a below-bar second in a menu or a load is counted apart.
For each dip (consecutive below-bar seconds merged) it names the input held, the inputs and probes in the 4 s
before, and the nearest route frame; then a table of play seconds, mean gfps and dip seconds by input held. It
says "not attributable" for a run with no input markers and "not measured" for one with no `gfps=` lines.

This answers "what was the run doing when it dipped". It does not say why. A dip under one input is a candidate;
the same input under many dips and none of the good seconds is a finding. The scene (water, a crowd) is in the
frame.

## Selftests

`pathclass_selftest.py` (standalone): 0 failures. The new checks run a driver against a stub whose picture
answers the pad (the recorded-answer stub cannot show a probe working). Each has a mutant that must fail the same
check, so none is vacuous:

- **HP2 case.** Gas is R1. A, X, Y miss and R1 wins; R1 is held once through the run and released at the end;
  nothing is left held; each probe is a `play` record. Mutants: `probe_idle_s = 0` never holds R1; `mark_input`
  a no-op leaves no input in logcat.
- **Fail loudly.** Nothing moves the screen: ROUTE FAIL naming the probe after 3 rounds, for an `unknown` that
  leans play and for a confident `stalled`, with no stall escape ahead of it. With the probe off the old
  `stalled` Fail still ends the run (a profile that does not opt in is unchanged).
- **Sustained motion.** A single moving capture never wins. Mutant: `probe_hits = 1` wins on it.
- **Winner re-probe.** The winner stops moving the screen at 30 s; it is released before the next candidate is
  held and a new round finds X. Mutant: nothing is ever released.
- **Learned first.** The next run tries the learned input first and wins on it. Mutant: learned play inputs
  ignored.
- **`kind`.** A play record is suggested to a probe and never to explore. Mutant: `_matches` ignores `kind`.
- **Axis override.** A probe-held `LY:max` is not overwritten by the cycle's `LY min`. Mutant: `probe_axes`
  returns nothing, and the LY events show the cycle overwriting it.
- **`input.probe`** naming START, B or SELECT is refused.

`99-playprobe-report.sh`: 19 checks against a logcat fixture with a known set of dips (a 3 s one that must come
out as one dip, a single second, a 29 gfps sample at the bar that must not be a dip and a 28 that must, and four
below-bar menu seconds that must not be counted), the real code and four mutants (the `play`-only filter
dropped, consecutive seconds not merged, the held input never found, no window before a dip). `--bar` moves the
line.

The sim's frames do not react to input; the reactive stub does. Neither shows that a press reaches the game.
That is the device run's job.

## Known limits

- **Motion is not "the player moved".** The probe reads pathclass's changed fraction. A camera, an attract loop
  or an animation moves the screen as well. Two captures running mitigates a blink, not a loop. The learned
  record keeps `motion` and `held_s`, so a bad winner can be found afterwards.
- **A held button stays down if the process is SIGKILLed.** TERM, Fail and a normal end release it.
- **A momentary effect can re-win.** An input that moves the screen once and then stops (a menu advance)
  wins for as long as the picture keeps moving, and the next idle starts a round that tries it last.
- **Holding A, X, Y, R1, L1 on a screen mistaken for play** can act on a menu. None of them leaves a screen
  the way B or START can. This is the same class of risk the play cycle's A tap already takes.
- **Non-idempotent games.** A game with computer-controlled opponents will not replay the same trail twice.
  Varied play is expected; the 30 fps bar applies on every path. The report is how a path that breaks it shows.
- **The report is by time, not cause**, as above. It is not wired into the dispatcher: soak_title.sh is
  not in this lane's files. It is run by hand on a result directory.
- **Step 3 is not built**: a trained play-input head on the collected tuples. The tuples are what it would train on.

## Full selftest run

`bash docs/testing/jobs/selftest.sh` on this tree (base 6448c914e0 + the files above): **3863 passed, 0 failed,
all 160 fragments** (159 on the base, plus 99-playprobe-report.sh). `python3 docs/testing/titles/pathclass_selftest.py`
(standalone; no fragment runs it): **0 failure(s)**. Territory: `[lane.playprobe1021]` pushed to origin/board
(cfc337b6ea), `check_territory.py` ok, every file released at ready.

## Proposed device proof (not part of the fold)

NFS Hot Pursuit 2 (45410028) on the Nova, through the dispatcher, no route (the auto route attaches). It passes if:
the car moves (a `play-probe won` line, and the picture moves under it), `input` and `play-probe` lines sit beside
the `gfps=` lines in the result's logcat.txt, `play` records land in the learned table, and
`playprobe_report.py <result dir>` ties every below-bar play second to an input or says there is none.
