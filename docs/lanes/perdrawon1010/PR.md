Lane: perdrawon1010       Issue: #433 (umbrella), none filed
Base: master @ 4fbff52ae9
Files: docs/lanes/perdrawon1010/**, docs/testing/predictions/perdrawon1010-*.json
Prediction: docs/testing/predictions/perdrawon1010-nfs-motion.json (MOTION-window toggle fps/frame-time), docs/testing/predictions/perdrawon1010-pgraph-inert.json (27-suite disc, registered via ab_compare.py)
Needs device: yes (Nova only, not yet used)
Needs NDK: no
Release note (none): measurement only, no emulator code changed, no default flipped

Measures whether perdraw1009's three default-off `HAKUX_UNI_BULK` /
`_UBERCACHE` / `_FOGCACHE` switches should default on, specifically in the
renderer-limited regime perdraw1009's own A/B did not reach (its STATIC
scene sits at the 30 fps cap; its separate-arm MOTION samples are
uncontrolled single points). Built and measured at `4ad1154e55`
(perdraw1009's head; confirmed `git diff 4ad1154e55 origin/master -- hw/`
is exactly perdraw1009's own unfolded commit, nothing else -- NOTES.md
section 0).

Plan (NOTES.md has the full reasoning): (2) a new `HAKUX_UNI_TOGGLE=4`
MOTION-window reader (`motionread.py`, reusing perdraw1009's
togread.py/armread.py functions via `git show` rather than copying them,
since perdraw1009 hasn't folded and those files aren't in this worktree),
binned by draws/frame, prediction registered before any run; (3) the same
27-suite pgraph-inert disc pfifowait1009 used, must_not_move, same ref,
switches on vs off; (4) two long separate runs (switches off/on) read
through `title_verdict.py`'s power block, no strict prediction (J/frame
has no falsifiable judge here; "no measurable change at this noise" is an
acceptable answer per the brief).

**State: not ready -- waiting on 3 more MOTION runs.** The first 3-run pilot
(`...-3286571`, `-3287113`, `-3290290`) landed and was read: M1/M2 (the
pooled on-off effect, -1.69 us/draw, separated from noise) PASS; V's
mechanical "route did not finish" on 2 of 3 runs is a harness poll-timing
artifact at the very tail of the run, not a real failure -- explained in
NOTES.md section 5a with the run.log evidence, and does not touch the
MOTION window (which closes ~40s before the route's RT release). M3/M4
(the hi-BE bin, >=700 draws/frame, closest to the owner's profiled
high-draw racing) FAIL on sample count alone (n=2/phase) -- too few rows
cross into "hi" in 3 runs' worth of ramp. Queued 3 more replicate runs
(`1-1791639780-perdrawon1010-3615994`, `-3618156`, `-3619271`, same
env/route/ref) to pool to n=6 before calling the hi-BE question settled
either way; still well inside the 4h/30min-batch budget (~45 min of 240 so
far). `docs/lanes/perdrawon1010/WAITING` holds these three ids; resumes
when they land. Next after that: re-read `motionread.py` over all 6, then
queue the disc leg (section 3) and the two power runs (section 4).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
