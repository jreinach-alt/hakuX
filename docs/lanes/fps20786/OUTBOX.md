## #786 -- 2026-10-03 (lane.fps20786)

[lane.fps20786] The ~20-fps class shares one new bound: synchronous surface-download finishes, which put the GPU's frame in series with the render thread.

**Per title, slow windows (2-s rows below 28.5 fps), Nova, perflog, "max" regimen:**

| title | run | fps median | share >= 28.5 | guest busy / frame | render thread: on-CPU + blocked (idle) | GPU ms | finish wait ms | vCPU lock wait ms | bound |
|---|---|---|---|---|---|---|---|---|---|
| NBA Live 2005 | 1-1791081646-lane.fps20786-2876934 | 24.2 | 0.07 | 21.1 of 41.5 | 24.7 + 11.0 (6.1) | 18.5 | 13.9 | 2.3 | serial renderer: 1 sync surface download per frame |
| NBA Live 2005 (pathfind hold, device defaults) | docs/lanes/pathfind/runs/nba-live-2005-hold | 19.96 | 0.00 | 22.0 of 50.1 | 26.4 + 15.5 (8.2) | -- | -- | 0.9 | same (always-on lines only) |
| Counter-Strike | 1-1791081646-lane.fps20786-2876984 | 25.8 | 0.00 | 20.6 of 38.8 | 22.8 + 14.3 (1.6) | 24.6 | 13.8 | 0.3 | serial renderer: 2 sync surface downloads per frame |
| Counter-Strike (retry) | 1-1791086565-lane.fps20786-3338415 | 25.9 | 0.00 | 20.7 of 38.7 | 22.5 + 14.2 (2.0) | 24.4 | 13.7 | 0.3 | same, to the tenth (both runs a standing view of the map with a HUD overlay, not moving play) |
| Top Spin | 1-1791080537-lane.fps20786-2538884 | 32.5 | 0.89 | 35.4 of 36.9 (slow rows) | 18.5 + 17.8 (0.1) | 13.1 | 19.8 | 17.7 | lock: ~30 sync surface downloads per frame hold pgraph.lock (#474) |
| Midnight Club 3 (today, Arcade) | 1-1791081681-lane.fps20786-2878057 | 25.4 | 0.01 | 21.3 of 39.4 | 22.5 + 9.8 (7.2) | 14.2 | 11.2 | 1.0 | serial renderer on the edge: 1 sync surface download per frame, renderer cost 32.2 ms |
| Midnight Club 3 (09-30 plain build, Arcade) | 1-1790734333-titleroutes-3037624 | 29.7 | 0.86 | 34.9 of 43.6 | 20.1 + 11.4 (12.2) | -- | -- | 0.4 | near-30; slow rows guest-busy |
| NBA Live 2004 / 06 / 07 | none | -- | -- | -- | -- | -- | -- | -- | not measured: no path or route; three held runs asked of lane.pathfind (#785) |

The pre-run guesses: NBA 2005 as a serial renderer (0.6) held. Counter-Strike as vCPU (0.4) was wrong: it is a serial renderer. MC3 as vCPU (0.6) was wrong on today's perflog build: it shows the shared signature, right at the edge. Top Spin is a near-30 title, not a 20-fps one. 10-02's 20 / 13 / 22 were single overlay readings on device defaults.

A caveat on every perflog row: perflog costs the render thread >= ~1.2 ms per frame (+30% CPU, lane.alwaystelemetry), and the cost scales with method count. That may be what tips MC3 (09-30 plain 0.86 vs today 0.01; the build also moved). It does not change NBA: pathfind's plain-build hold has NBA renderer-critical at 20 fps.

**Shared answer.** NBA Live 2005 and Counter-Strike are bound by neither the vCPU (the guest is busy ~21 ms of a ~40-ms frame) nor the lock (0.3-2.3 ms). The GPU alone (18.5 and 24.6 ms) is not the bound either. The bound is the render thread's CPU work and the GPU **in series**. Every frame makes 1-2 `VK_FINISH_REASON_SURFACE_DOWN` finishes, which are not in the deferred set (draw.c 4169). Each submits everything recorded so far and blocks the PFIFO thread until the GPU is done, a 13.8-ms wait. Renderer cost then lands at 35-37 ms, just over two VBLANKs, so frames take three. Top Spin takes the same finish ~30 times a frame with pgraph.lock held, and its vCPU waits 13-18 ms behind it on PGRAPH 0xb10.

**How common** (sdsurvey.py over every perflog soak of the last 10 days, 31 titles). Titles with no sync surface download spend <= 2.5 ms per frame in finish (Crimson 1.1, DOA 0.8, AUF 0.5, GTA SA 2.5). The ten with one or more per flip spend 8-26 ms: ToeJam 25.9, BloodRayne 14.7, CS 13.8, Blinx 2 13.7, NBA 2005 13.6, Top Spin 13.5, Burnout 12.9, Forza 11.2, MM3 10.1, Nightfire 9.9. Whole-logcat medians: they rank titles, they judge none.

**Fixes by P x win (none started here):**
1. Asynchronous surface downloads. Record the copy into the frame's command buffer (staged downloads are already recorded into the aux command buffer; it is their completion, `pgraph_vk_finish(SURFACE_DOWN)`, that waits). Wait for it only at the guest's next sync point (notifier, semaphore release, flip, PGRAPH idle poll), which is when a real NV2A's render target becomes coherent for the CPU. P 0.4. Win: NBA's renderer 35.4 -> ~25 ms and CS 37 -> ~25, both under 33.3, so 30 fps. It also removes 8-14 ms per frame from the near-30 set above. New component: vk/surface.c download paths and draw.c `pgraph_vk_finish`.
2. #474 extension: release pgraph.lock across the SURFACE_DOWN finish's wait, as `wait_frame_fence` already does for the predownload and coalesced waits (surface.c 1218-1231). P 0.6. Top Spin only: ~13 ms per frame of vCPU back, likely taking it from 0.89 to over 0.90.
3. #426 (capture/translation split): 5.5 ms of NBA's render thread off the critical path. P 0.3 alone; it compounds with 1.

(Filed as #794 at 2026-10-03 ~22:00 PDT from this OUTBOX.) NEW ISSUE: Synchronous surface-download finishes (VK_FINISH_REASON_SURFACE_DOWN, 1-30 per frame) serialize the render thread with the GPU: 13.8 ms/frame on NBA Live 2005 and Counter-Strike, 8-26 ms on 10 of 31 perflog titles (docs/lanes/fps20786/NOTES.md "Step 3").
NEW ISSUE: Top Spin's ~30 download-if-dirty surface finishes per frame hold pgraph.lock; the vCPU waits 13.6 ms/frame on PGRAPH 0xb10 (extend #474's fence lock release to pgraph_vk_finish SURFACE_DOWN).
NEW ISSUE: A lane's pathfind hold runs on device defaults, while dispatcher soaks run the "max" regimen. NBA Live 2005 read 19.97 vs 24.2 fps, so a title's verdict depends on which tool measured it.

Device runs: 5 of 5, all on the Nova, perflog build of 70ebd4435d (binary 622a9be57356), HAKUX_GPL=3, release tier. Counter-Strike needed two: 2876984 stood on a "Press A to continue" card, a route defect that was fixed; the retry 3338415 stood in the weapon wheel, which the loop has no B for. Both read the same.
