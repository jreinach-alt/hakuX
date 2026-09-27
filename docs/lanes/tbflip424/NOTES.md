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
