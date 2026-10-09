# fpstelemetry1008b: the four titles lane A could not measure -- NFS Most Wanted, Midnight Club II, Fantastic 4, Dino Crisis 3 (#433)

State: ready

Lane: fpstelemetry1008b      Issue: #433 (0.5)
Base: master @ 34a0b032b9
Files: docs/lanes/fpstelemetry1008b/NOTES.md, docs/lanes/fpstelemetry1008b/PR.md, docs/lanes/fpstelemetry1008b/steps2route.py
Prediction: none: telemetry survey, no golden, no A/B arm
Needs device: yes (Nova; four route pilots + two full telemetry runs this lane across attempts 1-3, see NOTES.md §6-8)
Needs NDK: no
Release note (none): analysis only; no emulator or Android code touched.

Follow-up to lane.fpstelemetry1008 (folded to master as 34a0b032b9), picking up the four
titles its own cause table could not reach. Fixed `steps2route.py`'s missing combo-token
branch (`RT+left`/`RT+right`, used by `HOLD_GENRES["drive"]` and by NFS Most Wanted's and
Midnight Club II's own recorded navigation) and added a `--hold-log` mode that replays a
title's own recorded `hold.jsonl` verbatim instead of inventing a genre loop, for
Fantastic 4 (needs `START`/`A` to skip a game_over/cutscene cycle between gameplay
bursts) and Dino Crisis 3 (the model adapted its own button mix mid-hold). See NOTES.md
§1-4 for the fix and the four generated routes, §5 for the gate audit (all four clear).

Four route pilots (NOTES.md §6): NFS Most Wanted and Fantastic 4 good, cleared for full
telemetry; Midnight Club II and Dino Crisis 3 bad (route/input defects — car/player never
moves — recorded and not retried, per the brief's own instruction for those two titles).
Two full telemetry runs (perflog + GPUXFR + FRAMETRACE, post-5c35880d0a) completed and
decomposed (NOTES.md §7-8): **NFS Most Wanted** corrects the prior OUTBOX.md CPU-only
citation — guest busy is only 53-57% of frame time and nearly flat across bar groups on
trusted stamps; the better-supported cause is a completion-deferred surface-download
finish-wait (1.5/flip, Fin 9.8 ms) that on its own exceeds the 6.9 ms GPU render budget,
the same class as this project's NBA Live 2005/Midnight Club II rows. **Fantastic 4**
(a hold-log replay of its own recorded cutscene/game_over cycle) is bimodal — roughly
half the window is fast non-gameplay screens — and inside the actual gameplay frames
shows a mixed picture: guest busy, render-thread blocked time, and an unusually large
unattributed guest wait (`v_blk`, the largest in this project's cause-table work so far)
all elevated together, not one clean driver.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
