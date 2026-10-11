# lane.fgrace1010 -- the display guard's "guest exit mid-route" leg loses a race and fails folds (#433, 0.5)

State: ready

Lane: fgrace1010          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 510dacff37
Files: docs/testing/jobs/selftest.d/99-display-covered.sh, docs/lanes/fgrace1010/NOTES.md, docs/lanes/fgrace1010/PR.md
Prediction: none: harness only
Needs device: no    Needs NDK: no
Release note (none): harness only

## The defect

Audit L3 ("guest exit mid-route", `docs/testing/jobs/selftest.d/99-display-covered.sh`)
intermittently failed with only `no-STOPPED-line` under host load (nightlynotes1009 10-09
21:20, surfgpu1009 10-09 23:32, pfifowait1009 10-10 04:59). `soak_title.sh` has two
independent pollers that each correctly detect a dead guest and stop the route without
voiding it: `fg_watch`'s post-kill `ps` (which writes `ROUTE STOPPED: ...`) and the main
hold loop's `alive()`/`probe()` (which writes `guest exited after Ns of Ms` and ends the
soak -- which then kills `fg_watch`'s PID, possibly before it gets to log its own line).
The leg ran both pollers at the identical 0.2 s cadence, so under a loaded host which one
notices first is a near coin-flip, not a cadence mismatch. **No defect in `soak_title.sh`**
-- both outcomes are correct and this race exists on real devices too; left untouched.

## Fix: (a), accept either stopper

Chosen over (b) (force the fixture to always let the watcher win) because (b) would hide a
property the real device has too, and would only ever exercise one of two code paths that
are both live in production. The leg's own claim ("the run is an exit, not a
not-foreground void") holds regardless of which poller wins, so the assertion now accepts
either: the watcher's `ROUTE STOPPED:` line, or the hold loop's `guest exited after...`
line -- both still gated on no `not-foreground:`/`ROUTE ABORTED` and no B press.

## Race reproduced on purpose

`SOAK_POLL_S=0.002 FG_POLL_S=0.3` (hold loop polling far faster than the watcher) makes
the hold loop win reliably: 15/15 standalone repro runs outside the fragment, and 4-5 of 6
inside the fragment's own new regression block every time it runs. The **old** assertion
fails on every one of these (`no-STOPPED-line`); the **new** one passes on every one of
these and is unchanged on the normal 0.2/0.2 run. That skew is now a permanent block in the
fragment ("Audit L3 holds whichever poller notices the guest first"), run 6x per pass.
Full writeup, including a fixture-timing pitfall found while tuning the skew
(`FG_POLL_S=1` let the route's own scripted B press fire before the simulated death could
activate, at any `SOAK_POLL_S`), is in `docs/lanes/fgrace1010/NOTES.md`.

## Mutants still turn the leg red

Re-verified against the relaxed assertion, both still red:
* "no watcher while the route plays" (existing mutant, line ~466 pre-change):
  `why=[no-stop-signal B-PRESSED]`.
* "dead guest voided as not-foreground" (the defect Audit L3 was written for; built fresh
  for this change, `fg_watch`'s guest-death special case removed): `why=[no-stop-signal
  VOIDED]`.

## 5x run, SELFTEST_ONLY=99-display-covered.sh

All 5 green, `24 passed, 0 failed` every time. The new race block's split across the 5
runs (silent == hold loop won / no ROUTE STOPPED line, out of 6 sub-runs each pass):
3, 4, 4, 3, 3 -- always a mix of both outcomes, never voided, never B-pressed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
