# hangwatch: a locked-up title is caught on telemetry in about 90 s, not waited out
State: draft

Lane: hangwatch            Issue: none (harness defect, dispatched directly)
Base: master @ 425ffe1ad1
Files: docs/testing/hangwatch.py, docs/testing/jobs/selftest.d/59-hangwatch.sh, docs/testing/titles/pathfind.py, docs/investigations/2026-10-04-hangwatch-lockup-detector.md, docs/lanes/hangwatch/NOTES.md, docs/lanes/hangwatch/PR.md, docs/lanes/hangwatch/OUTBOX.md, docs/lanes/hangwatch/WAITING, docs/lanes/hangwatch/calibrate.py, docs/lanes/hangwatch/calibration.md, docs/lanes/hangwatch/pathfind-hook.patch
Prediction: none: no arm
Needs device: no for this PR; the supervised Whiteout confirmation is open (see Not done here)
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
- `docs/testing/titles/pathfind.py` (grant on origin/board, row `[lane.hangwatch]`): the hook is applied to the screening
  loop (`run()`) and the hold loop (`hold_play()`), about 25 lines. `pathfind-hook.patch` is the same change, regenerated
  from the applied tree (the attempt-1 patch no longer applied after pathfind's fold).

## Evidence

- Selftest, alone: `env SELFTEST_ONLY=59-hangwatch bash docs/testing/jobs/selftest.sh`: 1 passed, 0 failed.
  The module selftest has 15 checks: real idle logcat lines do not trip; the Whiteout-shaped windows trip after
  HANG_S; a moving screen, audio still producing, a busy guest spread over many PCs, a vCPU that idles, no telemetry,
  a partial line, a press that moves the screen, and a press after which telemetry stops do not.
- Patched pathfind's dry selftest (`pathfind_selftest.py`, on a temp copy): 52 checks, all ok.
- Calibration (`docs/lanes/hangwatch/calibration.md`, from 1162 rr425 logcats): pinned+quiet reaches 90 s in one file,
  the Tron 2.0 hang (716 s, frames static from 30 s). The largest other value is 70 s (Forza, no frames to judge).
  All 18 gameplay holds stay at <= 5 s.
- Known misses, stated in the investigation: the Tron call/ret hang (#672 runs 1 and 6) reads 2-4 s pinned and is not
  caught; the detector needs a guest-progress signal for that class.

## Not done here

- The supervised Whiteout confirmation (Nova, <= 5 min, expecting HANG near 90 s) is not run. request.sh cannot run a
  pathfind claim, and a direct pathfind.py run is outside this lane's device rules. Owner decision in WAITING. The hook
  is not folded until it returns HANG.
- The dispatch soak has no stop condition. `dispatcher.sh` is lane.toolsmith's; not touched.
- The ESPN NHL 2K5, Simpsons and GTA SA loads have no telemetry in reach, so the legitimately static loads are not scored.

## Checks run

- `python3 docs/testing/hangwatch.py selftest`: all ok (15).
- `env SELFTEST_ONLY=59-hangwatch bash docs/testing/jobs/selftest.sh`: 1 passed, 0 failed.
- `python3 docs/testing/titles/pathfind_selftest.py` on the patched copy (staged in a temp dir): 52 ok.
- `python3 -m py_compile` on the patched pathfind: compiles.
- `git apply --check -R docs/lanes/hangwatch/pathfind-hook.patch`: matches the applied tree.
- `python3 docs/testing/titles/pathfind_selftest.py` on the applied tree (attempt 2): all ok.
- `env SELFTEST_ONLY=96-failgate bash docs/testing/jobs/selftest.sh`: 12 passed, 0 failed.
- `docs/testing/preflight.sh` (also with `--allow-tracker`): every gate passes except `coverage`. #811 (the Whiteout
  issue) has neither a lane nor a blocker on origin/board. That row is the board's and this lane may not write it;
  `--allow-tracker` does not clear this gate. Needs lane.local to classify #811 (see OUTBOX.md).
- Full `docs/testing/jobs/selftest.sh` (126 fragments): not run. Only fragment 59 was run, alone.

## Next

Owner picks how the supervised Whiteout run is taken (NOTES.md "Supervised confirmation"): (1) a hold.sh-taken direct
pathfind run, P about 0.9, about 6 min of Nova; or (2) a pathfind mode in request.sh (toolsmith), same P once built.
The hook is folded only if that run returns HANG. The guest-progress candidate (NOTES.md) comes after that.

Lane gate: pathfind.py is `[lane.hangwatch]` territory on origin/board (granted 10-04 14:18; pathfind retired).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
