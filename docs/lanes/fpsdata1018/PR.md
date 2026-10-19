# fpsdata1018: FPS dip causes in the 4-title owner capture, and fixes (#433)

State: draft

Lane: fpsdata1018            Issue: #433
Base: master @ 72af9cb92c
Files: docs/lanes/fpsdata1018/NOTES.md, docs/lanes/fpsdata1018/PR.md, docs/testing/perf/fpsdiag/fpsdiag.py, docs/testing/jobs/selftest.d/99-fpsdiag.sh
Prediction: none: analysis so far
Needs device: no    Needs NDK: no

Reads the owner's 2026-10-18 capture of RalliSport 2, GTA III, Fable and Blinx 2 (master perflog 72af9cb92c) for
the wait each title's dip windows add, per phase, and lands fixes for those waits.

`fpsdiag.py` gains two candidates: `c2b_fin_sub_renderthread_wait` (the Fin swing is the finish's own submit wait,
not the frame-slot fence) and `c9_surf_download_wait` (the Surf swing).

Release note (none): analysis and tooling only so far.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
