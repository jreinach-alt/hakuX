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

## Waiting

`docs/lanes/hangwatch/WAITING` names `grant docs/testing/titles/pathfind.py`. The hook (`pathfind-hook.patch`) and the
supervised confirmation both wait on it. Nothing else here needs a device.
