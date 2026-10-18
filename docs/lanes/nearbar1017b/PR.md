# nearbar1017b: three more near-cap titles on the 0.5.2 build -- two clear, one inconclusive

State: ready

Lane: nearbar1017b             Issue: #433
Base: master @ f799199e39
Files: docs/lanes/nearbar1017b/NOTES.md, docs/lanes/nearbar1017b/PR.md
Prediction: none: analysis-only (held device runs, judged by hand against the existing ledger bar; no code change to predict against)
Needs device: yes    Needs NDK: no
Selftest: none (docs only)
Release note (none): analysis/measurement only, no emulator-code change

Second near-cap batch on #433 (first was `nearbar1017`, folded `f799199e39`:
Panzer and Aeon Flux cleared, MoH inconclusive). This batch: Turok Evolution
(41430004), Burnout 3: Takedown (4541005B), Ty the Tasmanian Tiger: Night of
the Quinkan (41560055) -- each missed the Playable bar (>= 30 fps, >= 90% of
gameplay) only on fps on a pre-0.5.2 build, and 0.5.2 turned on
`HAKUX_S2T_CVT` by default, so this is a new measurement, not a retest.

Step 0 (`docs/lanes/nearbar1017b/NOTES.md`): no open `nv2a_issues.toml`
defect names any of the three, so all three needed the run.

Result: **2 of 3 clear the bar.**

| Title | Play seconds | Share >=30fps | Median fps | Clear/miss |
|---|---|---|---|---|
| Turok Evolution | 605.5 s | 0.975 (97.5%) | 29.97 | **Clear**, cap-riding (was 83.5%/29.85 pre-0.5.2; floor rose from 9.83 to 27.11 but median says it's still on the 30fps cap, not off it like Panzer) |
| Burnout 3: Takedown | 664.9 s | 0.9966 (99.66%) | 45.49 | **Clear**, off its old cap (was 84.75%/30.8 pre-0.5.2 -- first-ever ledger row for this title, none existed before) |
| Ty the Tasmanian Tiger: Night of the Quinkan | 193.3 s (hold's own early-exit) | 0.8337 of only 45 s of actual play -- not reliable | 42.34 (same caveat) | **Inconclusive**, not a clean fps miss -- the recorded path walked the character into a courtyard hedge/wall and got stuck there (frame review: camera frozen across dozens of hold-ticks, FPS counter still incrementing, no crash/hang); too little play happened to say whether 0.5.2 changed the sub-30 dips the brief asked about |

Ty got no perflog telemetry hold, same reasoning `nearbar1017` gave for MoH:
its own confirmation attempt never accumulated enough play to make an fps
deficit the dominant failure (`play_share` 0.2333, `still` 148 s of 193 s
scored) -- `near30`'s `decompose.py` telemetry is the right tool for an fps
deficit, not a path-stuck episode, so that device time would not have
decided anything. The `NOTES.md` final table and all three per-run sections
give full reasoning, frame evidence, and the on-device driver verification
(`gpu_driver/` file check, same method as `nearbar1017` -- the logcat
capture window in every run starts after the app's own driver-load line, so
log grep is not usable evidence here either).

Taken together with `nearbar1017`, **4 of 6** near-cap titles across both
batches now clear the Playable bar outright, and the two inconclusive
results (MoH, Ty) share the identical failure mode: a recorded path walking
into static scenery it didn't account for, not an fps problem. Recommending
lane.local treat "fix the MoH and Ty stuck paths" as one combined
`pathknow` task (same method for both) rather than two separate ones.

Recommendation to lane.local: file Turok's and Burnout 3's ledger rows from
these run directories (`docs/lanes/nearbar1017b/runs/n-41430004-1017`,
`n-4541005B-1017`). Turok's row should retire the
`turok-evolution-below-bar` registry hold (a board request, not edited
directly here); Burnout 3 gets a brand-new row, not a replacement. For Ty,
file the partial fps numbers as supporting context only, leaving the
Playable determination pending a `pathknow` route fix for the
courtyard-to-hedge stretch (~180-195 s into the route), then one fresh
confirmation (not a rerun of this one -- the stuck spot is deterministic).

Also flagged in NOTES.md: Burnout 3's recorded path
(`pathknow/paths/4541005B.json`) is untracked exactly like Aeon Flux's was in
`nearbar1017` -- found only in the `wt/pathfind` worktree, copied locally
(not staged/committed here) to let this run replay it. This is now the
**second** title this pair of lanes has found with real path knowledge that
exists nowhere but one worktree's untracked files -- worth a `pathknow`
commit sweep across that worktree rather than treating each discovery as a
one-off.

Also flagged in NOTES.md (Run 2): Burnout 3's gas-pedal probe found `A`, not
`RT`, confirmed the drive-gas input mid-hold after the car was stuck against
a barrier -- conflicts with `pathknow/hints/series-burnout.md`'s "In every
race RT accelerates" for the series generally. Recorded as an open question,
not a conclusion (the car may simply have been freed by other inputs right
before `A` was probed); did not block the run.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
