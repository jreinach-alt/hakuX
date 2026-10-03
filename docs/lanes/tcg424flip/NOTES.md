# lane.tcg424flip (#424): flip the range test to the default

**Outcome (2026-10-03): not flipped.** Arctic M1's falsifier failed on the
Nova, and the pgraph arm was a FAIL not attributable to the flip. The branch
restores master's tb-maint.c and tb-internal.h, so the range test stays
opt-in. See "Attempt 7" at the end. The section below describes the flip
commit as it was tested.

## What changed (62ef8bf0fe, reverted to master's text in attempt 7)

`hakux_tcg424_range_on()` (accel/tcg/tb-maint.c) now returns true unless
`HAKUX_TCG424_RANGE=0`. Before, it returned true only for
`HAKUX_TCG424_RANGE=1`. Nothing else changes. The opt-out keeps the
whole-page path (xemu 703566ce33) reachable for A/B runs. The comments in
tb-maint.c and tb-internal.h now describe the new default. The `[tlb68]` line's
`rt=` field reads the same function (cputlb.c:302), so each run reports which
path it took.

Commit: 62ef8bf0fe, on master 30538458a0.

The flip follows tbflip424-blinx2.json, which passed on the Thor over three
pairs (hostops' #424 comment of 2026-09-28 22:30 PDT): M0, M1 and M4' passed,
gfps medians 19 / 19, churn% 2.1 / 0.0.

## Two predictions, both registered before any run

| file | what | who runs it |
|---|---|---|
| `docs/testing/predictions/tcg424flip-pgraph.json` | full pgraph sweep, 100 suites, every capture `must_not_move`; a = master 30538458a0, b = 62ef8bf0fe; skip `Texture_render_target::RenderTextureLoop` as the other full-sweep arms do | the arms job (a_ref != b_ref, no title) |
| `docs/testing/predictions/tcg424flip-arctic.json` | Arctic Thunder soak, Thor, MAX, cool gate, 560 s, route `arctic-thunder`; A = 62ef8bf0fe with `--env HAKUX_TCG424_RANGE=0`, B = 62ef8bf0fe with no env; 3 runs per arm, pilot = first A and first B | this lane, with request.sh (arms.sh skips soaks) |

The Arctic legs are M0 (instrument, and B reading `rt=1` with no env is the
flip's own check), M1 (churn% A >= 5, B <= 0.5 x A; di/s B <= 0.1 x A), M2a
(lane.local's on-CPU leg: on% B <= A - 2), M2b (cpf B <= 0.95 x A), and M4'
(gfps B >= A - 1; no crash; tail <= 15 s). The flip ships iff M0, M1 and M4'
pass and the pgraph arm is byte-identical. M2a and M2b decide what the release
note can claim.

Why M2b was added: on% alone cannot tell apart a saving the vCPU spends on more
frames and no saving at all. On a guest-bound title the first case is the one
we want, so a fall in on% is not the only good outcome. cpf (vCPU on-CPU ms per
game frame) measures the same saving per unit of work.

## The reader

`docs/lanes/tcg424flip/arcticread.py` loads `docs/lanes/tbflip424/playread.py`
unchanged and swaps two strings in it before it runs:

- `'mark play'` becomes `'mark gameplay'`. The arctic-thunder route writes no
  `mark play`.
- `'mark booted'` becomes `'soak start'`, which is m50's start. The route writes
  no `mark booted`.

It adds `on%` and `cpf`. playread.py itself is not edited.

## Baseline on disk (A path only, before this lane)

`baseline.out`, from lane.slowtier2's two titleroutes runs (Thor, MAX):

| run | gfps | churn% | di/s | inv/s | slow/s | on% | cpf | m50 |
|---|---|---|---|---|---|---|---|---|
| 1-1790547557-titleroutes-979135 (677ae13af8) | 21 | 14.1 | 37,642 | 7,364 | 10,221 | 87.6 | 41.7 | 89 |
| 1-1790548502-titleroutes-1531400 (e884ad260e) | 23.0 | 13.9 | 41,061 | 8,092 | 11,202 | 87.1 | 37.9 | 88 |

Arctic spends 14% of its vCPU time on the two #424 mechanisms. Blinx spends
2.1%.

## Runs

Pilot queued 2026-09-29 05:4xZ, both pinned to the Thor at 62ef8bf0fe with
expect_sha 9aeef14aa07b (read back from the queue files):

- A: `1-1790660189-lane.tcg424flip-1147138` (`HAKUX_TCG424_RANGE=0`)
- B: `1-1790660193-lane.tcg424flip-1148129` (no env)

The Thor held a cold-slot hold for slowtier2's
`1-1790609664-lane.slowtier2-alias942359` when these were queued. The cool gate
applies to each run anyway.

The pgraph arm (tcg424flip-pgraph.json) is left to the arms job.

**Waiting on:** the two pilot results above, and the arms job's `[job.arms]`
verdict for tcg424flip-pgraph.json. Next step: read the pilot with
arcticread.py. If M0 is valid and M4' is not clearly failing, write
`pilots/lane.tcg424flip.ok` and queue the remaining A B A B.

## Attempt 2 (2026-09-29): the pilot is VOID; v2 registered

Attempt 1 did not finish because it had nothing left to do: it queued the
pilot and the pgraph arm and stopped, waiting on them as the brief said.
Hostops resumed this lane when the pilot finished.

### The pilot under tcg424flip-arctic.json: VOID on both arms

Both runs hit the Thor's thermal pause (thermal-pause-F8). run.log puts the
onset after +451 s (A) and +388 s (B) of the 560 s soak. M0 voids a paused run.
arcticread.py over the open window, for the record only:

| run | tail s | m50 | on% | cpf | gfps | churn% | di/s | slow/s | inv/s |
|---|---|---|---|---|---|---|---|---|---|
| A 1-1790660189-...-1147138 | -2.8 | 75 | 89.9 | 33.3 | 27.0 | 32.4 | 80,194 | 16,151 | 13,227 |
| B 1-1790660193-...-1148129 | 21.9 | 194 | 76.3 | 25.9 | 29.5 | 0.0 | 0.2 | 93,938 | 92,163 |

Reading it also exposed a second fault in the window. B's race gave way at
mark + 100 s to 59-60 gfps with Df:0 (a results or menu screen), then a load
(gfps 4), then another race at 26-29. The open window counted the menu as
gameplay, which pulled B's median up. Both titleroutes baselines end their race
the same way, at mark + 124-161 s (arcticread2.py's `hi` column), so this
happens on every run, not only on B. A's race ran 223 s to the pause without
ending. B's 21.9 s tail was not a hang: after the last gfps line the emulator
kept refreshing frames and writing [tlb68] (cpu 1,390 of 2,000 ms) up to
`soak end`. The 20-27 s gaps between gfps samples in B all came after its pause
began. Before the pause, the gaps on all four runs on disk are at most 4.3 s.

### tcg424flip-arctic2.json (supersedes; no threshold changed)

- Reader `arcticread2.py`: arcticread.py loaded unchanged, with the window closed
  at `hi`, the earliest of: the pause's earliest onset, the first gfps sample
  >= 45 (race over), and `soak end`.
- M0 no longer voids a run for pausing, because the window ends before the
  pause could have begun.
- M4''s tail check becomes `gap <= 15 s` inside the window. The frames in the
  window must show the race.
- The soak is 420 s instead of 560 s: anything after about +388 s is paused
  time. It captures a frame every 20 s.

The pilot read under the bounds, for information only: arcticread2.py was
written after this reading, so neither file counts it:

| run | hi s | ng | gap | rt | on% | cpf | gfps | churn% | di/s | slow/s | inv/s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 223 p | 93 | 2.3 | 0 | 97.2 | 34.7 | 28 | 32.3 | 107,591 | 21,622 | 17,690 |
| B | 100 m | 31 | 2.8 | 1 | 78.7 | 29.1 | 27 | 0.0 | 0.0 | 190,706 | 186,640 |

The range test sends B's stores to the slow path at about 9x A's rate
(190k/s against 22k/s), and still costs less vCPU per frame. A churns 32%
here, against 14% in the titleroutes baselines on older builds. The pilot's
A window covers more of the race (223 s against 124-161 s).

### Runs under v2 (queued 2026-09-29, Thor, 62ef8bf0fe, expect_sha 412fafbc4833)

| run | A (HAKUX_TCG424_RANGE=0) | B (no env) |
|---|---|---|
| 1 | 1-1790687707-lane.tcg424flip-3372535 | 1-1790687708-lane.tcg424flip-3372653 |
| 2 | 1-1790687721-lane.tcg424flip-3375977 | 1-1790687722-lane.tcg424flip-3376159 |
| 3 | 1-1790687722-lane.tcg424flip-3376343 | 1-1790687723-lane.tcg424flip-3376527 |

The pilot verdict is in `pilots/lane.tcg424flip.ok`. The pgraph arms pair
(1-1790661220-arms-tcg424flip-base/-fix) is still queued. It was not withdrawn,
because the pilot showed no gfps loss.

**Waiting on (attempt 2):** the six runs above and the `[job.arms]` verdict for
tcg424flip-pgraph.json. Next step: `python3 docs/lanes/tcg424flip/arcticread2.py
<the six ids>`, read each window's frames, judge M0/M1/M2a/M2b/M4' as
registered in tcg424flip-arctic2.json, then check scores1.tsv's status column
on the pgraph arm.

## Attempt 3 (2026-09-29 ~12:15 PDT): Arctic moves to the Nova

Attempt 2 did not finish because it had nothing left to do: it queued the
six Thor runs and stopped, waiting on them. None of them ran. lane.local
withdrew all six on 2026-09-29 12:00 PDT, after the owner moved fps runs
off the Thor until #507 has a fix: 16 of 66 Thor title runs paused in 30 h,
and both of this lane's Thor pilot runs paused.

Meanwhile the pgraph arm's first pair ran split (A Nova, B Thor). The arms
job ruled it CONFOUNDED (43 of 3379 checks, not attributable) and re-queued a
same-device pair hard-pinned to the Nova:
`1-1790707670-arms-tcg424flip-base-1207251` / `-fix-1207297`. That pair's
verdict is the one that counts.

### tcg424flip-arctic-nova.json (supersedes arctic2; no leg threshold changed)

- Registered on `7bcd6e6e2b`: 62ef8bf0fe merged with master (62 commits,
  clean merge) before registering. A = `--env HAKUX_TCG424_RANGE=0`, B = no env.
- Device nova, hard pin. Two pairs, A B A B, 420 s, frames every 20 s.
- Reader `arcticread3.py`: arcticread2.py loaded with one string swapped,
  the race-over cut `g >= 45` becoming `g >= 55`. Nobody has measured the
  Nova's race gfps, and 45 could cut a faster race short. The results and
  menu screens run at 59-60. On the four Thor runs on disk it gives the same
  windows as arcticread2.py: hi 223p / 100m / 161m / 124m.

### Not queued yet

Arctic Thunder is not on the Nova. At 12:05 PDT `hardware/titlepush/listing-nova.txt`
on master does not name 4D570002. lane.local requested a Nova investigation
copy at 12:00 PDT under #507. The four runs get queued once it lands.

**Waiting on (attempt 3):** (1) the Arctic Thunder copy landing on the Nova
(4D570002 in listing-nova.txt); after that, queue A B A B under
tcg424flip-arctic-nova.json and read them with arcticread3.py. (2) The
`[job.arms]` verdict on the Nova pgraph pair above. Check scores1.tsv's status
column for unreadable captures.

## Attempt 4 (2026-09-29 ~14:30 PDT): the Nova runs are queued

Attempt 3 did not finish because it could not queue: Arctic Thunder was not
on the Nova yet. It registered tcg424flip-arctic-nova.json and stopped,
waiting on the copy. lane.xbox verified the copy by 14:07 PDT
(`hardware/titlepush/listing-nova.txt` line 106, `4D570002-Arctic_Thunder.xiso.iso`),
and lane.local resumed this lane to queue.

Queued under tcg424flip-arctic-nova.json, ref 7bcd6e6e2b, pinned to the Nova,
420 s, frames every 20 s, route arctic-thunder. request.sh admitted the
34 min on the reviewed pilot (`pilots/lane.tcg424flip.ok`, 7.9 h old):

| run | A (HAKUX_TCG424_RANGE=0) | B (no env) |
|---|---|---|
| 1 | 1-1790716215-lane.tcg424flip-3229031 | 1-1790716219-lane.tcg424flip-3229494 |
| 2 | 1-1790716222-lane.tcg424flip-3229888 | 1-1790716226-lane.tcg424flip-3230429 |

The Nova pgraph pair (`1-1790707670-arms-tcg424flip-base-1207251` / `-fix-1207297`)
is still queued. The Nova sits at 35-45% on port power, so these probably
run after the evening top-up.

**Waiting on (attempt 4):** the four runs above and the `[job.arms]` verdict
on the Nova pgraph pair. Next step: `python3 docs/lanes/tcg424flip/arcticread3.py`
over the four ids, read each window's frames, and judge M0/M1/M2a/M2b/M4' as
registered. Then check scores1.tsv's status column on the pgraph arm.

## Attempt 5 (2026-09-29 ~16:30 PDT): still battery-blocked, nothing ran

Attempt 4 did not finish because it had queued its runs and correctly
stopped to wait on them. This session was a resume with no result to read.
The dispatcher log (`logs/dispatcher.log`) shows all six requests, the four
Arctic Thunder runs and the Nova pgraph pair, refused by the battery gate at
every tick from 14:10 through 16:15 PDT. The Nova sat at 35-37%, and the
gates need 38.0% (soaks) and 41.0% (arms pair). Nothing has run, so there is
nothing to judge. No leg, reader, prediction or ref changed.

This session could not see `queue/` or `results/` entries whose ids start
`1-` (FileNotFoundError on a direct stat, although the dispatcher logged a
write to `results/1-1790723547-hostops-1062899` at 16:22). The live
`logs/dispatcher.log` is the evidence used above. A resumed session that
cannot open its result directories should read that log first, then ask
hostops for the paths.

PR #605 is MERGEABLE/CLEAN with green CI on 7958fcdcc3. Master is 26 commits
ahead but touches none of this lane's files, so no merge was made (it would
only cost a CI run).

**Waiting on (attempt 5):** the same six ids as attempt 4:
1-1790716215-lane.tcg424flip-3229031, -3229494, -3229888, -3230429 and
1-1790707670-arms-tcg424flip-base-1207251 / -fix-1207297. They run once the
Nova is above its battery floor (dock, or the ~18:00 PDT top-up).

## For the next lane

- The arctic-thunder race ends 100-160 s after `mark gameplay`, and the route
  then drives the results and menu screens at 60 gfps. Bound any window by
  race end (the first sample >= 45) and by the pause's onset.

- Soak predictions are hand-read. arms.sh skips any prediction that has a
  `title`, and one whose a_ref equals its b_ref. Queue the soak with
  `request.sh --title` yourself.
- The arctic-thunder route marks `mark gameplay`, not `mark play`. playread.py
  would VOID every run.

## Attempt 6 (2026-09-29 ~16:58 PDT): re-queued after the dispatch wipe

Attempt 5 did not finish because nothing had run. The Nova sat below its
battery floor, and that session correctly stopped to wait. Between about
16:15 and 16:26 PDT a host-side dispatch wipe emptied `dispatch/queue` (see
PR #623). All six of this lane's requests were lost: the four Arctic Thunder
soaks and the Nova pgraph pair. None had run. The dispatcher log shows each
one refused by the battery gate up to 16:15:41, and none is in `results/`,
`running/`, `parked/` or `withdrawn/`.

Re-queued with the same arguments: same prediction, ref, device pin and
seconds. No leg, reader or threshold changed.

| what | old id (wiped) | new id |
|---|---|---|
| Arctic A1 (`HAKUX_TCG424_RANGE=0`) | 1-1790716215-lane.tcg424flip-3229031 | 1-1790726259-lane.tcg424flip-1691697 |
| Arctic B1 (no env) | 1-1790716219-lane.tcg424flip-3229494 | 1-1790726265-lane.tcg424flip-1692424 |
| Arctic A2 (`HAKUX_TCG424_RANGE=0`) | 1-1790716222-lane.tcg424flip-3229888 | 1-1790726265-lane.tcg424flip-1692530 |
| Arctic B2 (no env) | 1-1790716226-lane.tcg424flip-3230429 | 1-1790726266-lane.tcg424flip-1692609 |
| pgraph base (30538458a0) | 1-1790707670-arms-tcg424flip-base-1207251 | 1-1790726318-arms-tcg424flip-base-1704391 |
| pgraph fix (62ef8bf0fe) | 1-1790707670-arms-tcg424flip-fix-1207297 | 1-1790726318-arms-tcg424flip-fix-1704464 |

The soaks: request.sh, `--device nova --hard-pin`, 420 s, frames every
20 s, ref 7bcd6e6e2b, `--expect tcg424flip-arctic-nova.json`.

The pgraph pair: queued the way arms.sh's `samedev_rerun` queues one. The
same requesters (`arms-tcg424flip-base` and `-fix`), the same refs, the pair
record's 100 suites, the skip of `Texture_render_target::RenderTextureLoop`,
the arms job's frozen expect copy (`arms/expect/fbed11c3...json`), and
`--device nova --hard-pin`. `arms/pairs/fbed11c3...json` still names the old
ids, so `results/<old id>` is now a symlink to `<new id>`. That is how
lane.local handled a renamed arms request on 09-28, and it lets the arms job
judge the new pair as the confounded pair's re-run without anyone editing
its state. The links dangle until the runs start.

**Waiting on (attempt 6):** the six new ids above. They run once the Nova
is above its battery floor (38% for the soaks, 41% for the arms pair; it
read 31% at 16:57 PDT). Next step is unchanged:
`python3 docs/lanes/tcg424flip/arcticread3.py` over the four soak ids, then
the `[job.arms]` verdict and scores1.tsv's status column.

## Attempt 7 (2026-10-03): both verdicts are in; the flip does not ship

### Why attempt 6 did not finish

Attempt 6 queued six runs and correctly stopped to wait on them. All six ran
between 00:06 and 01:41 PDT on 2026-09-30, and the arms job judged the pgraph
pair at 02:10 PDT. No resume followed:

- GitHub suspended the account at about 21:00 PDT on 09-29, so the
  `[job.arms]` comment never posted.
- The WAITING / lanewaker mechanism did not exist until 10-03, and this lane
  had no WAITING file.

The 08:30 hostops addendum read the six `queue/withdrawn` entries as the
Nova requests. They are the six **Thor** runs of tcg424flip-arctic2.json
(`-3372535` ... `-3376527`). lane.local withdrew them on purpose at
2026-09-29 12:00 PDT, because the owner moved fps runs off the Thor (#507).
Each `.why` file says so. That reason still holds: the Thor's fan is dead.
Nothing needs re-queuing. The Nova re-runs of the same arm already ran.

### Arctic Thunder on the Nova: tcg424flip-arctic-nova.json, judged as registered

`arcticread3.py`, unchanged; the output is saved in `arctic-nova.out`. Ref
7bcd6e6e2b, apk dd2c266dcdf2, Nova, MAX. Battery 77 -> 70% across the four
runs. No thermal pause (no thermal-pause device above 0).

| run | arm | hi s | ng | gap s | rt | fatal | m50 | on% | cpf | gfps | churn% | di/s | slow/s | inv/s | fs/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1-1790726259-...-1691697 | A | 122m | 61 | 1.8 | 0 | 0 | 189 | 84.5 | 21.7 | 39 | 2.5 | 70,733 | 19,685 | 14,193 | 0 |
| 1-1790726265-...-1692424 | B | 104m | 48 | 1.8 | 1 | 0 | 202 | 75.0 | 19.7 | 38.0 | 0.0 | 0 | 267,422 | 262,007 | 264,600 |
| 1-1790726265-...-1692530 | A | 121m | 63 | 1.7 | 0 | 0 | 203 | 83.0 | 20.2 | 41 | 2.5 | 73,911 | 21,057 | 15,056 | 0 |
| 1-1790726266-...-1692609 | B | 101m | 49 | 1.7 | 1 | 0 | 202 | 75.1 | 18.3 | 41 | 0.0 | 0 | 287,536 | 281,531 | 284,534 |
| **A (mean of 2)** | | | | | | | | 83.75 | 20.95 | 40 | 2.5 | 72,322 | 20,371 | 14,625 | 0 |
| **B (mean of 2)** | | | | | | | | 75.05 | 19.0 | 39.5 | 0.0 | 0 | 277,479 | 271,769 | 274,567 |

| leg | rule | read | verdict |
|---|---|---|---|
| M0 | `mark gameplay`, ng >= 20, xx 0, m50 >= 40, A rt=0 only, B rt=1 only | all four | **PASS** |
| M1 | churn% A >= 5.0; B <= 0.5 x A; di/s B <= 0.1 x A | A churn **2.5** < 5.0; B 0.0; di/s 0 vs 72,322 | **FAIL** (the A falsifier) |
| M2a | on% B <= A - 2.0 | 75.05 vs 83.75 (-8.7) | PASS |
| M2b | cpf B <= 0.95 x A | 19.0 vs 20.95 (x0.907) | PASS |
| M4' | gfps B >= A - 1; no fatal; gap <= 15 s; frames show the race | 39.5 vs 40; fatal 0; gap <= 1.8 s; f00013/f00014 of each run show a live race with the timer running | **PASS** |

The registered decision is: ship iff M0, M1 and M4' pass, and the pgraph arm
is byte-identical. **M1 fails, so the flip does not ship on this
prediction**, and per its own rule Arctic does not price the lever. No
threshold was changed.

What the miss shows, for information only (this is not a re-judgment). On the
Nova, A discards 72k blocks a second, about twice the Thor baselines'
37-41k. churn% (jump-cache plus reset microseconds over vCPU time) reads only
2.5%, against 14-32% on the Thor. Yet B's on% falls 8.7 points, more than A's
whole churn%. churn% does not count the retranslation that follows a
discard, so on the Nova it under-reports what the lever saves. B pays for its
saving with 13x the slow-path stores (277k against 20k a second). Neither
title moves gfps: Blinx/Thor 19 vs 19, Arctic/Nova 40 vs 39.5.

### pgraph must-not-move: tcg424flip-pgraph.json, judged FAIL, not attributable

Same-device Nova pair `1-1790726318-arms-tcg424flip-base-1704391` (30538458a0)
/ `-fix-1704464` (62ef8bf0fe), judged by the arms job at 2026-09-30 02:10 PDT
(`arms/pairs/fbed11c3....verdict.txt`, and the unposted `.comment.md`):
**FAIL, 41 of 3379 captures differ byte for byte.** Its own line: "NOT
ATTRIBUTABLE: one run per arm cannot tell a change from device
nondeterminism. Requeue with --runs 3." Both arms have 3379 captures, the
progress-log proof and no unscored capture. The status column reads `ok`,
except ZPass_pixel_count's `white-content` rows, which match in both arms.

The 41 are five families: Antialiasing FramebufferNotModifiedBySurfaceState
(0 -> 1 px), Stencil_REPLACE (0 -> 40,000), GeometrySuperscreen 0.5624 /
0.9990 (0 -> 400 / 285), with 0.5000 going 400 -> 0, and 37 ZPass captures
(+550 to +1,020).

- `moverscan.py`: on both devices, every one of these keys takes two or three
  states at a single ref. For example, memfast-base at 31515f9751 read
  Stencil_REPLACE 0 once and 40,000 once; ZPass reads 1,008 / 1,202 / 1,750 at
  fixed refs; GeometrySuperscreen 0.5000 and 0.5624 trade 0/400/800 between
  runs of one build.
- `pgraphnoise.py`: **all 41 of the fix arm's differing captures are
  byte-identical to a capture made by a build that does not contain the flip**
  (`git merge-base --is-ancestor 62ef8bf0fe` false). The weakest match is
  ZPass, in 3 no-flip runs. Stencil_REPLACE matches in 31, and
  GeometrySuperscreen_0.5000 in 75.

So nothing in the pgraph arm points at the flip. It still did not pass as
registered. That is the second reason not to ship.

### What this branch now does

`accel/tcg/tb-maint.c` and `tb-internal.h` are restored to master's text. The
range test stays opt-in (`HAKUX_TCG424_RANGE=1`). The branch lands the
predictions, the readers and these notes. It changes no emulator behaviour.
The flip commit 62ef8bf0fe and the merge 7bcd6e6e2b stay in history, so
every registered ref still resolves.

### Next (owner rule 2026-10-02: P x win)

Measured win of the flip if shipped: **0 gfps on both titles measured** (Blinx/Thor
19 vs 19, Arctic/Nova 40 vs 39.5). It saves vCPU: Arctic/Nova cpf -9%,
on% -8.7 points. That is headroom on a frame that is not vCPU-bound on the
Nova, not fps.

| candidate | P | evidence for P | win | cost |
|---|---|---|---|---|
| 1. Arctic on the Thor under tcg424flip-arctic2.json (registered, pause-bounded window), once #507's fan is fixed | ~0.5 (M1 ~0.85, M4' ~0.6) | Thor pilot A churn 32.3%, baselines 14%; Thor pilot gfps 28 vs 27, run-to-run spread ~2 | the flip ships under a registered rule; ~0 gfps, ~9% vCPU/frame | 6 Thor runs, ~51 min; **blocked by device policy** (fps off the Thor, fan dead) |
| 2. pgraph re-run, `--runs 3` per arm, same-device Nova pair, same tcg424flip-pgraph.json | ~0.8 | 41/41 differing captures byte-identical to no-flip captures; the five families vary at a fixed ref | the pixel leg passes as registered; needed for any ship, worthless without 1 | 6 x 34 min = 3.4 h Nova |
| 3. A title whose frame is vCPU-bound on the Nova, to give the saving a chance to become fps | unknown, <0.3 | Arctic at 84% on-CPU did not convert -9% cpf into gfps | the only path to a player-visible win | a survey before any arm |
| 4. Leave the range test opt-in (this branch) | 1 | n/a | 0 | 0 |

Recommendation: 4 now. 1 and 2 only together, and only after the Thor fan
is fixed. Run 2 after 1 passes, because 2 alone cannot ship anything. The
larger vCPU wins are on the vCPU-JIT track, not in this lever.

### For the next lane

- Do not run Arctic M1 on the Nova again. Its A side churns 2.5% there, so
  the A >= 5.0 falsifier cannot pass, whatever the lever does.
- A single-run pgraph pair cannot pass must-not-move on these builds. Stencil_REPLACE,
  ZPass and GeometrySuperscreen flip between states at one ref. Queue
  `--runs 3`, or expect a not-attributable FAIL.
- `pgraphnoise.py` is a reusable check: for a pair's differing captures,
  does a build without the change produce the candidate's bytes?

## Attempt 8 (2026-10-03 08:55 PDT): resume for the 08:30 and 08:55 addenda; nothing to re-queue

### Why attempt 7 looked unfinished

Attempt 7 did finish. It committed the verdict at 08:38 PDT, set PR.md to
`State: ready`, pushed 5573c8548f, and needed no WAITING file. Hostops' 08:55
jam-duty addendum resumed the lane because it assumed the session had ended
before reading the 08:30 addendum. In fact, attempt 7 had already answered it
under "Why attempt 6 did not finish". The one defect: OUTBOX.md's header said
09:40 PDT, a time that had not yet come. It is now 08:38 PDT, the commit time.

### The withdrawn requests, checked again from the dispatch directory

`dispatch/queue/withdrawn/` holds six tcg424flip `.req`/`.why` pairs:
`-3372535`, `-3372653`, `-3375977`, `-3376159`, `-3376343` and `-3376527`. The
08:30 addendum's ids (1-1790687708-, -1790687722-, -1790687723-) are among them.

- Every `.req` has `"device": "thor"`, ref 62ef8bf0fe, and expect
  tcg424flip-arctic2.json.
- Every `.why` reads: "lane.local 2026-09-29 12:00 PDT: heat-sensitive Thor
  runs move to the Nova until #507 has a fix."

The withdrawal was deliberate, and its reason still holds: the Thor's fan is
dead, and the dispatcher is kept off it except for cold-slot runs of 480 s or
less. These 420 s soaks are MAX fps runs, and the device policy sends fps runs
to the Nova. The Nova replacements ran on 09-30 and were judged in attempt 7
(M1 FAIL). The six Thor runs are candidate 1 in the attempt 7 table. They
wait on the fan fix, not on this lane. Nothing was re-queued.

### Done this session

- Merged origin/master (6c828f9860). The net diff is unchanged: 14 files, all
  docs, predictions and readers. Nothing is under accel/.
- Fixed OUTBOX.md's timestamp and PR.md's Base line.
- Not waiting on anything, so there is no WAITING file. PR.md stays `State: ready`.
