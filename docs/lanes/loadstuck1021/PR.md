# loadstuck1021: a `loading` that never ends is handled as `unknown`, so the driver presses and the play probe gets a screen (#433)

State: ready

Lane: loadstuck1021            Issue: #433 (0.5)
Base: master @ e20a67e7d2
Files: docs/lanes/loadstuck1021/PR.md, docs/testing/titles/drive-profiles/generic.toml,
docs/testing/titles/drive.py, docs/testing/titles/pathclass_selftest.py
Prediction: none: harness-only; no fps or pixel claim about hakuX itself. The behavioural claim (a screen the
  classifier calls `loading` for longer than `loading_stuck_s` gets the same presses as an `unknown` one) is
  checked by the selftests and mutants below and, on the device, by a rerun of NFS Hot Pursuit 2
Needs device: yes, for the proof run only
Needs NDK: no

Follows playprobe1021 (folded e20a67e7d2). Built in the interactive session.

## What was built

**The gap.** The first rerun of the NFS Hot Pursuit 2 proof after playprobe1021 never reached the probe. The
driver sat in `loading` for ~530 s with nothing pressed: pathclass called the Career event briefing ("A
Advance", gfps 59) `loading` at >= 0.7, and `loading` is a wait state, so it was waited out for ever. The play
probe, the exploration ladder and the learned table only run from `unknown`, so none of them ever saw the screen.
`route-solution.json` for that run: `play_probes: []`, `explored: [A changed, START advanced]` from the earlier
screens.

**The fix (`drive.py`, `drive-profiles/generic.toml`).** `loading_stuck_s` (default 0 = off, as before;
`generic.toml` sets 90). In `act()`, a `loading` that is still `loading` that long after it began is handled as
`unknown` from then on, once:

- it logs `loading-overstay t=<s>: <n> s in loading (<source>); handled as unknown from here` to logcat
  (tag `hakuX-route`), so a long wait is visible beside the `gfps=` lines;
- it clears `explore_tried`, so the ladder starts at its first rung;
- the state the rest of the policy sees is `unknown`: the learned answer, the lean, the global learned answers
  and `EXPLORE_LADDER` (A first) all apply, and a play-leaning screen goes to the play probe;
- when the screen finally stops being `loading`, the press that was in flight resolves `advanced` (or
  `regressed`), exactly as for an `unknown` screen, so it is learned. The explore record's key is
  `unknown:pathclass:loading`: the screen's embedding is what matches it next time.

A hand-tuned profile has no `loading_stuck_s` and is unchanged.

## Selftests

`pathclass_selftest.py` (standalone) `loading_tests()`, against a stub that answers a confident `loading` (0.9)
until the condition for the case is met, then a confident `gameplay`. Each has a mutant that must fail the same
check, so none is vacuous:

- **HP2 case.** `loading` until A is pressed. Nothing is pressed before 90 s; the first press is A, at 90-100 s;
  the run reaches play; the overstay line is in logcat; `unknown:pathclass:loading` / A is recorded `advanced`.
  Mutant: `loading_stuck_s = 0` presses nothing and never reaches play.
- **A real load.** `loading` that ends by itself at 60 s gets no press before it ends. Mutant: the bar lowered to
  30 s presses into the load.

## Known limits

- **A real load longer than the bar takes a few presses.** A first, then the rest of the ladder (X, Y, DOWN, LX,
  R1, L1, B) if it goes on, as for any unknown screen; most loads ignore them. 90 s is above any load seen in the
  recorded runs; it is a profile number.
- **`black` and `boot` have no overstay.** Only `loading`, which is what the HP2 run was stuck in.
- **No Fail.** A `loading` that nothing moves ends at the budget with `time_to_play` None, visible in the verdict.
  The explore ladder's own Fail (`escape_max`) is what ends an unknown that nothing moves.
- **Presses buffered during a real load could reach the next screen.** The same risk any unknown press takes.

## Full selftest run

`bash docs/testing/jobs/selftest.sh` on this tree (base e20a67e7d2 + the files above): **3863 passed, 0 failed,
all 160 fragments**. `python3 docs/testing/titles/pathclass_selftest.py` (standalone; no fragment runs it):
**0 failure(s)**, including the 7 new `loading` checks. Territory: `[lane.loadstuck1021]` pushed to origin/board
(e2af95528f), `check_territory.py` ok, every file released at ready.

## Proposed device proof (not part of the fold)

NFS Hot Pursuit 2 (45410028) on the Nova, through the dispatcher, no route (the auto route attaches). It passes if:
the briefing is left (a `loading-overstay` line, then a press, then the picture changes), the car moves (a
`play-probe won` line), `input` and `play-probe` lines sit beside the `gfps=` lines in logcat.txt, and
`playprobe_report.py <result dir>` ties every below-bar play second to an input or says there is none.
