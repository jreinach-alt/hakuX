# lane.forza414 -- Forza Motorsport races at 3-16 fps on the Thor (#414)

Base master dc38b745b8. Title 4D53006E (Forza Motorsport), Ayn Thor (bdc158a5).
Source run: `0-0-y-1790433159-titleplay-p1-forza` (ref a5b5b628f2, apk
25abcaccbf45, survey route, no perflog, 2026-09-26 11:42-11:49 PDT).
Reader: `timeline.py <logcat> [--bucket 30] [--rows]`. t = 0 is the route's
`soak start` (11:42:28.474).

## 1. There is no gradual decay. There is one step, at 11:47:28.7

The issue's per-30-s fps (`10 30 28 22 6 12 12 14 14 20 2 4 4 2`) looks like
decay. The gfps/pace lines, which land every 60 flips, show three flat
regimes and one step between the last two:

| wall (PDT) | t (s) | what is on screen (frames) | fps | G ms | renderer idle Ri ms | vCPU ms per 2 s | fifo kicks per 2 s | pusher backlog | audio zero-filled |
|---|---|---|---|---|---|---|---|---|---|
| 11:42:49-11:44:25 | 20-117 | boot, menus | 29-30 | 33.4 | 27-31 | 1870 | 8-250 | small | 0% |
| 11:44:37-11:45:05 | 129-157 | loading screen (turbo icon) | one 16.2 s flip-less stall | -- | -- | -- | -- | -- | -- |
| 11:45:05-11:46:44 | 157-256 | race, start and pit straight, AI cars in view | 12-15 | 62-90 | **0.1** | 1910 | ~3000-3300 | ~480 KB, never drains | 0% |
| 11:46:44-11:47:27 | 256-299 | race, player stopped, field gone | 16-20 | 49-60 | **0.1** | 1780-1830 | ~3800 | ~480 KB, never drains | 0% |
| **11:47:28.7-11:49:27** | **300-419** | **the same frame** (114701 vs 114728 vs 114755) | **2-3** | **276-367** | **192-272** | **1400** | **~660** | **~30 KB, drains every kick** | **40-47%** |

Before the step, the renderer is saturated (Ri 0.1 ms of a 50 ms frame) and the
pusher runs ~0.5 MB behind the guest. `fifoskew` shows `drain(n=0)` and
`lost=kicks` in every window, so DMA_GET never reaches DMA_PUT. The window
that ends at 11:47:28.742 has the first completed drain, `max=23977634427` ns:
the pusher had not caught up for 24 s. From the next window onward, every
kick drains (`drain n == kicks`, mean 7-16 ms). The backlog falls to ~30 KB,
the renderer goes 70% idle and the vCPU thread goes 30% idle. All three change
in the same 2-s window as the audio starve line (0.06% to 47%).

Per displayed frame, from the 2-s counters:

| | before (11:47:09-27) | after (11:47:42-11:49:10) | ratio |
|---|---|---|---|
| flip interval G | 49-51 ms | 276-367 ms | ~6x |
| renderer busy (G - Ri) | ~50 ms | ~85-95 ms | ~1.8x |
| vCPU busy (cpu/2000 x G) | ~45 ms | ~200-230 ms | ~5x |
| fifo kicks per frame | ~95 | ~110 | ~1.1x |
| surface_update calls per frame (surf92 cadence, 2048 per line) | ~1250 | ~1600 | ~1.3x |
| TB invalidate calls (`ic`, pages line, one line per 120 flips) per frame | ~100 | ~400 | **~4x** |
| slow stores per frame (same line) | ~27 | ~125 | **~4.6x** |
| TB invalidate calls per second | ~2050 | ~1360 | 0.7x |

**The growing counter, as the brief asks: none grows over time.** `[watch311]
live` (the #311 leak signature) wanders 36-60 before and after. `inserts`
climbs at ~240/s before and ~40/s after. The TLB size, `rdus` and the watch
lists are flat within each regime. What changes is a regime, and it changes
once, in one 2-s window. Per displayed frame, the guest's CPU time grows ~5x
and its code-invalidation and slow-store work ~4x, while its GPU work (kicks,
surface updates) stays within 1.1-1.3x. So the frame costs more guest CPU,
not more drawing. And the guest no longer runs ahead of the GPU: it waits
on it every kick. The ~4x in `ic` and slow stores per frame is not a
per-second rise (0.7x per second), so it is not a hot trap loop that
switched on.

The scene does not change. The frames at 11:47:01, 11:47:28 and 11:47:55 are
the same view, with the car at 0 mph and 8th place. The race clock shows the
step. It reads 17.967 (11:46:33), 32.133 (11:47:01), 48.800 (11:47:30) and
52.066 (11:47:55). That is 51%, 62%, then **12%** of real time. The step lands
at race time ~48.5 s. **The game clock is fps/30:** 20 fps gives 62-67%, 3
fps gives 10-12%. The 26% in the issue is the average over the mix. It is not
a second defect, and it moves with fps.

## 2. The "hang gaps" are not hangs, and they have no period

The issue's gaps (14.8, 17.3, 17.4, 17.7, 17.1, 19.1 s) are the `ms=` field of
the `hakuX-pace` lines after the step: 14778.6, 17252.9, 17383.2, 17659.2,
17079.1, 19084.9. That field is the wall time of a **60-flip window**. The
same lines' `max=` (the longest single flip interval) is 433-801 ms, and
`v4=60` says every flip took 4+ VBLANKs. So at 3.5 fps a pace line arrives
every ~17 s, and the "period" is 60 flips / fps. No 15-19 s stall exists in
the race. The only flip-less stall in the run is the load (16.2 s,
11:44:49-11:45:05). A reader that scores "no 60 flips in N s" as a hang will
report one at every sub-4 fps window. That is a reader note for titlerun, not
an emulator defect.

## 3. The loading screen

The 6-7 fps in the issue's bucket 4 (t = 120-150) is one flip-less stall of
16.2 s (`max=16242.2` in the window that ends 11:45:05.094). The frames either
side of it run at 23-29 fps (11:44:25-11:44:37). The race's first scene then
runs at 12-15 fps, renderer-bound (Ri 0.1), with texture dirty queries at
their run maximum (Tq 3400-3900). The load is disc and asset time plus
whatever the first race frame compiles (the shader cache was cleared for this
apk: `result.json shader_cache`). It is not the same mechanism as the race
step, and no counter on this spec separates disc from compile.

## 4. What the step is not, and what it needs to be named

The non-perflog spec carries no `hakuX-phase`, `hakuX-stall` or `hakuX-cpu`
lines. Those are `NV2A_PERF_LOG` only (draw.c:984-1026, profile.c:636). So this
run cannot say where the vCPU sleeps or what the renderer's 85-95 ms is. What
it does rule out:

- **Not a leak, not a filling cache:** see the flat counters in section 1.
- **Not a scene change:** same frame.
- **Not a TLB resize:** the one `rs=1` (2048 to 1024 entries) is at 11:47:17.9,
  11 s before the step, with fps unchanged at 20.
- **Not the surface watch leak (#311):** `live` is bounded.

The shape (backlog collapses, every kick drains, renderer and vCPU both part
idle, the audio thread starves at the same moment) is a lock-step. The guest
waits for the GPU at some point in every frame, many times. The shared
starvation of the audio thread points at a lock the three threads share (BQL)
or at a guest-side wait (a CPU readback of GPU-drawn memory, a report or query
read, or a fence poll). The perflog soak (section 5) decides between them.
`pDl` (CPU access to a draw-dirty surface, which blocks the vCPU until a
SURFACE_DOWN finishes) and `Sub`/`Fen` per frame are the counters to read.

## 5. Next measurement (queued 2026-09-26 ~12:57 PDT)

- `1790450265-forza414-1731727`: Thor, perflog, 420 s, ref dc38b745b8, route
  `forza414` (the survey route's text copied verbatim from the source run's
  request.json into `docs/testing/titles/routes/forza414.route`, because
  `survey.route` exists only on PR #399's branch). It carries `hakuX-phase`,
  `hakuX-stall` and `hakuX-cpu` across the step.
- `1790450270-forza414-1731994`: the same on the Nova (brief item 4). The
  dispatcher's saved prefs for the two devices differ only in `dvdUri` and
  `gamesFolderUri`. If the Nova does not hold the title, the result says
  `title not on device` and item 4 stays open.

The perflog build adds a clock read around every method, so the step may land
at a different race time or not at all. The reading keys on the regime
signature (drain n == kicks, Ri > 100 ms), not on the wall time.

To read either run:
`python3 docs/lanes/forza414/timeline.py <logcat>`, then the stall and phase
lines on each side of the step.

The older Forza run on disk (`0-0-y-1790408503-titlebench-8`, Thor, 240 s)
never leaves the front end. It holds 30 fps with the renderer ~85% idle and
has no race to compare.

Attempt 1 ended here, waiting on both requests. That was a correct stop: a
lane session cannot wait ~90 min for a device. Attempt 2 (resumed
2026-09-26 13:50 PDT) reads the results below.

## 6. The perflog soak (Thor, 1790450265, apk 853368f2e827, 13:42-13:49 PDT)

**The step did not recur.** The race ran from 13:44:41 to the end (13:49:42,
~300 s of race, past race time ~48 s on any clock ratio above 16%) in the
pre-step regime the whole way: Ri 0.1 ms, `drain` 0, audio starve 0%, fps
14-20 per 30 s. The last bucket's 2 fps is the partial window at the end of
the run. So the step is not deterministic at race time ~48 s. It is either
timing-dependent (the perflog build reads a clock around every method) or
one-off. One run each way cannot say which. Its cause stays unnamed.

The Nova request (1790450270) returned `ERROR: title not on device`
(`/storage/E6C6-D7AA/Games/XBox/4D53006E-...`). Brief item 4 is still open
until the ISO is staged on the Nova.

What the soak does name is what the race costs before any step. Per displayed
frame, from `hakuX-phase` (ms/frame) and `hakuX-stall` (per 60 flips):

| wall (PDT) | Tot | Draw (Pipe) | Fin (Sub) | GPU R | Finish / 60 flips | of which sd | cDef | cDefC |
|---|---|---|---|---|---|---|---|---|
| 13:43 menus | 29.3 | 0.1 (0.0) | 0.1 (0.0) | 0.1 | 60 | 0 | 0 | 0 |
| 13:45:47 race | 63.0 | 21.3 (10.3) | 36.9 (36.4) | 32.4 | 417 | 357 | 357 | 0 |
| 13:46:39 | 60.9 | 20.5 (10.1) | 35.7 (35.1) | 30.8 | 382 | 322 | 322 | 0 |
| 13:47:39 | 43.6 | 13.1 (5.6) | 26.5 (25.9) | 21.7 | 382 | 322 | 322 | 0 |
| 13:48:19 | 62.8 | 22.2 (10.7) | 35.8 (35.3) | 30.3 | 396 | 336 | 336 | 0 |
| 13:49:20 | 43.2 | 12.0 (5.2) | 27.1 (26.5) | 21.7 | 396 | 336 | 336 | 0 |

- **Sub is 48-60% of every race frame**: 26-37 ms of 43-63. Each frame has
  ~5.5 `SURFACE_DOWN` finishes, and every one of them is `sd_complete_def`
  (`cDef == sd`, `cDefC` = 0). That is the uncoalesced branch of
  `pgraph_vk_download_surface_complete_deferred` (vk/surface.c:926-957). It
  submits and waits a fresh finish because no prior finish carried the
  staged downloads. That is ~5-6 ms of Sub per finish.
- `pDl`, `dDl`, `ev` are 0. The downloads are not guest CPU reads of a
  draw-dirty surface (the section 4 hypothesis). They come from one of the
  function's 10 call sites (surface.c:436, 1000, 1613, 1715, 1751, 1798, 1835,
  2933, 4097; renderer.c:2192). No counter on this build says which caller.
- The race's first scene had the shader cache cleared (`result.json`). Pipe
  is 5-11 ms/frame for the whole race, not only at the start, so pipeline
  lookup/creation is the second cost.

**Price (a bound, not a value).** If the ~5.5 mid-frame finishes coalesced
into the flip's own finish, a frame would cost at most the larger of the CPU
side without Sub (Tot - Sub = 17-27 ms) and the GPU work (R 22-32 ms). That is
~31-45 fps, capped at 30, against 14-20 today. The bound assumes the waits
can be dropped. Whether the guest needs those bytes before the next draw is
what the per-caller counter has to show.

## 7. Grant request (surface.c is held)

The site is vk/surface.c's deferred-download completion and its callers. PR
#396 (lane.blinx372d, "#372 remove the two synchronous surface downloads in
the Blinx demo") holds vk/surface.c and is open. Its change may already cut
some of these finishes, so the next Forza lane should rerun this soak on
master after #396 folds, before writing a hunk. The request, posted on #414,
is: after #396 folds, grant vk/surface.c (and draw.c for the stats line) for
a per-caller `cDef` split, and then coalesce the dominant caller.

No hunk and no arm on this PR, so `Prediction: none`.

## Do not repeat

- Do not read the 15-19 s "hang gaps" as stalls. They are pace-window spans at
  3.5 fps (section 2).
- Do not look for a counter that grows with time. The run has a single regime
  step at race time ~48.5 s (section 1).
- Do not treat the game-clock ratio as its own defect. It is fps/30.
- Do not expect the 2-3 fps step on a rerun. The perflog soak ran 300 s of
  race without it (section 6). The steady cost is the ~5.5 uncoalesced
  `SURFACE_DOWN` finishes per frame. Fix those first.
- Do not queue the Nova half until the ISO is on the Nova's card.

## Why the previous attempt did not finish (resume of 2026-09-27 07:12 PDT)

It did finish its own PR. #418 folded, and its deliverables (sections 1-7) are on master. The lane
then ended on a `waiting:` for the vk/surface.c grant. That file went from lane.blinx372d (#396)
to lane.doa413b (#440) and then to lane.blinx372e (#467). hostops granted it to this lane at
07:15 PDT, after lane.blinx372e retired. This attempt merged origin/master (398 commits, f131dd11c6)
and opened PR #479 for the step section 7 named.

## 8. The caller, from the Nova soak already on disk

lane.slowdown462's Nova perflog soak `1-1790492278-slowdown462-690198` (e5db66fa37, survey route)
already carries the recorder counters. Last 30 s of its race, per ~53-flip stall window:

| counter | per window | per frame |
|---|---|---|
| `cDef` (completion that submitted a finish) | 336-389 | ~7 |
| `cDefC` (completion that waited an earlier fence) | 0 | 0 |
| `evict[dl:]` (download recorded at an eviction) | 528-613 | ~11 |
| `evict[unshelve:]` | 384-448 | ~8 |
| `evict[stale:]` (unshelved surface must re-upload) | 96-110 | ~2 |
| `dif[ovl]` (texture/vertex/blit range lookup found a dirty surface) | 96-110 | ~2 |
| `pDl`, `dDl` (guest CPU or dirty-surfaces request) | 0 | 0 |

Downloads recorded at evictions complete in `pgraph_vk_surface_update`. That function calls
the completion unconditionally, at 4630 on master, and `expire_old_surfaces`, which runs at the
end of every update, calls it again. Either call submits a finish when the batch is still in the
open command buffer. Only ~2 of the ~8 unshelves per frame re-upload from VRAM (`stale`), so most
of those finishes feed no reader in the update that paid for them. That is the hypothesis. The
probe below tests it.

## 9. The probe: `[sdcall]` (4b22f2526b, perflog + Android only)

Each in-file caller of the completion passes a tag: range, tobuf, deffull, pend, pendfb, dirty,
dirtyfb, expire, surfupd. renderer.c's frame-dump call is `ext`, since renderer.c is lane.flip474's.
Every 60 guest frames the line prints, per caller:

- `fin`: completions that submitted a finish;
- `fence`: completions that waited an earlier fence;
- `pre`: completions that waited the flip pre-download;
- `dl`: downloads retired;
- wall ms of the wait.

`su_upl` counts the surface_update finishes that had a VRAM-reading upload after them, and
`su_deferred` counts the updates the cut let go (0 in A by construction).

Nova pilot: **`1790518618-forza414-1930404`** (4b22f2526b, perflog, survey route, 420 s), queued
07:17 PDT at queue position 14. The prediction is that `surfupd` carries most of the `fin` and
that `su_upl` is well under `surfupd`'s `fin`. If `range` carries it instead, the cut targets
the wrong caller. Then the next step is to coalesce the range lookup's finish (texture scans of
render targets), not this one.

## 10. The cut (94f002d309)

doa413b's refuted cut ("lazy completion", docs/lanes/doa413b) left only an already-submitted
batch for later. In DOA's fight such a batch never existed at a surface_update (`skips` 0 on every
fight line), so it could not reach the wait. This cut is the other branch, the one Forza's
counters show: a batch still in the open command buffer, whose completion submits a finish.

- `pgraph_vk_surface_update` leaves the batch to the next finish (`surface_update_may_defer_downloads`)
  unless one of these holds: a binding is about to upload from VRAM (`upload_pending`), the batch
  was already submitted, a display pre-download is pending, or TCG is off (no watch).
- `expire_old_surfaces` completes only when a surface expires or a shelved one is freed.
- Readers of guest memory complete an overlapping pending batch first
  (`deferred_downloads_overlap_range`):
  - `pgraph_vk_download_surfaces_in_range_if_dirty` (texture, vertex, blit). An evicted
    surface is shelved with `shelved_dirty` cleared, so the old surface scan did not see it.
  - `surface_access_callback`, via the existing `wait_for_downloads` hand-off. The evicted
    binding keeps its watch while `draw_dirty`, so the access traps. The download lands
    before a read, and before a write, which is today's order.
- `pgraph_vk_prerecord_display_download` may now share a batch still in its command buffer. It
  used to refuse any non-empty batch, which would have switched off the flip's pre-download (53
  per window) whenever a deferred batch was pending.

These readers were checked and need no guard:
- Image lifetime: `destroy_surface_image` releases on the frame's fence, and
  `deferred_downloads_clear_surface` handles a freed struct.
- texture.c's two `pgraph_vk_upload_surface_data` calls are unreachable
  (`surface_to_texture && upload_pending` right after that pair is forced false).
- display.c's upload runs its own PRESENTING finish when the display surface was drawn in the
  open command buffer.

Residual, named: a display.c upload with `upload_pending` over an evicted surface's range with no
draw in the open command buffer would read VRAM before the pending copy. It is rare, since the
display surface is active and an eviction of its range makes it the new binding.

**Price (a bound).** lane.slowdown462's Nova profile has the PFIFO thread waiting 18.1 ms per
frame in `pgraph_vk_finish` <- this completion, out of 35.7 ms. The vCPU is on-CPU 30.5 ms. With
the waits gone, the frame is at least the vCPU's time: <= 33 fps, and <= 30 fps at the title's
2-VBLANK pacing, against 23.0 fps in the soak. The registered mover asks for >= 1.15x (about
26.5 fps).

## 11. Predictions and runs

- `docs/testing/predictions/forza414-coalesce-mnm.json` (sha256 9ebf563f2a56...): goldens A/B
  4b22f2526b vs 94f002d309. The must-not-move suites are Depth_buffer_fixed_function,
  Color_zeta_overlap, Surface_format, Surface_clip, Clear, Texture_render_target,
  Texture_CPU_Update, Texture_render_update_in_place (PR #387's guard), Image_blit and
  Texture_Framebuffer_Blit. The arms job queues it from the commit.
- `docs/testing/predictions/forza414-coalesce-soak.json`: the same-session Nova soak A/B, read by
  hand (arms.sh skips title soaks). Queue it with request.sh after the pilot is read, one arm
  per ref: `--title 4D53006E-Forza_Motorsport.xiso.iso --seconds 420 --device nova --perflog
  --route survey --expect docs/testing/predictions/forza414-coalesce-soak.json`.

## Attempt 2 ends waiting (2026-09-27 07:30 PDT)

Pushed at 44519b7ec1 and preflight passes. PR #479 stays a draft, waiting on two things outside
this session:

- The Nova pilot `1790518618-forza414-1930404`, for the `[sdcall]` caller split (section 9).
- The goldens must-not-move arm from `forza414-coalesce-mnm.json`, a `[job.arms]` verdict.

On resume:
1. Read the pilot's `[sdcall]` lines over t = 243-414 s. Name the dominant `fin` caller and
   compare `su_upl` with `surfupd`'s `fin`.
2. If `surfupd` dominates, queue the soak A/B (section 11) as two requests on the Nova, one per
   ref.
3. If `range` dominates, the cut is aimed wrong. Say so, and re-aim the cut before queueing
   anything.
4. Read the arm verdict and every scores1.tsv `status`.

## Why attempt 2 did not finish (resume of 2026-09-27 09:17 PDT)

It ended on a `waiting:` (PR #479, 14:25Z) for two requests outside the session: the Nova pilot and
the goldens must-not-move arm. The pilot finished at 08:56 PDT. The arm pair
(`1-1790519668-arms-forza414-base/fix`) is still queued. The two older requests from attempt 1
(`1790450265`, DONE, and `1790450270`, ERROR) belong to #418, which folded. They are not re-read here.

## 12. The split: `surfupd` pays every finish (pilot `1-1790518618-forza414-1930404`)

Pilot run: Nova, apk 1a8d9178e52c (4b22f2526b), perflog, survey route. The race is the 111 `[sdcall]`
lines from 08:51:30 to 08:56:08 PDT, each summing 60 guest frames: 6660 frames at gfps 23.

| caller | fin | fence | pre | dl | wait ms | fin / frame | wait ms / frame |
|---|---|---|---|---|---|---|---|
| `surfupd` | 46620 | 0 | 6647 | 147232 | 139378 | **7.00** | **20.9** |
| `range` | 13 | 0 | 0 | 36 | 39 | 0.002 | 0.01 |
| all others | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

- `pgraph_vk_surface_update`'s completion is 99.97% of the finishes and of the wait. It waits 20.9 ms
  per frame, which matches lane.slowdown462's 18.1 ms of `pgraph_vk_finish` per frame. `expire` has none.
  `range` has 13, so the section 9 alternative is refuted.
- `su_upl` = 19993, which is 42.9% of `surfupd`'s `fin` and 3.0 per frame. In those updates a
  binding was about to upload from VRAM, so the cut at 94f002d309 still completes there. The cut can
  let go of at most the other 57%: 4.0 finishes and about 12 ms of wait per frame, if the waits are
  uniform. The deferred batches then ride the next finish that does happen.
- **The queued fix arm coalesces this caller.** 94f002d309's change is in
  `surface_update_may_defer_downloads`, the `SDC_SURF_UPDATE` site. The arms stay queued.

**Price, revised (a bound).** Finishes per frame fall from 7.0 to about 3.0, and the wait falls by up to
~12 ms of the ~43 ms frame: about 23 -> 30 fps at best, if the 3 remaining finishes wait no longer
carrying larger batches. The soak prediction's >= 1.15x mover (~26.5 fps) sits inside that bound.

**Next cut, not in this PR.** `su_upl` counts any `upload_pending` binding, whether or not its range
overlaps a pending download. Restricting the check to `deferred_downloads_overlap_range(binding)`
would free those of the 3.0 per frame that read VRAM the pending copies do not write. How many that is
needs one more counter (overlap vs not), so it waits for this arm's verdict.

## 13. Runs queued this session (priority 1, Nova)

- Soak A/B, `forza414-coalesce-soak.json`, read by hand: base `1-1790525921-forza414-1054756`
  (4b22f2526b), fix `1-1790525923-forza414-1055334` (94f002d309). Both are 420 s, perflog, survey route.
- The goldens must-not-move arm pair is still `1-1790519668-arms-forza414-base/fix`, judged by the arms job.

On resume: read both soaks' gfps and `[sdcall]` over the race (the fix arm's `su_deferred` should be
about 4.0 per frame and `surfupd` `fin` about 3.0), then the `[job.arms]` verdict and every
scores1.tsv `status`. Then merge master, and mark #479 ready when both hold.

## Why attempt 3 did not finish (resume of 2026-09-27, attempt 4)

It ended on a `waiting:` (PR #479, 16:19Z) for four device requests outside the session: the Nova
soak A/B and the goldens must-not-move arm pair. All four have finished. The host promoted the soak
pair, so its result directories are `0-0-x-1790525921-forza414-1054756` and
`0-0-x-1790525923-forza414-1055334`. Nothing was stuck; the session could not wait ~90 min.

## 14. Verdicts on 4b22f2526b vs 94f002d309

### Goldens must-not-move (`forza414-coalesce-mnm.json`): PASS

`[job.arms]` on PR #479, 10:16 PDT: all 266 captures in the 10 guarded suites are byte-identical
between the arms (`1-1790519668-arms-forza414-base-2225156`, `...-fix-2225522`). Image_blit scored
41 of 42 goldens in both arms, so that suite is a floor. The arm's logcat is not perflog, so it
does not show that the deferral fired on the discs. The soak below does show it on Forza.

### Nova soak A/B (`forza414-coalesce-soak.json`), read by hand: the mover is REFUTED

Reader: `abread.py <A logcat> <B logcat> [--from s --to s] [--bucket 30]`. A is apk 1a8d9178e52c,
10:40-10:46 PDT. B is apk dc9da6bd022b, 10:47-10:54 PDT. Same device, MAX regimen, survey route,
shader cache cleared for both. No crash or validation line in either.

Registered window, t = 243-414 s, medians:

| leg | rule | A | B | B/A | result |
|---|---|---|---|---|---|
| M0 | both reach the race; B `su_deferred` > 0; A prints none | race from t = 120 | 302 per frame | | holds |
| P1 | uncoalesced finishes (`cDef` per 60 flips) <= 0.5 | 429 | 240 | 0.559 | **fails** |
| P2 | `Sub` ms/frame <= 0.6 | 16.10 | 12.05 | 0.748 | **fails** |
| P3 | fps >= 1.15x | 29.34 | 29.49 | 1.005 | **fails** |

**P3 could not have passed in that window.** Arm A is already at the title's 30 fps cap there
(2.02 VBLANKs per flip). The route creeps the car off the pit straight, and from t = 300 s both arms
face a fence and trees (frames 104619 and 105345). The same window read 26.7 fps in the pilot, where
the car faced the grandstand (frame 085512), and 24.1 fps in lane.slowdown462's soak. So the base
alone spans 24.1-29.3 fps in the registered window, across three runs of the same route. The
window was chosen from one run and it is not one place.

The race's first two minutes are one place in all four runs (start line and pit straight, AI field
in view). Window t = 125-240 s, medians:

| | pilot (A ref) | slowdown462 (e5db66fa37) | arm A | arm B | B / arm A |
|---|---|---|---|---|---|
| fps | 18.43 | 19.17 | 19.22 | 19.77 | 1.029 |
| `Tot` ms/frame | 45.8 | 43.9 | 43.9 | 42.1 | 0.959 |
| `Sub` | 23.5 | 23.3 | 23.5 | 17.7 | 0.753 |
| `Surf` | | | 4.1 | 7.5 | 1.83 |
| `Draw` | 16.4 | 16.2 | 15.6 | 15.5 | 0.99 |
| GPU `R` | 21.6 | 20.3 | 20.9 | 18.5 | 0.885 |
| `cDef` per 60 flips | 357 | 371 | 367.5 | 179 | 0.487 |
| vCPU ms per 2 s | 1923 | 1927 | 1954 | 1924 | 0.985 |

`[sdcall]` per guest frame, same window:

| caller | A fin | A wait ms | B fin | B fence | B wait ms |
|---|---|---|---|---|---|
| `surfupd` | 6.82 | 23.45 | 3.08 | 0.00 | 20.26 |
| `range` | 0.00 | 0.00 | 0.14 | 0 | 0.27 |
| `expire` | 0 | 0 | 0.14 | 0 | 0.68 |
| total | 6.82 | 23.45 | 3.36 | 0.00 | 21.21 |

`su_upl` is 2.92 per frame in A and 3.08 in B. B's `surfupd` fin equals its `su_upl`: every finish
the update still pays is one where a binding was about to upload from VRAM.

What the two tables say:

- **The cut does what it was built to do.** Finishes fall from 6.8 to 3.4 per frame. They did not
  move to another caller: `range` and `expire` together gain 0.28 per frame.
- **The wait did not follow the count.** Finishes fall 51%, `Sub` falls 25% (5.8 ms), and the frame
  falls 4% (1.8 ms). B's fps of 19.77 is above all three base runs (18.43, 19.17, 19.22), by 3-7%.
  The base's own spread is 4%, and B is one run. That is not the >= 1.15x the prediction asked for.
- **Why the price in section 12 was wrong.** It assumed each finish costs the same wait, so that
  removing 57% of the finishes removes 57% of the wait. A finish waits for the GPU to catch up with
  every draw submitted so far. `Sub` tracks the GPU's render time in every run (23.5 vs `R` 20.9 in
  A, 17.7 vs 18.5 in B). With fewer sync points each one waits longer: 3.5 ms per finish in A,
  5.8 ms in B. While one synchronous completion remains late in the frame, the PFIFO thread waits
  for most of the frame's GPU work.
- **3.4 ms of the gain went back into `Surf`.** Inside `pgraph_vk_surface_update`, `[surf413]` has
  `cdef` - `fin` (the completion's time outside `pgraph_vk_finish`) rising from 1.65 to 4.33
  ms/frame, and `exp` from 0.16 to 0.85. The first is the pre-download branch: the deferred batch
  now rides the flip's command buffer, and the first update after the flip waits on that fence
  (`pre` 0.85 per frame). That is the branch lane.flip474 named for DOA. Forza pays it too, once
  the eviction finishes are out of the way.

**What the next lane should not repeat:** do not price a cut in sync points. Price it in the wait
that is left after the last sync point in the frame. And do not register a window on a creeping
route from one run's fps: read the frames for the place first.

### What is left, per frame (arm B, t = 125-240 s)

| sync point | per frame | wait ms/frame | what frees it |
|---|---|---|---|
| `surfupd` with an `upload_pending` binding | 3.08 | 17.9 | completing only when the upload's range overlaps a pending download (section 12's next cut), if most do not overlap |
| the flip pre-download, waited at the first update | 0.85 | ~2.7 | leaving `display_predownload_pending` set until a consumer (lane.flip474's list) |
| `range` + `expire` | 0.28 | 0.95 | real readers; they stay |

The bound with both gone is the larger of the PFIFO thread's CPU side (`Surf` + `Draw`, about
20-23 ms), the GPU (22.5 ms) and the vCPU, which is 96% on-CPU in this window: at most ~27 fps here
if the vCPU's time is the guest's own work. lane.slowdown462's profile was taken at 28 fps, not in
this window, so the vCPU's share here is not measured.

## 15. What the three remaining finishes are: the Vulkan clear never sets `cleared`

`[evict372]` in arm B, growth over 5 s at ~30 fps (10:54:11 to 10:54:16 PDT), per frame:

| pair | mask | from -> to | per frame |
|---|---|---|---|
| 6, 7 | m10 swizzle | C and Z, 128x128 linear -> 128x128 swizzled, same format and pitch | 2.8 each |
| 0, 1 | m10 swizzle | C and Z, 256x256 linear -> 256x256 swizzled | 0.94 each |
| 2 | m08 small | Z 640x480 -> Z 1280x480, pitch 5120 | 0.94 |
| 3 | m40 zdim | Z 1280x480 -> Z 640x480 | 0.94, half of them dirty |

`handoffs=0`: #372's GPU-side handoff declines all of them, because it needs the same swizzle and
the same size. No pair runs from swizzled to linear.

So about 3.75 times a frame Forza sets up a small render target like this:
1. It sets the surface type to linear and clears the target. The held binding is swizzled (last
   frame's). `update_surface_part` rescues that mismatch because `pg->clearing` is set, and the
   binding becomes linear.
2. It sets the type to swizzled and draws. The held binding is now linear. The rescue for this
   direction is `surface->cleared`: "a fully cleared linear surface to be marked swizzled"
   (surface.c, `update_surface_part`).
3. **`cleared` is never true in the Vulkan renderer.** `gl/draw.c:401-404` sets
   `binding->cleared = full_clear && write_color` (and zeta) at the end of the clear.
   `pgraph_vk_clear_surface` (vk/draw.c:7213-7496) has no such line on either of its two exits (the
   inline clear at 7391 and the pipeline clear at 7489). The only writers in vk/ set it false
   (`populate_surface_binding_target_sized`, `pgraph_vk_set_surface_dirty`).
4. So the draw evicts the colour and the zeta binding. Each records a download of the cleared
   pixels. The partner comes off the shelf stale (`vram_newer`), so it is `upload_pending`, and the
   update completes the downloads with a finish before it uploads them back.

That is a GPU -> VRAM -> GPU round trip of a uniform colour, 7.5 evictions of the ~9.5 per frame.
It is also why section 12's next cut (complete only when the upload overlaps a pending download)
is dead: these uploads read the very memory the eviction just downloaded. They overlap by
construction. Do not build it.

**The hunk, in vk/draw.c (not this lane's file):** at both exits of `pgraph_vk_clear_surface`, after
`pgraph_vk_set_surface_dirty`, set `cleared` as GL does. `full_clear` is the clip-bounded clear
rect covering the binding, taken before the scale factor is applied, as at `gl/draw.c:374-376`.
Two conditions are stricter than GL's, because the rescue relies on the content being uniform:
colour counts only when all four channels are cleared (`clear_all_color_channels`, already
computed there), and zeta only when Z is cleared, and stencil too if the format has it.

**Price (a bound, in finishes, and section 14 says not to trust a price in finishes).** The
small-target evictions go: 7.5 of 9.5 per frame, and with them their downloads, their uploads
(`realupl` 4.15 per frame) and the render-pass breaks around them. `su_upl` falls from 3.1-3.4 to at
most the Z 640/1280 flips, 0.94-1.9 per frame. What that does to the wait depends on where in the
frame the Z flips sit. If one is late, the PFIFO thread still waits for most of the GPU's work
there. The A/B has to say. No fps figure is claimed here.

**Not known:** whether Forza's clears of these targets are full clears. Eight clears a frame all
take the pipeline path (`InlClr:0/480`), and the logcat does not carry the clear rect. If they are
partial, `cleared` stays false and the A/B shows no change in `[evict372]` m10.

## 16. lane.flip474's O1 (the pre-download branch) also needs vk/draw.c

flip474's NOTES section 14 lists what lazy completion of the flip's display download needs. Rows 4
and 5 are in vk/draw.c: the finish at draw.c:3590 tags `deferred_downloads_frame` only while it is
< 0 and never re-tags entries recorded after the flip, and the slot rotation at draw.c:3785-3797
completes the staging without clearing `display_predownload_*`. The surface.c rows (1, 2, 3, 7,
11, 12) are this lane's. They are not safe to land without rows 4 and 5, because row 2's stale
copy becomes the normal case once the completion is lazy.

Forza pays this branch too (section 14: `pre` 0.85 per frame, ~2.7 ms in arm B).

## 17. Grant request: vk/draw.c

`hw/xbox/nv2a/pgraph/vk/draw.c` is on lane.remote's row (#426, #184, #109, #274, #461). The two
hunks this lane needs:

| hunk | site | size |
|---|---|---|
| set `cleared` after a full clear | `pgraph_vk_clear_surface`, both exits (7391, 7489) | ~15 lines |
| O1 rows 4 and 5 | the finish's tag (3590) and the slot rotation (3785-3797) | not written yet |

Requested on #414 and in `$DISPATCH_DIR/board-requests/forza414.md`. The first hunk is
independent of the second and goes first.

## 18. The merge and the re-registered arm

- Merged origin/master c91697f116 at c6bfa6c85a. One conflict, in vk/surface.c, with #475
  (`ef66174066`, the lock released across the completion's fence waits). Both sides are kept: the
  completion is `download_surface_complete_deferred_at(d, caller, release_lock)`, the tagged
  in-file callers go through `download_surface_complete_deferred(d, caller)` with the lock held
  as on master, and `pgraph_vk_surface_update` passes `qemu_thread_is_self(&d->pfifo.thread)`.
- No local compile exists on this host for these files. CI builds the head, and the arm's build is
  the Android one.
- `docs/testing/predictions/forza414-coalesce-mnm2.json` (sha256 e3771ace4860...): the same ten
  suites, A = c91697f116 (master), B = c6bfa6c85a. The arms job queues it from the commit. This is
  the arm the brief asks for before ready.
- The soak was not re-run on the merged refs. A second pair would measure a 3% effect again, and
  the Nova's queue is better spent on the `cleared` hunk's A/B.

## Attempt 4 ends waiting

PR #479 stays a draft, waiting on two things outside this session:

- The `[job.arms]` verdict for `forza414-coalesce-mnm2.json`.
- The board's answer on vk/draw.c.

On resume:
1. Read the arm verdict and every scores1.tsv `status`. If it passes and CI is green on the head,
   check the PR body's `Files:` against `git diff --stat origin/master...HEAD` and mark #479 ready.
2. If vk/draw.c is granted: write the `cleared` hunk, register a Forza soak prediction on the new
   refs with the window t = 125-240 s (the place all runs share) and a goldens must-not-move with
   Surface_format, Clear, Texture_render_target and any suite that draws swizzled targets, then
   queue one pilot. The mover to register is `[evict372]` m10 per frame falling from ~7.5 toward 0
   and `su_upl` from ~3.1 toward <= 1.9. Register fps as a readout, with the reason from section 14.
3. When flip474's DOA pair on 4b22f2526b / 94f002d309 lands (`1790527182`, `1790527188`), add DOA's
   cdef to section 14's table.

## Why attempt 4 did not finish (resume of 2026-09-27, addendum 3)

It ended on a `waiting:` (PR #479, 18:10Z) for the `forza414-coalesce-mnm2.json` arm and the
vk/draw.c grant. The grant landed at 11:13 PDT (board 5f78b6a5ba). At this resume the arms job had
not yet queued mnm2 (no `arms-forza414` result after `1-1790519668`), and CI on 7787feb2ae was
green on `check` with `build` still running.

## 19. Hunk 1: `cleared` after a full clear (51721e36aa)

`mark_clear_full()` in vk/draw.c, called at both exits of `pgraph_vk_clear_surface` after
`pgraph_vk_set_surface_dirty` (which resets the flag). The rect is the clip-bounded clear rect,
saved before the inline path's binding clamp. It is compared in anti-aliased units, as the binding's
size and GL's `surface_binding_dim` are, and before the scale factor. Colour counts only when all
four channels are cleared. Zeta counts only when Z is cleared, and stencil too if the host format
has a stencil aspect. There is no local compile for this file on this host, so CI builds it.

Predictions, registered before any device run, on A = 7787feb2ae (the head before the hunk) and
B = 51721e36aa:

| file | kind | legs |
|---|---|---|
| `forza414-cleared-mnm.json` | goldens, arms job | the ten suites of mnm/mnm2, byte-identical |
| `forza414-cleared-soak.json` | Nova soak, hand-read | M0 race reached; P1 m10 evictions <= 25% of A; P2 `su_upl` <= 1.9/frame; P3 `surfupd` fin <= 60% of A; fps is a readout, window t = 125-240 s |

P1 is also the only reading of whether Forza's clears are full: if they are not, m10 does not
move and the hunk is inert on Forza, not refuted.

Queued, Nova, priority 1 (a lane cannot make a `0-0-x` id; the host promotes):
`1-1790533007-forza414-3417242` (base 7787feb2ae) and `1-1790533010-forza414-3422338`
(fix 51721e36aa). The index was rebuilt for the new CLEAR_SURFACE references against the fold-pins
trees (tests_commit unchanged). `preflight.sh --allow-tracker` passes on the head.

## Attempt 5 ends waiting

PR #479 stays a draft, waiting on requests outside this session:
- the soak pair above, read by hand with `abread.py` plus the `[evict372]` m10 growth over the window;
- the `[job.arms]` verdicts for `forza414-coalesce-mnm2.json` and `forza414-cleared-mnm.json`.

On resume: judge the soak's legs from section 19. Then read both arm verdicts and every scores1.tsv
`status`. If all hold and CI is green, mark #479 ready. Hunk 2 and the DOA pre-download branch
(section 16, flip474's consumer list) come after the verdict, in the next PR.

## Why attempt 5 did not finish (resume of 2026-09-27, addendum 4)

It ended on a `waiting:` (PR #479, 18:18Z) for hunk 1's Nova soak pair and two goldens arms, all
outside the session. At this resume the soak pair had finished (promoted to
`0-0-x-1790533007-forza414-3417242` and `0-0-x-1790533010-forza414-3422338`), `forza414-cleared-mnm.json`
was judged PASS (266 of 266 byte-identical, 13:11 PDT), and the mnm2 fix arm
(`1-1790534057-arms-forza414-fix-3970185`) was still queued behind its base arm.

## 20. Hunk 1's soak, read: the swizzle round trip is gone, the finishes are not

`abread.py` over t = 125-240 s (the start line and pit straight), plus `evictgrow.py` for the
`[evict372]` masks. Same Nova, MAX, survey route, 2100 guest frames in the window in each arm. No
crash or validation line in either.

| leg | rule | A (7787feb2ae) | B (51721e36aa) | result |
|---|---|---|---|---|
| M0 | both in the race, `[evict372]` and `[sdcall]` printed | yes | yes | holds |
| P1 | m10 evictions per frame, B/A <= 0.25 | 16,088 in the window, ~7.7/frame | 0 | **holds** |
| P2 | B `su_upl` per frame <= 1.9 | 3.09 | 2.98 | **fails** |
| P3 | B/A `surfupd` fin per frame <= 0.6 | 3.086 | 2.982 (0.966) | **fails** |

Readouts: fps 19.52 -> 20.28 (1.039), `Sub` 18.8 -> 17.3, `Tot` 43.0 -> 41.5, `Surf` 8.1 -> 8.7,
`ev.dl` 586 -> 156 per 60 flips (0.27), `unshelve` 420 -> 0, `s413.exp` 0.93 -> 0.15, `realupl` 249
-> 249, `stale` 106 -> 104, `PreDL` 45 -> 52.

**So Forza's clears of the small targets are full clears, and the hunk does what it says.** Every
m10 eviction is gone, and with them the downloads (`ev.dl` -73%) and the shelf round trip
(`unshelve` to 0). The m08/m40 Z flips are unchanged (2,010 vs 2,006), as registered.

**But section 15's model of the finishes was wrong.** It said the unshelved partner comes back
`upload_pending` and the update finishes the eviction's downloads before uploading it. With every
unshelve gone, `su_upl` and `realupl` do not move at all: the ~3 `upload_pending` bindings per frame
come from somewhere else. The failure is P2's registered world, "the rescued bindings still come
back upload_pending (the watch marks them dirty another way)", seen as m10 falling while `su_upl`
holds. The surfupd fin per frame is the same 3.0 in both arms. P3 fails with it.

**What the next lane should not repeat:** do not attribute an `upload_pending` completion to the
eviction that happens to sit next to it. Read what set `upload_pending` (a `[sdcall]` split by the
setter: the VRAM watch on a CPU write, `vram_newer` on a shelf hit, the surface's creation) before
pricing a cut in these finishes. `stale` at ~105 per 60 flips in both arms is the first candidate.

The hunk stays: it is correct, it removes a real GPU -> VRAM -> GPU round trip per small target,
and its goldens arm is byte-identical. It is inert on the frame's wait on Forza.

## 21. Hunk 3: the per-pass state snapshot (addendum 4)

`flush_draw_one_pass` copied a whole `RenderCommandSnapshot` (`regs[0x2000]`, 32 KB, plus program
data, constants and lights, about 40 KB) on every draw pass, only to assert four fields at the end
under `#ifndef NDEBUG`. Android release configs pass `-UNDEBUG`, so shipped builds pay it.
5f07b1d542 keeps the four asserts and saves only `primitive_mode`, `clearing`, `CONTROL_0` and
`SETUPRASTER` in scalars. Nothing else in draw.c read `snap`. `pgraph_vk_snapshot_state` keeps its
other caller (render_thread.c). No local compile of this file on this host: CI builds it.

Price, two figures that disagree, and the arm decides between them:
- lane.slowdown462's Blinx profile: 47% of the PFIFO thread's `memcpy_opt` (30.5% of 13,080 ms
  on-CPU in 30 s, ~501 frames) is under the snapshot, about 3.7 ms/frame. #474's note says 2.2-2.5.
- Its size: ~40 KB per pass at a few GB/s is 5-10 us. At ~47 draw passes a frame that is 0.3-0.5
  ms/frame.

The time lands in `Draw` and outside every bracketed child timer, so the leg reads Draw's self time
(`Draw` - `Vtx` - `Syn` - `Prw` - `Pipe` - `Desc` - `Setup` - `Cmd`).

Predictions, registered before any device run, on A = 6ab1c50643 (the merge of origin/master
940c77e866) and B = 72de98abd1 (hunk 3 plus the index rebuild):

| file | kind | legs |
|---|---|---|
| `forza414-snap-mnm.json` | goldens, arms job | the same ten suites, byte-identical |
| `forza414-snap-soak.json` | Blinx Nova soak, hand-read | M0 level play reached, no abort; P1 Draw self falls by >= 1.0 ms/frame. It fails in the world where the size-based price is right (a 0.2-0.6 ms fall): the hunk is correct and small |

Queued, Nova, priority 1: `1-1790543736-forza414-3560854` (base 6ab1c50643) and
`1-1790543737-forza414-3561797` (fix 72de98abd1).

## Attempt 6 ends waiting

PR #479 stays a draft, waiting on requests outside this session:
- the Blinx soak pair above, read by hand: `abread.py` for the readouts, and Draw self from the
  perflog phase lines, window mark play + 10 s to the last line - 10 s;
- the `[job.arms]` verdicts for `forza414-coalesce-mnm2.json` (fix arm queued) and
  `forza414-snap-mnm.json` (queued by the arms job from this push).

On resume: judge P1 and M0, read both verdicts and every scores1.tsv `status`, post the verdict on
#414 and #474, then mark ready. After that, in the next PR: the setter split for `upload_pending`
(section 20), the DOA pre-download branch with flip474's consumer list, and addendum 4's uniform-block
skip (`apply_uniform_updates` / `fast_hash`).

## Why attempt 6 did not finish (resume of 2026-09-27, addendum 5)

It ended on a `waiting:` (PR #479, 21:17Z) for hunk 3's Blinx Nova soak pair and two goldens arms,
all outside the session. At this resume all had finished: the soak pair as
`0-0-x-1790543736-forza414-3560854` / `0-0-x-1790543737-forza414-3561797`, the mnm2 arm (judged
PASS, 15:22 PDT), and the snap-mnm arms `1-1790543810-arms-forza414-base-3588648` /
`1-1790543811-arms-forza414-fix-3588699` (DONE, no `[job.arms]` comment yet at this resume).

## 22. Hunk 3's verdicts: Draw self falls 4.1 ms/frame, pixels byte-identical

`drawself.py` (this directory) over both logcats, window mark play + 10 s to the last phase line
- 10 s, medians over the phase lines. Same Nova, MAX, survey route. No crash, abort or assert line
in either arm.

| | A (6ab1c50643) | B (72de98abd1) |
|---|---|---|
| window | 150.9 s, 39 lines | 152.7 s, 43 lines |
| Draw | 27.8 | 25.5 |
| **Draw self** (Draw - Vtx Syn Prw Pipe Desc Setup Cmd) | **5.8** | **1.7** |
| Draw self, also minus Sfp Mfp FTx | 5.6 | 1.5 |
| Pipe | 16.6 | 18.8 |
| Tot | 45.4 | 37.7 |
| GPU | 24.5 | 22.0 |
| Sub | 0.1 | 0.1 |
| fps (pace lines) | 16.81 | 17.16 |

| leg | rule | result |
|---|---|---|
| M0 | both arms reach level play, Draw > 0 in the window, no abort | **holds** (39/39 and 43/43 lines with Draw > 0) |
| P1 | A - B Draw self >= 1.0 ms/frame | **holds**: 4.1 |
| snap-mnm | 266 guarded captures byte-identical | **PASS**, 266 of 266 (`ab_compare.py` run by hand; the arms job will post its own) |

Every scores1.tsv row in both snap-mnm arms is `ok` except the same ten `white-content` rows (two
z16 Depth_buffer_fixed_function, eight TexFmt Texture_render_target). They are identical in both
arms and in hunk 1's base arm `1-1790534055-arms-forza414-base-3969468`, so they come from before
this lane.

**The profile's price was right, and the size-based price was wrong**: 4.1 ms against slowdown462's
~3.7 and the 0.3-0.5 of "40 KB at a few GB/s". The phase line has no draw count, so a scene
difference between the arms is not ruled out directly. But Pipe rose 2.2 ms in B, so B did not do
less work, and Draw self is the only child the hunk can reach. Tot fell 7.7 ms and fps rose only
2%: Blinx's bound is the vCPU (slowdown462), as the prediction said. No fps figure is claimed.

## 23. The merge of origin/master (38e33bae67)

origin/master at this resume was 69 commits ahead. Its only code change is #488's NOTIFY handler
(pgraph.c, methods.h.inc, nv2a_regs.h), with its own arm. It touches neither vk/draw.c nor
vk/surface.c. The only conflict was `nv2a_index.json`, rebuilt from the fold-pins trees (tests_commit
6743b6ab, 104 suites, `check` passes). **The arms were not re-run on the merge:** no line of either
hunk, nor anything they call, changed. The three judged goldens arms (cleared-mnm, coalesce-mnm2,
snap-mnm) stand on the code as it is. `preflight.sh --allow-tracker` passes on 38e33bae67.

## Next, in a new PR (not this one)

1. Split the ~3 surfupd finishes per frame by what set `upload_pending` (section 20): the VRAM
   watch on a CPU write, `vram_newer` on a shelf hit, or the surface's creation. `stale` at ~105 per
   60 flips is the first candidate.
2. The DOA/AUF display-predownload branch with flip474's consumer list (section 16, addendum 2).
3. Addendum 4's uniform-block skip in draw.c (`apply_uniform_updates` / `fast_hash`, 3.5-3.7
   ms/frame on Blinx and AUF).

## Why attempt 7 did not finish (resume of 2026-09-27, addendum 6)

It did finish its PR: #479 went ready after hunk 3's verdicts (section 22) and the master merge
(section 23), and the session ended on "next, in a new PR" with nothing queued. Nothing started
the next PR. PR #479 is now in audit, so this work is on `lane/forza414b`, stacked on #479, in its
own PR. Sections from 24 on are that PR's.

## 24. Probe: which setter left the surfupd finishes' `upload_pending`

`[sdcall]` gains `why=new/inv/stale/hoff/cpuw/gap/oth`: for every binding counted in `su_upl` (an
update that completed its downloads with a finish because a binding was about to upload from
VRAM), the site that last set that binding's `upload_pending`. perflog builds only; a side table in
surface.c, cleared by the upload.

| tag | setter |
|---|---|
| new | a fresh `g_malloc0` binding (populate sets `upload_pending`) |
| inv | a reused slot from the invalid list |
| stale | a shelf hit with `vram_newer` (another surface's download was recorded over it) |
| hoff | a shelf hit that was clean, made stale by a handoff fallback |
| cpuw | the CPU-write watch (`surface_access_callback`) |
| gap | the watch's re-arm gap check |
| oth | a setter this file does not tag: blit.c's two |

Section 20's `stale` at ~105 per 60 flips is the first candidate; `realupl` 249 per 60 flips and
`su_upl` ~3 per frame are what the split has to account for.

Pilot queued on the Thor, priority 1, perflog, survey route, 420 s:
`1-1790550241-forza414-2434853` on d04973ce9b. Read it with the `[sdcall]` line over the race
window (t = 125-240 s): `why=` per frame against `su_upl` per frame.

## 25. Hunk 4: the flip's pre-download stays pending until a consumer (ee830484bb)

This is lane.flip474's O1 (their NOTES sections 5 and 14, and addendum 2). It is all in vk/surface.c. The
draw.c rows of flip474's list need no change once the display flag is retired where the batch
completes.

| flip474 row | what the hunk does |
|---|---|
| 1, surface_update | `surface_update_may_defer_downloads` now defers a submitted batch when it is the flip's (`display_predownload_pending`). Other submitted batches complete there as before, so the next flip's pre-record is not refused more often than today. An uploading binding still completes it |
| 2 and 4, mixed batch | `complete_submitted_downloads()`: a download recorded after a finish submitted the batch completes that batch first, in `download_surface_record_deferred` and, before its generation test, in `download_surface_deferred`. So one fence always covers every entry. This was reachable before the hunk too: an eviction in the first update after any deferred-submit finish appended to the submitted batch, and the fence branch then copied that entry's staging before the GPU wrote it |
| 2, the override | the display branch no longer marks the display surface clean at its *current* generation. Its entry retires it at the generation the flip's copy captured (`pgraph_vk_complete_staged_downloads`) |
| 3, range lookup | `pgraph_vk_download_surfaces_in_range_if_dirty` no longer completes a submitted batch on every call. It completes it when a new download is recorded (row 2's rule), or when the range overlaps a pending entry or an overlapping surface (the existing test at its end) |
| 5 and 6, slot rotation | `pgraph_vk_complete_staged_downloads` clears `display_predownload_*`, so every completion retires the flag: the rotation into the flip's slot and a non-deferred finish's completion (draw.c), as much as `download_surface_complete_deferred` |
| 7, next flip | the pre-record completes a still-pending flip batch (`SDC_PREREC`) instead of returning early, so the display download is recorded every flip |
| 12, frees | `deferred_downloads_clear_surface` also clears `display_predownload_surface`. Nothing dereferences it now; `surface_handoff_partner` compares it |
| 11, 17 | unchanged. The CPU-access watch already completes an overlapping pending entry before the store lands, and row 17 is a diagnostic |

`[sdcall]` gains two callers: `record` (row 2's completion) and `prerec` (row 7's). With these,
the per-caller line shows where the wait went.

**The risk named before any run.** Android presents through the CPU path, and
`pgraph_vk_get_framebuffer_surface` forces a download request on every refresh. If that request
lands soon after the flip, the PFIFO thread waits for the same fence in `pend` instead of `surfupd`.
Then the wait moves between callers and does not go away. The W1 leg (total wait across callers) is
the one that separates the two cases.

**Remaining hazard, not fixed:** a surface freed while its entry is pending still has its staging
copied to VRAM when the batch completes. That is today's behaviour, but the window is now up to a
frame instead of one method. The CPU watch covers live surfaces. Freed ones have no watch.

Predictions, registered before any device run, A = d04973ce9b, B = ee830484bb:

| file | kind | legs |
|---|---|---|
| `forza414-predl-mnm.json` | goldens, arms job | the ten suites, byte-identical |
| `forza414-predl-doa.json` | DOA Nova soak, hand-read, 151-288 s | M0; G1 surfupd pre <= 0.1/frame; C1 cdef B/A <= 0.3; **W1 total completion wait B/A <= 0.5**; H0 no hang. fps is a readout (bound +1 to +2: DOA is GPU-bound, flip474 section 15) |
| `forza414-predl-auf.json` | AUF Nova soak, hand-read, 299-420 s | M0; G0 A's pre >= 0.5/frame (else inert on AUF); W1; H0 |

The addendum's "Tot <= 45 ms" is not registered: DOA's GPU work alone is about 64 ms a frame.

Queued, Nova, priority 1: DOA `1-1790550612-forza414-2663397` (A) and
`1-1790550616-forza414-2665748` (B). The AUF pair waits for the Thor pilot's verdict (the 30-min
rule).

## 26. Addendum 4's uniform-block skip is in vk/shaders.c, not draw.c: grant requested

`pgraph_vk_update_shader_uniforms` (vk/shaders.c:1349-1435) does the following on every draw:
1. Fills the whole `VshUniformValues`. That includes `c`, 192 vec4 = 3 KB memcpy'd from
   `pg->vsh_constants` (glsl/vsh.c:1196), plus the lights, ring and ltc arrays.
2. Copies every live uniform into the binding's layout, one element at a time
   (`apply_uniform_updates` -> `uniform_copy`, vk/glsl.h:123).
3. Hashes both whole layouts with `fast_hash`. It hashes them even when the dirty flags have
   already decided `uniforms_changed`: the hashes are recomputed only so the next draw has
   something to compare against.

The hunk, in two parts:
- **(a) No hash on a dirty draw.** Mark the saved hashes invalid instead. The next clean draw
  then hashes and counts as changed once. That costs one extra upload per dirty run and saves two
  whole-layout hashes on every dirty draw.
- **(b) Skip re-copying `c` and the light/ltc arrays into a binding whose copy is current.** This
  needs a per-binding "constants copied at generation N" and a generation counter bumped where
  the `*_any_dirty` flags are set. The flags are set in pgraph.c (lane.flip474's file) and cleared
  here. A side table in shaders.c keyed by binding avoids renderer.h, and a counter kept in
  shaders.c, bumped here when a flag is seen set, avoids pgraph.c.

Price: lane.slowdown462's 3.5-3.7 ms/frame (Blinx, AUF) is the whole of `apply_uniform_updates`
plus `fast_hash`. (a) takes the hash share on dirty draws, and (b) the constant copy on clean
draws. The split between the two is not measured.

The file is on no row (lane.remote released it 2026-09-26T18:20Z). The request is in
`$DISPATCH_DIR/board-requests/forza414.md`. Nothing is written until it is granted.

## 27. #479 folded with its audit fix: merge, new arm refs, re-registration

PR #479 folded (de2ed0f50f) with an audit fix in vk/surface.c (f65175f993):
- A pending download's struct is kept out of reuse and prune.
- A shelf reuse completes the download first (`[sdcall]` caller `reuse`).
- A download whose surface was freed marks its own range dirty.

That is the same path hunk 4 lengthens, and it is compatible with it. A reuse of a struct the
pending flip batch names now completes the batch first, and prune no longer frees such a struct.
That shrinks section 25's "freed while pending" hazard to surfaces freed by other paths.

PR #518 showed CONFLICTING and had no CI run. The conflict was the `SDC_*` enum and its name list;
both sides were kept, in the order `reuse, record, prerec`. Merged at 6eb7b1115c. The arms queued
on d04973ce9b/ee830484bb had not started. All five were withdrawn unrun
(`queue/withdrawn/*.why`): the Thor pilot, the DOA pair and the arms job's goldens pair. The
reason is that A/B on the pre-merge refs would measure code that does not ship.

New refs, both on this branch:
- **A = 35ee65562a**: the merge, with hunk 4 reverted.
- **B = 32657e9719**: A with hunk 4 re-applied. Its tree equals the merge's (`git diff 6eb7b1115c
  32657e9719` is empty).

All three predictions were re-registered on A/B before any arm ran, with the reason appended to
each.

Re-queued at priority 1:
- Thor pilot `1-1790552636-forza414-3224517` (A 35ee65562a, Forza, 420 s).
- DOA A `1-1790552638-forza414-3224848` and B `1-1790552639-forza414-3225184` (Nova, 300 s; they
  wait for the battery hold).

`preflight.sh --allow-tracker` on 24c705df60 passes every gate but `coverage`. That one is the
board's tracker row for #513 (status open, issue closed).

## 28. Hunk 4 on DOA, first pair: the post-flip wait is gone, and the GPU bound takes its place

`abread.py --from 151 --to 288` and `txline.py` (this directory) over
`1-1790552638-forza414-3224848` (A 35ee65562a) and `1-1790552639-forza414-3225184` (B
32657e9719). Both runs are the survey route on the Nova, MAX, and both are in the fight in the
window (route frames at 19:01:49 and 19:07:19). The stages and opponents differ: DOA picks them.

| | A | B |
|---|---:|---:|
| fps (pace lines) | 15.13 | 16.14 (B/A 1.066) |
| Tot | 60.7 | 53.3 |
| Surf | 52.4 | 0.8 |
| s413 cdef | 51.18 | 0.03 |
| `[sdcall]` surfupd pre per frame, wait ms | 0.981, 50.40 | 0, 0 |
| `[sdcall]` prerec pre per frame, wait ms | 0, 0 | 0.909, **0.00** |
| `[sdcall]` total completion wait, ms/frame | 50.40 | **0.00** |
| Draw | 6.6 | 50.7 |
| Pipe (Tx) | 2.9 (0.4) | 46.7 (~44) |
| GPU (phase line, uncorrected period) | 33.4 | 37.2 |
| vCPU ms per 2 s (`[tlb68]` cpu) | 1830 | 711 |

| leg | rule | result |
|---|---|---|
| M0 | both in the fight, lines printed, no crash | holds (34 / 37 lines, 0 crash lines) |
| G1 | B surfupd pre <= 0.1/frame | **holds**: 0.000 |
| C1 | B/A cdef <= 0.3 | **holds**: 0.001 |
| W1 | B/A total completion wait <= 0.5 | **holds as written**: 0.00. The flip batch now completes at the next pre-record with a 0 ms wait. **But the leg's instrument cannot see where the PFIFO thread's wait went.** It went into texture binding, which `[sdcall]` does not count (below) |
| H0 | longest phase-line gap <= 3 s; last line within 5 s of the end | **fails as written, in both arms.** The gap part fails in A too: 14 s loading gaps before the window, so it was mis-specified; it should have been scoped to the window. The tail part fails in B only: its last per-frame line is at 296.0 s against a soak end at 309.5, while A's lines run to the end. B's last route frame (19:07:46) is a KO, the loser falling through the stage floor at 9 fps. One run cannot separate a KO transition that flips fewer than 60 times from a hang. A replicate pair is queued |

**Where the wait went.** Tx (`pipe_bind_tex`) rises in every scene of B, the menus included (t =
95-115 s: Tx 11-18 ms in B, 0.3-2.8 in A), and it tracks the GPU time. The site is texture.c:2215:
a render-to-texture surface that was drawn since its texture node's last bind calls
`pgraph_vk_flush_all_frames` if that node was used within `num_active_frames` submits. That waits
every in-flight frame's fence. In A those fences had already been waited at the first surfupd after
the flip, so the flush found them signalled. In B the GPU is still on the previous frame when the
texture is bound, so the PFIFO thread waits there instead.

This is lane.flip474's section 15 bound. DOA is GPU-bound, and O1 moves the wait but cannot
shorten it. The fps gain, 15.13 -> 16.14 (+1.0), is inside the registered bound (+1 to +2). The
vCPU's on-CPU time fell from 1830 to 711 ms per 2 s: the guest now waits on the GPU instead of
spinning. The next lever for DOA is its GPU work, or the flush at texture.c:2215 (a per-surface
fence instead of all frames). texture.c is lane.remote's file, lent to lane.slowdown462.

**What the next lane should not repeat:** a completion-wait counter proves the wait left the
completion. It cannot prove the wait left the thread. Register the thread's total (Surf + Draw's
children, or Tot against the GPU) as the claim, and the per-caller counter as the mechanism.

## 29. The split: Forza's surfupd finishes are new bindings and stale shelf hits, not CPU writes

Thor pilot `1-1790552636-forza414-3224517` on 35ee65562a (arm A: master with #479 plus the
probe), Forza race, survey route, 420 s. `abread.py --from 125 --to 240`: 1680 guest frames, 28
phase lines. `thermal.jsonl` has 14 samples over the run, and none shows a pause.

| | per frame |
|---|---:|
| surfupd finishes (fin), all with an uploading binding (`su_upl`) | 2.95 |
| surfupd wait | 22.4 ms |
| why = **new** (a fresh `g_malloc0` binding) | **1.77** (60%) |
| why = **stale** (shelf hit, `vram_newer`) | **0.99** (33%) |
| why = inv (invalid-list reuse) | 0.20 (7%) |
| why = cpuw, gap, hoff, oth | 0 |

Readouts: fps 17.4, Tot 44.8, Fin 18.3 (Sub 17.9), GPU 22.8 (uncorrected period), `realupl` 249
per 60 frames, `stale` 108 per 60 flips.

- **No CPU write is involved.** The watch, its gap check and blit set nothing here. Section
  20's candidate `stale` is a third of it.
- **The largest share is a fresh binding every time.** 1.77 per frame matches the two Z flips
  between 640x480 and 1280x480 at one address (section 15: m08 and m40, 0.94 each). Each flip
  evicts the Z binding and records its download. The replacement is a size no shelved or invalid
  slot matches, so it is created and uploads from VRAM, and its upload overlaps the download by
  construction. So the finish.
- **The lever, if the flips start with a full clear:** a binding whose first use is a full clear
  needs no upload. So it needs no completion either, and the deferral applies. This is draw.c's
  own FIXME at `pgraph_vk_clear_surface` ("If doing a full surface clear, mark the surface for full
  clear and we can just do the clear as part of the surface load").
- **Not known yet: whether they do.** `[sdcall]` now also prints `clr` (of those bindings, the
  ones on a clearing update) and `clrfull` (the ones that clear then covered whole). This is
  perflog only, 53c81b1a7a. Thor pilot 2: `1-1790561602-forza414-3260817`.

Price, a bound: if every new and stale binding were a full clear, 2.76 of 2.95 finishes go. But
section 14 says a price in finishes is not a price in ms: the last sync point in the frame still
waits for the GPU.

Posted on #414, #462 and #474 with the first DOA pair (section 28).

## 30. DOA replicate pair: the result repeats, and the first B's short tail was the KO

`1-1790561463-forza414-3120192` (A 35ee65562a) and `1-1790561465-forza414-3121451` (B
32657e9719), same window, same readers.

| | A1 | B1 | A2 | B2 |
|---|---:|---:|---:|---:|
| fps | 15.13 | 16.14 | 13.90 | 15.80 |
| Tot | 60.7 | 53.3 | 64.9 | 55.7 |
| s413 cdef | 51.18 | 0.03 | 55.54 | 0.03 |
| `[sdcall]` total wait, ms/frame | 50.40 | 0.00 | 56.16 | 0.00 |
| where the batch completes | surfupd, pre 0.98 | prerec, pre 0.91, 0 ms | surfupd, pre 1.00 | prerec, pre 0.89, 0 ms |
| Pipe (Tx inside it) | 2.9 | 46.7 | 3.0 | 47.4 |
| vCPU ms per 2 s | 1830 | 711 | 1817 | 741 |
| last phase line / log end, s | 309.5 / 310.4 | **296.0 / 314.7** | 311.7 / 313.7 | 313.5 / 315.5 |

| leg | pair 1 | pair 2 |
|---|---|---|
| M0 | holds | holds (31 / 36 lines, 0 crash lines) |
| G1 surfupd pre <= 0.1 | holds (0) | holds (0) |
| C1 cdef B/A <= 0.3 | holds (0.001) | holds (0.001) |
| W1 total wait B/A <= 0.5 | holds (0.00) | holds (0.00) |
| H0 as written | fails in both arms (loading-screen gaps; mis-specified) and B's tail | the gap part fails in both arms as before; **the tail holds** (2.0 s) |

**Verdict on DOA:** the hunk does what it claims. The flip's post-flip wait is gone in both
pairs, and fps rises by 1.0 and 1.9 (+7% and +14%), inside flip474's bound (+1 to +2). The first
B's short tail was not reproduced. Its last frame is a KO, and a KO transition that flips fewer
than 60 times in 13 s prints no per-frame line. **What moved** is section 28's texture-bind flush,
`pgraph_vk_flush_all_frames` at texture.c:2215. It waits for all in-flight frames whenever a
render-to-texture surface is re-bound, so DOA stays GPU-bound. Replacing that all-frames wait
with the surface's own last-use fence is the next DOA lever. It is in texture.c, which is not
this lane's file.

## 31. Hunk 4 on AUF, and the goldens: +16% fps, pixels byte-identical

AUF A `1-1790561467-forza414-3123358` (35ee65562a) and B `0-0-x-1790561468-forza414-3125441`
(32657e9719; the host promoted it, and `1-...` is a symlink to it). Window t = 299-420 s, level
play in both: the same vault door, rendered the same (route frames 19:52:03 and 19:59:41).

| | A | B |
|---|---:|---:|
| **fps** | **17.25** | **19.99** (B/A 1.159) |
| Tot | 52.7 | 37.8 |
| Surf | 35.3 | 2.2 |
| s413 cdef | 31.32 | 0.09 |
| `[sdcall]` surfupd pre per frame, wait ms | 0.951, 30.44 | 0, 0 |
| `[sdcall]` prerec pre per frame, wait ms | 0, 0 | 0.115, 1.01 |
| `[sdcall]` total wait, ms/frame | 30.44 | 1.01 |
| Draw (Pipe) | 9.2 (4.3) | 18.7 (13.6) |
| Fin (Fen) | 0.6 (0.2) | 2.7 (2.6) |
| Idle | 7.6 | 14.0 |
| GPU (uncorrected) | 25.7 | 24.0 |
| vCPU ms per 2 s | 1917 | 1607 |

| leg | rule | result |
|---|---|---|
| M0 | both in level play, lines printed, no crash | holds (34 / 40 lines, 0 crash lines) |
| G0 | A's pre per frame >= 0.5 | **holds**: 0.951. AUF waits in the branch the hunk defers |
| W1 | B/A total completion wait <= 0.5 | **holds**: 0.033 |
| H0 | as for DOA | the gap part fails in both arms (loading gaps of 9.6 and 12.0 s; mis-specified as before); the tail holds in both (3.0 and 0.1 s) |

In B the flip batch mostly completes where `[sdcall]` does not count: prerec takes only 0.115 per
frame. The rest retires at the frame-slot rotation or a non-deferred finish, whose fence has
already been waited (`pgraph_vk_complete_staged_downloads`, vk/draw.c). About 12 ms of the 30
moved into Pipe, Fen and Idle. Idle is the PFIFO thread waiting for the guest, so AUF's frame is
now bound by something other than this completion. lane.flip474's `[cblat]` priced it at 19.3
ms/frame of AUF's 71.4 ms frame: at most 14 -> 19 fps. **B reads 17.25 -> 19.99.**

**Goldens, `forza414-predl-mnm.json`:** `[job.arms]` VERDICT PASS, 266 of 266 byte-identical
(base `1-1790552915-arms-forza414b-base-3330273`, fix `...-fix-3330409`). Every scores1.tsv row is
`ok` except the same ten `white-content` rows as every earlier forza414 arm (two z16
Depth_buffer_fixed_function, eight TexFmt Texture_render_target), identical in both arms.

**Hunk 4's verdict:**

| title | wait before -> after | fps |
|---|---|---|
| DOA, two pairs | 50-56 -> 0 ms/frame | +7%, +14%. GPU-bound: the wait moves to texture.c:2215's all-frames flush |
| AUF | 30.4 -> 1.0 ms/frame | **+16%** |

The pixel suites are byte-identical, with no hang and no crash.

## 32. The merge of origin/master (0e938db24f), and what is left

origin/master 4fcbe0262e merged without conflict. Its only code changes since 6eb7b1115c:
- #504's GPU timestamp period, measured at start-up (vk/renderer.c). This is an instrument: it
  changes the phase line's GPU figures, not what is drawn or waited on.
- A perflog-only wall probe in `pgraph_vk_bind_textures` (vk/texture.c).

Neither reaches the deferred-download path or anything hunk 4 calls. **The arms were not re-run
on the merge**, as in section 23. The three judged results (the goldens PASS and the DOA and AUF
pairs) stand on the code hunk 4 ships. The two perflog-only probe commits after B, `clr`/`clrfull`
(53c81b1a7a) and abread/txline, change no non-perflog line.

**Next, in the next PR (not this one):**
1. Read Thor pilot 2 (`1-1790561602-forza414-3260817`, 53c81b1a7a): `clr` and `clrfull` per frame
   against `su_upl`. If the forced uploads are full clears, build hunk 5, draw.c's FIXME in
   `pgraph_vk_clear_surface`: skip the upload, and so the completion, for a binding the coming
   clear covers whole. It needs `r->clear_parameter` set before `pgraph_vk_surface_update` rather
   than after (draw.c), and the coverage test in surface.c. That test must match `mark_clear_full`
   (draw.c), so share one helper rather than writing a second copy. Register first: surfupd fin
   and `su_upl` fall by `clrfull`'s share; pixels bit-identical.
2. The uniform-block skip (section 26) once vk/shaders.c is granted.
3. DOA's next lever, texture.c:2215's all-frames flush (section 28). It is in lane.remote's file,
   so it goes to the board, not here.

## 33. Thor pilot 2: a third of Forza's forced uploads are full clears

`1-1790561602-forza414-3260817` on 53c81b1a7a (B plus `clr`/`clrfull`), Forza race, Thor,
survey route, 420 s, t = 125-240 s, 1680 guest frames.

| per frame | pilot 1 (A) | pilot 2 (B + probe) |
|---|---:|---:|
| fps | 17.38 | 17.24 |
| `su_upl` (surfupd finishes forced by an uploading binding) | 2.95 | 2.86 |
| why new / inv / stale | 1.77 / 0.20 / 0.99 | 1.73 / 0.18 / 0.96 |
| **clr** (on a clearing update) | - | **0.96** |
| **clrfull** (that clear then covered the binding whole) | - | **0.96** |
| surfupd wait, ms | 22.36 (incl. the flip batch, pre 0.99) | 16.53 |
| record wait, ms (hunk 4: the flip batch, completed by the first download recorded after the flip) | - | 5.68 (pre 0.95) |
| total completion wait, ms | 22.37 | 22.23 |

- **Every forced upload on a clear is a full clear.** 0.96 per frame, a third of `su_upl`,
  and the same count as `why=stale`. The other ~1.9 per frame, the fresh Z bindings and the
  invalid reuses, are on draws, where the binding's old content is read, so the upload is needed.
- **Hunk 5's price, a bound:** it takes at most 0.96 of 2.86 finishes per frame, about 5.5 of
  the 16.5 ms. Section 14's caveat holds: a finish removed early in the frame moves its wait to
  the next sync point unless that one is later and shorter.
- **Hunk 4 is neutral on Forza, as expected.** Forza's first update after each flip evicts, and
  the eviction's download completes the flip batch (`record`) at nearly the same point as before.
  The total wait is unchanged (22.4 -> 22.2 ms, two runs on one device, not an A/B).
- **What hunk 5 needs that this lane does not hold.** The coverage rule must be one function
  used by both `mark_clear_full` (draw.c, after the clear) and the new pre-upload test (surface.c,
  inside the update). The two files share only vk/renderer.h (lane.remote's) for a declaration.
  Requested in `$DISPATCH_DIR/board-requests/forza414.md`: one prototype line in renderer.h, or a
  new `vk/clear.h`. draw.c also has to set `r->clear_parameter` before the update rather than
  after, which is one line.

## 34. Why the previous session did not mark this PR ready (resume, 2026-09-28)

The work was finished at section 33. At 03:59Z hostops parked the PR back in draft and took
`needs-audit-1` off it, because the audit outlet had claimed it while this lane's session was still
writing to the branch (two writers on one branch; cloud.sh's guard is #532). The session ended at
05:54Z with a `blocked:` comment saying the PR was complete, but it left the PR in draft, waiting
for hostops to restore it, which hostops only does once the lane has stopped.

State on resume: CI green on 0c56689783, `[job.arms]` PASS (266 of 266 byte-identical), and the PR
is mergeable. Since the merge at 0e938db24f, master's only code change is to vk/texture.c, which
this PR does not touch. Nothing is re-measured here. The PR is marked ready and `needs-audit-1` is
restored. Hunk 5 and the uniform-block skip stay with the next PR (section 32).

## 35. Why attempt 1 of this resume did not finish (lane/forza414-c, 2026-09-28)

The session before this one did everything its brief asked: #518 was marked ready at 06:03Z
(section 34), and it ended with nothing queued. The hostops addendum that grants vk/shaders.c and
lends vk/renderer.h is dated 23:11 PDT, which is 06:11Z, eight minutes after that session ended.
It asks for a third branch. So no session had read it, and lane/forza414-c did not exist. This
session starts that branch.

Also found on resume: the audit of #518 (docs/audits/2026-09-27-forza414b-pass1.md, 08f09e3d19)
came back needs-remediation with one MEDIUM. M1: a diag session's per-draw dump
(`diag_download_surface`, vk/renderer.c:580) writes BUFFER_STAGING_DST at offset 0 while the flip's
pre-download batch can now be pending. The fix is one call in vk/renderer.c, which is on [free]
and not on this lane's row. A grant is requested in `$DISPATCH_DIR/board-requests/forza414.md`.
Nothing is pushed to lane/forza414b until it is granted.

## 36. Hunk 5: a covering clear drops the binding's upload (b991fb4c21)

Section 33 found that 0.96 of Forza's 2.86 forced surfupd finishes per frame are on a clearing
update, and that every one is followed by a clear that covers the binding whole.

- `pgraph_vk_clear_covers_binding(pg, b, parameter)` (draw.c, one prototype in renderer.h) is now
  the one coverage rule. It uses the clip-bounded rect from (0,0) over the binding's
  anti-aliased size. Colour counts only with all four channels; zeta only with Z, plus stencil if
  the format has one. `mark_clear_full` calls it, and so does surface.c. The clip-bounded clear
  rect is one helper too, `clear_rect_clipped`, which `pgraph_vk_clear_surface` also uses.
- `pgraph_vk_clear_surface` sets `r->clear_parameter` before `pgraph_vk_surface_update` rather
  than after. Its other reader, the clear pipeline key, runs later still.
- `surface_drop_covered_upload` (surface.c) runs in a clearing update after the bindings are
  settled and before the deferral gate reads `upload_pending`. For a covered binding it does
  what the upload does besides the copy: it re-arms the CPU-write watch under
  `surface_watch_lock`, clears `upload_pending`, and marks the binding initialized, which
  begin_draw asserts. The render pass may then load undefined texels, and the clear overwrites
  every one of them. Zeta layout is handled by begin_render_pass's own transition; colour stays
  GENERAL.
- perflog: `clrskip` on the `[sdcall]` line counts the dropped uploads.
- Not changed: a clear the clip excludes entirely still returns after the update. The coverage
  test says no to it, so its upload runs as before.

No local compile exists for these files on this host (section 18); CI builds the head.

## 37. The uniform hash skip, part (a) only (79f0102478)

Section 26 named two parts. **(a) is in:** a draw whose constant or light flags are dirty no
longer hashes both whole layouts. A file-static `uniform_hashes_stale` makes the next clean draw
count as changed once. The same data is uploaded, so pixels cannot move. The one extra upload per
dirty run is the cost.

**(b) is not in, and the next lane should not assume it is cheap.** Skipping the constant and light
copy on clean draws would need all three of these:
1. Every writer of `vsh_constants`/`ltctx*`/`ltc1` sets its `*_any_dirty` flag. The method handlers
   in pgraph.c do. The reset and savevm paths were not audited, and a writer that misses the flag
   costs nothing today but would leave a stale constant under (b).
2. A per-layout "copied at generation N" table in shaders.c. It has to survive LRU eviction and
   pointer reuse of `ShaderBinding` and `module_info`, and modules may be shared between bindings.
3. The 3 KB memcpy into `VshUniformValues` is in glsl/vsh.c
   (`pgraph_glsl_set_vsh_uniform_values`), which is not on this row. Without that file, (b) saves
   only the second copy.

Price anchor: on hunk 3's Blinx pair (0-0-x-1790543736), `Sh` (pipe_bind_shd, which contains
`pgraph_vk_bind_shaders` and so the uniform update) reads 9-11 ms/frame in level play, inside
Pipe's 16-20 ms/frame. That is more than slowdown462's 3.5-3.7 ms for apply plus hash, so `Sh`
holds something else too. `pgraph_glsl_check_shader_state_dirty` is the next candidate to price.

## 38. Predictions and requests (PR #543)

| file | sha256 | pair | device |
|---|---|---|---|
| forza414-clrskip-soak.json | e346b1da35ed | fa56a26f1f -> b991fb4c21 | Thor, Forza race |
| forza414-uhash-soak.json | 33fa46d6ac17 | b991fb4c21 -> 79f0102478 | Nova, Blinx level |
| forza414-clrskip-mnm.json | 9d005e4f6ff1 | fa56a26f1f -> 79f0102478 | goldens, 17 suites |

A is lane/forza414b @ 08f09e3d19 merged with origin/master 548017f7ba. That is the last merge, and
every ref is after it. Pilot, under the 30-minute rule: the Forza pair,
`1-1790576328-forza414-1156305` (A) and `1-1790576328-forza414-1156419` (B), Thor, priority 1.
The Blinx pair goes in after the pilot is read. The goldens guard is the arms job's.

## 39. #518 folded; M1 was remediated on its branch by someone else; the pilot swap

- #518 folded at 06:25Z (2e36e51d5ed5) with pass 1's M1 fixed in 61e7a0d326, the same one call
  in `diag_download_surface`, and audit pass 2 clean. The renderer.c grant this lane requested
  for M1 (board 94108831c8) is not needed. It is released in the board request file, and this
  PR does not touch renderer.c.
- lane/forza414-c merged origin/master at 73b9209088, which contains #518. So the PR no longer
  stacks, and `git diff origin/master...HEAD` is exactly its own nine paths. The merge happened
  after the predictions were registered; their refs (fa56a26f1f, b991fb4c21, 79f0102478) are
  unchanged ancestors of the head.
- After B, only behaviour-identical commits. `clear_rect_clipped` reads into locals. The
  index read a line that begins with a pointer store (`*xmin = GET_MASK(...)`) as a comment line,
  so four CLEARRECT READ sites became COMMENT sites. The nv2a index is rebuilt against fold-pins
  tests 6743b6ab16.
- **The pilot swap.** The Forza pair on the Thor (`1-1790576328-forza414-1156305/-1156419`) had
  3.6 h of sustain507 and pacing work ahead of it, and the Thor was under lane.xbox's title-push
  hold. The 30-minute rule allows one pair in the queue, so the Forza pair was withdrawn unclaimed
  (`queue/withdrawn/*.why`). The Blinx pair went first as the pilot:
  `1-1790576971-forza414-1229800` (A) and `-1229835` (B), Nova. The Forza pair is re-queued once
  the pilot is read. The goldens guard is the arms job's (`1-1790577097-arms-forza414-base-...`).

**Waiting (session end, 2026-09-27 ~23:55 PDT):** on the Blinx pilot `1-1790576971-forza414-1229800`
/ `-1229835` (Nova, about 2 h of 1- work ahead of it), and on the arms job's goldens guard for
forza414-clrskip-mnm. On resume: judge forza414-uhash-soak, write `pilots/forza414.ok`, re-queue
the Forza pair on the Thor at priority 1 (forza414-clrskip-soak, refs fa56a26f1f / b991fb4c21), and
read the `[job.arms]` verdict.

## 40. Resume 2026-09-28 (attempt 3): the pilot judged, the goldens guard passed, the Forza pair queued

**Why the previous session did not finish.** It ended while it was waiting, which was correct. The
Blinx pilot pair and the arms job's goldens guard were both still queued on the device (section 39),
and a lane cannot wait inside a session. Both have now finished.

**Goldens guard, `forza414-clrskip-mnm.json`: PASS** (`[job.arms]`, 08:45 PDT). All 385 captures in
17 suites are byte-identical between fa56a26f1f and 79f0102478. PR label `verified`.

**Pilot, `forza414-uhash-soak.json` (Blinx, Nova, hand-read):** `1-1790576971-forza414-1229800` (A,
b991fb4c21) and `-1229835` (B, 79f0102478). Window: mark play + 10 s to the last phase line - 10 s,
about 165 s. Medians over the window's phase lines and gfps lines:

| | A | B |
|---|---|---|
| phase lines (Draw > 0) | 54 | 53 |
| Sh ms/frame | 6.95 | 7.00 |
| Pipe | 9.1 | 9.2 |
| Draw | 14.65 | 14.8 |
| Tot | 31.35 | 29.6 |
| gfps | 20.5 | 21.0 |
| Df (draws/frame) | 74.5 | 75.0 |

- **M0 PASS.** Both arms reach level play. There is no crash or abort line.
- **P1 FAIL, inert.** A's Sh minus B's is -0.05 ms, against a registered bar of >= 0.5, at the same
  draw count. This is the world the leg named: on Blinx, dirty-constant draws are too small a share
  of the draws for skipping their hash to show. The hash on clean draws and the constant copy
  (section 37, part (b)) are where the cost is. The hunk stays in the PR because its pixels are
  byte-identical and it removes work, but it claims no fps. **Do not re-measure part (a) alone.**

**Pilot verdict** is written to `pilots/forza414.ok`. **Forza hunk-5 pair re-queued** on the Thor
at priority 1, judged by `forza414-clrskip-soak.json` (refs fa56a26f1f -> b991fb4c21):
`1-1790613195-forza414-3088454` (A) and `1-1790613195-forza414-3088504` (B).

**Waiting (session end, 2026-09-28 ~09:55 PDT):** on that pair. On resume: judge
forza414-clrskip-soak by hand (the arms job skips title soaks), post fps and J/frame on #414 and
#474, merge origin/master, then `gh pr ready 543` and release vk/draw.c to lane.pacing.

## 41. Resume 2026-09-28 (attempt 3, second resume): arm B aborted, the pair re-queued

**Why the previous session did not finish.** It ended waiting on the Forza hunk-5 pair (section 40),
which was correct. That pair has finished, but it cannot be judged:

- A, `1-1790613195-forza414-3088454` (fa56a26f1f): valid. The race was reached, with 82 `[sdcall]`
  lines and 710 hakuX-stall lines, no thermal pause, and a hottest zone of 95.0 C.
- B, `1-1790613195-forza414-3088504` (b991fb4c21): **aborted before its first input.** The run.log
  reads `ROUTE ABORTED: not foreground (unknown)`: the Thor had no focused window on display 0, and
  both displays were OFF at the start. Its logcat is 5 lines, soak start to soak end in 45 s. This
  is a harness and focus failure, not a result of the code under test: no input was sent and hakuX
  never drew.

So **forza414-clrskip-soak is VOID on M0** for this pair. Nothing is judged from A alone. A
one-arm comparison against a different session's B would read the thermal state, not the hunk.

**Re-queued as a fresh adjacent pair** on the Thor at priority 1, with the same refs and the same
prediction: `1-1790619761-forza414-1092424` (A, fa56a26f1f) and `1-1790619761-forza414-1092523`
(B, b991fb4c21). Together that is about 17 min of device time.

**Waiting (session end, 2026-09-28 ~11:25 PDT):** on that pair. On resume, judge
forza414-clrskip-soak by hand (P1 clrskip >= 0.7 per frame, P2 su_upl <= 2.2 per frame, P3 surfupd
fin B/A <= 0.85, over t = 125-240 s), post fps and J/frame on #414 and #474, merge origin/master,
then `gh pr ready 543` and release vk/draw.c to lane.pacing. draw.c stays on this row until the
verdict, because hunk 5's coverage rule lives there.
