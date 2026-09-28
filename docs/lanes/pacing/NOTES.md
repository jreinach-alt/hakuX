# lane.pacing (#526)

Host work that does no emulation, removed for power at zero fps cost: the
frame limiter's busy spin, the 120 Hz panel under a 60 Hz presenter, and
(proposed only) the two render waits in vk/draw.c.

## What changed (branch lane/pacing)

| change | where | selector for the A/B |
|---|---|---|
| limiter waits with `clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME)` to the deadline | `ui/xemu.c` `android_limiter_wait` | `HAKUX_LIMITER=spin` = master's wait |
| `[pace526]` line every 10 s (tag `hakuX-lane`) | `ui/xemu.c` | always on, Android only |
| game surface asks for 60 Hz (`setFrameRate`, FIXED_SOURCE, CHANGE_FRAME_RATE_ALWAYS) | `SDLSurface.java` `requestGameFrameRate` | `HAKUX_SURFACE_RATE=off` = no request; `=mode` also sets `preferredDisplayModeId` |
| `[rate526]` display mode before / on change / 2 s after | `SDLSurface.java` | always, API 30+ |
| `HAKUX_VSYNC=0\|1` overrides the vsync pref for one run | `ui/xemu.c` at the Android `SDL_GL_SetSwapInterval` | default unchanged (pref, false) |

### The clock

`qemu_clock_get_ns(QEMU_CLOCK_REALTIME)` is `get_clock()`
(`util/qemu-timer.c:671`), which is `CLOCK_MONOTONIC` when `use_rt_clock`
is set (`include/qemu/timer.h:837`); `init_get_clock` sets it whenever
`clock_gettime(CLOCK_MONOTONIC)` works (`util/qemu-timer-common.c:52`). So
the absolute deadline the limiter already keeps is a `CLOCK_MONOTONIC`
time, and `clock_nanosleep` sleeps to it with no conversion. If
`use_rt_clock` were ever 0 the limiter falls back to the spin wait and the
mode line says `rt_clock=0`.

### The limiter's structure (read before changing it)

`sdl2_gl_refresh` is called in a loop by `xemu_android_display_loop`. A call
that arrives before `next_render_ns` polls events, waits, and **returns**;
the next call finds the deadline passed and renders. So the wait is one
call and the render the next; `[pace526]` measures lateness at the point
the second call lets the frame through (`pace526_release`), and only for
frames that were held (`waited`). A frame that arrives late on its own
(render-bound) is counted in `rel`, not in the lateness histogram.

### `[pace526]` fields

`rel` display frames let through; `waited` of those that the limiter held;
`late_p50_us`/`late_p99_us` upper edges of 50 us bins (a bound, not a
value); `late_max_us`; `late_gt1ms`; `thr_cpu_ms` render-thread CPU
(`CLOCK_THREAD_CPUTIME_ID`); `wait_cpu_ms` the part of it spent inside the
limiter's wait; `proc_cpu_ms` process CPU; `flips` guest flips
(`g_nv2a_stats.frame_count`); `pres` present intervals and `pres_1ms` those
within 1 ms of 16.67 ms.

## Predictions (registered before any run)

| file | kind | queued by |
|---|---|---|
| `pacing-pgraph-inert.json` | 12 pgraph suites, 65eaea9b8c vs ead1086cb5, must not move | the arms job |
| `pacing-limiter-kabuki.json` | Nova, 60-capped window, spin vs sleep, 2 runs/arm | me (request.sh) |
| `pacing-limiter-doa.json` | Nova, uncapped window (DOA1U ~20 fps), 2 runs/arm | me |
| `pacing-display.json` | Nova off / setFrameRate / +preferredDisplayModeId; Thor off / on | me |
| `pacing-vsync.json` | Nova swap interval 0 vs 1 at 60 Hz, Kabuki + DOA1U | me, only if the display arm reaches 60 Hz |

Judge: `docs/lanes/pacing/pace_judge.py` (reads results; never the
prediction). `find_runs.py` and `timeline.py` are the scratch readers used
to pick the titles: Kabuki Warriors holds gfps 59 / D 16.7 from boot to
`mark gameplay` on the Nova (1-1790481308-titlebench-2892494), and DOA1U's
survey window 150-288 s runs 13-22 gfps (flip474's Nova runs).

## Why an env for vsync and not the request's prefs

The brief asked for the vsync A/B to be set in the request's prefs. The
dispatcher writes exactly one pref, `env_vars` (`dispatcher.sh` set-env
block); nothing in the request path writes `vsync` or
`runtime_override_vsync`. `HAKUX_VSYNC` is the env route to the same swap
interval, with the pref and its default untouched.

## Step 5, proposed: the vk/draw.c render waits (file held by lane.forza414)

`hw/xbox/nv2a/pgraph/vk/draw.c:3713` and `:3778` wait for the render
thread's `vkQueueSubmit` with `while (!frame_submitted) sched_yield();`.
`sched_yield` on an otherwise idle core returns at once, so this is a spin
at full clock for however long the render thread takes to submit.

The code's own comment says the first wait "typically completes in
<100 us". That is a claim, not a measurement: the wait is for the render
thread to reach THIS command, and `pgraph_vk_render_thread_enqueue` puts
it behind whatever the render thread has not yet drained, so its length is
the render thread's backlog, not one submit. The second wait "rarely
triggers" by its comment (three frame slots). So the first step is a
counter, not a change: per 10 s, the number of waits at each site and a
duration histogram (the `[pace526]` 50 us-bin shape). If the first site's
p99 is under ~50 us and the second site fires almost never, the spin
costs little and there is nothing worth changing. Only if the waits are
long does the change below pay.

The change I would make, when the file is free and the counter says so:

1. Keep a bounded spin first: poll `frame_submitted` (acquire load) for
   20-50 us with a `cpu_relax`/`yield` instruction, no syscall. Most waits
   that end quickly end inside that.
2. Then block: a `QemuEvent` owned by the render thread's submit path
   (`qemu_event_reset` before queuing the work, `qemu_event_set` after
   `vkQueueSubmit` returns and `frame_submitted` is stored), and the waiter
   does `qemu_event_wait`. QemuEvent is a futex on Linux, so a set with no
   waiter costs one atomic.
3. Count, per 10 s, how many waits ended in the spin vs the block and the
   total blocked time, on the same `hakuX-lane` line style.

The measurement that judges it: the same one-binary env A/B as the limiter
(old wait vs new), on a title where these waits fire every frame, with
legs (a) CPU time of the waiting thread per guest frame falls by the
spin's share; (b) the waiting thread's wake-up latency after the submit
(timestamp at `qemu_event_set` to timestamp after `qemu_event_wait`
returns) p99 under 100 us; (c) gfps unchanged within the title's run-to-run
spread; (d) pgraph suites byte-identical. A wake-up p99 over 100 us would
say the futex path is too slow for this handoff and the spin bound should
grow, not that blocking is wrong.

## Status and what the next lane should not repeat

- Code and predictions are pushed; arms not yet read. See the PR for the
  current state.
- A lone host-side compile of the limiter helpers (stubs, `-Wall -Wextra`)
  was clean; running it needs approval a headless lane cannot get, so the
  device arm is the first run.
