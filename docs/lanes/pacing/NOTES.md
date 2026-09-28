# lane.pacing (#526)

Host work that does no emulation, removed for power at zero fps cost: the
frame limiter's busy spin, the 120 Hz panel under a 60 Hz presenter, and
(proposed only) the two render waits in vk/draw.c.

## What changed (branch lane/pacing)

| change | where | selector for the A/B |
|---|---|---|
| limiter waits with `clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME)` to the deadline | `ui/xemu.c` `android_limiter_wait` | `HAKUX_LIMITER=spin` = master's wait |
| `[pace526]` line every 10 s (tag `hakuX-lane`) | `ui/xemu.c` | always on, Android only |
| game surface asks for 60 Hz (`setFrameRate`, FIXED_SOURCE, CHANGE_FRAME_RATE_ALWAYS) | `SDLSurface.java` `requestGameFrameRate` | opt-in: unset or `off` = no request (the default); `=on` = the request; `=mode` also sets `preferredDisplayModeId` |
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

- Code and predictions are pushed. Pilot, display and pixel arms are read
  (attempt 2, below). The second runs are queued.
- 2026-09-27 18:45 PDT, WAITING on the Nova (about an hour of other
  lanes' work ahead):
  - limiter pilot, pacing-limiter-kabuki.json: A1 spin
    1790559839-lane.pacing-2276057, B1 sleep 1790559842-lane.pacing-2277012;
  - display, pacing-display.json: A1 off 1790559882-lane.pacing-2288269,
    B1 setFrameRate 1790559882-lane.pacing-2288358, C1 +mode
    1790559882-lane.pacing-2288430;
  - pixel arm pacing-pgraph-inert.json: the arms job queues it.
- On resume: read the pilot with `pace_judge.py --from 30 --to
  mark:gameplay --a <A1> --b <B1>`. If the instrument lines are there and
  H1 reads the way it should, write `pilots/lane.pacing.ok` (python3) and
  queue Kabuki A2/B2, DOA1U A1/B1/A2/B2, and the Thor display pair. Queue
  pacing-vsync.json only if the display arm's B or C reached mode_hz ~60.
- A lone host-side compile of the limiter helpers (stubs, `-Wall -Wextra`)
  was clean; running it needs approval a headless lane cannot get, so the
  device arm is the first run.

## Attempt 2 (2026-09-27 late PDT): why attempt 1 did not finish

Attempt 1 ended correctly, with `waiting:` on dispatch ids, but its runs sat
about an hour behind other lanes' work. Several then had to be re-run: the
Nova dropped off adb, a "Use USB for" dialog took focus after the replug,
and lane.titleroutes force-stopped the first base pgraph arm on the Thor.
Nothing resumes a lane when a run finishes, so the reading waited for
hostops' addendum. No code was left unfinished.

### Pilot (Kabuki, Nova, 30 s to `mark gameplay`, 1 run per arm): passes

| field | A spin (…2276057) | B sleep (…2277012) |
|---|---|---|
| windows / pause samples | 21 / 0 | 21 / 0 |
| gfps median | 59 | 59 |
| wait_cpu_ms per display frame (H1) | 1.367 | 0.011 |
| thr_cpu_ms per display frame (H2) | 1.713 | 0.572 |
| proc_cpu_ms per flip (H3) | 26.19 | 25.61 |
| late p99 median / max bin, us | 50 / 50 | 200 / 250 |
| late_max_us, frames > 1 ms | 80, 0 | 1189, 1 of 12612 |
| pres within 1 ms of 16.67 | 0.993 | 0.991 |
| flips taking 2+ VBLANKs | 0.25% | 0.22% |

H2: 1.14 ms fell out of 1.36 ms of removed wait (ratio 0.84, band 0.6-1.4).
H3 holds by a hair: 0.58 against a floor of 0.57. It needs the second runs
before anyone quotes it. Pilot file: `pilots/lane.pacing.ok`.

### Display (Nova, Kabuki, 30-140 s): the prediction's guess held

| arm | request | before | after |
|---|---|---|---|
| A (…2288269-r2) | none | mode 2, 120 Hz | (no change) |
| B (…2288358-r2) | `setFrameRate(60, FIXED_SOURCE)` | mode 2, 120 Hz | **120 Hz** (overridden) |
| C (…2288430) | + `preferredDisplayModeId=1` | mode 2, 120 Hz | **mode 1, 60 Hz** (`changed` line) |

`min_refresh_rate` read 120.00001 in all three. gfps 59 / 59 / 59, and
proc CPU per flip 20.71 / 20.78 / 20.88. So the user-level minimum outranks
`setFrameRate` on this Nova (Android 13, sdk=33), and the window's base-mode
vote outranks the user minimum. On the Nova, `HAKUX_SURFACE_RATE=mode` is the
lever. `off` and plain `setFrameRate` leave the panel at 120 Hz.

These arms ran on ead1086cb5, where an unset `HAKUX_SURFACE_RATE` made the
request, so B's `b_env: []` selected `setFrameRate`. Since the pass-1 audit
(MEDIUM 1) the request is opt-in: unset behaves as `off`, and `=on` is what
B's empty env was. The prediction file stays as registered because its refs
pin that binary.
The pairs below measure CPU, not panel power. No power record exists yet
(#523), so what the 60 Hz panel saves in watts is still unmeasured.

### Pixel arm (pacing-pgraph-inert.json): holds, but on a cross-device pair

Base re-run 1-1790565197-arms-pacing-base-rr ran on the **Nova**, and fix
1-1790560695-arms-pacing-fix-2707884 on the **Thor**. That happened because
the re-run was not pinned to the first arm's device. Both arms have 682 rows,
all `ok`/`white-content` in the same places, 0 unreadable, and 0
UtilAcceptVsock lines. 681 rows are identical in differing/max_rgb/max_a/
off_by_one. The one that moved, `Vertex_shader_rounding_tests/GeometrySuperscreen_0.0010`
(0 → 400 px, max 255), is outside must_not_move on purpose. It also scored
both 0 and 800 at one ref (2dc2b5c49a, the dpforce345 base arms). I did not
spend a same-device re-run on it.

### Queued 2026-09-27 ~23:52 PDT (ref ead1086cb5, `1-` priority)

| id | device | what |
|---|---|---|
| 1-1790575938-lane.pacing-1078186 | nova | Kabuki A2 spin |
| 1-1790575939-lane.pacing-1078233 | nova | Kabuki B2 sleep |
| 1-1790575939-lane.pacing-1078282 / -1078334 | nova | DOA1U A1 spin / B1 sleep |
| 1-1790575939-lane.pacing-1078381 / -1078429 | nova | DOA1U A2 spin / B2 sleep |
| 1-1790575940-lane.pacing-1078477 / -1078524 | nova | vsync Kabuki swap 0 / 1, at 60 Hz (`mode`) |
| 1-1790575940-lane.pacing-1078573 / -1078630 | nova | vsync DOA1U swap 0 / 1, at 60 Hz |
| 1-1790575941-lane.pacing-1078684 / -1078761 | thor | display TA1 off / TB1 setFrameRate |

Judge commands are in each prediction's `judge` field. The arms job SKIPPED
the soak predictions (`a_ref == b_ref`). That is expected: they are env A/Bs
on one binary, and I queue them myself.

### For the next lane

- Pin every re-run of an A/B arm to the other arm's device. An unpinned
  re-run is how the pixel pair above ended up Nova against Thor.
- On a Nova with `min_refresh_rate=120`, `Surface.setFrameRate` alone does
  nothing. Do not measure the panel's power with it.

## Attempt 3 (2026-09-28): why attempt 2 did not finish, and the second batch read

Attempt 2 ended correctly on dispatch ids, but the Nova froze off adb at
23:11 PDT, then sat on a battery hold (11%, 500 mA port) until 80%. Two DOA
runs were voided when the adb link dropped mid-soak (VOID.txt in
`...1078282` and `...1078334`; re-run as `-r2`, same device). The Thor pair
was renamed to `1-1790572033-...`. Every run had finished by the time the
handback job resumed this lane. No code was left unfinished.

Judge commands are in each prediction's `judge` field. Logs from this read:
`docs/lanes/pacing/.j_*.log` (not committed). No run had a thermal pause
sample. No result carries a power record (#523), so `net_w` and
`j_per_frame` are not reported.

### Limiter, Kabuki (capped, Nova, 2 runs per arm, pilot + A2/B2)

| leg | A spin | B sleep | verdict |
|---|---|---|---|
| gfps median | 59 / 59 | 59 / 59 | no change |
| H1 wait_cpu_ms / display frame | 1.367 / 1.348 | 0.011 / 0.008 | PASS (A in 0.7-2.5, B <= 0.15) |
| H2 thr_cpu_ms / display frame | 1.720 pooled | 0.486 pooled | PASS: 1.234 of 1.348 removed (0.92) |
| H3 proc_cpu_ms / flip | 25.85 | 24.76 | PASS: -1.10, floor was -0.62 |
| L1 late > 1 ms share, p99 | 0, 50 us | 0.0008, 150 us | PASS (bound 1 ms) |
| pres within 1 ms of 16.67 | 0.992 | 0.991 | no change |

H3 needed the second pair: the pilot alone held by 0.01 ms. With A2/B2 it
holds by 0.5 ms.

### Limiter, DOA1U (uncapped, Nova, 150-288 s, 2 runs per arm)

| leg | A spin (r2, A2) | B sleep (r2, B2) | verdict |
|---|---|---|---|
| gfps median | 15 / 12 | 9.5 / 14 | P1 PASS (11.75 >= 13.5 - 2); P2 PASS (1.75 < 2) |
| H1 wait_cpu_ms / display frame | 0.860 / 1.047 | 0.011 / 0.007 | PASS |
| H2 thr_cpu_ms / display frame | 1.412 | 0.495 | PASS: 0.917 of 0.944 removed (0.97) |
| L1 late > 1 ms share, p99 | 0, 50 us | 0.0002, 150 us | PASS |

P1 and P2 pass, but they carry little weight: runs within one arm spread
by 3-4.5 gfps (9.5-15). One B run (`1078334-r2`) flipped only 2.35 times a
second against a gfps median of 9.5, so that window was mostly not in the
fight. proc_cpu_ms_per_flip (169 vs 448) is dominated by that run and is
not read. The fps claim rests on Kabuki. DOA shows the render-thread saving
holds when the guest is the slow side.

### Vsync-aligned present, at the 60 Hz panel (Nova, `HAKUX_SURFACE_RATE=mode`), measure only

| title | swap | gfps | pres within 1 ms | thr_cpu_ms / display frame | proc_cpu_ms / flip | late max us |
|---|---|---|---|---|---|---|
| Kabuki (30 s to gameplay) | 0 | 59 | 0.9995 | 0.347 | 24.63 | 1070 |
| Kabuki | 1 | 59 | 0.9935 | 0.386 | 23.93 | 465 |
| DOA1U (150-288 s) | 0 | 16 | 0.220 | 0.373 | 79.05 | 2061 |
| DOA1U | 1 | 15 | 0.236 | 0.433 | 82.02 | 764 |

All four runs reached mode 1 / 60 Hz (`changed` line). Swap interval 1 did
not make presents more regular (guess 1 refuted on Kabuki: 0.9935 < 0.9995,
though both are near 1). It did not cost gfps (guess 2, 3 hold). Render
thread CPU per display frame went up 11-16%, outside guess 4's 10%. With
swap interval 1 the limiter rarely waits (Kabuki `waited` 379 against
12013), because the blocking swap is doing the pacing. One run per arm; the
differences are within what one run can show. No default changed.

### Display, the Thor (Alien Hominid, 30-120 s)

The Thor's panel was already at mode 1, 60 Hz, with `min_refresh_rate=60.0`
and modes 60/120 available. TB's `setFrameRate(60, FIXED_SOURCE)` logged
no `changed` line: a no-op, as D4 predicted. gfps 59 / 59, proc CPU per
flip 26.46 / 26.54. The Thor has no 120 Hz panel to fix.

### State at the end of attempt 3

Every leg is read. What is still open, and not this PR's to close:
- Panel and limiter power in watts: needs #523's power record live on the
  dispatcher. Re-run the Kabuki pair and the display A/C pair then.
- The `HAKUX_SURFACE_RATE` default is `off` (unset makes no request; the
  code agrees since the pass-1 remediation). On the Nova the lever that
  moves the panel is `mode`. Making it the default is a product call,
  because it overrides the user's own 120 Hz minimum.
- vk/draw.c: still lane.forza414's; the proposal above stands.
