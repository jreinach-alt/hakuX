# hangwatch: a locked-up title is caught on telemetry in about 90 s, not waited out
State: ready

Lane: hangwatch            Issue: none (harness defect, dispatched directly)
Base: master @ 425ffe1ad1
Files: docs/testing/hangwatch.py, docs/testing/jobs/selftest.d/59-hangwatch.sh, docs/testing/titles/pathfind.py, docs/investigations/2026-10-04-hangwatch-lockup-detector.md, docs/lanes/hangwatch/NOTES.md, docs/lanes/hangwatch/PR.md, docs/lanes/hangwatch/OUTBOX.md, docs/lanes/hangwatch/calibrate.py, docs/lanes/hangwatch/calibration.md, docs/lanes/hangwatch/pathfind-hook.patch, docs/lanes/hangwatch/runs/whiteout/result.json, docs/lanes/hangwatch/runs/whiteout/verdict.json, docs/lanes/hangwatch/runs/whiteout/hang.jsonl, docs/lanes/hangwatch/runs/whiteout/IDENTIFIED.json, docs/lanes/hangwatch/runs/whiteout/steps.jsonl, docs/lanes/hangwatch/runs/whiteout/calls.jsonl, docs/lanes/hangwatch/runs/whiteout/run.log, docs/lanes/hangwatch/runs/whiteout/hdd.json, docs/lanes/hangwatch/runs/whiteout/screen-logcat.txt, docs/lanes/hangwatch/runs/whiteout/strip.jpg, docs/lanes/hangwatch/runs/whiteout/hang/dumpsys.txt, docs/lanes/hangwatch/runs/whiteout/hang/logcat-tail.txt, docs/lanes/hangwatch/runs/whiteout/hang/last-frames.txt, docs/lanes/hangwatch/runs/whiteout/hang/tombstone.txt, docs/lanes/hangwatch/runs/whiteout/hang/probe-before.png, docs/lanes/hangwatch/runs/whiteout/hang/probe-after.png
Prediction: none: no arm
Needs device: no (the supervised Whiteout confirmation ran 10-04 14:49 PDT, before this PR's last change)
Needs NDK: no

## What this does

Owner, 2026-10-04: a locked-up title must be caught on telemetry in about two minutes, not waited out. The Whiteout
claim held the Nova for 15 minutes on one loading card. This adds a stop condition. It never turns a failed run
into a pass; no threshold, the 600-s rule and the perf verdict are unchanged.

- `docs/testing/hangwatch.py` (stdlib only): a HANG is three signals bad together for `HANG_S` = 90 s. The screen did
  not change (pathfind's own measure, FPS masked); the guest's audio made no new non-silent window (`hakuX-audio`
  level lines); the vCPU is pinned (`[rr425w]` idle <= 50 ms, one `[rr425pc]` pc takes >= 0.9 of the returns). A
  signal the log does not carry is unknown and never confirms.
- On a trip: ONE A press, logged as a probe, then the screen and the telemetry are checked again for 20 s. Only then
  the verdict: the logcat tail, the crash buffer, `dumpsys cpuinfo`, `verdict.json`, and
  `failure_intake.py one --force` (class `hang`). Result `hang`, distinct from `gave-up`.
- Recheck fix (this attempt): the verdict's telemetry must be post-press. The log is drained before the press, and
  the streak must hold at the end of the log, RECHECK_S past the press. Before, a guest that woke within 20 s could
  still return a HANG on lines written before the press. Selftest case `telemetry-recovers` added (16 checks).
- `docs/testing/titles/pathfind.py` (grant on origin/board, row `[lane.hangwatch]`): the hook is applied to the screening
  loop (`run()`) and the hold loop (`hold_play()`), about 25 lines. `pathfind-hook.patch` is the same change, regenerated
  from the applied tree.

## Evidence

- Supervised confirmation (Nova, `pathfind.py 4B4E0001 --device nova --budget-min 5`, 10-04 14:49 PDT, owner-approved):
  HANG at 286.7 s, 32 steps, 21 model calls, hold released. Frames still from the first static look (run 174.7 s)
  through the trip; audio quiet and the vCPU pinned on the hang's own logcat (`runs/whiteout/screen-logcat.txt`): an
  offline replay gives one pinned+quiet streak of 116 s, starting at the verdict's `since`. One A press changed nothing
  (frame change 0.000). The stop came about 90 s after the static onset. Detail and caveats: NOTES.md "Supervised
  Whiteout confirmation".
- Module selftest: `python3 docs/testing/hangwatch.py selftest`: all ok (16 checks). Real idle logcat lines do not
  trip; the Whiteout-shaped windows trip after HANG_S; a moving screen, audio still producing, a busy guest spread over
  many PCs, a vCPU that idles, no telemetry, a partial line, a press that moves the screen, a press after which
  telemetry stops, and a press after which the guest recovers do not.
- Calibration (`docs/lanes/hangwatch/calibration.md`, from 1162 rr425 logcats): pinned+quiet reaches 90 s in one file,
  the Tron 2.0 hang (716 s, frames static from 30 s). The largest other value is 70 s (Forza, no frames to judge).
  All 18 gameplay holds stay at <= 5 s. No legitimately static load with telemetry is in the corpus (see Not done).
- Known misses, stated in the investigation: the Tron call/ret hang (#672 runs 1 and 6) reads 2-4 s pinned and is not
  caught; the detector needs a guest-progress signal for that class.

## Not done here

- The dispatch soak has no stop condition. `dispatcher.sh` is lane.toolsmith's; not touched.
- The ESPN NHL 2K5, Simpsons and GTA SA loads have no telemetry in reach, so the legitimately static loads are not scored.
- The Whiteout row's hold in `failure_intake.py` is not verified: the intake's record has route_sha `da39a3ee5e6b`
  (empty route). host-tools is outside this worktree. Already in OUTBOX as the gate issue.

## Checks run

- `python3 docs/testing/hangwatch.py selftest`: all ok (16 checks, after the recheck fix).
- `env SELFTEST_ONLY=59-hangwatch bash docs/testing/jobs/selftest.sh`: 1 passed, 0 failed (after the recheck fix).
- `python3 docs/testing/titles/pathfind_selftest.py` on the applied tree: all ok (after the recheck fix).
- `python3 -m py_compile docs/testing/hangwatch.py docs/testing/titles/pathfind.py`: compiles.
- `env SELFTEST_ONLY=96-failgate bash docs/testing/jobs/selftest.sh`: 12 passed, 0 failed (attempt 2).
- `docs/testing/preflight.sh`: every gate passed except `coverage` in attempt 2 (#811 has no lane or blocker on the
  board; that row is the board's). Not re-run in attempt 3.
- Full `docs/testing/jobs/selftest.sh` (126 fragments): not run; it exceeds one tool call.

## Next, by P x win

1. Wire `hangwatch.look` into the dispatch soak (`dispatcher.sh`, lane.toolsmith's; needs a grant). P about 0.9 for the
   class it catches (the Tron 2.0 hang would have stopped at about 130 s of 720 s; the Whiteout hang at about 270 s of
   the 5-min budget). Win: about 590 s of device time per such soak. Cost: a grant and one harness session, no device.
2. The guest-progress signal for the call/ret class (`hakuX-pace` flips or GPU submits; #672 runs 1 and 6). P about 0.5
   (no measurement yet on the 18 holds). Win: the class the rule misses (Tron 2.0 at minimum). Cost: one offline pass
   over existing logs, no device. Can run in parallel with (1).
3. Score the legitimately static loads with telemetry (ESPN NHL 2K5, Simpsons, GTA SA). P that they do not trip: high
   but unmeasured. Win: a false HANG on a legal load is the one way this rule costs a good title. Do before widening
   the rule to the soak on more titles.

Lane gate: pathfind.py is `[lane.hangwatch]` territory on origin/board (granted 10-04 14:18; pathfind retired).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
