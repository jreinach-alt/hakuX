# nearbar1017: three near-bar titles on the 0.5.2 build -- two clear Playable now

State: ready

Lane: nearbar1017            Issue: #433
Base: master @ 07b7b6d9960ba029076b675faa7ce6b5cd7f26c5 (merged forward to
  origin/master's a6ec42fadc before concluding; no conflicts, no change to
  the nv2a texture/render-target path this lane's runs were made under)
Files: docs/lanes/nearbar1017/NOTES.md, docs/lanes/nearbar1017/PR.md
Prediction: none: analysis-only (held device runs, judged by hand against the existing ledger bar; no code change to predict against)
Needs device: yes    Needs NDK: no
Selftest: none (docs only)
Release note (none): analysis/measurement only, no emulator-code change

Re-ran Panzer Elite Action, Aeon Flux, and Medal of Honor: Frontline on the
current (0.5.2) build: each had scored below the 90%-at->=30fps Playable bar
on a pre-0.5.2 build, and 0.5.2 turned on `HAKUX_S2T_CVT` (16-bit render
target texture path) by default, so this was a new measurement, not a
retest.

Step 0 (`docs/lanes/nearbar1017/NOTES.md`): no open `nv2a_issues.toml`
defect names any of the three, so all three needed the run.

Result: **2 of 3 clear the bar.**

| Title | Play seconds | Share >=30fps | Median fps | Clear/miss |
|---|---|---|---|---|
| Panzer Elite Action | 627.3 s | 1.0 (100%) | 62.5 | **Clear** (was 89.65%/30.41 pre-0.5.2 -- `HAKUX_S2T_CVT` moved it off its 30fps cap entirely) |
| Aeon Flux | 602.5 s | 0.936 (93.6%) | 29.96 | **Clear**, but close (was 84.6%/29.96 pre-0.5.2 -- still capped at ~30fps, mid-hold checkpoints read 86.8-88.7% before the final share) |
| Medal of Honor: Frontline | 287.3 s (stuck_abort) | 1.0 of the 287 s played | 59.94 | **Inconclusive**, not an fps miss -- the autoplay path got physically stuck against a beach obstacle (frame review: pinned looking at the sky, ammo spent, no crash/hang); fps itself was clean the whole time it played (min 29.96, vs 15.9 pre-0.5.2) |

MoH got no perflog telemetry hold: its own confirmation run already measured
`fps_ok_share: 1.0`, so there is no fps deficit for `near30`'s `decompose.py`
to decompose -- that device time would not have decided anything. The
`NOTES.md` final table and both per-run sections give the full reasoning,
frame evidence, and the driver verification method (direct on-device
`gpu_driver/` file check, not log grep -- the logcat capture window in every
one of these runs starts after the app's own driver-load line, for all
three titles, same shape as prior truncation issues).

Recommendation to lane.local: file the Panzer and Aeon Flux ledger rows from
these run directories (`docs/lanes/nearbar1017/runs/n-4A570009-1017`,
`n-4D4A0014-1017`); for MoH, file the fps numbers as supporting context but
leave the Playable determination pending a `pathknow` route fix for the
beach-obstacle stretch, then one fresh confirmation attempt (not a rerun of
this one). Given 2 of 3 clear and the third's partial data points the same
way, this reads like a real win for the whole near-the-cap cohort, not one
title's coincidence -- worth re-running more of the near-bar list rather
than stopping at these three (brief's own instruction: report and let
lane.local decide whether more are worth it).

Also flagged in NOTES.md: Aeon Flux's recorded path (`pathknow/paths/
4D4A0014.json`) was never committed anywhere -- found only as an untracked
file in the `wt/pathfind` worktree, copied locally (not staged/committed
here) to let this run replay it. Worth lane.local committing it properly so
it isn't lost.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
