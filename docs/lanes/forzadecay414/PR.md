# lane.forzadecay414: the +11 min step in Forza's 1200-s confirmation is the car moving to a heavier view (#414)
State: ready

Lane: forzadecay414-step   Issue: #414
Base: master @ b73367209a
Files: docs/lanes/forzadecay414/NOTES.md, docs/lanes/forzadecay414/OUTBOX.md, docs/lanes/forzadecay414/PR.md, docs/lanes/forzadecay414/step_split.py
Prediction: none: analysis-only (reads the existing run 1-1790826491-lane.verdict433-3477700; no device run)
Needs device: no    Needs NDK: no

Release note (none): documentation only

lane.local's 22:40 addendum asked what changes at about +11 min in the Playable confirmation `1-1790826491-lane.verdict433-3477700` (Nova, master b1cea467c6, default regimen, 1200 s). In that run Forza steps from 30 fps to 20 fps.

**What the step is.** The survey route parked the car at 0 mph at the start grandstand for 10.5 minutes. It then drove onto the circuit (41 mph at t = 683 s) and parked again in a forest section until the end. The fps steps one second later, at t = 684 s.
- **The forest view** puts most flips on 3 vblanks. The renderer is never idle there (Ri 0.0, against 11.5 ms/frame before), and the guest idles more (41%, against 25%).
- **No creep.** The invalid list holds at 10. G is flat over 8 minutes of identical frames. Heat and the CPU clocks do not change.
- **One open item: the GPU clock.** `gpuclk` reads 401 MHz throughout under the default regimen, where the MAX runs read 615 MHz. This run does not decide whether the forest view is bound by that clock.

The details are in NOTES.md section 13. `step_split.py` produces the per-minute table.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
