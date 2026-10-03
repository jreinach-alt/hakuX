# near30: why near-30 titles cannot hold 28.5 fps -- frame decomposition, Blinx 2 ocean dip, and the levers
State: ready

Lane: near30            Issue: #433
Base: master @ 9d1155f919
Files: docs/lanes/near30/PR.md, docs/lanes/near30/NOTES.md, docs/lanes/near30/OUTBOX.md, docs/lanes/near30/decompose.py, docs/lanes/near30/decompose.out, docs/lanes/near30/windows.tsv, docs/lanes/near30/tron-perflog.out, docs/lanes/near30/tron-perflog.tsv, docs/lanes/near30/tron-newgame.route, docs/lanes/near30/peek_runs.py, docs/lanes/near30/peek_rdc.py, docs/lanes/near30/b2.py, docs/lanes/near30/ocean433.py, docs/lanes/near30/scored433.py, docs/lanes/near30/build-perflog.sh, docs/lanes/near30/blinx2-perflog-extract.tsv
Prediction: none: analysis-only (no emulator change; no arm)
Needs device: yes (Nova, one held session; the device is released and `titlestate release` has run)    Needs NDK: no

Attempt 3 finished the two things attempts 1-2 left waiting: the Blinx 2 perflog capture on the owner's
"Jaguars" save, and the lever ranking that includes Blinx 2.

**Blinx 2, the ocean dip (GPU-side, from draw count).** Steady frames on the post-tutorial "Arch" area:

| window | fps | draws/frame | GPU ms | vCPU on-CPU |
|---|---|---|---|---|
| sea out | 25.0 | 26 | 35 | 0.88 |
| sea in | 19.0 | 44 | 50 | 0.88 |

The sea adds draw calls (+70%) and GPU ms per draw falls, so the count is the cost. The vCPU is unchanged and the guest is idle about half the time. Texture uploads are zero in both windows.

**Scored window: partial.** A checkpoint retry prompt and a scripted dialogue interrupted the walk. Valid gameplay is 314 s; the share of per-second rows at or above 28.5 fps is 0.115 (median 22.2). The 600-s bar is not met, and the first 98 s alone were 0.44.

**Tron 2.0 and ToeJam (from attempt 1, unchanged):** Tron is CPU-bound on the vCPU thread with its GPU at the floor clock; ToeJam holds with 11 ms of guest work per 16.7 ms frame.

Levers ranked by probability x win, the successor brief for the top one (the ocean's draws, by a per-draw frame dump), and the per-title budget tables are in NOTES.md.

Local checks: `docs/testing/jobs/hold.sh` take/wait-idle/release run on the Nova; `perflog` APK built locally (`build-perflog.sh`, GRADLE_EXIT=0, stamp `0.4.1-1003-9169b18587-perflog`); `ocean433.py` reproduces the windows from `blinx2-perflog-extract.tsv`. No emulator code changed, so selftest does not apply.

Release note (none): analysis only, no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
