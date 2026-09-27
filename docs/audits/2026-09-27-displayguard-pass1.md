# Audit pass 1: lane.displayguard (PR #495, #494)

Head audited: `fbe37e204e`. I read the diff of `docs/testing/devices.sh`
(`display_clear`, `hakux_in_front`), `docs/testing/soak_title.sh` (the refusal,
`fg_wait`, `fg_watch`, the black-frame guard, `SOAK_RC`),
`docs/testing/title_verdict.py` (`void`) and the selftest and NOTES, against
how `dispatcher.sh` calls the soak (it ignores the exit code and writes the
result either way) and against the `void` consumers (none outside
`title_verdict.py`; `status_html.py` shows it as a failure).

**Result: no HIGH, no MEDIUM, four LOW.** Next state: `needs-audit-2`.

## What I checked and found sound

- The refusal (exit 4) runs after the force-stop and wake, and before
  `arm_audio`, `perf_enter`, the logcat stream and `am start`. So clearing the
  EXIT trap skips nothing that has already happened, and the lease is removed
  by hand. The dispatcher's frame-capture loop is stopped by the dispatcher.
- `start_route` returning 1 leads to `exit 5` with the EXIT trap still set.
  `release()` runs, so MAX mode, the title and audio are all put back.
- `fg_watch` inherits `ROUTE_PID` because it is forked after `ROUTE_PID=$!`.
  It writes `FG_FLAG`, and `$$` names the same path in the subshell. The
  zombie check on `/proc/<pid>/stat` stops it from acting on a route that has
  already finished. `stop_route` reaps it before it touches route.sh.
- `display_rc=$?` after `DISPLAY_STATE=$(...)` carries the function's status.
  Every new variable read under `set -u` has a default.
- In `title_verdict.py` the regex is anchored at the start of a line, so
  the `FOREGROUND: waiting: not-foreground: ...` lines do not void a run; only
  `fg_abort`'s bare line does. A void run has no fps windows, and the "fewer
  than two perf lines" failure is not added on top of `void`.
- The trailing `exit "$SOAK_RC"` turns a previously implicit status into 0 on
  the normal path. No caller reads it.

## Findings

### L1 (LOW): black frames from hakuX itself are reported as a harness void

`soak_title.sh:~500` and `title_verdict.py:~244`. `display-black` fires
whenever every route frame is under 12,288 B. It cannot tell a foreign cover
apart from hakuX drawing black, and the line it prints says the cause is the
cover: "nothing on display 0 was hakuX's".

**Scenario:** a title boots, flips and plays audio, but its output is black
because of a hakuX render defect. Every route frame is about 10.9 KB. The
verdict's first failure becomes `void: display-black ...` and every fps field
is null. Its NOTES (Do not repeat) reason that "the route saw nothing either",
which is true for a near-black loading screen. For a render bug, though, the
cause is hakuX, and a triager reading `void` treats it as a harness rerun, not
a rendering issue. The pass/fail answer is still right (not Playable), so this
is LOW.

**Suggested fix (optional):** after the hold, run `display_clear` a second
time. If it reads `display-clear`, log something like `render-black:` (a title
failure) rather than `display-black:` (void). For the frames-only path, used
on old run.logs, void only when the run.log has no `display-clear:` line.

### L2 (LOW): two consecutive adb unknowns abort and void a route soak

`soak_title.sh` `fg_watch`, and `hakux_in_front` with `ADB_RETRIES=0`. Two
failed reads in a row, about 4 s apart, abort the route. `alive()` in the same
file was changed on 2026-09-25 so that a vsock drop is no longer a result.

**Scenario:** a two-call `UtilAcceptVsock` burst at 900 s into a 1200 s
confirmation run voids the run. The NOTES chose this on purpose ("a void run
costs a re-queue, and input with nobody watching can cost the owner's save").
I agree with the direction. I record it only so the cost can be seen if route
soaks start coming back `not-foreground: unknown` in bulk. A single retry
inside the read (`ADB_RETRIES=1`, ~2 s) would cut the false rate without
widening the unwatched window much.

### L3 (LOW): a title that exits mid-route can be labelled not-foreground before it is labelled exited

In the hold loop the `FG_FLAG` check runs before `alive()`, and `fg_watch`
polls every 2 s against the loop's 5 s.

**Scenario:** the guest process dies and the app closes to the launcher. The
watcher sees the launcher in front first, so run.log gets
`not-foreground: <launcher>` and `soak aborted`, not `guest exited after Ns`.
`crash` stays true only if a `hakuX-crash` E/F line was logged. Otherwise the
verdict reads void where it used to read crash. A fix would be to run `alive`
before honouring the flag, or to have `fg_watch` check `$PKG:xemu` before it
calls the answer not-foreground. Whether the app actually leaves the front
when `:xemu` dies was not measured.

### L4 (LOW): the `fg_wait` remedy re-issues the title's VIEW intent

If hakuX is running the title but focus is elsewhere, `am start ... --es
rom_path` may restart the guest after `soak start` has already been logged.
Boot timing for that run would then be measured from the wrong moment. This is
rare (it needs the remedy path) and the effect is bounded.

## For pass 2

With only LOWs there is no remediation to verify. Pass 2 can confirm that the
head is still `fbe37e204e` (or that later commits do not touch the paths
above), that the selftest `99-display-covered.sh` is still green in CI, and
whether the lane chose to act on L1.
