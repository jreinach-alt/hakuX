# fpstelemetry1008: one cause table for the below-bar titles -- perflog + GPU xfr + frame trace on the Nova (#433)

State: in progress

Lane: fpstelemetry1008      Issue: #433 (dispatched directly, no tracker issue)
Base: master @ 7960e78e20
Files: docs/lanes/fpstelemetry1008/NOTES.md, docs/lanes/fpstelemetry1008/PR.md
Prediction: none: telemetry survey, no golden, no A/B arm
Needs device: yes (Nova; 2 fresh requests this session, see NOTES.md §3)    Needs NDK: no
Release note (none): analysis only; no emulator or Android code touched.

Waiting on the two queued Nova requests (MechAssault 2, Buffy) to finish before the cause
table and this PR are final. See NOTES.md for everything already verified: where the
brief's `pm/*` paths actually live, why `prequeue.py` cannot print CLEAR for any below-bar
title by construction, the full candidate list with gate/route/ISO results, and the
titles already attributed from existing data at zero device cost.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
