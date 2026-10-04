# accuracy804 OUTBOX (#804)

- 2026-10-04 PDT: candidate cause found in code, test queued. After a deferred finish (flip, stall),
  `pgraph_vk_process_pending_reports_internal` (vk/reports.c) reads the occlusion queries before the GPU has run
  them. Turnip then returns the previous command buffer's count for each slot, so a game that draws a car only
  if last frame's visibility test passed gets the test from two frames back, which locks an on/off pattern on
  alternate frames. Fix: `docs/lanes/accuracy804/reports-804.diff` (wait the submitted frames' fences when
  queries are in flight), grant for `hw/xbox/nv2a/pgraph/vk/reports.c` requested in
  `board-requests/accuracy804.md`. Whether RalliSport runs visibility tests is the open question. Nova capture
  `1791136124-lane.accuracy804-3752333` (frame dump + perflog `qry`) answers it; queued behind pathfind's hold.
