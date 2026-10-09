# fpstelemetry1008b: the four titles lane A could not measure -- NFS Most Wanted, Midnight Club II, Fantastic 4, Dino Crisis 3 (#433)

State: in progress

Lane: fpstelemetry1008b      Issue: #433 (0.5)
Base: master @ 34a0b032b9
Files: docs/lanes/fpstelemetry1008b/NOTES.md, docs/lanes/fpstelemetry1008b/PR.md, docs/lanes/fpstelemetry1008b/steps2route.py
Prediction: none: telemetry survey, no golden, no A/B arm
Needs device: yes (Nova; four route pilots queued this session, see NOTES.md §6)
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

Four route pilots queued this session (NOTES.md §6, in progress as this is written).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
