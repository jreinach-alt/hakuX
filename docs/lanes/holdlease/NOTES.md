# lane.holdlease

The Stop hook (`docs/testing/stop-emulator.sh`) killed the app on a HELD
handheld. Toolsmith defect 21 (filed 2026-09-25 15:15 PDT), never landed until
this lane.

## The defect

The hook force-stops `com.jreinach.hakux*` and sends `KEYCODE_SLEEP` on every
attached handheld at every session's turn end, unless the shared lease or that
device's lease was touched < 90 s ago. It never read `$DISPATCH_DIR/hold/<label>`.
A hold stops the dispatcher claiming, so nothing refreshes the per-device lease
while a device is held: every held session (a pilot, `profile_ab.sh`, a title
push, a driver run) was killed by the next turn end of any other session.
Evidence: the Nova, 2026-09-26 16:24:25 PDT, `forceStopPackage:
com.jreinach.hakux.debug` mid-Crimson (lane.buildflags427 arm B; arm A 15:18
same shape, PR #435, #444); lane.perfregimen's first Nova pilot VOID (PR #444).

## The change

- `device_lease()` became `device_label_lease()`: one devices.sh subshell
  yields the label and the lease path.
- `held_by <label>`: `$DISPATCH_DIR/hold/<label>` exists (DISPATCH_DIR resolved
  with the dispatcher's own default, `/home/justin/hakux-work/dispatch`) and
  `<label>.why` does not mention "battery" (case-insensitive). A held device is
  skipped before any adb call: no `ps`, no force-stop, no sleep.
- A battery hold falls through to the normal stop + sleep: there the device is
  held so it charges, and sleeping it is the point.
- No new sleep anywhere: the holder sleeps the device when it lifts the hold.
- Exit 0 is unchanged.

## Selftest: `jobs/selftest.d/79-stop-hook-hold.sh`

Runs the hook from a scratch copy of `docs/testing` with devices.sh's lease path
sed'd under the test dir (the real `/tmp/hakux-device-lease.<label>` is touched
live by `hakux-holdlease.service` for a held device: reading it would make leg
(a) pass on the old hook for the wrong reason). adb is a shim that logs every
call; verdicts are read from that log per serial. `SH_HOOK` selects the hook
under test.

| leg | fixture | fails when |
|---|---|---|
| (a) | Nova held (title push), both leases 10 min stale | the hook ignores the hold (Nova stopped/slept/touched); or skips everyone (Thor not stopped) |
| (b) | Nova held, `.why` "Battery: ..." | the hook honours a battery hold |
| (c) | no hold, Thor lease fresh | the hold check broke the per-device lease |
| (d) | no hold, no fresh lease | the hold check skips an unheld, unleased device |

New hook: 16 ok, 0 FAIL.

origin/master's hook (5172e9ac67), leg (a) fails as it must:

```
  FAIL (a) held Nova was stopped or slept: -s ee317437 shell ps -A -o NAME;-s ee317437 shell am force-stop com.jreinach.hakux.debug;-s ee317437 shell input keyevent KEYCODE_SLEEP;
  FAIL (a) adb calls on the held Nova: (same three calls)
pass=14 fail=2
```

Mutant with the battery exception removed: leg (b) fails (2 FAIL), every other
leg passes.

## Retires

Host mitigation `hakux-holdlease.service` (touches
`/tmp/hakux-device-lease.<label>` every 20 s for a non-battery hold). It can go
once this is folded AND no live session still runs the old file. The hook is
`$CLAUDE_PROJECT_DIR/docs/testing/stop-emulator.sh`, i.e. each session's own
checkout: a lane worktree branched before the fold keeps the old hook until it
merges master. Retire the service when every running worktree's copy contains
`held_by`, not at fold time.

## Do not repeat

- The full `jobs/selftest.sh` runs past the Bash tool's 10-minute limit; run it
  in the background of the session, not in the foreground.
