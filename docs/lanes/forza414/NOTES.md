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
