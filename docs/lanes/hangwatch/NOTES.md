# lane.hangwatch: notes

The record is `docs/investigations/2026-10-04-hangwatch-lockup-detector.md`. This file is what the next lane needs.

## Tried, measured

- `docs/testing/hangwatch.py`: three signals (still, quiet, pinned) over `HANG_S` = 90 s. Selftest: 15 checks,
  green alone (`SELFTEST_ONLY=59-hangwatch`) and in the dry pathfind selftest (52 checks, on the patched copy).
- Calibration over 1162 rr425 logcats: pinned+quiet reaches 90 s in one file (the Tron 2.0 hang, 532476). The
  largest other value is 70 s (Forza memfast-3557775, no frames to judge it). `calibration.md` is the top 27 rows;
  `calibrate.py` regenerates the full table.
- Whiteout claim: no logcat was kept (the screening loop never started one). Its frames were static from look 15
  (about t=146 s) to the end (about t=898 s). The screen half alone would have tripped about t=236 s.

## Must not repeat

- Do not tune thresholds to the Whiteout alone. The table has no legitimately static load with telemetry; ESPN NHL
  2K5, Simpsons and GTA SA loads are not in reach. Score them before moving HANG_S or PIN_SHARE.
- Do not treat audio or the pinned PC alone as a hang. Audio is silent for 600+ s in two legitimate runs; the pinned
  PC reaches 88 s in Midnight Club 3.
- Do not assume `steps.jsonl` has `changed`. The loop writes the line before it sets the value (in memory only).
- Do not read `[rr425pc]` top entries as "the stuck PC" in a call/ret loop: the #672 Tron hang's top entries are
  interrupt paths, and the pinned signal misses it.

## Next, by P x win (candidates re-scored after this lane's results)

1. Guest-progress signal for the call/ret class (`hakuX-pace` flips, or GPU submits). P about 0.5 (the #672 notes:
   no GPU submission, no flips; not yet measured on the 18 holds). Win: the class the rule misses; Tron 2.0 at minimum.
   Cost: one pass over existing logs, no device. Goes first: it decides whether the rule can catch #672's hang.
2. Wire `hangwatch.look` into the dispatch soak (`dispatcher.sh`, owned by lane.toolsmith). P about 0.9 for the class it
   catches (the 532476 run would have stopped about 130 s into 720 s). Win: about 590 s of device time per such hang.
3. Score the screen half on the loading cards (a supervised Whiteout run with logcat kept). P unknown; it is the case
   that started the rule and it is untested.

## Attempt 2: why attempt 1 did not finish, and what this one did

- Attempt 1 ended on `WAITING: grant docs/testing/titles/pathfind.py`. It never applied the hook and never queued the
  supervised run, so the one thing the rule needs (a HANG confirmed on the live Whiteout) is still open.
- The grant landed on origin/board (row `[lane.hangwatch]`, `territory.toml` line 789; `[lane.pathfind]` retired).
  WAITING is deleted.
- `pathfind-hook.patch` no longer applied: pathfind's fold (3fe51047d8) moved `pathfind.py`. The import, `__init__`,
  `run()` and `finish()` hunks landed; the `hold_play()` hunk was rejected and placed by hand after the `still` line.
  The patch was regenerated from the applied change (`git apply --check -R` passes). One change from attempt 1: the
  hold's hang exit guards `cat` (it is None on the dry device).
- Selftests on the applied tree: `hangwatch.py selftest` ok; `pathfind_selftest.py` ok (all checks); fragment 59 1/0;
  fragment 96-failgate 12/0. The full `selftest.sh` (126 fragments) runs longer than one tool call (it passed 5 of 126
  in 580 s when timed out), so it is not run here.

## Supervised confirmation: not queued (blocker)

`request.sh` cannot run a pathfind claim: it has no pathfind mode, and `pathfind.py` drives the Nova over adb from its
own `Device` class. Nothing in the tree names the Whiteout ISO, so a plain `--title` soak is not possible either. A
direct `pathfind.py 4B4E0001 --device nova` would touch the device outside request.sh, which this lane may not do. So
the Nova is untouched and the HANG confirmation is open. Candidates for the next step, P x win:

1. Owner decides: a supervised `hold.sh take nova lane.hangwatch` plus one `pathfind.py 4B4E0001 --device nova
   --budget-min 5 --out ...` run (the way lane.pathfind ran its claims). P about 0.9: the same device path ran 138 looks
   on this title, and the signals are already selftested on the Whiteout-shaped windows. Win: the hook's first live
   result, and the rule is confirmed or refuted on the case that started it. Cost: one run, about 6 min of Nova time.
2. Toolsmith adds a pathfind mode to request.sh. P about 0.9 once it exists, same win, but it is a harness change in
   lane.toolsmith's territory and takes a session of its own. Do after (1) if the rule proves itself.

The hook is not folded until (1) or (2) returns HANG, per the brief.

## Attempt 3: why attempt 2 did not finish, and what this one did

- Attempt 2 ended on `WAITING` (the owner's choice of how to take the Nova). It never ran the one thing that confirms
  the hook, so the hook could not be folded. Nothing in the attempt was wrong; it was blocked on a decision.
- The owner took option 1 (lane.local, 10-04 15:15 PDT): the supervised Whiteout run was done with the Nova
  (`pathfind.py 4B4E0001 --device nova --budget-min 5`, hold released). Artifacts are under
  `docs/lanes/hangwatch/runs/whiteout/`. `WAITING` is deleted.

## Supervised Whiteout confirmation: HANG (10-04, 14:49 PDT run)

Result: `HANG` at 286.7 s, 32 steps, 21 model calls, released the Nova. The title sat on the "LOADING / COMING UP NEXT"
card after Track select (step 16) from look 17.

| | run clock | log clock (rr425 / hakuX-audio) |
|---|---|---|
| first static look (look 18, `changed` <= 0.01) | 174.7 s | streak start 146.745 (= 174.5 on the run clock) |
| first trip (pinned + quiet + still, `HANG_S` 90 s) | ~264.7 s | 236.983 |
| the one A press (probe) | after the trip | not logged on the log clock (the probe event has wall time only) |
| verdict (after the post-press recheck) | 286.7 s | 242.003 |

Answers to the questions the owner asked:

- **Does the 95 s cover frames, audio and PC from the hang's own logcat?** Audio and PC: yes. The detector reads
  `screen-logcat.txt` (the file the run kept, 3034 lines, 136 `[rr425pc]`, 136 `[rr425w]`, 262 `hakuX-audio`). An
  offline replay through `Watch` gives exactly one pinned+quiet streak, 27183146.745 to the end of the log (116 s),
  which starts at the `since` the verdict records. Before the static onset the audio had non-silent windows (quiet
  False from 27183001 to 27183141), so the quiet signal starts only with the screen: the three signals line up
  at one moment, they are not a pre-existing condition. Frames: the still signal is not in the log. It comes from the
  looks. Pathfind's `changed` over consecutive loading frames 017 to 033 (`frames/`, the 160x120 rule) is 0.0 on every
  pair, so the still signal holds for the whole window. The probe pair (`hang/probe-before.png`, `probe-after.png`)
  scores 0.000.
- **How many looks after the static onset?** 15 recorded looks (18 to 32, all `loading`, all `static`-labelled
  except 23 and 29, which the model labelled `fast`; their frame change is 0.0 as well), plus the look that tripped
  (033), so 16 looks in all; about 90 s from the first static look to the trip.
- **Is it a wait or a hang?** A hang. The PC is pinned (`[rr425w]` idle_us 0, busy_us 2047086 of a 2048 ms window,
  one PC `r:800151ed` at share 1.0), the audio is flat and the screen is still. One A press changed nothing. The
  tombstone file is empty (`hang/tombstone.txt`, 1 byte): no crash record, so a hang, not a crash. `hang/dumpsys.txt`
  holds the cpuinfo and the emulator process (`com.jreinach.hakux.debug:xemu`, pid 12087); it was not read for load.
- **Pinned before the trip:** the PC was pinned from log 27183068 (about 1 minute before the streak), so the vCPU was
  already busy before the screen stopped moving. The screen stop, not the PC, is what set the 90 s clock.

Four caveats for the next lane:

1. The verdict's recheck was flawed (fixed in this lane, see below). In this run the verdict's telemetry is the 242.003
   line, the first line the recheck read; the press was not stamped on the log clock, so this run cannot show that the
   telemetry was post-press. The frame check (0.000 after the press) and the 95 s of pre-press telemetry hold regardless.
2. `IDENTIFIED.json` has `route_sha` `da39a3ee5e6b` (the sha of an empty route): the screening claim has no route file,
   the same cause as the OUTBOX issue "the hang gate in failure_intake.py cannot hold a screening claim". Whether
   the Whiteout row is held by its gate could not be checked from this worktree (host-tools is outside it). Open.
3. `steps.jsonl` `changed` is still null on every row (the known loop-order issue; the still signal here came from the
   frames, not the step file).
4. The legitimately static loads are not scored: no logcat exists for the ESPN NHL 2K5, Simpsons or GTA SA loads.
   The table in `calibration.md` still has no legitimate static load with telemetry.

## The recheck fix (this attempt)

`look()` judged the verdict with the first unread log line after the press. The pre-press lines were still unread
(the poll stops at the first trip), so a guest that woke up within RECHECK_S could still return a HANG on its
pre-press lines. Now:

- the log is drained before the press, so `pressed` is the log's clock at the press (a streak that broke before the
  press is not a trip);
- after the press, the log is drained again, and the verdict needs the streak to still hold at the end of the log and
  the log to have run RECHECK_S past the press;
- selftest case `telemetry-recovers` (the pre-press lines still pinned, the guest makes audio after the press) is not
  a HANG. Under the old code that case returns a HANG; this was not run against the old code, only reasoned.

## What the confirmation changes

- The hook is confirmed by one live HANG on the case that started the rule. It is cleared to fold.
- The screen half alone (the old candidate 3) would have tripped at about 236 s on the log clock. The trip used all
  three signals, so this run does not separate the screen half from the audio and PC halves; it only shows that all
  three hold together on this title.

## Next, by P x win (re-scored after the confirmation)

1. Wire `hangwatch.look` into the dispatch soak (`dispatcher.sh`, lane.toolsmith's territory; needs a grant). P about
   0.9 for the class it catches: the Tron 2.0 hang (532476) would have stopped at about 130 s of 720 s, and the
   Whiteout hang at about 270 s of the 5-min budget. Win: about 590 s of device time per such soak. Cost: a grant and
   one harness session; no device for the wiring itself.
2. The guest-progress signal for the call/ret class (`hakuX-pace` flips or GPU submits; #672 runs 1 and 6). P about
   0.5 (no measurement yet on the 18 holds; the #672 notes say no GPU submission and no flips, which is the case the
   signal would need). Win: the class the rule misses (Tron 2.0 at minimum). Cost: one offline pass over existing
   logs, no device. Run in parallel with (1): it decides whether the rule can cover the call/ret class at all.
3. Score the legitimately static loads with telemetry (ESPN NHL 2K5, Simpsons, GTA SA). P that they do not trip: high
   but unmeasured. Win: a false HANG on a legal load is the one way this rule costs a good title. Cost: one logcat-kept
   run per title. Do before widening the rule to the dispatch soak on more titles.

Attempt 3 did not touch the device again.

## Waiting

Nothing. The confirmation is in; the hook is ready to fold.
