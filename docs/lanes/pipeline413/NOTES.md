# lane.pipeline413 -- #413: price the scene-load pipeline-compile stall

Base master 59fe489a77. Disc `54430006-Dead_or_Alive_1_Ultimate.xiso.iso`, Nova, survey route.
Source: lane.doa413c (PR #536, `docs/lanes/doa413c/NOTES.md`): the menu -> first fight load
stalls 12.8-13.0 s cold and 3.1 s warm, the PFIFO thread inside Turnip's compiler.

## 1. Instrument (ecf5e05dd2, `hw/xbox/nv2a/pgraph/profile.c` only)

A `[shd413]` line on tag `hakuX-perf`, emitted beside `hakuX-pace` every 60 flips (Android only,
always on, no NV2A_PERF_LOG):

    [shd413] f=<flips> dt_ms=<wall ms since last line> ph= pm= dph= dpm= sh= sm= dsh= dsm= vh= vm= dvh= dvm= L=Y|N W=<saves>

p = graphics pipelines (`vk/draw.c`: a miss is a `vkCreateGraphicsPipelines`, or an async
enqueue), s = shader modules (`vk/shaders.c`), v = SPIR-V cache (`vk/glsl.c`); h/m = running
hits/misses, dh/dm the deltas since the last line. Because it is emitted per 60 flips, **a stall
is the gap before a line**, and that line's deltas are the compiles inside the stall.

**Wall ms inside the compile is not in it, and cannot be from profile.c.** The only timer around
`vkCreateGraphicsPipelines` is `NV2A_PHASE_TIMER_BEGIN_EXCL(shader_compile)` (`vk/draw.c`, after
`pipeline_cache_misses++`), and the phase timers compile to nothing without NV2A_PERF_LOG
(`debug.h`). doa413c also found that timer reads `Shd 0.0` across a 14 s stall in a perflog
build. What it needs: one always-on accumulator in `vk/draw.c` around the create call,
`g_nv2a_stats.shader_stats.pipeline_create_us += (nv2a_clock_ns() - t0) / 1000;` (plus the field
in `debug.h`), which profile.c would then print as `dpc_ms`. Not taken: draw.c is lane.forza414's,
then lane.pacing's. Until then the price below is wall ms per window / misses, bounded by the
warm figure.

Why not append to the `gfps=` line: `title_verdict.py` and others regex it; a separate
bracket-tagged line is the convention `[lock474]`/`[notify488]` already use, and it is emitted in
the same block as `gfps=`, so no gap-based hang rule sees a new timing.

Syntax-checked with the NDK's clang against an existing release compile command (0 errors).

## 2. Pre-registration (committed before any device run)

`docs/testing/predictions/pipeline413-doa-coldload.json`. One-arm measurement (a_ref == b_ref ==
ecf5e05dd2, queued by hand; the arms job skips a soak). Reader: `shdwin.py <result dir>`
(`--selftest` passes). Legs, in short:

- **M0** cold cache, >= 20 lines, all parse, totals monotonic, a first-load window >= 8 s.
- **P1, the falsifier:** the first-load stall window carries dpm >= 30 and a miss rate >= 5x the
  non-stall median. Fails if the load's time goes elsewhere; then the compile explanation for
  this load and for the inferred 76 s ring-out hang is wrong.
- **P2** (dt_ms - 3100) / dpm between 20 and 300 ms per pipeline.
- **P3** dpm between 30 and 500.
- **P4** if a >= 8 s window comes after `mark play`, it carries dpm >= 10 (else refuted for the
  ring-out); none, inconclusive.

## 3. Runs

Pilot: one 180 s cold soak (first load is ~85 s in, `mark play` is ~210 s in). Then one 440 s
soak for the ring-out.

- 2026-09-28 04:53Z: pilot queued, `1-1790571190-pipeline413-3895602` (ref ecf5e05dd2, Nova,
  survey, 180 s, `--expect` the prediction above). Thirteen Nova-pinned soaks were ahead of it
  (~1.5-2 h). Session ended **waiting** on that request id. On resume: `shdwin.py
  $DISPATCH_DIR/results/<id>`, check the `[shd413]` fields and `shader_cache`, then queue the 440 s
  ring-out soak on the same ref and prediction.
