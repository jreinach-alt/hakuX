# lane.gpuclock (#433): is the GPU clock-limited? GPU ms per frame against the Adreno clock, per title

State: draft

Lane: gpuclock              Issue: #433
Base: master @ d32c35d3ce
Files: hw/xbox/nv2a/pgraph/profile.c, docs/lanes/gpuclock/PR.md, docs/lanes/gpuclock/NOTES.md, docs/lanes/gpuclock/OUTBOX.md, docs/lanes/gpuclock/survey.py, docs/lanes/gpuclock/clockdist.py, docs/lanes/gpuclock/gpuclock.py, docs/lanes/gpuclock/fixture.py, docs/lanes/gpuclock/synchk.py, docs/lanes/gpuclock/forza-gpuclock.route
Prediction: none yet (a measurement lane; the clock ladder is registered before any run)
Needs device: yes (Thor queued <= 480 s; Nova queued in pathfind's gaps)    Needs NDK: no

Release note (none): telemetry only. A `[gpuclk433]` log line (GPU ms per frame, and the Adreno clock and busy share sampled at 10 Hz); nothing a player sees changes.

## Status

Knobs (NOTES 1): `performance_mode` 0/1/2 sets the kgsl floor 401/550/615 MHz; nothing a shell
or the app can reach sets the ceiling (680) or pins the clock. On disk, the stock governor sits on
its floor in 78-88% of 30 s samples on both handhelds. The instrument (`[gpuclk433]`, profile.c,
grant asked) gives GPU ms per frame in plain builds and the clock + busy% at 10 Hz. Criteria are
registered in NOTES 3 before any run. Thor Forza pilot next.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
