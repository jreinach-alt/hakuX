# perdraw1009 OUTBOX

- **ubosz default flip**: the HAKUX_UBOSZ_LOG gate (shaders.c, this lane) turns
  bf2ubosize433's `ubosz[...]` hakuX-stall line OFF by default in every perflog
  build. A reader of that line needs `HAKUX_UBOSZ_LOG=1` in its env from this fold
  on. Side effect: perflog renderer time drops by ~1.8 ms/frame at NFS's 3-racer
  start (the hook's own cost), which is a measurement change, not a player speedup.
- **pfifo.c (not mine): the perflog clock reads are 87.5% of pfifo_thread's self
  time.** 3,703 of 4,231 self samples are `nv2a_clock_ns` (debug.h:477-478), reached
  from the per-method timing in the puller and from cbl_enter/cbl_leave: pfifo.c
  lines 849, 864, 1680, 1767, 1776, 1783, 1787, 1799, 1836, 2202. That is ~5.3
  ms/frame at 15.6 fps that a release build does not pay. The real pusher and
  puller work is ~0.5 ms/frame and the FIFO spin ~0.1. Ask: whoever owns pfifo.c,
  sample the per-method clock (1 in N methods) or gate it behind an env flag, so
  perflog runs stop inflating the renderer thread. No release-build gain.
- **snprintf (attempt 2's "not found" was wrong)**: it is
  `pgraph_glsl_vsh_uber_values` -> `uber_printed_float` -> snprintf, every draw,
  0.46-0.50 ms/frame. It is cached by HAKUX_UNI_UBERCACHE (this lane, shaders.c,
  default off).
- **Fin, ~10 ms/frame on NFS, for surfgpu1009 (draw.c/surface.c)**: the fixed race
  scene's phase line is `Fin:10.0(Sub:2.5 Fen:1.4)` with `Sd1`, one surface download
  per frame forcing a finish. 6.1 ms of it is outside Sub and Fen, i.e. blocked in
  the download wait (draw.c 5017-5183, qemu_event_wait). A cpu-clock profile cannot
  see it. It is free at the 30 fps cap but on the frame's path in the heavy
  3-racer start. The largest single renderer phase on this title.
- **Per-draw candidates in files this lane does not hold** (10-09 profile, 13 fps,
  ~1,630 draws): create_texture/bind_textures 2.1/2.3 ms/frame (texture.c:
  check_texture_dirty 0.76, fast_hash 0.61); sync_vertex_ram_buffer ->
  tlb_reset_dirty 1.6/1.5 every draw (draw.c); download_surfaces_in_range_if_dirty
  0.71 (draw.c); reports.c:374 memcpy 1.17. This lane does not need these files for
  its PR. They are listed for whoever takes them after surfgpu1009 folds.
- **No simpleperf hook in the dispatcher**: request.sh and the soak take no
  profiling option. The flag-on re-profile (job step 5) is a separate pass with
  host-tools/profile_ab.sh after the A/B is judged, not a hand recording on a timed
  arm.
