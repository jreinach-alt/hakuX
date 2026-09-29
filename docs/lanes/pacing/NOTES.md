# lane.pacing (#526)

Host work that does no emulation, removed for power at zero fps cost: the
frame limiter's busy spin, the 120 Hz panel under a 60 Hz presenter
(PR #529, folded as d054c1c731), and the two render waits in vk/draw.c
(PR #572, branch lane/pacing-spin; see "Attempt 4" at the end).

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

## Attempt 4 (2026-09-28): the vk/draw.c render waits, PR #572

### Why attempt 3 did not finish

It did, as far as it could: every leg of PR #529 was read, CI was green, and
the session ended with the PR in draft waiting on the arms job's verdict.
The handback job resumed the lane (arms label `verified`), and #529 folded
as d054c1c731. Hostops then lent `hw/xbox/nv2a/pgraph/vk/draw.c` from
lane.forza414 for the two `sched_yield` waits only, on a second PR on
`lane/pacing-spin`. That is this attempt.

### What changed (23f0ee233f)

Both waits in `pgraph_vk_finish` (the deferred finish, and the frame
rotation when the next slot is still queued) call `wait_frame_submitted()`:

1. return at once if `frame_submitted[frame]` is already set (counted as a
   call, not a wait);
2. poll the flag for up to 30 us with `cpu_relax()`;
3. then block on the render thread's `idle_event`: reset, check, wait,
   loop. `render_thread.c` sets that event after every command it
   completes, so the waiter wakes once per drained command and checks again.
   The finish being waited on is still queued or running, so another set
   always follows. On the way out the waiter sets the event again, because
   `pgraph_vk_render_thread_wait_idle()` shares it: a reset here could swallow a
   set that a caller on another thread had not observed yet. An extra set
   costs that caller one more check of its queue.

`HAKUX_RENDER_WAIT=yield` keeps the old loop. The render-thread context
keeps the old loop too: it cannot wait on itself, and `wait_idle` returns
early there.

Why `idle_event` and not a new per-frame event, which the proposal above
named: the setters of `frame_submitted` are in `render_thread.c` (:153) and
`submit_worker.c` (:61). Neither file is lent to this lane, so a new event
could not be set. The submit worker is dead code (nothing calls
`pgraph_vk_submit_worker_enqueue`), and `idle_event` is the render thread's
only per-command signal. `pending_post_fence_cb` is never set to non-NULL
anywhere. If it were, a deferred finish would wait for its fence before the
idle set, and the block would return later than the spin.

`[rwait526]` (tag `hakuX-lane`, every 10 s, from the PFIFO thread): flips,
`thr_cpu_ms` and `wait_cpu_ms` of that thread, and per site calls, waits,
spun, blocked, wakes, wait wall-time p50/p99/max (10 us bins). The wait's CPU
is two `CLOCK_THREAD_CPUTIME_ID` reads per non-trivial wait, in both modes
alike.

No host compile of draw.c exists here. The helper compiled standalone
(`gcc -Wall -Wextra`, desktop and `-D__ANDROID__` with a log stub,
`.rwait_test.c`, not committed) with no warnings. Running that harness
needs an approval a headless lane cannot get, so the device run is the
first execution.

### Predictions (registered 18:31Z, before any run)

- `pacing-rwait-pgraph-inert.json`: 12 pgraph suites byte-identical,
  01e62d8d1c vs 23f0ee233f. Queued by the arms job.
- `pacing-rwait-soak.json`: one binary (23f0ee233f), A
  `HAKUX_RENDER_WAIT=yield`, B unset, both `PERF_REGIMEN=default`, Thor,
  240 s. Crimson Skies (30-capped) and Otogi (renderer-bound), 2 runs per arm.
  Legs M0, F0, W1 (premise: A spends >= 0.5 ms of wait CPU per flip on
  Crimson), H1, H2, K1 (wake-up cost <= 100 us at p99), P1, P2, H0 (no
  hang), E1 (J/frame, a labelled guess), T. Judge:
  `docs/lanes/pacing/rwait_judge.py --a ... --b ...`.

### Queued (pilot, Thor)

| id | arm |
|---|---|
| 1-1790620342-lane.pacing-1207085 | Crimson A1, yield |
| 1-1790620342-lane.pacing-1207159 | Crimson B1, block |

On resume: `python3 docs/lanes/pacing/rwait_judge.py --a <A1> --b <B1>`.
Check that F0 holds, that the windows are there, that B blocked, and that A's
wait CPU per flip is not ~0. If W1 fails (A under 0.5 ms per flip), the lever
is small on this title: say so and do not queue the rest of the Crimson runs.
If the pilot reads, write `pilots/lane.pacing.ok` (python3) and run
`bash docs/lanes/pacing/queue_rwait.sh rest` (Otogi A1/B1, Crimson A2/B2,
Otogi A2/B2; 6 x 330 s).

## Attempt 5 (2026-09-28 12:20 PDT): the pilot read, an instrument defect, the batch queued

### Why attempt 4 did not finish

It ended correctly, waiting: the Crimson pilot pair was queued on the Thor
and a `[lane.pacing] waiting:` comment named both ids. The handback job
resumed the lane once both were DONE (CI green on 0673e39c1b, no arm
verdict yet). The brief counts that resume as "attempt 2"; it is the same
PR.

### Pilot (Crimson Skies, Thor, 240 s, ref 23f0ee233f, `PERF_REGIMEN=default`)

`rwait_judge.py` over `mark gameplay` to the soak end (129 s, 13 windows,
62 gfps lines per run). No crash or ANR, no thermal pause (every cooling
device at 0 at the end), no VOID.txt.

| | A1 yield (…-1207085) | B1 block (…-1207159) |
|---|---|---|
| gfps median | 29 | 29 |
| wait CPU, ms per guest flip | 0.783 | 0.276 |
| deferred waits per flip | 4.96 | 6.22 |
| deferred wait wall, ms per flip | 0.79 | 1.19 |
| waits ended inside the 30 us poll / blocked | - | 3290 / 20023 |
| wakes per blocked wait | - | 1.0 |
| wait p50 / p99 (median of windows), us | 120 / 1110 | 160 / 1090 |
| perf-line gap max, s | 1.4 | 1.7 |
| net_w (battery + USB) | 5.96 | 5.60 |
| J per guest frame | 0.2055 | 0.1936 |

Legs on the pilot (one run per arm; the prediction's legs are pooled over
two): M0, F0 hold. W1 holds (A 0.783 >= 0.5). K1 holds (B p99 is not above
A's). P1 holds (29 / 29). H0 holds. **H1 missed**: B/A = 0.35, above the
0.25 bar. It is not a futex storm (1.0 wake per blocked wait). About six
waits per flip each poll up to 30 us before blocking, about 0.18 ms per
flip, which is most of B's 0.276. The bar did not budget the poll. It
stays as registered; the batch pools two runs per title. **H2 was
unreadable** (below). E1: B 6% lower J/frame on one run each, inside
what two runs of one arm could differ by; the batch has four per title.
The rotate site never waited in either arm (`waits=0`). On this title
the frame-rotation wait (:3953) never finds the next slot unsubmitted, so
the whole lever is the deferred finish.

### The instrument defect: `thr_cpu_ms` diffed two threads' clocks

The window's thread-CPU delta went negative (-5639, -36137, -66839 ms) and
above the window length (23398, 45619, 73718 ms in 10 s) once gameplay
began, in both arms. `wait_frame_submitted` is reached from more than one
thread: `pgraph_vk_finish` is called from the PFIFO thread, the render
thread (FLUSH), the display's present (display.c:1729) and the
surface-download paths. The 10 s window is closed by whichever thread
crosses it, and each close diffed its own `CLOCK_THREAD_CPUTIME_ID`
against the previous closer's. `wait_cpu_ms` is sound, because both of
each wait's reads are on the waiting thread.

Fixed in f53000f7e4 (log fields only): each thread keeps a thread-local
span and reports `tid= thr_s= thr_flips= thr_cpu_ms=` for its own span
when it closes a window (-1 on its first). The judge sums each thread's
CPU rate, then over threads, and divides by flips per second. Lines
without `tid=` read as UNREADABLE, never as a number. It was checked on a
synthetic fixture (two threads, one first-report -1): 2.0 ms per flip, as
constructed. Limit: a thread whose waits never close a window is not in
the thread-CPU sum. `threads` in the judge output names the tids that were.

The judge also reads power and heat now. A request.sh soak writes no
verdict.json, so it runs `title_verdict.py` on a temp copy of the result
dir (the dispatch dir is never written).

### Re-registered, and queued (Thor, ref f53000f7e4, `1-` priority)

Both predictions were re-registered on f53000f7e4 (df12e07bbf) with the
legs and thresholds unchanged. The old pilot's read is recorded in the soak
prediction's `reregistered` field. The pixel arm had not run on the old
refs. `pilots/lane.pacing.ok` carries this pilot's verdict (the previous
one kept below it).

| id | arm |
|---|---|
| 1-1790623012-lane.pacing-2311381 | Crimson A1, yield |
| 1-1790623012-lane.pacing-2311486 | Crimson B1, block |
| 1-1790623013-lane.pacing-2311543 | Otogi A1, yield |
| 1-1790623013-lane.pacing-2311591 | Otogi B1, block |
| 1-1790623013-lane.pacing-2311638 | Crimson A2, yield |
| 1-1790623014-lane.pacing-2311725 | Crimson B2, block |
| 1-1790623014-lane.pacing-2311827 | Otogi A2, yield |
| 1-1790623015-lane.pacing-2311898 | Otogi B2, block |

On resume: read VOID.txt in each, then
`python3 docs/lanes/pacing/rwait_judge.py --a <Crimson A1 A2> --b <Crimson B1 B2>`,
and the same for Otogi. First check that the new window lines carry
`tid=` and that `thr_cpu_ms` is non-negative and under `thr_s` x 1000. If
not, H2 stays unreadable: say so, and do not re-run for it. Apply the legs
as registered, post the table on #526 and the PR, and mark #572 ready.

### For the next lane

- Do not diff a per-thread clock across a window that any thread can close.
- `title_verdict.py` gives a soak's power (`net_w`, `j_per_frame`) from
  thermal.jsonl. A soak's result has no verdict.json of its own.
- A request.sh soak's power is 5 samples over about 130 s of gameplay. One
  run per arm is not a J/frame comparison.

## Attempt 6 (2026-09-28 16:20 PDT): the batch read; Otogi void, re-queued

### Why attempt 5 did not finish

It ended correctly, waiting on its eight Thor soaks. They all finished;
the handback job resumed this session. Nothing was lost.

### Crimson Skies (Thor, f53000f7e4, 2 runs per arm, all valid)

Order A1 B1 A2 B2. Start xo-therm: A1 46.9 C (cold), B1 66.1, A2 69.3,
B2 68.5. No run paused; no crash or ANR; 13 windows each, all with
`tid=`, `thr_cpu_ms` inside `thr_s` x 1000.

| | A yield | B block | leg |
|---|---|---|---|
| gfps median | 29 / 29 | 29 / 29 | P1 holds |
| wait CPU, ms per flip | 0.853 | 0.259 | W1 holds (A >= 0.5); H1 B/A 0.30, bar 0.25: **misses** |
| thread CPU, ms per flip (all reporting tids) | 17.48 | 18.38 | H2: needs A-B >= 0.36; got -0.90: **fails** |
| the PFIFO tid alone, ms per flip | 16.77 | 16.77 | (not a leg) |
| deferred wait p99 us (median of windows) | 1025 | 1065 | K1 holds (<= A+100) |
| perf gap max s | 1.65 | 1.9 | H0 holds |
| net_w per run | 5.95, 5.33 | 6.47, 6.28 | |
| J/frame pooled | 0.1976 | 0.2232 | E1 (a guess): **misses** |

Reading:
- The mechanism does what it says: 87% of B's waits block, 1.0 wake
  per blocked wait, and the time spent spinning in the waits falls by
  0.59 ms per flip (70%). H1 misses its 0.25 bar as it did in the pilot:
  the residual is the 30 us poll on the ~13% of waits that end inside it
  plus the futex call on the rest.
- The removal does not show in the thread's CPU. The 0.59 ms falls inside
  the run-to-run spread (A1 vs A2 on the PFIFO tid: 15.9 vs 17.6 ms per
  flip). The "all tids" row is higher in B because a second tid reports in
  both B runs and in only one A run; it is not a like-for-like sum.
- Power: B minus A net_w per pair is +0.52 and +0.95 W (pilot: -0.36 W).
  0.59 ms per flip at 28.4 flips/s is 17 ms/s of CPU, about 1.7% of one
  core, which is tens of mW. The pair differences are 20-40 times that and
  change sign across pairs. The 5-sample power record cannot see this
  change, in either direction. It is not a power win on this evidence, and
  the release note now says so.

### Otogi: all four runs VOID, re-queued at 400 s

`mark gameplay` is about 270 s into the otogi route (48 s boot wait, START,
25 s, 6 A presses at 5 s, 35 at 4 s, B, 3 s, plus the 2 fps menu). The
soaks were 240 s, so none reached it. The intro frames match
lane.slowtier2's 550 s run, which marked gameplay 165 s after the intro
shot, so the route itself works. That was my registration error: I did
not add up the route's waits against `seconds`.

P2 (a renderer-bound title's fps does not fall by more than 1) is the
safety leg for the wake-up latency. B's waits take 0.25 ms longer per flip
on Crimson, and that is harmless there because the title is capped. So it
gets read before the PR folds. New prediction
`docs/testing/predictions/pacing-rwait-otogi.json` (8f073fd457): same
binary, arms and legs, 400 s, M0 at >= 8 windows. Queued A1 B1 B2 A2:

| id | arm |
|---|---|
| 1-1790637578-lane.pacing-3957178 | A1 yield |
| 1-1790637578-lane.pacing-3957219 | B1 block |
| 1-1790637578-lane.pacing-3957257 | B2 block |
| 1-1790637579-lane.pacing-3957294 | A2 yield |

On resume: `python3 docs/lanes/pacing/rwait_judge.py --a <A1 A2> --b <B1 B2>`,
apply P2, F0, K1 and H0 (a run with `first_pause_s` inside the window
is not read for P2), post on #526 and #572, and mark #572 ready if P2
holds. If P2 fails, the next step is a longer poll bound (K1's note), not
reverting the block.

### For the next lane

- Add up a route's waits before choosing `seconds`. A soak that ends
  before `mark gameplay` is VOID in every arm.
- A 1-2% of one core CPU saving is below what the 5-sample power record
  resolves. Price one with thread CPU over longer runs, not with J/frame.

## Attempt 7 (2026-09-29): the Otogi read; #572 ready

### Why attempt 6 did not finish

It ended correctly, waiting on the four Otogi re-runs named above. All four
finished DONE; the handback job resumed the lane. Nothing was lost.

### Otogi (Thor, f53000f7e4, 400 s, 2 runs per arm, all valid)

No VOID.txt. Every run marked gameplay and has 14 windows (M0 needs 8).
Start xo-therm: A1 48.2 C, B1 72.8, B2 67.6, A2 63.4. No run paused, no
cooling device above 0 at the end. No FATAL, ANR or crash line in any
logcat.

| | A yield (A1, A2) | B block (B1, B2) | leg |
|---|---|---|---|
| gfps median | 29 / 29 | 29 / 29 | P2 (B >= A - 1): holds |
| mode lines, blocked waits | yield, 0 | block, 4135 + 4165 | F0 holds |
| wait CPU, ms per flip | 0.2259 | 0.0510 | H1 B/A 0.23, bar 0.25: holds |
| wakes per blocked wait | - | 1.0 | |
| deferred wait p99 us (median of windows) | 1250 | 1282.5 | K1 (<= A+100): holds |
| deferred wait wall, ms per flip | 0.230 | 0.276 | |
| thread CPU, ms per flip (one tid each) | 9.02 | 9.05 | not a leg on Otogi |
| perf gap max s | 1.1, 1.9 | 1.7, 1.7 | H0 holds |
| net_w per run | 5.45, 4.79 | 5.29, 5.12 | |
| J/frame pooled | 0.1734 | 0.1759 | E1 (a guess): misses by 1.4% |

Reading:
- **P2 holds, but not in the case it was written for.** The prediction
  called Otogi renderer-bound at 12.6 fps. In this window, after the
  route's gameplay mark, it ran at 29 fps in all four runs, with one
  deferred wait per flip. So these runs are a second capped title, and P2
  holding says nothing about a renderer-bound one. The wake-up cost is
  bounded instead by K1: B's waits end 30-40 us later at p50 and p99, about
  0.05 ms per flip. On a title that does not reach its cap, that could cost
  fps. Neither title here tested it.
- H1 holds here: 0.23. Otogi's waits are longer (p50 160 us), so almost
  all of them block (8300 of 8308), and the 30 us poll is a smaller share.
- E1: the A pair differs by 0.66 W, and B sits between A's two runs. As on
  Crimson, the power record cannot resolve a saving this small.

### Verdict on #572

Pixels: `verified` by the arms job (pgraph inert). Every safety leg holds
on both titles: F0, K1, H0, and P1/P2 at the cap. The removed spin is
0.59 ms per flip on Crimson and 0.17 ms on Otogi. Neither thread CPU nor
J/frame can see it, so the release note claims no fps or power change.
#572 is marked ready.

### For the next lane

- A title's fps in a prediction comes from a run of the same route window.
  Otogi's 12.6 fps was from another place in the game, and the route's
  gameplay window runs at the cap.
- To test the wake-up cost on a renderer-bound title, pick one whose route
  window is measured below its cap on the Thor. Read `[rwait526]` p99 and
  gfps together.
