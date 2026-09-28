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

**Why attempt 1 did not finish:** it ended correctly on a device wait (the pilot sat behind 13
Nova soaks), but it posted no `[lane.pipeline413] waiting:` comment, so its PR stayed a draft.
handback.sh resumed it at 07:12Z, after the pilot was DONE.

## 4. Pilot result (`1-1790571190-pipeline413-3895602`)

`shader_cache=cleared: apk 6818e127bd17 -> 8196a7015b52` (cold), Nova, 180 s. The full reader output
is in `pilot-shdwin.txt`. A perf-line sample:

    00:07:55.277 f=3360 dt=13870 ms  p 30071/40 +15809/+26  s 3047/35 +2878/+23  v 0/54 +0/+24

It has 89 lines, 0 unparsed, and the totals are monotonic. The route reached `mark booted` but not
`mark play` in 180 s. The non-stall miss rate after 60 s is 0.00/s.

| window closes | dt_ms | dpm | dsm | dvm | (dt-3100)/dpm |
|---|---|---|---|---|---|
| 07:55.277 (first load) | 13870 | 26 | 23 | 24 | 414 ms |
| 08:15.219 | 5660 | 8 | 8 | 8 | 320 ms |
| 08:25.197 | 7014 | 11 | 8 | 3 | 356 ms |
| 08:41.761 | 6187 | 14 | 13 | 9 | 220 ms |
| 09:09.881 | 5710 | 2 | 2 | 0 | (1305: not compile) |
| 08:51-09:37, 10 windows | 3848-5710 each | 0-3 | | | 60 flips per 4.5 s, **0 misses** |

The 3100 ms warm subtraction is doa413c's figure for the first load only. For the later windows,
the raw dt_ms/dpm (442-708 ms) is the upper bound.

Scored against the registered legs:

- **M0 PASS.** The run is cold, has 89 lines, and has a 13.87 s window at about 77 s after launch.
- **P1 FAIL, as written.** The rate clause holds: the load's 1.9 misses/s is against a base of 0.
  The count clause fails: dpm is 26, not >= 30. The stall does line up with a miss burst. Every
  window of 5 s or more but one carries 8-26 misses, and every 1-2 s window carries 0-1. So the
  compile explanation for this load stands, but the registered threshold was too high by 4.
- **P2 FAIL (above 300).** The price is 414 ms per missed pipeline. The leg said to read dsm to
  split "few expensive pipelines" from "cost outside pipelines". dsm = 23 of dpm = 26, and dvm = 24
  (glslang). So almost every missed pipeline brings a new shader, and the per-pipeline cost is
  that new shader's compile.
- **P3 FAIL (below 30).** The first load has 26 misses, and 77 misses come after boot in 180 s.
- **P4 INCONCLUSIVE.** The route did not reach `mark play`.
- The post-load windows at 4.5 s per 60 flips (about 13 fps) carry **zero** misses. That slowness is
  not compile, and a ring-out "hang" that looks like it is not this mechanism either. The 440 s soak
  is what tests that (P4).

## 5. Price of doa413c's options 2-4, from the pilot (bounds per first load)

The compile share is 13870 - 3100 = 10.8 s over 26 misses, or 414 ms each. The 3.1 s warm floor is
not compile, and no option below touches it.

| option | bound per first load | needs |
|---|---|---|
| 2. skip a pending pipeline in async mode (draw nothing and do not block) | saves <= 10.8 s. The load drops toward 3.1 s, at the cost of up to 26 pipelines' draws missing for the frames until each compile lands | `vk/draw.c` (the miss path must return "pending" and not call `vkCreateGraphicsPipelines` inline), `vk/compile_worker.c` (the queue) |
| 3. more compile workers | only acts together with 2. With N parallel workers the compile share is at least 10.8/N s, so it saves <= 10.8(1-1/N) s: 8.1 s at N=4. The per-pipeline 414 ms does not shrink | `vk/compile_worker.c` (the worker count), plus option 2's `vk/draw.c` |
| 4. fewer or cheaper pipelines | fewer: dsm/dpm = 23/26, so only about 3 of 26 reuse shader modules. Deduplicating keys saves <= 3 x 414 ms = 1.2 s. Cheaper: the cost is per new shader, so it scales at most linearly with shader compile time (10.8 s x the fraction cut) | `vk/draw.c` (the pipeline key), `vk/shaders.c` / the GLSL generators (shader size and variant count) |

The pilot does not measure wall ms inside `vkCreateGraphicsPipelines`. §1 names the one-line
draw.c accumulator that would. None of these files is this lane's to take. They are asked for by
name on #413.

## 6. Ring-out soak

- 2026-09-28: pilot verdict written to `$DISPATCH_DIR/pilots/pipeline413.ok`. Queued
  `1-1790579572-pipeline413-1715785` (ref ecf5e05dd2, Nova, survey, 440 s, same prediction). Record
  its `shader_cache`. If the Nova ran no other apk since the pilot, the first load is WARM and is
  not comparable to the pilot's. The ring-out pipelines were never compiled in the pilot, so they
  are cold either way. On resume, run `shdwin.py` on it and score P4 against windows after
  `mark play`.
