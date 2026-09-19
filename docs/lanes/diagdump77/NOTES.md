# lane.diagdump77 -- a marker-file-armed frame dump that does not serialize

Issue: #77. Base: master @ ab471cc80f.

## What this lane is for, in one line

#77 is blocked on a *capability*, not on an analysis: the only per-draw frame
dump this emulator has is reachable from the Debug Capture button and calls
`pgraph_vk_finish` before every draw, so it is blind to exactly the behaviour
a subtle stipple needs visible -- draw merging, deferred submission, barriers.
This lane adds a second instrument with a different trigger and no per-draw
finish, and takes one run with it. It does **not** diagnose the stipple.

## Status

Started 2026-09-19. Filling in below as the work lands.

## What the existing path does (read, not assumed)

- `nv2a_dbg_trigger_diag_frames()` (hw/xbox/nv2a/pgraph/vk/renderer.c:555) is
  called from exactly one place: `nativeDumpDiagFrames`
  (android/app/src/main/cpp/xemu_android.cpp:1457), a JNI entry point on
  `MainActivity`. There is no file, env var or property that reaches it.
- `nv2a_diag_log_draw_call()` (renderer.c:1049) calls
  `pgraph_vk_finish(pg, VK_FINISH_REASON_SURFACE_DOWN)` (renderer.c:1370)
  **per draw**, to make `diag_download_surface` safe. That finish flushes the
  draw queue and the reorder window (draw.c:3188-3217), so under a diag
  capture no draw is ever merged with the one after it and no barrier
  behaviour survives to be observed. This is the blindness #77 names.
