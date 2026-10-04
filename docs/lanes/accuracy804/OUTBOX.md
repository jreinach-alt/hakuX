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
