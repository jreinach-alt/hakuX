# near30: why near-30 titles cannot hold 28.5 fps -- frame decomposition, Blinx 2 ocean dip, and the levers
State: ready

Lane: near30            Issue: #433
Base: master @ 6c828f9860 (merged; first base 9d1155f919)
Files: docs/lanes/near30/PR.md, docs/lanes/near30/NOTES.md, docs/lanes/near30/OUTBOX.md, docs/lanes/near30/decompose.py, docs/lanes/near30/decompose.out, docs/lanes/near30/windows.tsv, docs/lanes/near30/tron-perflog.out, docs/lanes/near30/tron-perflog.tsv, docs/lanes/near30/tron-newgame.route, docs/lanes/near30/peek_runs.py, docs/lanes/near30/peek_rdc.py, docs/lanes/near30/b2.py, docs/lanes/near30/ocean433.py, docs/lanes/near30/scored433.py, docs/lanes/near30/build-perflog.sh, docs/lanes/near30/blinx2-perflog-extract.tsv, docs/lanes/near30/dips433.py
Prediction: none: analysis-only (no emulator change; no arm)
Needs device: yes (Nova, one held session; the device is released and `titlestate release` has run)    Needs NDK: no

Attempt 3 finished the two things attempts 1-2 left waiting: the Blinx 2 perflog capture on the owner's
"Jaguars" save, and the lever ranking that includes Blinx 2.

**Attempt 4 (10-03 09:31-09:40 PDT, no device run).** This attempt answers Addendum 1's open question offline, from the session's logcat (`dips433.py`). Blinx 2's first-appearance hitches are not texture uploads: at most 17 new textures and 106 KB per hitch second. They are not readbacks either: there are none. 8 of the 9 hitch seconds carry a new pipeline, against 3 of the other 249. Even so, with the ubershader on, the measured draw-path compile in 5 of those 8 is at most 0.3 ms, so the 100-380 ms frames are spent where the counters cannot see. The 3.7-s stall at the first gameplay load is a real 2.96-s compile. The NEW ISSUE lines (sea draws, new-pipeline hitches, a golden that times out into RETRY CHECKPOINT) are in OUTBOX.md. Lane.vcpuwait433 now owns Tron's lever.

**Next (P x win, NOTES "Lever table, re-scored at attempt 4"):**

| # | candidate | P (evidence) | win | cost |
|---|---|---|---|---|
| 1 | Blinx 2 sea draws: per-draw dump, then batch them or cut fragment cost (`oceandraw433`) | 0.35 (draws +70%, GPU +40%, per-draw cost falls) | sea-in 19 -> ~24 fps | 1 held session + a renderer change |
| 2 | Tron vCPU GPU-side sleep (lane.vcpuwait433) | 0.3 (intro wait removed, in-level not yet measured) | ~3 ms/frame Tron, ~6 BF2 | owned |
| 3 | memfast phase 2 (fastmem) | 0.5 Tron / 0.15 Blinx 2 (phase 1 folded) | ~3.5 ms/frame Tron | board grants, owned |
| 4 | Blinx 2 new-pipeline hitches, timed per frame | 0.25 | 100-380 ms hitches, about 3% of seconds | 1 perflog session |

**Blinx 2, the ocean dip (GPU-side, from draw count).** Steady frames on the post-tutorial "Arch" area:

| window | fps | draws/frame | GPU ms | vCPU on-CPU |
|---|---|---|---|---|
| sea out | 25.0 | 26 | 35 | 0.88 |
| sea in | 19.0 | 44 | 50 | 0.88 |

The sea adds draw calls (+70%) and GPU ms per draw falls, so the count is the cost. The vCPU is unchanged and the guest is idle about half the time. Texture uploads are zero in both windows.

**Scored window: partial.** A checkpoint retry prompt and a scripted dialogue interrupted the walk. Valid gameplay is 314 s; the share of per-second rows at or above 28.5 fps is 0.115 (median 22.2). The 600-s bar is not met, and the first 98 s alone were 0.44.

**Tron 2.0 and ToeJam (from attempt 1, unchanged):** Tron is CPU-bound on the vCPU thread with its GPU at the floor clock; ToeJam holds with 11 ms of guest work per 16.7 ms frame.

Levers ranked by probability x win, the successor brief for the top one (the ocean's draws, by a per-draw frame dump), and the per-title budget tables are in NOTES.md.

Local checks: `docs/testing/jobs/hold.sh` take/wait-idle/release run on the Nova; `perflog` APK built locally (`build-perflog.sh`, GRADLE_EXIT=0, stamp `0.4.1-1003-9169b18587-perflog`); `ocean433.py` reproduces the windows from `blinx2-perflog-extract.tsv`. `docs/testing/preflight.sh --allow-tracker` at the attempt-4 head (after merging master 6c828f9860): passed, rc 0. aci_vmstate, nv2a index, territory, coverage (read from a 23-h-old cache) and board files were all ok. `dips433.py` reproduces the step-2d table from `b2run/r1/logcat.txt`. No emulator code changed, so selftest does not apply.

Release note (none): analysis only, no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
