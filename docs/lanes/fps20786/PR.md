# fps20786: the bound behind the ~20-fps class on the Nova (#786, #747)
State: draft

Lane: fps20786            Issue: #786 #747
Base: master @ 4a3308a21e
Files: docs/lanes/fps20786/NOTES.md, docs/lanes/fps20786/OUTBOX.md, docs/lanes/fps20786/PR.md, docs/lanes/fps20786/decompose.py, docs/lanes/fps20786/extras.py, docs/lanes/fps20786/make-routes.sh, docs/lanes/fps20786/nba-live-2005-hold.steps.jsonl, docs/lanes/fps20786/routes/fps786-cs.route, docs/lanes/fps20786/routes/fps786-nba2005.route, docs/lanes/fps20786/routes/fps786-topspin.route, docs/lanes/fps20786/sdsurvey-by-title.tsv, docs/lanes/fps20786/sdsurvey.py, docs/lanes/fps20786/steps2route.py
Prediction: none: analysis-only (telemetry soaks; the bound signatures were registered in NOTES.md at e95ca394c1 before any run)
Needs device: yes (Nova, 5 --perflog soaks via request.sh)    Needs NDK: no

**The class shares one bound, and it is new: synchronous surface-download finishes (#794).** Every frame, NBA Live 2005, Counter-Strike and Midnight Club 3 make 1-2 `pgraph_vk_finish(VK_FINISH_REASON_SURFACE_DOWN)` calls. That reason is not in the deferred set, so each call submits everything recorded so far and blocks the PFIFO thread until the GPU is done, a 11-14 ms wait. The render thread's CPU work and the GPU then run in series, putting renderer cost at 32-37 ms per frame. That is just over two VBLANKs, so frames take three. The vCPU is not the bound (guest busy ~21 ms of a ~40-ms frame), nor the lock (0.3-2.3 ms), nor the GPU alone (14-25 ms). Top Spin takes the same finish ~30 times a frame with pgraph.lock held, and its vCPU waits 13-18 ms per frame behind it (#474). On today's build Top Spin is a near-30 title (0.89).

| title | run | fps | share >= 28.5 | render thread on-CPU + blocked | GPU | finish wait | bound |
|---|---|---|---|---|---|---|---|
| NBA Live 2005 | 1-1791081646-lane.fps20786-2876934 | 24.2 | 0.07 | 24.7 + 11.0 | 18.5 | 13.9 | serial renderer (1 sync download per frame) |
| NBA Live 2005, plain build, device defaults | pathfind nba-live-2005-hold | 19.96 | 0.00 | 26.4 + 15.5 | -- | -- | same, without perflog |
| Counter-Strike | 1-1791081646-lane.fps20786-2876984 | 25.8 | 0.00 | 22.8 + 14.3 | 24.6 | 13.8 | serial renderer (2 per frame) |
| Counter-Strike (retry) | 1-1791086565-lane.fps20786-3338415 | 25.9 | 0.00 | 22.5 + 14.2 | 24.4 | 13.7 | same |
| Midnight Club 3 | 1-1791081681-lane.fps20786-2878057 | 25.4 | 0.01 | 22.5 + 9.8 | 14.2 | 11.2 | serial renderer, on the 33.3 edge (perflog-sensitive) |
| Top Spin | 1-1791080537-lane.fps20786-2538884 | 32.5 | 0.89 | 16.0 + 14.4 | 10.6 | 15.5 | lock behind ~30 sync downloads per frame (#474) |
| NBA Live 2004 / 06 / 07 | -- | -- | -- | -- | -- | -- | not measured: no path or route; held runs asked of lane.pathfind (#785) |

Across every perflog soak of the last 10 days (31 titles, `sdsurvey.py`), titles with no synchronous surface download spend <= 2.5 ms per frame in finish. The ten that make one or more per flip spend 8-26 ms. Several of those ten are near-30 titles (Blinx 2, Forza, Burnout, MM3, Nightfire).

The fixes, ranked by P x win, are in NOTES.md ("Fixes, by P x win"). The first is asynchronous surface downloads: wait at the guest's next sync point instead of at the download. P 0.4, and it would bring NBA and Counter-Strike under 33.3 ms. None was started here.

Preflight: everything passes except the board's coverage gate, which flags #794 and #795 because neither has a lane or blocker yet. That is the tracker's to classify; this lane does not edit board files.

Release note (none): analysis only, no emulator change.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
