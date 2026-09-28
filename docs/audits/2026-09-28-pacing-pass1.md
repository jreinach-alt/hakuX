# Audit pass 1: PR #529 (lane/pacing)

PR: #529, "lane.pacing: sleep the frame limiter, request 60 Hz for the game surface (#526)"
Head audited: 29ddd809d1 (merge base with master d684d57e83)
Scope: the diff against master. Code: `ui/xemu.c` and
`android/app/src/main/java/org/libsdl/app/SDLSurface.java`. Also five
predictions under `docs/testing/predictions/pacing-*.json` and the lane
tools and notes under `docs/lanes/pacing/`. CI (`build`, both runs) is green
on the head.

Verdict: **one MEDIUM, three LOW. needs-remediation.**

## What the change does

1. The Android frame limiter in `sdl2_gl_refresh` now waits through
   `android_limiter_wait`. By default it sleeps to `next_render_ns` with
   `clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME)`, retrying on EINTR.
   `HAKUX_LIMITER=spin`, or `use_rt_clock == 0`, selects the old
   sleep-then-spin wait unchanged.
2. `[pace526]` counters: per-release lateness histogram, thread CPU inside
   the wait, thread and process CPU per 10 s window, guest flips, and
   present intervals within 1 ms of 16.67 ms. One line every 10 s.
3. `HAKUX_VSYNC=0|1` overrides the swap interval from the pref, logged once.
4. `SDLSurface.surfaceChanged` calls `requestGameFrameRate`. On API 30+ it
   logs the display, registers a `DisplayListener` for `changed` lines, and,
   unless `HAKUX_SURFACE_RATE=off`, calls `setFrameRate(60, FIXED_SOURCE)`
   (with `CHANGE_FRAME_RATE_ALWAYS` on 31+). `=mode` also sets
   `preferredDisplayModeId` to a 60 Hz mode of the current size.

## Checked and found sound

- **The sleep targets the same instant the spin did.** `qemu_clock_get_ns
  (QEMU_CLOCK_REALTIME)` is `get_clock()`, which reads `CLOCK_MONOTONIC`
  when `use_rt_clock` is set (`include/qemu/timer.h:839`). The mode function
  falls back to spin when it is not, so the absolute deadline is never
  interpreted on the wrong clock.
- **The sleep is bounded.** `next_render_ns` is at most `now + 16.67 ms`
  when it is set (the `now > next + min_frame_ns` reset and the `+=` both
  keep it within one frame of the release time). A sleep entered from the
  `now < next_render_ns` branch therefore lasts under one frame, as the old
  `SDL_Delay` did. No event poll is lost that the old path made: both poll
  once before the wait and return.
- **`clock_nanosleep` error handling.** It returns the error number rather
  than setting `errno`; the loop compares the return to `EINTR`, which is
  correct. The only other error, `EINVAL`, needs a negative or out-of-range
  `tv_nsec`, which `deadline % NANOSECONDS_PER_SECOND` on a positive
  monotonic deadline cannot produce.
- **The percentile helper.** `late_hist` sums to `waited` (each counted
  release adds one bin and one `waited`), `want = ceil(q*n)`, and `n == 0`
  returns -1 instead of reading bin 0. Lateness is clamped at 0 before
  binning and the last bin holds the overflow, so the index never exceeds
  `PACE526_BINS`.
- **`pending_wait` pairs a wait with its release.** It is set only after a
  wait and cleared on the next release, so a frame that was already late
  (no wait) is counted in `rel` but not in the lateness histogram, as the
  line's fields say.
- **Non-Android builds are untouched.** Every new C block is inside
  `#ifdef __ANDROID__`; the desktop path keeps `SDL_Delay(1)`.
- **Vsync override.** Only the exact strings `0` and `1` are accepted;
  anything else keeps the pref. The pref and its default are unchanged.
- **The env reader** reads `x1box_prefs`/`env_vars`, the same pref the
  settings screen and dispatcher write, and matches on `KEY=` at line start.

## Findings

### MEDIUM 1: the shipped `HAKUX_SURFACE_RATE` default is "request 60 Hz", not `off` as the PR and NOTES state

`SDLSurface.requestGameFrameRate` returns early only for `"off"`; with the
variable unset it calls `surface.setFrameRate(60, FIXED_SOURCE[, ALWAYS])`.
The code comment says so ("unset requests 60 Hz"), and the display
prediction's B arm uses `b_env: []` to get exactly that request. But the PR
body ("The default is still `off`") and NOTES (line 174, "`off` (the
default)"; line 286, "The `HAKUX_SURFACE_RATE` default is `off` ... Making it
the default is a product call") both say the default makes no request.

Failure scenario: a user on a device with a 120 Hz panel and no user-level
`min_refresh_rate` pin (the stock setting on most 120 Hz phones and
handhelds) installs this build. With no env var set, the game surface now
votes 60 Hz with `CHANGE_FRAME_RATE_ALWAYS`, and the panel switches to 60 Hz
for the game. That is a default change nobody measured: the Nova's user pin
overrode the request (no effect), and the Thor's panel was already at
60 Hz (no-op). So the one configuration in which the default does anything
was never run, and the PR's own reasoning ("a product call") says it should
not have been made in this lane. The release note does not mention it.

Remediation: pick one and make code, PR body and NOTES agree.
(a) Make unset behave as `off` (request only for an explicit
`HAKUX_SURFACE_RATE=on|mode`), which matches the stated default and the
"product call" line; the display prediction's B arm then needs its env set
explicitly (it can stay registered as-is only if its B arm is re-run with
the new value, since its `b_env` would no longer select the request).
(b) Keep the request as the default, correct the PR body and NOTES, add it
to the release note, and say plainly that its effect on an unpinned 120 Hz
panel is unmeasured.

### LOW 1: the `DisplayListener` is never unregistered

`mRateListener` is registered with the process-wide `DisplayManager` and
never removed (no `unregisterDisplayListener` in `surfaceDestroyed` or on
activity destroy). It holds the `SDLSurface` and so its activity. Blast
radius is small because `MainActivity` runs in its own `:xemu` process and
kills it on exit (`MainActivity.kt:339`), and `configChanges` covers
rotation and resize. If the activity is ever recreated in the same process,
the old surface leaks and keeps logging `changed` lines against
`mDisplay`. Unregister in `surfaceDestroyed` (and null the field).

### LOW 2: the `[pace526]` counters and log line are always on in release

Two `CLOCK_THREAD_CPUTIME_ID` reads per limiter wait, one per release, one
`qemu_clock_get_ns` per present, and a logcat line every 10 s ship
unconditionally. The cost is small (vDSO-or-syscall clock reads at 60 Hz,
not a hot inner loop, so not the `SYS_gettid` hazard in AGENTS.md), and the
line is useful to the arms. Consider gating the report behind an env var
once the lane's measurements are done, so the shipped build does not log
every 10 s forever.

### LOW 3: the pixel leg is a cross-device pair

`pacing-pgraph-inert.json`'s base re-run ran on the Nova and the fix arm on
the Thor. The NOTES say so. Nova and Thor have agreed per capture before,
and 681 of 682 rows are identical, so this does not change the verdict, but
a same-device pair would remove the question. Not a code defect.

## What pass 2 must verify

- MEDIUM 1: with no `HAKUX_SURFACE_RATE` in `env_vars`, the code path taken
  matches the default the PR body, NOTES and release note state; and if the
  default makes a request, the PR says what was (not) measured about it.
