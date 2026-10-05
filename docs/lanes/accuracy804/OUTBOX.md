# accuracy804 OUTBOX (#804)

- 2026-10-04 PDT: candidate cause found in code, test queued. After a deferred finish (flip, stall),
  `pgraph_vk_process_pending_reports_internal` (vk/reports.c) reads the occlusion queries before the GPU has run
  them. Turnip then returns the previous command buffer's count for each slot, so a game that draws a car only
  if last frame's visibility test passed gets the test from two frames back, which locks an on/off pattern on
  alternate frames. Fix: `docs/lanes/accuracy804/reports-804.diff` (wait the submitted frames' fences when
  queries are in flight), grant for `hw/xbox/nv2a/pgraph/vk/reports.c` requested in
  `board-requests/accuracy804.md`. Whether RalliSport runs visibility tests is the open question. Nova capture
  `1791136124-lane.accuracy804-3752333` (frame dump + perflog `qry`) answers it; queued behind pathfind's hold.
- 2026-10-04 PDT: first capture read. RalliSport runs visibility tests every race frame (5 box draws per tested
  frame; `qry` 400-594 per 60 flips in the race, 0 in menus). It could not show the car body, because no rival was
  in view: the route went through Career, and the positive bursts all came from pathfind's Single Race. Second
  capture `1791147878-lane.accuracy804-1639330` replays the Single Race path (`rallisport-804b.route`), queued.
- 2026-10-04 PDT: third capture read. The guest issues the near rival's body every frame of the pass, and we record
  it every frame (`9d4f17a01cee3e05`, 2673 indices, race clock ~8-10). So the game is not skipping the body on
  alternate frames: the stale-occlusion explanation (H1) is refuted for #804, and the body is lost after it is
  recorded. The dump cannot see where (vertex data, constants, depth, dynamic state). NOTES section 11.
- 2026-10-04 PDT, **for the PM / harness: a void class that hits every old-ref request.** Since libfolders folded
  (`10f14d301d`), `GamesFolders` removes the `gamesFolderUri` pref when it migrates to `gamesFolderUris`. Any build
  older than that fold, started on a device after a newer build, finds no games folder and never reaches
  `SDL_main` (3 logcat lines, "guest never appeared"). My `5e4196fefd` runs `1791150751` and `1791151399` voided this
  way on the Nova, each right after a hitchcause build. A/B base arms on old refs will void the same way. Fix
  (android/, not my territory): keep writing the legacy key alongside the list. NOTES section 12.
- 2026-10-04 PDT, **#804 result: the frame dump cannot identify the cause, because no instrumented run blinked.**
  Six Nova captures. From the third on, the route reproduces flicker801's scene (the Nissan's rear filling the left
  half at race clock 7.3-8.6). Capture 6 imaged every frame of that pass (118 frames, race clock 5.49-9.58): the body
  is drawn in all of them, and its draws are issued every frame in every dump. flicker801's 3/3 blinking runs
  differ in build flavour (non-perflog debug app; mine perflog), in having no frame dump, and in being recorded
  with screenrecord. The nv2a code is identical. Next, for the PM: a video of a no-dump, non-perflog master run
  through `docs/lanes/accuracy804/rallisport-804d.route`. It needs a `record` step in route.sh or one
  flicker801-style claim burst; this lane can do neither. If it does not blink, go straight to the RalliSport
  Playable confirmation with the owner's flicker check. NOTES sections 13-16.
- 2026-10-04 16:15 PDT, **#804 identified and fixed (addendum).** The plain master build blinks: held screenrecord
  bursts on the Nova, non-perflog `63f4827758` (p90 29.4, countdown cars vanish with their shadows kept: the
  owner's "no cars during a countdown") and perflog `10f14d301d` (p90 22.1, the Nissan at race clock 7.9). The
  knob that hid it in my captures was the `images` frame dump's per-frame fence wait, not perflog. Cause: occlusion
  query results read after a deferred finish without waiting, so on Turnip a not-yet-reset slot returns the previous
  frame's count and the game's visibility-gated car bodies alternate (NOTES section 3, H1). Fix in
  `vk/reports.c` (granted): wait the submitted frames' fences before reading the results. Master + fix: clear in 2
  of 2 runs over the same close pass (p90 0.83, 1.02; body in every frame by eye). **For the PM:** the fps cost of
  the wait is unmeasured; RalliSport's Playable confirmation with the owner's flicker check measures both, on this
  branch's build or after the fold. Other titles that gate draws on visibility tests (lens flares, LOD) get the
  same fix. NOTES section 17.

- 2026-10-04 ~19:45 PDT [lane.accuracy804] #804 re-open, attempt 2: **the owner's build (064ca7aa43) is byte-for-byte the code
  of three captures that show rival cars**: my patched-run1/2 (Nissan beside the camera, body every frame) and
  lane.local's own 600 s hold (`perf/2026-10-04-ralli804-fps/run/frames/015-gameplay.jpg`: Beetle and Corolla on the
  grid at 00:00.00; `016-probe-a.jpg`: the Nissan at 06.67). The hold's strip has no rival because the player is last
  and stuck, not because cars are missing. So "the fix zeroes every visibility count" is not what the captures show.
  What the captures never ran is the owner's session: dispatched runs swap the HDD to the golden `titles.qcow2`, the
  owner plays on `hdd.img` (own profile/options), and mode, track and driving are unknown. **For the PM / owner:**
  which mode, track and car, and was it the grid/countdown or later? A phone photo of a moment with no cars would
  settle it. Meanwhile two Nova runs are queued (fence wait on/off in one binary, per-frame visibility values in
  logcat, grid + pass shots); they run when the owner hold lifts. NOTES section 19. **Recommend no revert yet**: a
  revert brings the blink back, and no capture shows the fix removing cars.
