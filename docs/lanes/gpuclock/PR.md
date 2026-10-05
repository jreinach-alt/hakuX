# lane.gpuclock (#433): is the GPU clock-limited? GPU ms per frame against the Adreno clock, per title

State: draft

Lane: gpuclock              Issue: #433
Base: master @ d32c35d3ce
Files: docs/lanes/gpuclock/PR.md, docs/lanes/gpuclock/NOTES.md, docs/lanes/gpuclock/OUTBOX.md
Prediction: none yet (a measurement lane; the clock ladder is registered before any run)
Needs device: yes (Thor queued <= 480 s; Nova queued in pathfind's gaps)    Needs NDK: no

Release note (none): measurement and a recommendation; no emulator change.

## Status

Started 2026-10-05. Step 1 (the knobs) from the record on disk, then the existing
results as a natural experiment, then the controlled ladder.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
