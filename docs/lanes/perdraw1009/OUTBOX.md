# perdraw1009 OUTBOX

- **ubosz default flip**: the HAKUX_UBOSZ_LOG gate (shaders.c, this lane)
  turns bf2ubosize433's standing hakuX-stall `ubosz[...]` line OFF by default
  for every perflog build, not just this lane's own A/B runs. If anything
  else reads that line by default, it needs `HAKUX_UBOSZ_LOG=1` added to its
  env from now on. Brief instructed "env-gated, default off, or removed", so
  this is expected, but flagging it since the line's prior consumers (if any
  beyond bf2ubosize433 itself) aren't known to this lane.
- **pfifo_thread's 6.0 ms self time is unsplit** and pfifo.c is not in this
  lane's territory. Have not yet run the simpleperf `report-sample`/
  `--sort symbol,srcline` split the brief asks for (no device run this
  session). Once split, if it points at the FIFO spin (XEMU_OPT_FIFO_SPIN)
  rather than pusher parse or method dispatch, naming the lines here before
  touching anything, per the brief's rule.
- **snprintf in "shader bind 2.4 (snprintf 0.4 of it)"**: not found in
  shaders.c's shader-bind path or in draw.c's begin_draw/begin_pre_draw_inner
  (read this session). May be in create_pipeline/create_clear_pipeline
  (draw.c, not yet read in full) or a debug-marker string -- unresolved,
  not guessed at.
- **vk/draw.c, vk/surface.c, vk/texture.c transfer**: still surfgpu1009's as
  of this session (its PR head 31897cb197 not yet on master -- last fold
  attempt failed on nbalive07.route territory, board grant for that landed
  22:32 PDT). Watching for the transfer; the vertex-RAM sync, texture bind
  and surface_update candidates (NOTES.md section 1) are blocked on it.
