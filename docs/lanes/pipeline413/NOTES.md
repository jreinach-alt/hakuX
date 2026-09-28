# lane.pipeline413 -- #413: price the scene-load pipeline-compile stall

Base master 59fe489a77. Disc `54430006-Dead_or_Alive_1_Ultimate.xiso.iso`, Nova, survey route.
Source: lane.doa413c (PR #536, `docs/lanes/doa413c/NOTES.md`): the menu -> first fight load
stalls 12.8-13.0 s cold and 3.1 s warm, the PFIFO thread inside Turnip's compiler.

## 1. Instrument (ecf5e05dd2, `hw/xbox/nv2a/pgraph/profile.c` only)

A `[shd413]` line on tag `hakuX-perf`, emitted beside `hakuX-pace` every 60 flips (Android only,
always on, no NV2A_PERF_LOG):

    [shd413] f=<flips> dt_ms=<wall ms since last line> ph= pm= dph= dpm= sh= sm= dsh= dsm= vh= vm= dvh= dvm= L=Y|N W=<saves>

p = graphics pipelines (`vk/draw.c`: a miss is counted only when `vkCreateGraphicsPipelines`
runs inline; both `OPT_ASYNC_COMPILE` early returns come before `pipeline_cache_misses++`, so an
async-compile run shows `dpm` near 0 in a stall window and must not be read as P1's "time goes
elsewhere" world; both runs here were synchronous, the default), s = shader modules (`vk/shaders.c`), v = SPIR-V cache (`vk/glsl.c`); h/m = running
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

**Why attempt 2 did not finish:** it ended correctly on the ring-out soak, which was a device
request outside the session, but again without a `waiting:` comment. The soak finished, and
handback resumed the lane (attempt 3, 2026-09-28).

## 7. Ring-out soak result (`1-1790579572-pipeline413-1715785`)

`shader_cache=cleared: apk 609a183e76fa -> 8196a7015b52` (cold: another apk ran on the Nova
between the two soaks), Nova, 440 s. The full reader output is in `ringout-shdwin.txt`. It has 163
lines, 0 unparsed, and the totals are monotonic. `mark booted` is at 58 s and `mark play` at 231 s.

**A correction to §4, from this run's frames.** The 13.8 s window the pilot called the "first load"
is not the menu -> fight load. It closes about 80 s after launch in both runs, between the DOA2U
title card (frame `093213`, black background) and the title screen with its 3D stage (frame
`093224`). It is the **title screen's background stage** loading. It still meets the registered
definition (a >= 8 s window within 200 s of launch), so the §4 scores stand, but its label was
wrong. The menu -> first fight load comes after `mark play` in this route: a black screen at
59 fps (frame `093722`), then `GET READY` in stage 1 (frame `093747`).

| window closes | what (frames) | dt_ms | dpm | dsm | dvm |
|---|---|---|---|---|---|
| 09:32:25.885 | title-screen stage load (the pilot's "first load") | 13751 | 24 | 21 | 23 |
| 09:32:46-09:33:15 | menus, 4 windows | 5322-7071 | 5-14 | 5-13 | 3-9 |
| 09:37:00.210 | DOA2U title -> mode select | 6025 | 10 | 9 | 6 |
| 09:37:30.587 | **menu -> first fight**, black screen | 9322 | 11 | 11 | 9 |
| 09:37:33.091 | (same load) | 2504 | 0 | 0 | 0 |
| 09:37:40.319 | (same load) | 7228 | 5 | 5 | 3 |
| 09:37:42.954 | (same load) | 2635 | 0 | 0 | 0 |
| 09:37:49.046 | `GET READY` | 6091 | 3 | 3 | 1 |
| 09:37:54-09:38:10, 4 windows | the fight, 11 fps | 5257-5492 | 0 | 0 | 0 |
| 09:38:25.663 | **mid-fight hitch** (Ryu knocked down, `2 HIT COMBO`, clock 95) | 15238 | 8 | 8 | 4 |

Prices, subtracting the neighbouring low-miss windows as the non-compile floor. Each is the
excess over the floor divided by the misses, so it is an **upper bound** on compile cost per
pipeline, not a measurement of it: the non-stall miss rate is 0 in both runs, so co-occurrence
cannot separate compile time from other load work in the same window. The `dpc_ms` falsifier
(§9) is what measures it. (The title-stage 2105 ms floor window carries `dpm=2`; the post-stall
windows, 1.7-2.5 s, give nearly the same floor.)

- Title-stage load: (13751 - 2105) / 24 = **<= 485 ms per pipeline** (upper bound: excess / miss) (the pilot's was 414 ms with doa413c's
  3.1 s floor).
- Menu -> first fight: the three miss windows hold 19 misses in 22.6 s. Against the 2.5-2.6 s
  zero-miss windows between them, the excess is 14.8 s, or **<= 780 ms per pipeline** (upper bound). The whole load
  from black to `GET READY` is 27.8 s. That is longer than doa413c's 12.8-13.0 s, and this
  instrument cannot say whether doa413c timed the same span.
- Mid-fight hitch: (15238 - 5300) / 8 = **<= 1.24 s per pipeline** (upper bound). The fight's four windows before it
  run 5.3 s per 60 flips with 0 misses.

**P4 scored as written:** two windows of 8 s or more follow `mark play`. 09:37:30 carries dpm 11
(>= 10, PASS), and 09:38:25 carries dpm 8 (< 10, FAIL by 2). **For the ring-out it is
INCONCLUSIVE.** The frames show no ring-out: the last frame is round 1 at 95 s on the clock. The
leg's premise, a >= 8 s window standing in for the ring-out, did not hold. The 76 s post-ring-out
hang was not reproduced in 440 s. What the run does show, on the P1 falsifier's side:

- **Every stall window of 5 s or more carries misses, except in the steady fight.** 14 stall
  windows are >= 5 s. Ten carry 3-24 misses. The four without misses are the fight's steady
  11 fps, where each 60-flip window takes 5.3 s whether or not anything compiles.
- **The one in-play hitch is a miss burst.** It is 15.2 s against a 5.3 s floor, with 8 new
  pipelines and 8 new shader modules, after 20 s of zero misses. A hitch inside a fight is the
  same mechanism as the loads. It is the nearest this run comes to the ring-out case.
- **The fight's 11 fps is not compile.** It has zero misses per window. That slowness is a
  separate cost, outside #413's stall. Do not price it with these numbers.

## 8. Price of options 2-4, both runs (bounds)

The per-pipeline cost is 414-485 ms at the title-stage load, 780 ms at the fight load, and 1.24 s
mid-fight. dsm/dpm is 0.73-1.0 in every window, so almost every missed pipeline brings a new shader
module. What a load costs is how many shaders it brings, times the compile per shader.

| option | bound | needs |
|---|---|---|
| 2. skip a pending pipeline in async mode | saves <= the excess: 10.8-11.6 s at the title-stage load, <= 14.8 s at the fight load, and <= 9.9 s per mid-fight hitch. The cost is up to 24 / 19 / 8 pipelines' draws missing until each compile lands | `vk/draw.c` (the miss path returns pending), `vk/compile_worker.c` |
| 3. more compile workers (only with 2) | saves <= excess x (1 - 1/N): at N=4, 8.7 s / 11.1 s / 7.4 s | `vk/compile_worker.c` plus option 2's `vk/draw.c` |
| 4. fewer or cheaper pipelines | fewer: dedup saves <= (dpm - dsm) x cost. That is 3 x 485 ms = 1.5 s at the title-stage load, 0 at the fight load (19 of 19 new modules), and 0 mid-fight. Cheaper shaders scale the excess linearly | `vk/draw.c` (pipeline key), `vk/shaders.c` and the GLSL generators |

**Decided by hostops (2026-09-28): draw.c and compile_worker.c are not granted to this PR.** draw.c
is lane.forza414's, then lane.pacing's (#526). So this PR ships the measurement and the price table
without the compile timer.

## 9. The one-timer patch for the next holder of `vk/draw.c`

This gives `dpc_ms` (wall ms inside pipeline creation) so the price above stops needing a
subtracted floor. In `hw/xbox/nv2a/pgraph/vk/draw.c`, around the synchronous
`vkCreateGraphicsPipelines` call on each miss path. At this merge there are two sites that bump
`pipeline_cache_misses++`, and the second is followed by `NV2A_PHASE_TIMER_BEGIN_EXCL(shader_compile)`.
Time the create call after each of them:

```c
int64_t t0 = nv2a_clock_ns();                 /* before vkCreateGraphicsPipelines */
VkResult result = vkCreateGraphicsPipelines(...);   /* existing call, unchanged */
g_nv2a_stats.shader_stats.pipeline_create_us += (nv2a_clock_ns() - t0) / 1000;
```

It also needs `uint64_t pipeline_create_us;` in the shader_stats struct in `debug.h`, and, in this
lane's `[shd413]` emitter in `profile.c`, a `dpc_ms=` delta beside `dpm=`. It adds two clock reads
per miss and nothing on a hit. The falsifier to carry with it: at the fight load, `dpc_ms` should
be within about 20% of the 14.8 s excess. If it is far below that, the stall's time is somewhere
other than in the create call (for example, a wait on the async worker), and option 2's bound
shrinks to `dpc_ms`.

## Do not repeat

- Do not call the ~80 s window the "first load". It is the title screen's stage. The fight load
  comes after `mark play` on the survey route.
- Do not read the fight's 5.3 s per 60 flips as a stall. It is 11 fps with zero misses.
- The survey route does not reach a ring-out in 440 s. P4 for the ring-out needs a route that wins
  or loses round 1 by ring-out, or a longer soak. 440 s cold ends at round 1, 95 s on the clock.
- Do not quote §7's per-pipeline figures as measured compile cost. They are excess / miss, upper
  bounds until `dpc_ms` (§9) exists.
- Do not read `dpm` from an async-compile run as "no compiles in the stall". An async enqueue is
  not counted (§1).
