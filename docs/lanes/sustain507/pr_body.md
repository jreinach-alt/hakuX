Lane: sustain507            Issue: #507 #424
Base: master @ f82e7e87fe
Files: docs/lanes/sustain507/NOTES.md, docs/lanes/sustain507/regimen_read.py, docs/lanes/sustain507/scan_marks.py, docs/lanes/sustain507/dispatch_state.py, docs/lanes/sustain507/pr_body.md, docs/testing/predictions/sustain507-regimen.json
Prediction: docs/testing/predictions/sustain507-regimen.json @ 04a75e83c36a6d9e0eeb1cfe8c6c1cac9d9fc07472c4f845de402bb1bbbbf8bd
Needs device: yes    Needs NDK: no

Measurement only. No code changes.

**Part A (#507).** MAX against the device defaults on the Thor. Crimson Skies, GTA San Andreas and MechAssault 2 each run 30 minutes after `mark gameplay` in each regimen, on the same apk, from a cool start through the #519 gate. The prediction and its reader (`regimen_read.py`) were committed before any run. On the Thor, MAX and the defaults differ in `performance_mode` only: the fan is SMART in both.

**Part B (#424).** Two more Thor pairs of `tbflip424-blinx2.json` (Blinx, survey route, 540 s, MAX as registered). A thermal pause before the window's end voids the run.

Results go in `docs/lanes/sustain507/NOTES.md` and on #507, #433 and #424.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
