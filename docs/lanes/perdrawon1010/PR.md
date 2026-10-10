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

**State: not ready -- device requests not yet queued.** Tooling and both
predictions committed first (prediction-before-arm, never rebased after).
Next: queue the 3-run MOTION pilot (~22.5 min, under the pilot cap), read
it, then the disc and power legs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
