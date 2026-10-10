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
