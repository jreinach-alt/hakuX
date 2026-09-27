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
| `1790477690-lane.tbflip424-1974936` | B | r1 (pilot) | 25 | 0.0 | 55 | rt 1, fatal 0, tail 2.8 s; G 40.2 ms, slow/s 146,950, inv/s 145,605, fs/s 140,324; STAGE 01 fight in `route-frames/000218-play.png` |

r2 and r3 were never queued: see section 7.

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

## 7. Attempt 4 (2026-09-27 ~14:00Z): the DOA1U pilot review, and back to Blinx

Why attempt 3 did not finish: it ended on a correct wait. Pilot B (`1974936`) was still queued
behind lane.slowdown462's holds on the Nova. It ran 06:57-07:04Z. `jobs/handback.sh` resumed the
lane at 13:47Z with CI green on ce3cf5d12e.

### The DOA1U pilot, reviewed against the batch's purpose

Both runs pass M0 (`mark play`, ng 53 / 55, rt 0 on A and 1 on B, fatal 0, tail 4.9 / 2.8 s), and
the counter moves (churn 1.4 -> 0.0, di/s 260 -> 0). As registered, one run per arm reads
**A 30, B 25 gfps**, which leans to FAIL on M4'. That is one run per arm. It is not a verdict and
it is not a pass.

The remaining four runs were not queued, because the pilot shows the instrument cannot price a
vCPU cost on this title. Both reasons come from A-path runs alone:

1. **The vCPU thread is idle most of the window.** vCPU cpu over wall (`cpu=` / `dt=` on the
   [tlb68] lines after the mark):

   | title | runs | vCPU busy |
   |---|---|---|
   | DOA1 Ultimate (Nova) | `1974728`, titlebench `2613663`, slowdown462 `3154279` | 37.6, 46.4, 44.9% |
   | Blinx (Thor) | pass 1, tbchurn424 A `3970398` / `3970610` | 68.2, 58.1, 60.8% |
   | Crimson (Thor) | tbchurn424 A `3968865` / `3970176` | 87.1, 85.4% |

   At ~40% busy the fights are not bound by guest CPU, so gfps does not follow a vCPU cost.
   `why_this_title` in tbflip424-doa1u.json read "below its cap" as "can show a cost". That was
   wrong: it is below its cap for another reason.
2. **The window is not one kind of content, and the route does not take one path.** A fought as
   Hayabusa in the desert (`1974728/route-frames/213116-play.png`), with a story cutscene at
   FPS 29 (`212957-play.png`). B fought as Kasumi in the clock tower (`000218-play.png`) and was
   back on CHARACTER SELECT at FPS 59 by `000334-play.png`. Three A-path runs on disk read 21,
   27.5 and 30 in this window, a spread of 9 against a margin of 1.

What the pilot does give is the cost side's counter. On B, 145,605 stores a second reach the
invalidator (A: 260), and the bitmap answers 140,324 of them (96%). That is 3x Crimson's 47k and
4x Blinx's 32-42k. B's vCPU busy share is 39.9% against A's 37.6%, on different content, so that
pair decides nothing either.

tbflip424-doa1u.json stays on file as registered: piloted, not completed, no verdict.

### Back to Blinx on the Thor: `tbflip424-blinx2.json`

- The Thor claims requests again (titleroutes and lanelocal soaks, 08:31Z-13:46Z), so the leg
  returns to the title the brief and the tracker row name.
- Merged origin/master (f131dd11c6) as 00c2840810. Master now has JC on by default (#465 folded
  04:46Z), so the binary the flip ships in is not the one the first Blinx file names. The branch's
  accel/ diff against master is empty.
- Registered `docs/testing/predictions/tbflip424-blinx2.json` on 00c2840810 before any run. The
  legs are tbflip424-blinx.json's with the same thresholds (M1: A churn >= 1.0, B <= 0.5 x A,
  di/s B <= 0.1 x A; M4': B median gfps >= A - 1, no FATAL, tail <= 15 s). Blinx's churn on A is
  rd% 1.9-2.6 plus jc% 0.2, so JC on leaves the 1.0 floor standing.
- One M0 clause is new, stated before any run: **m50 >= 4**. The Thor has a slow state in which a
  whole run crawls (titlebench `2612887`: gfps 2 in the window, 12 perf samples before the mark;
  tbchurn424's Crimson A r2 was another). The title and menu screens before `mark play` run at the
  59 cap on either arm, so `playread.py` now counts the samples >= 50 between `mark booted` and
  `mark play`. Five normal Blinx runs on disk read 6, 6, 6, 8 and 21 (both B runs read 6); the
  slow run reads 1. Under 4, the run is VOID and re-queued once.
- What the leg cannot resolve is in the file: A-path medians on the Thor read 11, 12 and 15, so a
  true loss under ~2 gfps can pass and a true zero can fail.

### Runs (Blinx, Thor, 00c2840810, 540 s)

| request | arm | round | gameplay gfps | churn% | ng | m50 | note |
|---|---|---|---|---|---|---|---|
| `1-1790517344-lane.tbflip424-1425036` | A | r1 (pilot) | 19 | 2.5 | 81 | 29 | rt 0, fatal 0, tail 0.3 s; G 51.9 ms, di/s 520, slow/s 894; stage play in `route-frames/085757-play.png` |
| `1-1790517350-lane.tbflip424-1433200` | B | r1 (pilot) | 17.0 | 0.0 | 74 | 25 | rt 1, fatal 0, tail 2.8 s; G 53.0 ms, di/s 0, slow/s 31,384, fs/s 31,561; stage play in `route-frames/090705-play.png` |
| `1-1790525434-lane.tbflip424-730013` | A | r2 (**Nova**) | 23.0 | 0.9 | 88 | 30 | rt 0, fatal 0, tail 1.6 s; G 43.8 ms, di/s 564, slow/s 929 |
| `1-1790525435-lane.tbflip424-730250` | B | r2 (**Nova**) | 21 | 0.0 | 89 | 31 | rt 1, fatal 0, tail 1.3 s; G 46.2 ms, di/s 0, slow/s 35,784, fs/s 35,671 |
| `0-0-x-1790525435-lane.tbflip424-730605` | A | r3 (**Nova**) | 19.0 | 0.8 | 86 | 30 | rt 0, fatal 0, tail 2.4 s; G 49.6 ms, di/s 533, slow/s 1237 |
| `0-0-x-1790525435-lane.tbflip424-730719` | B | r3 (**Nova**) | 21.5 | 0.0 | 92 | 30 | rt 1, fatal 0, tail 1.0 s; G 46.0 ms, di/s 0, slow/s 37,615, fs/s 36,672 |
| `1-1790532976-lane.tbflip424-3375310` | A | r4 (Nova) | 19 | 0.8 | 87 | 31 | rt 0, fatal 0, tail 5.1 s; G 47.8 ms, di/s 537, slow/s 1232 |
| `1-1790532976-lane.tbflip424-3375824` | B | r4 (Nova) | 21.0 | 0.0 | 86 | 31 | rt 1, fatal 0, tail 2.6 s; G 48.7 ms, di/s 0, slow/s 37,119, fs/s 37,169 |

## 8. Attempt 5 (2026-09-27 ~16:10Z): the Blinx pilot, reviewed

Why attempt 4 did not finish: it ended on a correct wait. The Blinx pilot pair was queued on the
Thor at 14:09Z and ran ~15:50-16:08Z.

- Both pilot runs pass M0: `mark play` present, ng 81 / 74, m50 29 / 25 (floor 4), rt 0 on A and
  1 on B, fatal 0, tail 0.3 / 2.8 s. The play frames are Blinx stage gameplay on both arms, with
  the stage timer running.
- The counter moves as M1 requires: churn 2.5 -> 0.0, di/s 520 -> 0, and the bitmap answers the
  stores that reach the invalidator on B (fs/s 31.6k against inv/s 31.1k).
- One run per arm reads A 19, B 17 gfps. That is under M4''s A - 1, but it is one run per arm
  against a noted A-path spread of 11-15 on the Thor. It decides nothing until all six are read.
- The pilot verdict is in `pilots/lane.tbflip424.ok`. r2 and r3 are queued at priority 1 (above).

### On resume

1. `python3 docs/lanes/tbflip424/playread.py 1425036 1433200 730013 730250 730605 730719`. Check
   M0 on each run (an m50 under 4 is VOID and re-queued once), then read M1 and M4' as registered in
   tbflip424-blinx2.json: medians over the three runs per arm, no refit.
2. If M4' passes, flip `hakux_tcg424_range_on()` (default and comment only), then run the pgraph
   byte-identity check on the flipped binary. If it fails, do not flip: diagnose from cb/s, inv/s
   and slow/s and post on #424.

### Do not repeat

- Do not pick a cost-side title on "runs below its cap". Read vCPU busy (`cpu=` / `dt=`) first.
- Do not read the survey route's window on DOA1U as one workload: it is story mode, and the
  character it picks changes from run to run.
- tbchurn424's "66-68k slow stores a second on Blinx" is over the survey span. In the gameplay
  window A takes ~800-900 a second and B 32-42k.

## 9. Attempt 6 (2026-09-27 ~18:10Z): r2/r3 read, on the Nova; r4 queued

Why attempt 5 did not finish: it ended on a correct wait for r2/r3. hostops resumed the lane at
11:15 PDT once all four had run.

- **Device change.** The Thor went off USB at 10:01 PDT with a flat battery, so hostops re-pinned
  r2 and r3 to the **Nova**. Each run.log confirms it: r1 ran on serial bdc158a5 (Thor), and r2/r3
  on ee317437 (Nova). gfps from the two handhelds is not pooled.
- The amendment is on #424 (issuecomment-5858473673), posted before r4 was queued. The verdict
  comes from the Nova only: the per-arm median of r2, r3 and r4, with thresholds, reader and window
  unchanged. r1 is reported on its own as a Thor pair (A 19, B 17.0).
- All four Nova runs pass M0: ng 86-92, m50 30-31, rt as expected, fatal 0, tail <= 2.4 s.
- **Where it stands after two Nova pairs:** gfps A 23.0 / 19.0, B 21 / 21.5. **The Nova's A churn
  reads 0.9 and 0.8, under M1's registered floor of 1.0.** The Thor's A read 2.5. The floor is not
  moved. If A's Nova median stays under 1.0, M1 fails as registered and the rule says do not flip
  on this arm: Blinx gameplay on the Nova cannot price the lever. The counter itself engages fully
  (di/s ~550 -> 0, B churn 0.0).
- r4 is queued at priority 1: A `1-1790532976-lane.tbflip424-3375310`, B `...-3375824`.

### On resume

1. `python3 docs/lanes/tbflip424/playread.py 730013 730250 730605 730719 3375310 3375824`, then
   check M0 on r4 and take Nova medians over r2-r4.
2. M1 A floor < 1.0 -> no flip; report on #424 (with M4' as read, labelled inert). All legs pass
   -> flip `hakux_tcg424_range_on()` and run the pgraph byte-identity check.

## 10. Attempt 7 (2026-09-27 ~21:30Z): the verdict, no flip

Why attempt 6 did not finish: it ended on a correct wait for the r4 pair, which ran on the Nova
after the session ended. `jobs/handback.sh` resumed the lane at 21:26Z with CI green on 96af7a8506.

Merged origin/master (173 commits, clean). The branch's diff against master is now docs only: this
NOTES file, `playread.py` and the three prediction files. There is no accel/ change, since #465
landed JC default-on and the range flip is not made.

### Verdict, tbflip424-blinx2.json as amended on #424 (Nova, r2-r4, medians over three runs per arm)

| leg | A | B | registered test | verdict |
|---|---|---|---|---|
| M0 | ng 86-88, m50 30-31, rt 0, fatal 0, tail <= 5.1 s | ng 86-92, m50 30-31, rt 1, fatal 0, tail <= 2.6 s | all clauses | PASS, no VOID run |
| M1 churn% | 0.9, 0.8, 0.8 -> **0.8** | 0.0, 0.0, 0.0 -> 0.0 | A >= 1.0 and B <= 0.5 x A | **FAIL (A < 1.0)** |
| M1 di/s | 564, 533, 537 -> 537 | 0, 0, 0 -> 0 | B <= 0.1 x A | pass |
| M4' gfps | 23.0, 19.0, 19 -> **19** | 21, 21.5, 21.0 -> **21** | B >= A - 1 | reads pass, **inert** because M1 failed |

The Thor pair (r1, reported on its own, not pooled): A 19 gfps, churn 2.5; B 17.0 gfps, churn 0.0.

Gameplay frames: A `dispatch/results/1-1790517344-lane.tbflip424-1425036/route-frames/085757-play.png`,
B `dispatch/results/1-1790517350-lane.tbflip424-1433200/route-frames/090705-play.png` (Thor pilot).
The Nova runs were not read frame by frame. Their M0 columns (m50 30-31, ng 86-92) match the pilot's
normal state.

**Decision, as registered: do not flip.** M1's "A < 1.0" branch says Blinx gameplay on the Nova
spends too little on the two #424 mechanisms for the arm to show a cost that trades against a saving.
`hakux_tcg424_range_on()` stays default-off.

### What the counters show anyway (diagnosis, not a verdict)

- The range test engages fully. di/s goes ~540 -> 0. On B, ~36-37k stores a second reach the
  invalidator (A: ~530), and the bitmap answers all of them (fs/s ~ inv/s). slow/s goes ~1.2k -> ~37k.
- B's cost does not show in gfps on the Nova. B is at or above A in all three pairs, and G is flat
  (A 43.8-49.6 ms, B 46.0-48.7 ms). B's extra ~36k invalidator entries a second do not cost a
  measurable frame here.
- A narrower default (for example, the range test only on pages above a store-rate threshold) is
  **not worth a lane on this evidence**. It would exist to cut B's invalidator traffic, and nothing
  measured so far shows that traffic costing anything. What stands between the lever and 0.5 is a
  Blinx arm whose A side churns enough to price it. The Thor's A read 2.5% on r1, and
  tbflip424-blinx2.json was registered for the Thor. Two more Thor pairs would complete it as
  written (three Thor pairs with r1). That call belongs to hostops, because the amendment moved the
  verdict to the Nova.

### Do not repeat

- Do not judge a cost-side leg on the Nova's Blinx: A churns 0.8-0.9% there, against 2.2-2.8% on
  the Thor, on the same window.
- Check that the A side's counter clears its floor on the device that will run the arm before you
  move a registered arm across devices.
