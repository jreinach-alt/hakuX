# lane.fgrace1010 -- Audit L3 ("guest exit mid-route") loses a race and fails folds (#433, 0.5)

Brief: `docs/testing/jobs/selftest.d/99-display-covered.sh`'s Audit L3 leg intermittently
failed with `no-STOPPED-line` under host load (nightlynotes1009 10-09 21:20, surfgpu1009
10-09 23:32, pfifowait1009 10-10 04:59). Decide and fix.

## Root cause, confirmed by reading `soak_title.sh`, not just the brief

Two independent pollers both detect the same real event (the guest process died) and
both correctly stop the route without voiding it:

* `fg_watch` (background subshell, `soak_title.sh` ~832-864): after it kills the route's
  own PID on seeing the launcher in front, it does one more `ps -A -o NAME` to tell a real
  "guest exited" apart from a real "not-foreground" void, and on the exited case logs
  `ROUTE STOPPED: <pkg>:xemu is gone, so the guest exited (...)`.
  Polled at `FG_POLL_S` (prod default 2 s; the selftest overrides to 0.2 s).
* The main hold loop's `alive()`/`probe()` (~886-963) polls the same guest liveness on its
  own schedule (`SOAK_POLL_S`, prod default 5 s, selftest 0.2 s) and, if it notices the
  guest gone first, logs `guest exited after Ns of Ms` and ends the soak, which calls
  `stop_route()` -- which kills `fg_watch`'s PID, by PID, possibly mid-sleep, before
  `fg_watch`'s own post-kill `ps` ever runs.

Both outcomes are correct: the route stops, nothing reads `not-foreground`/`ROUTE ABORTED`,
and B is never pressed. Only which line appears in the log differs. The selftest ran both
pollers at the *same* 0.2 s cadence, so under a loaded host the winner is a near coin-flip
decided by OS scheduling, not a cadence mismatch -- confirmed by grepping the fragment:
`SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1` and `FG_POLL_S=0.2` were already identical before this
change.

**No defect in `soak_title.sh`.** Left untouched, per territory and per the brief's "only
touch it if a real product defect is found" -- there isn't one; the race is a harmless
property of two equally-valid liveness checks, and it exists on real devices too, not just
in the fixture.

## Fix chosen: (a), accept either stopper

Rejected (b) (force the fixture to always let the watcher win): that would hide a property
the real device has too (both pollers really do race there), and would leave the test
exercising only one of two code paths that are both live in production. (a) matches what
the leg's own comment claims to guard ("the run is an exit, not a not-foreground void") --
that claim is true regardless of which poller gets there first, so the assertion should
accept both.

New assertion (same `$DG/run/run.log` and `$DG/calls` the old one read):
* pass: `ROUTE STOPPED: ...` line **or** `guest exited after...` line (old code required
  only the first and separately required the second elsewhere, so it already always had
  the `guest exited` line available as a fallback signal -- it just wasn't being used as one)
* fail if `not-foreground:`/`ROUTE ABORTED` appears (void)
* fail if a B sendevent appears (watcher never got control of the route's own kill)

## Reproducing the race on purpose

Standalone repro first (`/tmp/race-repro.sh`, outside the worktree, deleted when the
session's scratch work was done -- never committed, never named like a stdlib module).
Driving the real `soak_title.sh` with `SOAK_POLL_S` far below `FG_POLL_S` reliably makes the
hold loop win:

* `SOAK_POLL_S=0.002 FG_POLL_S=1`: 6/6 runs instead produced a **B-PRESSED** failure, not a
  race demonstration -- a test-harness bug, not the production race. Cause: the fake adb's
  "guest gone" response only activates once the watcher's own poll counter (`fgn`) reaches
  5, and `fgn` only increments on the watcher's polls. At `FG_POLL_S=1` those 4 polls take
  ~4 s, past the fixture route's `wait 2` -> `press B` transition at ~2 s, so the route
  pressed B on its own schedule before the simulated death could ever fire, independent of
  `SOAK_POLL_S`. Fixed by keeping the watcher fast enough to clear the threshold before the
  route's own timer does: `FG_POLL_S=0.3` (4 polls land by ~1.2 s, safely under 2 s).
* With `SOAK_POLL_S=0.002 FG_POLL_S=0.3`: 15/15 repro runs had the hold loop win (no
  `ROUTE STOPPED:` line, `guest exited after...` present, nothing voided, no B press). The
  **old** assertion (`no-STOPPED-line` required) fails on every one of these. The **new**
  assertion passes on every one of these, and unchanged on the normal (0.2/0.2) run.

This skew (`SOAK_POLL_S=0.002 FG_POLL_S=0.3`) is now a permanent regression block in the
fragment itself ("Audit L3 holds whichever poller notices the guest first"), run 6x per
selftest pass so the hold-loop-wins path is exercised every time the fragment runs, not
just in a throwaway repro. Typical split across runs: 4-5 of 6 silent (hold loop won),
1-2 with the `ROUTE STOPPED:` line (watcher won) -- both must show no void and no B press,
and the block fails loudly (`bad`) if either ever shows up.

## Mutants re-verified against the relaxed assertion

Built in `/tmp/mutant-test` and `/tmp/mutant-nowatch` (outside the worktree, not committed):

* **No watcher while the route plays** (existing mutant, `fg_watch &` replaced by `: &`):
  still red. `why=[no-stop-signal B-PRESSED]` -- with no watcher at all the route plays to
  its scripted B press with no stop and no exit line either, so this trips both of the new
  assertion's fail conditions as well as the old one's.
* **Dead guest voided as not-foreground** (the defect Audit L3 was originally written for;
  `fg_watch`'s guest-death `ps_out` special case removed, so a dead guest falls through to
  `fg_abort`): still red. `why=[no-stop-signal VOIDED]`.

Both mutants still turn the leg red under the new, relaxed assertion -- the relaxation
widened which *passing* behavior is accepted, not which *failing* behavior is caught.

## 5x clean run (SELFTEST_ONLY=99-display-covered.sh)

All 5 runs: `selftest: 24 passed, 0 failed`. Audit L3's race block split 4-5/6 silent
(hold loop won) across runs, 1-2/6 with the watcher's line, every run -- see PR.md for the
exact per-run counts.

## What the next lane should not repeat

If you touch this fragment again and need to simulate "guest gone" in the fake adb: the
simulated death only becomes visible to a poller once the **watcher's** poll counter
(`fgn`, incremented only by `fg_watch`'s own `dumpsys input` reads) crosses the fixture's
threshold -- it is not driven by wall-clock time or by `SOAK_POLL_S` at all. A watcher poll
rate slower than the route's own scripted timing (e.g. `FG_POLL_S=1` against a `wait 2`
route) will let the route's own B press fire first and produce a misleading
B-PRESSED failure that looks like a race bug but is a fixture-timing bug.
