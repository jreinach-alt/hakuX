# Where Crimson Skies' frame time goes on the Nova

Measured 2026-09-11. Retroid Pocket Nova, Adreno 740, Turnip T30. Build
`33557e82ab`. Harness and raw logs in `docs/testing/perf/`.

The question was whether the roughly 30 fps this game shows is the emulator's
limit or the game's, where the ceiling is, and what upscaling costs.

## How a run is made

`docs/testing/perf/run_perf.sh <surface_scale> <tag> [seconds]` boots the
title, presses A through the intro and the first tutorial prompts, settles,
then measures with the sticks centred so the plane flies level. Input goes in
at the evdev layer, because `input keyevent` arrives with a non-gamepad source
and the emulator treats it as an exit.

Two things are recorded at once. The emulator's own pacing line, always on
under logcat tag `hakuX-perf`, gives the guest's flip rate and frame times.
`loadsample.sh` reads GPU busy and per-thread CPU from the kernel, which costs
the emulator nothing. A build with `-Pperflog=true` adds the frame-phase
breakdown; it perturbs what it measures, so it is read for proportions only.

**Caveat on repeatability.** The input sequence is fixed but the flight path
is not, so scene load varies between runs. Two 1x runs gave median guest rates
of 27 and 22. Compare the floors and the load trends, which are stable, rather
than single medians.

## The 30 is the game's

| quantity | measured |
|---|---|
| display frame time | 16.70 ms, flat, min 16.6 max 16.7 |
| swap | 0.3 to 3.6 ms |
| game frame time floor | **33.2-33.3 ms, in every run at every scale** |
| emulated vblank | 59.94 Hz (`nv2a_calc_vblank_period_ns`, 480p path) |

The guest is offered a 59.94 Hz display and presents on every second vblank.
Its flip interval never once fell below 33.2 ms across seven runs, which is a
hard floor at 30.0 fps and not the ragged curve a compute limit produces. Our
display side meanwhile holds a flat 60 Hz with cheap swaps.

So **60 fps is not reachable in this title at any settings**, and the target
for it is a locked 30. The emulator's own limiter is hardcoded to 60 Hz and
never comes into it. (Unrelated but worth noting: `XEMU_ANDROID_TARGET_FPS` is
parsed and logged into `g_android_frame_interval_ns`, and the limiter then
uses its own `min_frame_ns` constant instead. The variable does nothing.)

What we do not always do is *hold* 30. In light scenes we sit at 29-30; in
heavy ones the frame time rises to 45-75 ms.

## Nothing is saturated

At 1x, in a window where the guest was managing 18 fps:

| resource | reading |
|---|---|
| GPU busy | 25% |
| GPU clock | 220 MHz, the minimum; the part goes to 680 |
| GPU work per frame | 6.2 ms |
| hottest thread | `qemu_main`, 84% of one core |
| all threads | 208% of one core, on an 8-core part |
| GPU temperature | 48-50 C, no throttling |

The GPU is doing about 6 ms of work in a 37 ms frame while refusing to leave
its lowest power level, because at 25% busy the governor sees no demand. That
is roughly 8% of the chip. Total CPU across every thread is about a quarter of
the package.

**We are slow while both resources are idle**, which means the limit is
neither throughput: it is one thread's serial work, and the waiting around it.

## Where the frame actually goes

Frame-phase breakdown at 1x, milliseconds, from the instrumented build. These
are inflated by the instrumentation; the shares are the point.

| phase | ms | what it is |
|---|---|---|
| draw dispatch | 19.5 | CPU preparing draws |
| - texture bind | **7.2** | largest single item, ~595 draws a frame |
| - vertex sync | 4.4 | |
| - shader bind | 1.7 | |
| - descriptors, setup, command | 2.1 | |
| finish | 3.6 | of which 2.4 waiting on the GPU fence |
| idle | 15.5 | 9.1 waiting for the next frame, 6.4 starved mid-frame |
| surface update | 1.1 | |
| texture upload | 0.0 | nothing is being uploaded |
| **total** | **39.7** | against 6.6 ms of GPU work |

Half the frame is CPU-side draw preparation and a third is idle. Texture
binding alone is a fifth of the whole frame, roughly 12 microseconds per draw,
with no uploads happening at all: this is lookup and validation, not data
movement.

## What upscaling costs

| surface scale | guest fps (median) | GPU busy | GPU clock | GPU ms/frame | hottest thread |
|---|---|---|---|---|---|
| 1x | 27 | 25% | 220 | 6.2 | 84% |
| 2x | 24 | 36% | 220 | 9.1 | 83% |
| 3x | 22 | 56% | 220 | - | 79% |
| 4x | 22 | 66% | 220-295 | - | 76% |

Held against each other in the instrumented runs, 1x and 2x differ by about
two frames a second. GPU work rises 6.2 to 9.1 ms for four times the pixels,
which is sublinear, and the clock still does not move. The CPU side barely
notices: draw dispatch goes 19.5 to 21.9, almost all of it in descriptor
setup and surface update.

**2x upscaling is close to free here, and the reason is that the GPU is
idle.** Even 4x only reaches two thirds busy at a near-minimum clock. The
ceiling on upscaling is not the GPU; it is the same CPU thread that sets the
frame rate.

## What follows

The GPU has roughly five times the headroom it is using and will not clock up
while it stays this idle, so moving rendering work onto it does not help;
there is no queue to drain. The constraint is serial CPU work in the draw
path, on a machine using two of its eight cores.

In rough order of expected return:

1. **Texture binding, 7 ms a frame.** No uploads occur, so the cost is
   per-draw lookup and validation. Caching the resolved binding against the
   texture state generation should collapse most of it.
2. **Get the draw path off the emulation thread.** Six cores are idle. The
   thread that pulls the FIFO also prepares every draw, and it sits at 85%
   rather than 100%, so it is alternately working and blocked.
3. **The 15 ms of idle.** Part is the game pacing itself to 30, which is not
   ours to remove, but 6.4 ms of it is mid-frame starvation, meaning the
   renderer ran dry while the guest was still producing.
4. **Vertex sync, 4.4 ms.** Not yet broken down further.

None of this is upscaling work. Anything that buys frame time at 1x buys the
same at 2x, and 2x is already nearly free.
