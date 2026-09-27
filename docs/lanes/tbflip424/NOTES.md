# lane.tbflip424 -- #424 Blinx gameplay leg and range-test default flip

Base: master @ 46936c6a3d (PR #434 folded). PR #456.

## 1. The instrument

- Route and title: those of titlebench's Blinx soak (`1790467161-titlebench-2612887`):
  `4D530013-Blinx_The_Time_Sweeper.xiso.iso`, `--route survey`, Thor.
- The survey route writes `mark play`, never `mark gameplay`, so `churn.py` would read from
  the first log line, menus included. `playread.py` (this dir) is `churn.py` with the window
  anchored on `mark play` + 30 s. With no mark, a run is VOID. It adds `ng` (gfps samples),
  `rt` (the [tlb68] rt= values), `fatal` and `tail` (last gfps sample to `soak end`).
- Blinx is already in its first stage before `mark play`: the START/A rounds pause and
  resume it. After the mark the route only plays. Pass 1's frames show this
  (`0-0-y-1790433159-titleplay-p1-blinx/route-frames/110116-play.png` onward, FPS 9).
- `mark play` lands ~257 s into the soak, so 420 s leaves ~130 s of window. The arm runs
  540 s.
- On tbchurn424's Blinx runs (300 s, 3-4 samples in the window), A reads churn% 2.2/2.8 and
  B reads 0.0/0.0. The counter leg can separate the arms on gameplay.

## 2. The prediction

`docs/testing/predictions/tbflip424-blinx.json`, committed in 442834864e before any run.
A = 46936c6a3d with no env; B = the same apk with `--env HAKUX_TCG424_RANGE=1`. 3 runs per
arm, interleaved. Legs M0 (instrument), M1 (counter: A churn >= 1.0, B <= 0.5 x A, di/s
falls >= 10x) and M4' (B median gfps >= A - 1, no FATAL, frames to the end).

## 3. Runs

| request | arm | round | gameplay gfps | churn% | ng | note |
|---|---|---|---|---|---|---|
| `1790473035-lane.tbflip424-1078946` | A | r1 (pilot) | | | | queued |
| `1790473037-lane.tbflip424-1082948` | B | r1 (pilot) | | | | queued |

## 4. Waiting (2026-09-27 ~01:45Z)

The pilot is queued behind ~43 min of titlebench runs on the Thor. `handback.sh` resumes this
lane when the two pilot results carry DONE/ERROR (`draft-strand-runs`; the arms job skips soak
predictions, so no `[job.arms]` verdict will come). On resume:
1. `python3 docs/lanes/tbflip424/playread.py 1078946 1082948`. Check M0 (mark play, ng >= 20,
   rt 0 on A and 1 on B, fatal 0, tail <= 15 s) and look at one play frame per arm.
2. Write `pilots/lane.tbflip424.ok` (with python3), then queue A B A B for r2 and r3.
3. Do not push the flip until M4' is read.
