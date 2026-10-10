# lane.perdrawon1010 -- should perdraw1009's three uniform switches default on?

Brief: `/home/justin/hakux-work/briefs/perdrawon1010.md`. #433, 0.5. Measurement
only: no emulator code touched, no default flipped. The owner decides the flip.

## 0. Ref

`git diff 4ad1154e5528eb51455f8de1a597575a543216fb origin/master -- hw/` is
non-empty: perdraw1009 (head `4ad1154e55`, ready, folding) has not landed on
master yet. The diff is read in full above and is exactly perdraw1009's own
commit (`shaders.c`/`renderer.h`: the three `HAKUX_UNI_*` switches, the
`uniform_copy_bulk`/`vsh_cache`/`uni_toggle_*` machinery, and the unrelated
`ubosz_on()` gate it also touches) -- nothing else moved. So this lane builds
and measures at **`4ad1154e5528eb51455f8de1a597575a543216fb`** throughout.
Revisit if perdraw1009 folds before this lane's device time is spent; as of
this writing it has not.

## 1. What perdraw1009 already settled (not re-measured)

Full detail in `docs/lanes/perdraw1009/NOTES.md`/`PR.md` (read in full, on
`lane/perdraw1009`). Headline numbers this lane builds on:

| window | scene | Draw us/draw on-off | gfps on-off | notes |
|---|---|---|---|---|
| STATIC (40,78] | parked against a wall, 65-68% complete | -1.70 (-15.2%) | +0.00 | 30 fps cap, ~14 ms/frame renderer idle; a per-draw cut cannot show as fps here |
| MOTION (0,24] pair 1 | RT held, 438-439 draws/frame | -2.29 | +0.0 (29.0->29.0, still capped) | separate-arm, same wall at +10s |
| MOTION (0,24] pair 2 | RT held, 801-855 draws/frame | -1.49 | **+2.0 (26.4->28.4)** | separate-arm, below the cap -- the only gfps movement either lane has on record |
| BF2 MC heavy row | GPU-bound | -21.0% us/draw | +1.81 | generalization check, different title |

perdraw1009's own MOTION legs (armread.py's P3/P6) already PASS on that
separate-arm data. What is still missing, and what this lane's brief asks
for: a MOTION-window read where both states share one scene (the toggle
instrument), binned by draws/frame, with a run-to-run band -- pair 1 and
pair 2 above are two uncontrolled single samples from two different walls,
not a controlled A/B.

## 2. The main question: FPS where the renderer limits the frame rate

**Scene choice.** The owner's own profiled renderer-bound scenes (1v1
circuit 18.5 fps/14-25, 3-racer sprint 13 fps/~1650 draws/frame,
`briefs/perdraw1009.md`) are not reachable by any scripted route today --
`nfs-mw.route` (perdraw1009's, reused unmodified, not in this lane's
territory to edit) is the only scripted NFS route, and its only "driving"
material is the one RT-held MOTION window before the car reaches a wall.
Building a steering script that holds a real multi-car race for tens of
seconds is a route-authoring job this lane does not have the territory or
budget to attempt from scratch (perdraw1009 itself noted this needs "a
separate route job"). Per the brief's own fallback ("that window may be
enough with HAKUX_UNI_TOGGLE and matched-work binning, or you may need a
longer-driving route. Choose, and say why"): **chosen: the existing MOTION
window, with HAKUX_UNI_TOGGLE and draws/frame binning.** It is the only
place in any NFS data on disk (either lane's) where gfps has moved off the
cap at all, and reusing the already-built route keeps this lane inside its
device budget; the honesty leg (M4 below) reports if it is too short to
settle the question rather than asserting it settled one it didn't.

**Toggle period.** MOTION is 24 s of 2-s perf rows: at most 12 rows/run
before any are dropped for straddling a flip. Draws/frame ramps hard across
those 24 s (350 -> 1025 in perdraw1009's own sample) as the car accelerates
from a standing start, so a toggle period long relative to the window would
let one phase own the light end of the ramp and the other the heavy end --
confounding the switches with time-in-ramp, exactly the problem matched-work
binning is meant to avoid. **Chosen: `HAKUX_UNI_TOGGLE=4`** (6 flips across
24 s), which interleaves both phases across the ramp at the cost of roughly
half of each run's rows being dropped as impure (togread.py's pure-row
rule: no flip inside a row's own 2-s interval). `BE_SPLIT = 700` draws/frame
splits the pooled rows into "lo" and "hi" bins, the midpoint between
perdraw1009's two separate-arm MOTION pairs (438-855 vs 855-1025).

**Tooling.** `docs/lanes/perdrawon1010/motionread.py` (this dir): reuses
perdraw1009's `togread.py`/`armread.py` functions (`read_run`, `read_toggle`,
`phase_at`, `flips_in`, `regions`, `dmax`, `summ`) rather than copying them.
Since perdraw1009 has not folded, those files do not exist in this worktree;
the script materializes them via `git show <ref>:<path>` into a temp dir
(pinned to `PERDRAW1009_REF`, default the same `4ad1154e55` this lane
builds against) rather than committing a second copy that could drift from
theirs. Verified before spending device time: the import/exec chain runs
end-to-end (usage message on no args); `pure_rows`/`bins_motion`/`summ`
checked directly against hand-built row dicts (not a real logcat parse,
which is perdraw1009's already-shipped code, not this lane's) -- a 4-s
period over a 14-row synthetic run survived 5/14 rows as pure, split
3 on/2 off, consistent with the ~50% survival the period:row-spacing ratio
predicts.

**Prediction**, registered before any scored arm:
`docs/testing/predictions/perdrawon1010-nfs-motion.json` (judge:
`motionread.py`). Three `HAKUX_UNI_TOGGLE=4` runs of `nfs-mw.route`, pooled.
Legs: V (validity), M1 (pooled on-off us/draw in [-3.0,+0.2]), M2 (separation
over pooled SE, x2), M3 (hi-BE bin gfps on-off >= -1.0, no regression
required), M4 (every phase x BE-bin cell has >= 3 pooled rows -- the
honesty leg: if this fails, MOTION on nfs-mw.route is declared too short
for this question rather than the numbers being asserted as settling it).

### Result

*(not yet run -- device requests queued after this file and the prediction
are committed; results filled in here once read)*

## 3. Pixels: pgraph inert disc

`docs/testing/predictions/perdrawon1010-pgraph-inert.json`, registered via
`ab_compare.py --register` (machine-checked composition, not hand-typed):
same 27-suite disc pfifowait1009 used (`origin/lane/pfifowait1009`'s
`pfifowait1009-pgraph-inert.json`, read in full for the suite list), one
binary at `4ad1154e55`, A = no env, B = all three switches on. `must_not_move`
every suite. If any capture violates, per pfifowait1009's own precedent
(Stencil moved 0->30,000 px on its own lock-scope change, then proved
ATTRIBUTABLE with `runs=3 --allow-same-binary` after confirming each arm was
self-identical across three runs) -- this lane re-queues the scoped suite(s)
with `runs=3` before attributing any violation to the switches rather than
device nondeterminism.

### Result

*(not yet run)*

## 4. Energy

At the 30 fps cap a CPU saving can show as power, not fps (device-power.md,
`title_verdict.py`'s `power` block, J/frame). Toggle runs are unsuitable for
this leg: `thermal.jsonl` samples every 30 s, far coarser than a 4-8 s toggle
period, so a single power sample would average across several flips and wash
out any difference. **Plan: two separate, non-toggled long runs of
`nfs-mw.route`** (switches all-off, all-on), each long enough for a >=600 s
scored window once past the parked-STATIC scene, read with `title_verdict.py`.
Camera/wall drift across separate runs does not matter for an energy total
the way it matters for pixel-diffing, so the separate-run approach (ruled out
for pixels, section 3) is fine here. No prediction file registered for this
leg: there is no falsifiable judge for J/frame the way `ab_compare.py` or
`motionread.py` are for pixels/fps -- "no measurable change at this noise" is
explicitly an acceptable answer per the brief, and this leg is reported as
telemetry, not scored pass/fail.

### Result

*(not yet run; queued after the main question's pilot batch is reviewed, per
the pilot gate -- see section 5)*

## 5a. Attempt 2: why attempt 1 did not finish, and the pilot's read

Attempt 1 ended the turn with the three pilot requests queued and a WAITING
file holding their ids; it never finished because the runs were still
in-flight when the turn ended, not because of any blocker. All three
completed cleanly (`DONE` present, `dispatch/results/1-1791638052-
perdrawon1010-3286571`/`-3287113`/`-3290290`).

**Reading them (`motionread.py ... --expect perdrawon1010-nfs-motion.json`):**

```
run                                      flips toggle_ms route fatal apk
1-...-3286571                               32      4000  True     0 72fe2eabc46e
1-...-3287113                               33      4000 False     0 72fe2eabc46e
1-...-3290290                               33      4000 False     0 72fe2eabc46e
V   FAIL  ...-3287113: route did not finish; ...-3290290: route did not finish
M1  PASS  MOTION (all BE) Draw us/draw on-off -1.69 (off 10.72 n=8, on 9.03 n=9); in [-3.0, +0.2]
M2  PASS  |on-off| 1.69 us/draw against pooled-row SE 0.43 (x2.0 needed)
M3  FAIL  HI-BE bin gfps on-off -1.50 (off 27.0 n=2, on 25.5 n=2), us/draw on-off -1.67
M4  FAIL  every phase x BE-bin cell has >= 3 pooled rows (thin: 0/hi, 1/hi)
```

**V's "route did not finish" is a harness polling artifact, not a real route
failure**, checked by reading `soak_title.sh:915-946` and all three run.logs
in full:
- The hold loop polls every `SOAK_POLL_S` (5s) and only prints `ROUTE
  finished (rc 0) after Ns; holding without input` on the poll cycle where it
  reaps the now-zombie route PID (`soak_title.sh:936`). If the route exits
  within a few seconds of `SECONDS_TO_HOLD` (360s here), the loop's `s <
  SECONDS_TO_HOLD` condition can go false before the next poll ever samples
  the zombie, and the line never prints -- even though the route genuinely
  completed. `armread.py`'s `route_done` is a literal string match on that
  one line, so it reads this as "did not finish".
- Neither failing run shows `soak aborted`, `route-died` or `guest exited`
  anywhere in its `run.log` (grepped in full) -- the three strings
  `soak_title.sh` uses for every real abort path. `-3290290` (run 3) even
  shows the full tail of input steps (`shot drive-end`, `done`, `end`)
  byte-for-byte like the "good" run 1, just missing the one summary line
  after it; `-3287113` (run 2) is missing the last two steps too, consistent
  with the same race landing a poll or two earlier.
- The MOTION window this lane reads is (0,24] seconds after the `mark
  gameplay` line, which lands at roughly +235s of a 360s run -- forty-plus
  seconds before the route's RT release and `drive-end` shot even start
  (`route.txt`: `mark gameplay` then `wait 10`/`wait 7`/`repeat 18 { wait 5
  }` before `axis RT min`). Whatever did or did not get polled in the last
  2-3s of the run cannot touch rows already collected and logged minutes
  earlier. Confirms by inspection, not assumption: pooled MOTION rows exist
  for both "failing" runs (`bins_motion` picked up rows from all three dirs;
  the pooled table below is consistent across runs, nothing from -3287113 or
  -3290290 reads as an outlier against -3286571).

Treating V's "route did not finish" wording as blocking here would be
grading a tail-timing artifact of the harness, not the measurement this lane
is making. Recorded, not silently overridden: the prediction's own V leg
FAILs mechanically and this file is where that is explained, same as the
pfifowait1009 precedent (NOTES must say why a mechanical FAIL is not being
taken as the last word) -- the difference there was device nondeterminism
needing a runs=3 check; here it is confirmed to be a logging race against a
scene that already closed.

**M1/M2 (the headline on-off effect) PASS** on n=8/9 pooled rows: -1.69
us/draw, consistent in sign and magnitude with perdraw1009's own STATIC
(-1.70) and separate-arm MOTION (-2.29, -1.49) numbers, and separated from
noise (SE 0.43, >> the x2 bar).

**M3/M4 (the hi-BE bin, closest to the owner's profiled high-draw racing)
FAIL on sample count, not direction**: only n=2 pooled rows per phase in the
hi bin (>=700 draws/frame) from 3 runs -- the ramp spends most of its ~24s
below 700 draws/frame and only the last couple of toggle-interleaved rows
before the wall cross into "hi". This is exactly the honesty leg's intended
read: "too few rows to say anything about the hi bin yet," not "the switches
don't help there." The hi-bin DIRECTION already present (-1.67 us/draw,
gfps -1.50) is consistent with M1 rather than contradicting it, just too
thin (n=2) to clear M3/M4's own bar.

**Decision: queue 3 more replicate runs (same env/route/ref) rather than
stop at "too short."** The brief's own fallback for M4 failing is to declare
the window too short for this question -- but that is the honesty leg's
job only once more of the same cheap, in-budget replicate has been tried;
quitting on n=2 without trying n=4-6 first would be exactly the
"cheap-first" mistake this project's owner has flagged before (see the
`balanced, not cheap-first` guidance). 3 more 360s runs cost ~22.5 min of
Nova time, well inside the 4h budget (pilot batch ~22.5 min + this batch
~22.5 min = 45 min of 240 min), and the pilot gate's own accounting (`mine`
sums only queue/running records for this requester; the first three are
already in `results/`, not counted) admits this second batch directly
without needing a `pilots/perdrawon1010.ok` file -- each batch is its own
<=30-min pilot-sized request, not a single >30-min batch split to dodge the
gate. Queued: `1-1791639780-perdrawon1010-3615994`,
`1-1791639787-perdrawon1010-3618156`, `1-1791639788-perdrawon1010-3619271`
(same purpose, suffixed "fill hi-BE bin, M3/M4 thin"). If pooling all 6 runs
still leaves M4 thin, that IS the answer: MOTION on `nfs-mw.route` is too
short for the hi-BE question, reported as such in section 2's Result, and
section 2's recommendation leans on M1/M2 (which already have enough power)
plus BF2's generalization check rather than on M3.

## 5b. Attempt 3: why attempt 2 did not finish; the prologue batch, read

Attempt 2 did not finish because it ended, as designed, on a WAITING file
holding the three replicate runs (`...-3615994`, `-3618156`, `-3619271`): device
runs outside the session. All three finished (`DONE`), and lanewaker resumed
this lane as attempt 3, together with lane.local's 07:05 addendum (owner order:
measure the race start, not the prologue). Perdraw1009 has still not folded
(`git diff 4ad1154e55 origin/master -- hw/` is still exactly its own two
files, after fetching), so every run stays on `4ad1154e55`.

**All six runs of `nfs-mw.route`, pooled (`motionread.py`, the six dirs once
each). This is the prologue scene, not the race start.** The route plays
Career's scripted prologue race and gets control mid-lap 2/2; the MOTION rows
after the mark are the player's car alone or nearing a wall.

| phase | BE bin | rows | us/draw | se | gfps | draws/frame | Tot ms | Idle ms |
|---|---|---|---|---|---|---|---|---|
| off | <700 | 12 | 11.34 | 0.13 | 29.0 | 513 | 29.47 | 13.40 |
| off | >=700 | 3 | 9.90 | 0.30 | 26.7 | 889 | 32.30 | 10.70 |
| on | <700 | 13 | 9.46 | 0.17 | 29.1 | 547 | 29.28 | 13.98 |
| on | >=700 | 5 | 8.04 | 0.21 | 25.4 | 928 | 33.56 | 11.76 |

Legs: V FAIL (4 of 6 runs miss the `ROUTE finished` line, the tail poll race
of section 5a, after the window closes), M1 PASS (on-off **-2.01 us/draw**, off
10.91 n=15, on 8.90 n=18), M2 PASS (SE 0.29), M3 FAIL (hi bin gfps on-off
-1.27, off 26.7 n=3, on 25.4 n=5), M4 PASS (every cell >= 3 rows).

Run-to-run band of the on-off per-draw cost (each run alone, 2-3 pure rows
per phase): -1.71, -1.90, -1.25, -3.11, -2.01, -2.02 us/draw. Every run has
the same sign; the spread is 1.25-3.11.

M3's -1.27 is not evidence of a regression: the on rows in that bin carry
more work (928 against 889 draws/frame, Tot 33.56 against 32.30 ms), there are
3 and 5 rows, and Idle is still 10-12 ms per frame in both, so the renderer is
not the limit in these rows at all. What this batch settles is the per-draw
cost, -2.0 us/draw (-18%) in a moving scene, the same size as perdraw1009's
STATIC -1.70. It cannot say anything about fps where the renderer limits it,
because nothing after the mark in this route is that scene: 24-30 fps at
288-1,043 draws/frame. The one multi-car scene in the route is the cutscene
before control (14-21 fps, ~2,100 draws/frame), where lane.local read about
-6 ms/frame with the switches on and no fps change.

So the race start needs its own route (addendum step 1), section 7.

## 5. Device budget and pilot

Pilot batch queued (2026-10-10, ~22.5 min estimated, under the 30 min cap,
no `pilots/perdrawon1010.ok` needed): three `HAKUX_UNI_TOGGLE=4` runs of
`nfs-mw.route`, 360 s each, ref `4ad1154e55`, device nova, `--expect
perdrawon1010-nfs-motion.json`.

| run | request id |
|---|---|
| 1 | `1-1791638052-perdrawon1010-3286571` |
| 2 | `1-1791638067-perdrawon1010-3287113` |
| 3 | `1-1791638073-perdrawon1010-3290290` |

`nfs-mw.route` is perdraw1009's (ready, folding, not yet on master); its
route file is not yet in this tree so it was materialized **untracked**
(`git show lane/perdraw1009:docs/testing/titles/routes/nfs-mw.route`,
verified byte-identical, not staged/committed -- `git status --porcelain`
shows it `??`) purely so `request.sh`'s local route-resolution step could
read it. No `refs/` crop assets exist for this route (grep: no `waitfor`
steps), so nothing else was needed. Not a WAITING-grant case: the route is
not new, just not locally present yet because of fold timing; nothing in
this lane's committed tree changed.

Writing `docs/lanes/perdrawon1010/WAITING` with the three request ids and
ending this turn here; the next turn reads the results, then queues the
disc (section 3) and power (section 4) legs, pilot-reviewed and written to
`pilots/perdrawon1010.ok` if that next batch would push cumulative time
past 30 min. 4 h Nova budget total; ~22.5 min spent on this pilot so far.

## 6. Second title (optional, job item 5)

Not started. Revisit if budget remains after sections 2-4 are read.
