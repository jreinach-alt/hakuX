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

## Waiting

`docs/lanes/hangwatch/WAITING` names the owner's decision in candidate 1 above. Nothing else here needs a device.
