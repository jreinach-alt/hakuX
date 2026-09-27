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

## 3. Why attempt 1 did not finish, and the move to the Nova

Attempt 1 ended correctly on a wait: the Blinx pilot pair (`1790473035-...-1078946` A,
`1790473037-...-1082948` B) was queued on the Thor. The pair never ran. At 02:30Z the
owner put the Thor on hold to charge it from 7% on a 500 mA port, and only the owner lifts
that hold. Blinx is staged on the Thor only. hostops (19:51 PDT) asked for M4' on a Nova title.
Attempt 2 (2026-09-27 ~03:00Z) did the following:

- Merged origin/master (231d04df51) and withdrew the Thor pair to `dispatch/queue/withdrawn/`
  with no result. `tbflip424-blinx.json` stays on file as registered, unmeasured.
- Registered `docs/testing/predictions/tbflip424-doa1u.json` (ab07cd2483, sha256 8178685c...)
  before any run: Dead or Alive 1 Ultimate, survey route, 420 s, Nova, A/B = 231d04df51 with and
  without `HAKUX_TCG424_RANGE=1`, the same reader (`playread.py`, unchanged).
- Why DOA1U: of the Nova titles with a survey soak that reaches play and carries [tlb68] lines,
  it is the closest to Blinx's cost-side profile. titlebench's `1790467161-titlebench-2613663`
  (pre-#434 binary) reads churn 1.2%, slow/s 1115 against inv/s 305, and gfps 27.5 against a
  target of 60, so it runs uncapped. Every play frame after `mark play` is a STAGE 01 fight
  (`route-frames/192135-play.png` to `192434-play.png`). Rejected: Crimson (already priced by
  M3), CoD3 (29 against a cap of 30), and AUF (churn 0.6).
- The M1 floor on A's churn is 0.5 here, not 1.0. The one run on disk reads 1.2, and a floor at
  1.0 would decide the leg on noise. It was fixed in the file before the pilot was queued.
- The addendum's `HAKUX_TCG68_JC` default flip is commit af6fffdc0c (cputlb.c, the default plus
  the comment). Its pixel must-not-move leg goes in the pgraph arm on the flipped binary.

## 4. Runs (DOA1U, Nova)

| request | arm | round | gameplay gfps | churn% | ng | note |
|---|---|---|---|---|---|---|
| `1790477688-lane.tbflip424-1974728` | A | r1 (pilot) | 30 | 1.4 | 53 | rt 0, fatal 0, tail 4.9 s; G 33.5 ms, slow/s 1320, inv/s 260; STAGE 01 fight in `route-frames/213116-play.png` |
| `1790477690-lane.tbflip424-1974936` | B | r1 (pilot) | | | | queued |

## 5. Waiting (2026-09-27 ~03:15Z)

The Nova queue ahead holds an AUF soak (#412), a DOA pair (#413) and lane.titleroutes' 30-min
sessions. On resume:
1. `python3 docs/lanes/tbflip424/playread.py 1974728 1974936`. Check M0 (mark play, ng >= 20,
   rt 0 on A and 1 on B, fatal 0, tail <= 15 s) and look at one play frame per arm.
2. Write `pilots/lane.tbflip424.ok` (with python3), then queue A B A B for r2 and r3.
3. Do not push the range flip until M4' is read.

## 6. Attempt 3 (2026-09-27 ~04:10Z)

Why attempt 2 did not finish: it ended on a correct wait. The Nova pilot pair was queued behind
#412, #413 and lane.titleroutes' sessions and had not run. At 04:12Z both `.req` files were still
in `dispatch/queue/`, next in line behind `slowdown462`. Attempt 2 also ended before the 21:11 PDT
addendum arrived.

- The JC default-on (#425) is now its own PR, #465 (`lane/tbflip424-jc`, cf09ea47a1 = af6fffdc0c
  cherry-picked onto e5db66fa37). accel/tcg/cputlb.c compiles clean with the desktop build's
  command under `-Werror`, and with the Android arm64 NDK clang command from
  `android/app/.cxx/Release/3z4l2q3k` (no diagnostics on the changed lines; that file already had
  `-Wshift-negative-value` warnings, which is why that check runs without `-Werror`). #456 still
  carries the same commit. The two changes are identical, so whichever folds first leaves the other
  merging cleanly.
- Merged origin/master (e5db66fa37) into this branch. The DOA1U prediction's refs (231d04df51)
  are still ancestors, since this was a merge and not a rebase.
- Pilot A ran 04:25-04:34Z and passes M0: `mark play` present, ng 53, rt 0, fatal 0, tail 4.9 s.
  A's churn of 1.4% is above M1's 0.5 floor. The play frames are a STAGE 01 fight. At 05:16Z pilot B
  (`1974936`) was still queued. Ahead of it on the Nova were lane.slowdown462's repeated short holds
  (the battery is under 15%, on an owner override until 23:30 PDT) and three 60 s arms. r2/r3 stay
  unqueued until B shows rt 1 and a lower churn, per the pilot rule.
