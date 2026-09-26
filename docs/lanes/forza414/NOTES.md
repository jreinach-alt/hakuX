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

## 5. Next measurement (queued)

A perflog Thor soak on the same survey route, 420 s, on master. It carries the
stall and phase lines across the step. See the PR for the request id.

## Do not repeat

- Do not read the 15-19 s "hang gaps" as stalls. They are pace-window spans at
  3.5 fps (section 2).
- Do not look for a counter that grows with time. The run has a single regime
  step at race time ~48.5 s (section 1).
- Do not treat the game-clock ratio as its own defect. It is fps/30.
