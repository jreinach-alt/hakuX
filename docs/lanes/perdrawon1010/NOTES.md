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

The six runs of `nfs-mw.route` are read in section 5b: -2.01 us/draw with the
switches on (-18%), every run the same sign. But no row after the mark in that
route is a renderer-limited scene: the car is alone, or near a wall, at 24-30
fps. The owner's 10-10 order replaced this scene with the race start, which
section 7 measures. The scene choice above (the existing MOTION window) is
superseded by section 7's route.

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

Arm A `1-1791641570-perdrawon1010-3943774` (no env), arm B
`1-1791642456-perdrawon1010-4121401` (all three on), both on the Nova, one
apk (`98514fe8c452`), 1,060 captures each. `ab_compare.py --expect
perdrawon1010-pgraph-inert.json`: **5 of 1,060 checks moved**, and every other
capture is byte-identical:

| capture | A px | B px |
|---|---|---|
| Stencil/Stencil_REPLACE | 0 | 40,000 |
| Stencil/Stencil_REPLACE_ST | 0 | 30,000 |
| Stencil/Stencil_REPLACE_ST_ZB | 0 | 30,000 |
| Vertex_shader_rounding_tests/GeometrySuperscreen_0.5626 | 0 | 570 |
| Vertex_shader_rounding_tests/GeometrySuperscreen_0.9990 | 570 | 0 |

The Stencil moves are pfifowait1009's known nondeterminism: the same
REPLACE variants moved 0 -> 30,000-40,000 px between plain runs of one binary.
The GeometrySuperscreen pair is one 570 px difference trading places between
two neighbouring tests, and the suite total is unchanged (1,638 both arms).
That is the signature of run-to-run noise, not of a copy that changed a
value. `ab_compare.py` says the same: NOT ATTRIBUTABLE with one run per arm.
The `COMPOSITION DIFFERS` warning is the suite-name spelling only (the
registered names are underscored, the request's are spaced); the 27 suites
are the same, and every leg is an A-B difference.

Determinism check: those two suites alone, `--runs 3`, both arms
(`1-1791643407-perdrawon1010-118147` A, `1-1791643408-perdrawon1010-118235`
B), same apk. Every capture that moved above takes BOTH values within ONE
state across that state's four runs (the first A/B's run plus three):

| capture | off (A) runs: A/B, det 1-3 | on (B) runs: A/B, det 1-3 |
|---|---|---|
| Stencil_REPLACE | 0, 40,000, 0, 40,000 | 40,000, 0, 40,000, 0 |
| Stencil_REPLACE_ST | 0, 30,000, 30,000, 30,000 | 30,000, 0, 0, 0 |
| Stencil_REPLACE_ST_ZB | 0, 30,000, 30,000, 0 | 30,000, 0, 0, 0 |
| GeometrySuperscreen_0.5626 | 0, 0, 0, 0 | 570, 0, 0, 0 |
| GeometrySuperscreen_0.9990 | 570, 0, 0, 0 | 0, 0, 0, 0 |
| GeometrySuperscreen_1.0000 | 570, 0, 0, 0 | 570, 0, 0, 0 |
| GeometrySuperscreen_0.4999 / 0.5000 / 0.5624 | 0 in all four | 0, 768 / 384 / 400 in det runs 2-3 |

`ab_compare.py` on the determinism pair puts Stencil_REPLACE and
REPLACE_ST_ZB inside the measured band (NOISE), and calls REPLACE_ST "better"
(30,000 -> 0) because each 3-run request happened to be self-consistent; the
first A/B had it the other way round (0 -> 30,000), so the direction belongs
to the request, not the state. Its 25 other violations are "matched no
capture" for the 25 suites this 2-suite disc does not carry. **Pixels: no
capture moves with the switches.** Every mover moves within the off state
alone, which is the definition of not attributable to the switches.

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

Plan changed with the addendum: the energy runs are section 7's four
fixed-state race-start runs, not long `nfs-mw.route` runs. Each is a whole run
in one state, so its `thermal.jsonl` samples (every ~26 s) are all in that
state. The scored window is title_verdict's: `mark gameplay` to the soak's
end, ~300 s that hold all twelve starts, the eleven restart prompts and ~35 s
idle on the track after the route ends. The window is the same in both states.
The power block comes from `title_verdict.judge()` called in Python. It is the
same function the CLI runs, without writing `verdict.json` into the dispatch
results dir.

| run | state | samples | battery W | USB W | net W | scored s | guest flips | J/frame | median fps |
|---|---|---|---|---|---|---|---|---|---|
| `1-1791644405-perdrawon1010-365120` (OFF1) | off | 11 | +0.955 | 6.541 | 7.496 | 300.2 | 7,200 | 0.3126 | 23.79 |
| `1-1791645060-perdrawon1010-726861` (ON1) | on | 11 | +0.807 | 6.538 | 7.345 | 304.3 | 7,680 | 0.2910 | 26.35 |
| `1-1791645063-perdrawon1010-728778` (ON2) | on | 11 | +0.805 | 6.541 | 7.346 | 299.5 | 7,500 | 0.2934 | 25.62 |
| `1-1791645064-perdrawon1010-729270` (OFF2) | off | 11 | +0.898 | 6.544 | 7.442 | 299.2 | 7,320 | 0.3041 | 25.68 |

USB is a measurement (`usb current_now x voltage_now`, `usb_bound` false), and
no sample is `sign_suspect`. `flips` is title_verdict's count, 60 per perflog
line, so it moves in steps of 60 frames.

**Energy result:** off 0.3126 and 0.3041 J/frame (net 7.50 and 7.44 W). On
0.2910 and 0.2934 J/frame (net 7.35 and 7.35 W). On-off: **-0.016 J/frame
(-5%)**, and -0.12 W net while drawing 3-7% more frames. With two runs per
state the bands do not overlap (off 0.304-0.313, on 0.291-0.293), but two runs
are a thin sample. Read it as "a small saving, the same sign as the per-draw
cut", not as a measured size. USB input is pinned at 6.54 W in every run, so
the difference shows up in battery draw: +0.90-0.96 W off, +0.81 W on.

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

**Device time at the end of attempt 3**, from each result dir's first file
to its `DONE`. All on the Nova; the Thor was never used.

| batch | runs | minutes |
|---|---|---|
| prologue, `nfs-mw.route` toggled, 360 s (sections 5a, 5b) | 6 | 40 |
| pixel disc A/B, 60 s (section 3) | 2 | 15 |
| pixel determinism check, runs=3 (section 3) | 2 | ~15 (timestamps give 2 each; three runs of a 60 s disc each) |
| race route passes 1-3 (section 7) | 3 | 23 |
| race start, 500 s: T1 (pilot), OFF1, ON1, T2, T3, ON2, OFF2 | 7 | 62 |
| total | | **~2 h 35 min of the 6 h (4 h + 2 h)** |

`pilots/perdrawon1010.ok` was written (python3, 2026-10-10 08:16 PDT) after the
T1 pilot's read. It cites T1 and pass 3, and what their frames and rows showed.
The remaining five race-start runs went through the gate on it.

## 6. Second title (optional, job item 5)

Not done. Device budget remained (about 2.5 h used of 6 h), but a second title
would not change the recommendation:

- The question is whether the switches harm anything, and whether they help
  where the renderer limits the frame rate.
- Harm is covered for every title by the 27-suite pixel disc (section 3) and
  by perdraw1009's host byte-identity check of the BULK copy.
- Help is now measured in two titles: perdraw1009's BF2 (+1.81 gfps on heavy
  rows) and this lane's NFS race start (section 7).

A third title is the place to start if the owner wants a wider sample before
flipping the default. Choose one from `title_verdict` output with
`fps_window_median` under 25 at 1,000+ draws/frame, and run it toggled on an
existing route. Read it with `startread.py --window` over its own mark (one
`mark gameplay` gives one "start").

## 7. The race start (addendum, owner order 10-10)

### The route, `docs/testing/titles/routes/nfs-mw-quickrace.route`

The owner's 10-09 frames (`lanelocal-scratch/nfs-race-1009/prof/221803.png`)
show the 3-racer start: HUD `1 / 3` (Player 1, GARDI, JASON), so **3 racers
in all, 2 opponents**, Fiat Grande Punto, GO with the clock at 0.20 s. The
route sets that up. Every menu step below was read from a frame:

| screen | what the frames show | input |
|---|---|---|
| main menu | Career, Challenge Series, Quick Race, ... (clamped) | right x2, A |
| quick race | Quick Play, Custom Race, Split Screen | right, A |
| custom race mode select | Circuit, Sprint, Drag, Lap Knockout, Speedtrap | right (Sprint), A |
| sprint track select | opens on Diamond & Union, 1/44, 3.5 mi (default); down does nothing | A |
| sprint options | Traffic Level Minimum, Opponents 3, Difficulty Medium, Catch Up On; down cycles the rows | down, left (Opponents 2), A |
| car select | opens on Stock 1/32 Lexus IS 300; right is 2/32 Fiat Punto | right, A |
| transmission prompt | Manual / Auto, Auto focused | A |
| race | Controls/loading, intro flyby, countdown, GO about 20-22 s after A (pass 2, with a frame every 2 s) | RT from the countdown |
| in race, d-pad up | STANDINGS: A Exit, X Statistics, Y Restart | Y |
| restart prompt | "Are you sure you want to restart the race?" OK / Cancel, opens on **Cancel** | left, A |

Pass 1 (`1-1791641530-perdrawon1010-3932477`) mapped the main menu and Quick
Play, which is a random race (it gave a Circuit with a Golf GTI and 3
opponents), so the route uses Custom Race instead. Pass 2
(`1-1791642016-perdrawon1010-4029199`) mapped Custom Race. It raced the IS 300
with 3 opponents, because the exploration returned to the first car, and its
Y Restart did nothing: the prompt opened on Cancel. Pass 3
(`1-1791643217-perdrawon1010-95991`, `HAKUX_UNI_TOGGLE=4`, unscored pilot) runs
the whole setup with four starts (one plus three restarts), with frames before
each GO and one 11 s after it, to time each GO from the HUD race clock.

The track differs from the owner's: their start was downtown (tall buildings
in frame), on a track picked by hand; this route takes Sprint's default,
Diamond & Union. Draws/frame is the common axis, so every result here is
binned by it, next to the owner's numbers.

### Pass 3, read: the timing, and why only its first start counts

Pass 3's frames and route log time every GO. The first start's GO came ~21.0 s
after the transmission A (21.6 s in pass 2). A restart does **not** reload: the
countdown runs as soon as OK is pressed, and GO comes ~4.1 s later (4.2, 4.2
and 4.0 s for its three restarts). Pass 3 had guessed a reload of ~20 s, so
its restarts pressed RT and wrote `mark go2`-`go4` ~22 s after GO: the Punto
sat on the line while the opponents drove off. Those three windows are not
the race start and are not used. Its one valid start (the first) ran:

| rows around GO (device s from the mark) | gfps | draws/frame |
|---|---|---|
| countdown (-6.3 .. -4.0) | 14 | 2,001 |
| straddling GO (-4.0 .. +0.5; GO ~ -1.6) | 13 | 1,913 |
| GO+2 .. GO+6 | 20 | 1,508 |
| GO+6 .. GO+8 | 25 | 886 |
| GO+8 .. GO+11 | 29 | 498 |

So on this track the heavy part is the countdown and the first ~4 s, at the
owner's 13 fps and at more draws than their 1,374-1,658; by GO+8 the two
opponents have pulled away from the Punto and the frame is light.

The device's logcat clock runs ~3.1-3.5 s ahead of the host's route log
(`mark gameplay` 07:46:36.403 host, 07:46:39.531 device), which matters only
when matching a frame to a row by wall time; marks and rows are both device
time.

### The final route (12 starts per boot)

Same boot and menus. The first start keeps pass 3's frames every ~2.5 s
through the load, presses RT ~3.5 s before GO and writes `mark gameplay` ~1.5 s
before it. Each restart presses OK, then RT 0.8 s later, then writes `mark
go<N>` at OK + ~2.6 s, ~1.5 s before GO. The mark is early on purpose: route.sh
takes a screencap with every mark (~0.8 s), and it should finish before the
race starts, not inside the measured window. Each start drives ~11 s past GO,
takes a frame (`s<N>-g11`), releases RT and restarts. A cycle is ~21.6 s, which
also keeps every start at a different point of the toggle's 8-s cycle (it
steps ~5.6 s each start), so neither state owns the first seconds after GO.
Twelve starts, ~463 s of route, `--seconds 500`.

### How a start is read

`docs/lanes/perdrawon1010/startread.py`. The first start is `mark gameplay`
and later ones are `mark go<N>`. A perflog row (a ~2 s window, timed at its
end) belongs to a start when its window lies inside [mark + 1.5 s, mark +
12.0 s], i.e. GO + 0 .. GO + 10.5 (the half second for the first start's GO,
which wanders ~0.6 s with the load). It counts only when no toggle flip falls
inside it (perdraw1009's pure-row rule, loaded from its `togread.py` at
`4ad1154e55`). Results are given per state (switches off/on), per draws/frame
bin, and as a matched-work (bin weighted) on-off. Frame ms is pooled wall
time per guest frame, 1000 x rows / sum of gfps. RT is pressed during the
countdown, so the car launches at GO whatever the GO timing; holding the gas
through a countdown does not false-start in this game. `--window -4,1.5`
reads the countdown instead. A run without the toggle is read as one fixed
state from the build's `[perdraw433] bulk= ubercache= fogcache= toggle_ms=0`
startup line, which is how the energy runs double as a separate-arm check.

### The prediction and the runs

`docs/testing/predictions/perdrawon1010-racestart.json`, registered before any
scored run. Legs: V (12 marks, route finished, no fatal, no thermal pause,
toggle_ms 4000 or one fixed state), S1 matched us/draw on-off in [-4.0, 0.0],
S2 matched gfps on-off in [-1.0, +2.0], S3 at least 10 pure rows per state,
S4 switches-on gfps over the first 10 s after GO below 28 (the start does not
hold 28-30 fps). Judged set: three toggled runs. Cross-check and energy set:
four fixed-state runs, off, on, on, off.

Queue order as run (all at `4ad1154e55`, apk `72fe2eabc46e`, `--seconds 500`,
`--expect perdrawon1010-racestart.json`). The fixed-state arms are interleaved
with the toggled runs, so the two OFF arms bracket everything:

| # | request | env | shader cache at start |
|---|---|---|---|
| T1 | `1-1791644404-perdrawon1010-362940` | `HAKUX_UNI_TOGGLE=4` | cleared (new apk) |
| OFF1 | `1-1791644405-perdrawon1010-365120` | none (shipped) | kept |
| ON1 | `1-1791645060-perdrawon1010-726861` | `HAKUX_UNI_BULK=1 HAKUX_UNI_UBERCACHE=1 HAKUX_UNI_FOGCACHE=1` | **cleared** (a 90 s Forza request on another apk ran in between) |
| T2 | `1-1791645061-perdrawon1010-727551` | `HAKUX_UNI_TOGGLE=4` | kept |
| T3 | `1-1791645062-perdrawon1010-728073` | `HAKUX_UNI_TOGGLE=4` | kept |
| ON2 | `1-1791645063-perdrawon1010-728778` | the three switches =1 | kept |
| OFF2 | `1-1791645064-perdrawon1010-729270` | none (shipped), queued last | kept |

Every run's frames were read (contact sheets of every `go<N>`, `r<N>-ok` and
`s<N>-g11` frame). All 84 starts are valid:
- every mark frame shows the grid with the race clock at 0.00 and the
  countdown, or GO! at the first start of T3, whose load ran long;
- every `r<N>-ok` frame shows the restart prompt on OK;
- every `s<N>-g11` frame shows the race running, with the clock at 11.0-11.4 s.

With no steering, the Punto reaches the first corner's chevron barrier by
~GO+9-11, so the tail of each window is a light scene (500-900 draws/frame).
Binning by draws/frame keeps that tail apart from the start. The opponents'
cars (colours) change from boot to boot, which is part of the run-to-run band.
ON1 began with a cold shader cache and OFF1 with a warm one. That works
against the switches, and ON1 still reads at or above ON2 in every table
below.

### Results: the judged set (three toggled runs), `startread.py T1 T2 T3 --expect perdrawon1010-racestart.json`

**Legs: V PASS, S1 PASS, S2 PASS, S3 PASS, S4 PASS.**

| state | draws/frame bin | pure rows | gfps (min-max) | frame ms | us/draw | draws/frame |
|---|---|---|---|---|---|---|
| off | <1100 | 11 | 25.7 (22-29) | 38.9 | 11.35 | 827 |
| off | 1100-1400 | 2 | 22.0 (21-23) | 45.5 | 10.07 | 1,231 |
| off | all | 13 | 25.2 | 39.8 | 11.08 | 889 |
| on | <1100 | 19 | 27.7 (24-31) | 36.1 | 9.81 | 778 |
| on | 1100-1400 | 7 | 21.6 (21-22) | 46.4 | 8.31 | 1,295 |
| on | all | 26 | 26.0 | 38.4 | 9.24 | 917 |

Matched-work on-off: **+1.41 gfps, -1.9 ms/frame, -1.59 us/draw** (S1 needs
[-4, 0], S2 [-1, +2]). Run-to-run band, each run's own on-off: +1.79, +1.09,
+2.11 gfps; -1.47, -1.94, -1.99 us/draw. Every run has the same sign.

The toggled set is thin where it matters. It has no pure row above 1,400
draws/frame. A perflog row is 60 guest frames, so at 17 fps a row lasts
~3.5 s, and a 4-s toggle half-period almost never holds a whole one. A pure
row also has to fit inside the window, which drops the rows that straddle GO.
T2 gave 1 off row against 11 on: its restart cycle (~22.4 s) drifts slowly
against the 8-s toggle cycle, so most of its pure rows fall in one phase. The
toggle instrument cannot see the start's heaviest frames, and the fixed-state
arms below are the measurement for them.

### Results: the fixed-state arms (OFF1, ON1, ON2, OFF2), same reader

**Legs: V PASS, S1 PASS, S2 PASS, S3 PASS, S4 PASS** (unjudged cross-check,
the registered expect).

| state | draws/frame bin | rows | gfps (min-max) | frame ms | us/draw | draws/frame | Tot ms | Idle ms |
|---|---|---|---|---|---|---|---|---|
| off | <1100 | 48 | 27.0 (23-31) | 37.0 | 11.49 | 750 | 30.7 | 10.8 |
| off | 1100-1400 | 21 | 20.8 (19-22) | 48.1 | 9.81 | 1,292 | 38.2 | 10.2 |
| off | 1400-1700 | 3 | 18.0 (17-19) | 55.6 | 9.11 | 1,551 | 43.9 | 10.8 |
| off | all | 72 | 24.8 | 40.3 | 10.65 | 941 | 33.4 | 10.6 |
| on | <1100 | 45 | 26.6 (23-30) | 37.7 | 9.58 | 823 | 30.8 | 11.1 |
| on | 1100-1400 | 23 | 21.6 (20-23) | 46.3 | 8.26 | 1,272 | 36.0 | 10.0 |
| on | 1400-1700 | 6 | 20.2 (19-21) | 49.6 | 7.86 | 1,463 | 39.3 | 11.0 |
| on | all | 74 | 24.5 | 40.8 | 8.87 | 1,015 | 33.1 | 10.7 |

Per run: OFF1 24.2 gfps / 10.53 us/draw / 978 draws/frame; ON1 24.6 / 8.70 /
1,025; ON2 24.4 / 9.03 / 1,005; OFF2 25.5 / 10.78 / 904. Matched-work on-off:
+0.08 gfps, -0.5 ms, **-1.76 us/draw**. The near-zero gfps comes from the
<1100 bin: there the on rows carry 823 draws/frame against off's 750, and a
300-draw bin is too wide to match work. The two fits below take load out
properly.

**Frame time against draws/frame** (`startfit.py`, unjudged, added after the
read). For each state it fits frame ms = a + b x draws/frame by least squares
over the same rows. It is a reading aid for the bin problem above, and none of
the registered legs depend on it.

| draws/frame | off fps (ms) | on fps (ms) | on-off ms | on-off fps | per-run off | per-run on |
|---|---|---|---|---|---|---|
| 1,133 | 22.2 (45.1) | 22.9 (43.6) | -1.5 | +0.8 | 22.1, 22.2 | 23.1, 22.8 |
| 1,259 | 21.0 (47.7) | 21.8 (45.9) | -1.8 | +0.8 | 21.0, 21.0 | 21.9, 21.7 |
| 1,374 | 20.0 (50.1) | 20.9 (47.9) | -2.1 | +0.9 | 20.0, 20.0 | 21.0, 20.7 |
| 1,500 | 19.0 (52.6) | 19.9 (50.2) | -2.5 | +0.9 | 19.1, 18.9 | 20.0, 19.8 |
| 1,658 | 17.9 (55.9) | 18.9 (53.0) | -2.8 | +1.0 | 18.0, 17.8 | 19.0, 18.7 |

At every load from 1,133 to 1,658 draws/frame, both on runs are faster than
both off runs. The per-run bands do not overlap, and the gap grows with draws:
the slope falls from 20.5 to 18.0 us per draw of frame time. The toggled set's
own fit agrees: -1.7 to -1.8 ms, +0.6 to +1.2 fps at 800-1,650 draws/frame.

**Sensitivity windows** (same four arms, unjudged):

| window | what it holds | off gfps (ms) | on gfps (ms) | per-run off | per-run on | matched on-off |
|---|---|---|---|---|---|---|
| mark+0 .. +6 (GO-1.5 .. GO+4.5) | the first seconds of racing, 1,400-1,500 draws/frame | 19.1 (52.5) | 20.7 (48.4) | 19.0, 19.1 | 20.5, 20.8 | +1.08 fps, -2.8 ms |
| mark-4 .. +1.5 (the countdown) | 1,560-1,600 draws/frame | 18.0 (55.4) | 19.5 (51.3) | 18.3, 17.8 | 19.0, 20.0 | +1.41 fps, -3.8 ms |
| mark+1.5 .. +12 (GO .. GO+10.5, registered) | the start and the run to the first corner | 24.8 (40.3) | 24.5 (40.8) | 24.2, 25.5 | 24.6, 24.4 | -1.76 us/draw (fits above) |

### Next to the owner's numbers

| scene | draws/frame | owner 10-09 (build 1b1fec978d, switches not in it) | this lane, switches off | this lane, switches on |
|---|---|---|---|---|
| 3-racer sprint start | 1,374-1,658 | 12-16 fps; 13 fps at ~1,650 | 20.0-17.9 fps (50-56 ms) | **20.9-18.9 fps (48-53 ms)** |
| 1v1 circuit start | 1,133-1,259 | 16-19 fps | 22.2-21.0 fps (45-48 ms) | 22.9-21.8 fps (44-46 ms) |
| first 6 s after the mark, measured | ~1,450 | -- | 19.1 fps (52.5 ms) | **20.7 fps (48.4 ms)** |

This lane's off column runs faster than the owner's at the same draws/frame.
That is expected: a different track (Diamond & Union, Sprint's default,
against the owner's downtown pick) and a newer build. Draws/frame is the common axis, but it does not make the two scenes
the same. The comparison that carries weight is on against off on the same
route and build.

**The start does not hold 28-30 fps with the switches on.** At the owner's
1,374-1,658 draws/frame it runs 18.9-20.9 fps (48-53 ms per frame). 30 fps
is 33.3 ms. The switches take 2-4 ms off a start frame, and a start frame
would need to lose another 15-20 ms to reach 30 fps.

## 8. What the next lane should not repeat

- **`nfs-mw.route` is not a race start.** It plays Career's prologue and gets
  control mid-lap 2/2, alone. Use `nfs-mw-quickrace.route`: 12 three-racer
  starts per boot in ~460 s, every one valid on frames.
- **A restart does not reload.** GO comes ~4.1 s after the restart prompt's
  OK, and the prompt opens on Cancel (left, then A).
- **Do not use `HAKUX_UNI_TOGGLE=4` where the frame rate is under ~20 fps.** A
  perflog row is 60 guest frames, ~3.5 s at 17 fps, so a 4-s half-period
  almost never holds a pure row. The toggled race-start set had no pure row
  above 1,400 draws/frame. Fixed-state arms (whole runs per state, bracketed
  off-on-on-off) see every row. With 12 starts per run, two runs per state
  gave 72-74 rows.
- **Wide draws/frame bins do not match work.** Inside <1100 the on rows sat
  at 823 draws/frame against off's 750, and that alone took the matched gfps
  from about +0.9 to +0.08. Fit frame ms against draws/frame
  (`startfit.py`), or use bins of 200 draws or less.
- **A different apk between two arms clears the shader cache** for the arm
  that follows (`result.json` `shader_cache`). Check it per run; ON1 started
  cold here.
- **Do not cite the owner's 13 fps as this route's off number.** The owner's
  start was a different track and build: 13 fps at ~1,650 draws/frame, where
  this route's off fit gives 17.9.
