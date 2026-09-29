# lane.fgunknown (#592): an unreadable foreground read is not an unknown one

## The defect

`hakux_in_front` (docs/testing/devices.sh) threw away `adb_call`'s exit code and
sent stderr to /dev/null. A read that hung (rc 124) or failed left empty stdout,
and the awk printed `foreground-unknown: <serial> answered no FocusedDisplayId`,
which is also the answer for a device that replied without the field.
`fg_watch` (docs/testing/soak_title.sh) aborts a route on two unknowns in a
row, so two hung reads aborted runs in which hakuX held the screen. That
happened in seven runs (the brief lists them), all on the Nova, including
`1-1790624589-forzadecay414-3394871` at 95.1 C, where the two reads took 26 s
(two 10 s timeouts) and logcat shows hakuX still drawing after the abort.

## What changed

- `hakux_in_front` keeps adb_call's rc. It returns **3**,
  `foreground-unreadable: <serial> <reason>`, for three reasons: `adb hung (no answer in Ns)`
  (rc 124), `adb failed (exit N)` (any other non-zero rc, after adb_call's one
  retry), and `adb answered nothing` (rc 0, blank output). 0/1/2 keep their
  meaning. 2 is now only a device that answered without a FocusedDisplayId, or
  without a focused window on display 0.
- `fg_watch` counts unreadable reads apart from unknowns: `FOREGROUND: <line> (n/FG_UNREADABLE_MAX)`,
  and it aborts at `FG_UNREADABLE_MAX` in a row (default **5**) as
  `not-foreground: unreadable (...)`. A hung read costs its 10 s timeout plus
  the 2 s poll, so 5 is about 60 s. A read that fails fast (adb exits at once,
  one 2 s retry) costs about 6 s, so 5 of those is about 30 s. That is shorter,
  and on the safe side. The 2-read rule for exit 2 and the immediate abort for exit 1
  are unchanged. Any readable answer clears the unreadable count, and in front
  clears both. An unreadable read neither adds to nor clears the unknown
  count, because it says nothing about focus.
- `fg_wait`, before the first input, **treats unreadable like unknown**. It waits
  FG_WAIT_S, re-issues `am start --display 0` once, waits FG_REMEDY_S, then
  aborts with `not-foreground: unreadable (...)` and sends no input. I chose
  not to give it a longer bound: before the first input there is nothing to
  lose by refusing, and a route that has not started has no evidence yet that
  hakuX holds focus.
- No path takes 2 or 3 as in front. The end-of-hold black-frame guard still
  counts anything but 0 as display-black.

The 60 s window is the trade-off to know about. For up to about a minute of hung
reads the route keeps sending input without a confirmed foreground. When
adb hangs, the route's own `sendevent` calls go through the same adb, so
little of that input lands. The 09-27 Lime3DS incidents were read as
`not-foreground` (exit 1), which still aborts on one read.

## Proof

`docs/testing/jobs/selftest.d/99-fg-unreadable.sh` uses a stub adb whose Nth
`dumpsys input` read serves `fg.N`, where `HANG` execs `sleep 30` past
`ADB_QUICK_TIMEOUT=1` and `FAIL` exits 1.

This branch, `SELFTEST_ONLY="99-fg-unreadable 99-display-covered 99-usb-dialog"`:
41 passed, 0 failed.

```
  ok   (a) hung read: exit 3, foreground-unreadable, adb hung
  ok   (a) failed read: exit 3, foreground-unreadable, adb failed
  ok   (a) empty read: exit 3, foreground-unreadable, answered nothing
  ok   (b) an answer without FocusedDisplayId: exit 2, foreground-unknown, as before
  ok   (c) unreadable x3 then in front: counted 1/5..3/5, the route plays on, nothing aborted
  ok   (d) unknown x2: aborted before the second press, as before
  ok   (d) unreadable x FG_UNREADABLE_MAX (3): aborted as not-foreground: unreadable
  ok   (e) not-foreground x1: aborted at once
  ok   (f) unreadable before the first input: one am start remedy, no input, exit 5 not-foreground: unreadable
```

The same fragment against `origin/master` @ 2c950e0a1e's docs/testing
(`git archive`, sourced with `TESTING` pointed at it). (a) and (c) fail as the
brief requires. The unreadable-bound and wait legs fail on their words only:
master also aborts there, but it calls the cause `unknown`.

```
  FAIL (a) hung read: [2|foreground-unknown: ee317437 answered no FocusedDisplayId]
  FAIL (a) failed read: [2|foreground-unknown: ee317437 answered no FocusedDisplayId]
  FAIL (a) empty read: [2|foreground-unknown: ee317437 answered no FocusedDisplayId]
  ok   (b) an answer without FocusedDisplayId: exit 2, foreground-unknown, as before
  FAIL (c) unreadable x3: rc=5 ABORTED no-(1/5)-line no-(2/5)-line no-(3/5)-line B-not-pressed | ...
       FOREGROUND: foreground-unknown: ee317437 answered no FocusedDisplayId (1/2)|
       FOREGROUND: foreground-unknown: ee317437 answered no FocusedDisplayId (2/2)|...|ROUTE ABORTED: not foreground (unknown)
  ok   (d) unknown x2: aborted before the second press, as before
  FAIL (d) unreadable bound: no-ABORTED-line no-not-foreground-line no-(3/3)-line | ... ROUTE ABORTED: not foreground (unknown)
  ok   (e) not-foreground x1: aborted at once
  FAIL (f) unreadable wait: no-ABORTED-line | ... ROUTE ABORTED: not foreground (unknown)
```

The (c) failure on master is the 09-28 Nova abort, reproduced.

99-display-covered.sh's `silent` leg (adb answers nothing) now expects
`3|foreground-unreadable: ee317437 adb answered nothing`, not exit 2.

A read-only call against the real Nova, 2026-09-28 16:15 PDT, with SERIAL
explicit, no input and no hold:

```
$ . docs/testing/devices.sh; hakux_in_front ee317437
in-front: ee317437 app=com.jreinach.hakux.debug focus=com.jreinach.hakux.debug display=0
rc=0     (0.11 s)
```

## For the next lane

- Once this folds, the host's interim edit to the snapshot (`$DISPATCH_DIR/bin/soak_title.sh`,
  5 unknowns) is overwritten by the re-snapshot. That is intended, since this
  replaces it.
- Do not widen the exit-2 rule to cover hangs. A device that answers without a
  focused window is real evidence. Only an adb that did not answer gets the
  longer bound.
- The hangs themselves (adb unresponsive on a Nova at about 95 C) are not
  explained here. Look for `FOREGROUND: foreground-unreadable: ... adb hung`
  counts in run.log to see how often they occur now that they are visible.
