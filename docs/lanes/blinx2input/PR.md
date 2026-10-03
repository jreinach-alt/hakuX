# blinx2input: Blinx 2 "never moves" is Test 1's right-stick camera gate, not an input defect

State: ready

Lane: blinx2input            Issue: #670 [#433]
Base: master @ 0426a98181
Files: docs/lanes/blinx2input/NOTES.md, docs/lanes/blinx2input/PR.md, docs/lanes/blinx2input/OUTBOX.md, docs/lanes/blinx2input/rstick_probe.py, docs/lanes/blinx2input/center.py, docs/lanes/blinx2input/nav.sh, docs/lanes/blinx2input/test1.py, docs/lanes/blinx2input/confirm.py, docs/lanes/blinx2input/ref/title.png, docs/lanes/blinx2input/ref/test1.png, docs/lanes/blinx2input/ref/bearings.jpg, docs/lanes/blinx2input/frames/walk-sheet.jpg, docs/lanes/blinx2input/frames/balloons-fp-sheet.jpg, docs/lanes/blinx2input/frames/confirm-600s-strip.jpg
Prediction: none: no emulator change (the defect was in the prober, not hakuX)
Needs device: yes    Needs NDK: no

Blinx 2 (4D530065) did not stop answering input in gameplay. The level both
pathfind runs probed is Challenge Test 1 of 7, which locks movement until the
player turns the camera with the RIGHT stick to find 3 balloons, then finds
them again in first person (R3). pathfind's vocabulary sends only the left
stick, the hat and the buttons, so none of its 30+ probes could pass that
gate.

On the Nova, `test1.py` drives a fresh launch through both balloon steps with
closed-loop right-stick pulses. The tutorial then unlocks movement, and the
player walks and runs under the left stick (`frames/walk-sheet.jpg`).
The 600-s confirmation passed (13:37-13:48 PDT): the player walked back and
forth for 31 cycles across 641 s, with a frame at least every 23.6 s
(`frames/confirm-600s-strip.jpg`). It awaits the owner's frame review. The
battery was not charging, but the Nova stayed on USB.
hakuX's input path delivers every input the title asks for. Nothing in the
emulator changes.

For the prober: Blinx 2 needs a right-stick token in pathfind, which is
lane.pathfind's file. Driving notes for any tool:
- RX below ~12500 does not yaw (dead zone).
- Yaw persists after release.
- In third person, pitch springs back.
- adb adds ~0.15 s to every stick pulse.

Local checks: no harness or emulator files changed, so neither selftest nor a
dispatch run applies. `python3 -m py_compile` passes on the lane scripts.

Release note (none): no emulator change.
