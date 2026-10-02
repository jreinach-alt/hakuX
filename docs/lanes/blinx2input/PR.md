# blinx2input: Blinx 2 never moves in Challenge 1 -- find why

State: draft

Lane: blinx2input            Issue: #670 [#433]
Base: master @ 0426a98181
Files: docs/lanes/blinx2input/NOTES.md, docs/lanes/blinx2input/PR.md, docs/lanes/blinx2input/OUTBOX.md, docs/lanes/blinx2input/rstick_probe.py
Prediction: none: analysis-only (so far)
Needs device: yes    Needs NDK: no

Leading hypothesis (offline): the probed "gameplay" is Challenge Test 1, which
tells the player to move the RIGHT thumbstick to look at 3 balloons; the
prober (pathfind) can only send the left stick. See NOTES.md.
