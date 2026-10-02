# near30: why near-30 titles cannot hold 28.5 fps -- frame decomposition and the lever
State: draft

Lane: near30            Issue: #433
Base: master @ 7e1b471ef1
Files: docs/lanes/near30/PR.md, docs/lanes/near30/NOTES.md, docs/lanes/near30/OUTBOX.md, docs/lanes/near30/decompose.py, docs/lanes/near30/decompose.out, docs/lanes/near30/windows.tsv, docs/lanes/near30/tron-perflog.out, docs/lanes/near30/tron-perflog.tsv, docs/lanes/near30/tron-newgame.route, docs/lanes/near30/peek_runs.py, docs/lanes/near30/peek_rdc.py
Prediction: none: analysis-only (one survey capture, expected result written in its request)
Needs device: yes (Nova; 1 of 3 runs used: 1790983969-lane.near30-3991603)    Needs NDK: no

Tron 2.0 on the Nova is CPU-bound on the vCPU thread. In below-bar windows (median frame ~43 ms):
- the vCPU runs guest code for 32.7 ms;
- it sleeps 10.3 ms, and that sleep tracks GPU ms per frame (r = 0.64);
- the guest never idles;
- the renderer idles 17.6 ms;
- the GPU sits at its 401 MHz floor.

Measured out as the cause of the sleep: pgraph.lock (#474), the fifo skew bound, read-downloads. ToeJam & Earl III, the control, holds with 11 ms of guest work per 16.7 ms frame.

Levers ranked by probability x size, with a successor brief for the top one (name the vCPU's GPU-side wait), are in NOTES.md.

WAITING: the Blinx 2 capture needs lane.local's addendum that the owner's save past Test 1 exists on the Nova. Not received by 16:50 PDT.

Local checks: no harness or emulator files changed, so selftest does not apply; decompose.py runs on all 9 result dirs named in NOTES.md.

Release note (none): analysis only, no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
