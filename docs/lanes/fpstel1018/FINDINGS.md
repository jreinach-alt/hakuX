# fpstel1018: Forza and Buffy missed the bar -- frame decomposition and levers

Issue #433. Both runs: Nova, perflog APK, `PERF_REGIMEN=default`, screenshot
every 30 s (the brief's noted frame-rate cost -- read every number below
comparatively, window vs window, not as either title's device-default
ceiling). Method and the mark-time fix for Forza: `NOTES.md`. Full per-row
data: `forza-decompose.tsv`, `buffy-decompose.tsv`.

## Forza Motorsport (4D53006E), `forza-soak1010`

### The scored window is two different things

`frames/f00014-f00016.png` (04:56:06-04:57:09) show live racing, Lap 2/2,
Place 8/8. `frames/f00017.png` (04:57:41, just past the drive script's 480 s
budget) already shows the **RESULTS** screen, and it is still on screen in
every frame through the capture's end (05:05:03). The race finishes and the
results screen appears between decompose-time (t = wall - mark 04:51:28.204)
341-373 s; the table below splits at t=355. The results screen is a largely
static table over a slowly-rotating parked car, not active play.

| window | scene | span | fps p50 | fps p10 | F ms | gbusy ms | Ri ms | v_run ms | BE draws/f |
|---|---|---|---|---|---|---|---|---|---|
| race | lap 1-2, driving (often scrubbing a guardrail at 30-50 mph, last place) | t=0-355s (355s) | 24.1 | 18.8 | 43.1 | 28.7 | 0.5 | 40.4 | 1025 |
| post-race | static RESULTS table + idle parked-car render | t=355-838s (483s) | 23.6 | 20.3 | 43.0 | 35.7 | 0.2 | 39.6 | 970 |
| worst decile, whole run | mixed, both windows | 192s of 838s | 19.4 | -- | 51.5 | 34.9 | 0.0 | 48.0 | 1349 |

**fps is the same, within noise, whether the title is racing or sitting on a
static results screen.** Renderer idle (Ri) is ~0 ms in both windows: the
render thread essentially never waits for the guest's next command. The
vCPU/guest thread (`v_run`) occupies 92-94% of the frame budget (F) in both
windows. `THERMAL` in `run.log` shows the GPU clock pinned at its floor the
*entire* run (401 of 680 MHz, never once stepping up) -- Buffy, same device
model, same night, ranges 401-680 (reaches max). A GPU that's not asked to
ramp is consistent with a renderer that isn't the bottleneck.

This matches forza414's own unresolved conclusion (NOTES §42: "Forza's lever
is still the decay... guest-CPU-driven, not a drawing/GPU-load increase")
and narrows it: this run shows no decay (no regime step; fps is flat ~22-27
throughout both race and post-race, see the 30 s bins in `NOTES.md`), and
the guest-CPU cost is not proportional to *scene* complexity either -- a
near-static menu costs the same ~40 ms/frame of vCPU time as a fully
rendered, actively-driven race scene. That rules out per-object/per-draw
guest work (AI, physics, scene traversal) as the fixed cost; it has to be
something closer to constant-per-frame.

**Checked and ruled out directly** (not just "not previously tried"):
TB-invalidate / slow-store load (`pages(22265): slow stores N`, the
mechanism forza414's *original*, pre-perflog decay pinned at a 4-4.6x jump)
is flat across this entire run, race and post-race alike (roughly 3100-4600
per ~4.5s interval throughout, no step, no correlation with the race ending)
-- this run's guest-CPU cost does not have that signature, so a fix lane
should not re-chase self-modifying-code/page-invalidation as this run's
mechanism. The gta3fps surface-as-texture copy/bind path
(`pgraph_vk_bind_textures`, `copy_surface_to_texture`) is confirmed idle by
Forza's own `hakuX-stall` `txw[...]` lines (`bt` 0.03-0.4 ms, `cp` 0.00/0.00
throughout) -- not exercised, not a lever. #488's NOTIFY handler touches
neither `vk/draw.c` nor `vk/surface.c` (forza414 NOTES §23). None of
forza414's three shipped surface/clear/upload fixes could move this run's
fps even in principle: they all cut GPU-side/render-thread cost, and Ri~0
with GPU clock pinned at floor says the render thread and the GPU are not
where this run's time goes.

### Ranked levers

| rank | lever | code location | fps estimate | status |
|---|---|---|---|---|
| 1 | guest/vCPU-thread per-frame cost (currently ~92% of F, flat across scene complexity) | guest CPU emulation (dynarec/TLB layer tagged `tlb68`/`pages` in telemetry); subsystem within it not identified by this lane -- TB-invalidate/slow-store directly ruled out above, so it is not where forza414's original decay mechanism was | if ~10 ms of the steady ~40 ms/frame vCPU cost is a fixable, scene-independent cost, F drops from ~43ms to ~33ms: 23fps -> ~30fps on the steady-state rows | open; next step below |
| 2 | GPU DVFS/clock floor (401/680 MHz pinned whole run) | device governor, not renderer code | diagnostic/corroborating for #1, not independently actionable from this lane's evidence; a forced-max-clock run is the cheap falsifier | open, likely downstream of #1 |
| 3 (not a code lever) | route/harness: `forza-soak1010`'s drive script ends its budget mid-race and nothing dismisses the resulting RESULTS screen, so 465.5 of 838.1 scored seconds (`verdict.json` `timeline.by_state.end`) are a static post-race menu, not racing | route/scoring, `docs/lanes/*` route tooling | N/A -- doesn't change in-race fps, but changes what "17.5% of gameplay at >=30fps" is measuring | flag to lane.local/board separately; out of scope here |

**Top lever and the falsifiable prediction**: the guest/vCPU thread's
per-frame cost (#1). Next measurement, not concluded by this lane: a
host-side CPU profile (perf/simpleperf) of the vCPU thread during a repeat
of `forza-soak1010`, since offline log analysis can attribute time to the
thread (`v_run`/`gbusy`) but not to a subsystem inside it, and the one
subsystem this lane could check from the logs (TB-invalidate/slow-store) is
ruled out. **Prediction**: if the profile attributes >=50% of the vCPU
thread's ~40 ms/frame busy time to one identifiable subsystem, fixing it
should raise `forza-soak1010`'s steady-state median fps (currently ~24 in
the race window, ~23.6 on the results screen) toward 30; if the time is
spread thinly with no single contributor over ~20%, this is not a
single-site fix and needs a different approach. The run that shows it: a
repeat of `forza-soak1010` with a CPU profiler attached to the vCPU thread,
or equivalently the parked-car results screen alone (no AI/physics/input)
since it already reproduces the same ~40 ms/frame cost with far simpler
guest-side logic running.

## Buffy the Vampire Slayer (45410012), `buffy.returning`

### Decomposition

`route-frames/` (no `route-state.tsv`; this is the scripted press-route, not
the screen-aware driver) shows the mark lands on `050815-gameplay.png`
(canyon mission start) and `050826/050838/050850/050901-play.png` are
continuous live play (running through a canyon). The worst single hitch
(`verdict.json`: 104.9 ms, classified `shader`, at off_s=40.4) falls between
the `050850` and `050901` play frames -- mid-play, not a loading transition.

| window | span | fps p50 | fps p10 | F ms | Ri ms | rthr % | ph_Tot ms | gap = F-ph_Tot | BE draws/f |
|---|---|---|---|---|---|---|---|---|---|
| opening (mission start) | t=0-100s | 27.5 | 25.1 | 36.7 | 11.8 | 42.3 | 21.3 | 15.4 | 1536 |
| steady state | t>=120s | 29.7 | 27.5 | 34.3 | 19.1 | 34.0 | 26.2 | 8.1 | 1171 |
| worst decile, whole run | 33 rows (66s) | 25.6 | -- | 39.1 | 10.0 | 42.6 | 20.0 | 19.1 | 1712 |

The opening ~90-100 s (right after the canyon mission loads) is distinctly
worse than the rest of the run: lower fps, ~1.3x the draws/frame, and nearly
double the per-frame gap -- a scene/streaming-settle cost, not this run's
main shortfall (steady state is already close to the 30fps bar; 73.9% of
gameplay still passes it). The persistent, title-wide signature is the `gap`
column: `F` (the frame interval, from `hakuX-pace`) minus `ph_Tot`
(`profile.c`'s own `Tot:`, the self-reported sum of every phase it times --
Surf, Tex, Shd, Draw and its children, Fin, **Flip**, and fifo-Idle;
confirmed by reading raw `hakuX-phase` lines that `Tot` already equals that
sum, e.g. `0+0+0+0.2+0.3+0+54.7=55.2=Tot`). The gap is 7-9 ms steady state
and grows to ~19 ms in the slowest decile. Two causes are directly ruled
out: `lockw` (#474/`[lock474]`, pgraph.lock wait) measures ~0.01-0.02 ms in
every group, and `Flip` (vsync/present wait, confirmed by reading the raw
lines) is 0.0 in every sampled line -- so the gap is neither lock contention
nor a flip/vsync stall. `ph_Fin` (the Vulkan finish/fence-wait phase) also
stays flat near 0, extending belowbar1005's #804 fence-wait refutation to
this run. The gap is time inside each frame that none of the render
thread's own phase timers (which jointly define `Tot` by construction)
account for -- it is either the render thread scheduled off-CPU for a
reason the instrument doesn't tag, or `F` (from `hakuX-pace`, the display
thread's frame counter) and `Tot` (from `profile.c`'s own per-60-frame
average) are each a legitimate measurement of a slightly different window,
and the two have never been tied to the same single frame before now. This
lane cannot tell which from logs alone.

### Ranked levers

| rank | lever | code location | fps estimate | status |
|---|---|---|---|---|
| 1 | the `F`-vs-`Tot` gap (7-9 ms steady, ~19 ms slowest decile), outside all measured phases | `hw/xbox/nv2a/pgraph/profile.c:947` (`nv2a_profile_get_phase_timing_str`, called every 60 frames) and whatever the render thread does between its own phase markers | closing the steady-state 7-9 ms gap moves F from ~34ms to ~26-27ms: 29.7fps median -> ~37-38fps, comfortably over the 30fps bar; closing the worst-decile 19ms gap would do more for the tail that currently drags `fps_ok_share` to 73.9% | open; next step below |
| 2 | opening-90s streaming/scene-settle cost (1536 vs 1171 draws/frame, elevated gap) | unclear from logs alone -- correlates with mission-start load, not this run's main shortfall | smaller, localized to the first ~100s of a ~972s gameplay_s run | lower priority than #1 |
| (ruled out) | #474/`[lock474]` pgraph.lock wait | `lockw` ~0.01-0.02ms in every group | -- | not Buffy's cause, confirmed directly |
| (ruled out) | #804 fence wait | `ph_Fin` ~0 throughout | -- | not Buffy's cause (extends belowbar1005) |
| (ruled out) | gta3fps surface-as-texture copy/bind | `txw[...] cp0.00/0.00` throughout | -- | not exercised by this title |

**Top lever and the falsifiable prediction**: the `F`-vs-`Tot` gap (#1).
Next measurement: add a wall-clock timestamp pair around the *entire*
per-frame render-thread body in `profile.c`, printed on the same
`hakuX-phase` line as `Tot`, so the comparison is same-measurement rather
than reconciled after the fact from `hakuX-pace` (a different thread's
counter) and `hakuX-phase`. **Prediction**: on a repeat of
`buffy.returning`, if that new field shows a gap of >=5 ms/frame in the
steady-state window (t>=120s) that still isn't inside Surf/Tex/Shd/Draw/
Fin/Flip/Idle, the render thread has a real, unattributed wait and the next
step is to bisect where in its frame loop it happens; if the new field
instead shows the gap collapses to <2 ms once measured same-window, the
7-9ms this lane found is a measurement-window artifact between two
different counters, not a real cost, and this lever is closed without a
code change.

## Do Forza and Buffy share a dominant cost?

No. Forza: render thread essentially never idle (Ri~0), guest/vCPU thread
occupies ~92% of frame time, GPU clock never leaves its floor -- a
guest-CPU-bound title where none of the available GPU/surface levers can
move fps further. Buffy: render thread does have real idle time (Ri
11-20ms) that shrinks in slow frames while the thread's own phase
accounting fails to cover a growing share of the frame -- a render-thread
cost (not yet attributed to a specific phase) is Buffy's bound, not guest
CPU and not GPU-side draw work. The two titles need different next steps;
neither is served by returning to the vk/surface.c-style work already
shipped for Forza (#414's folded PRs) or by re-raising #474/#804 for either
title.
