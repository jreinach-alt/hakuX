# Audit pass 1: PR #595, lane/battadmit-2 (#507)

Head audited: `72aaffc916`. Diff: `battery_admit.py`, `dispatcher.sh`,
`selftest.d/51-dispatch-hardening.sh`, `selftest.d/99-battery-admit.sh`,
`docs/lanes/battadmit/{NOTES.md,link_floor.py}`. CI: build x2 and selftest
(0-3) green.

**Verdict: no HIGH, no MEDIUM, three LOW.** Next state: `needs-audit-2`.

## What was checked and holds

- **Fail closed.** `battery_admit` returns 1 on an empty level, and
  `serve_one` returns 1 before the `mv` claim, so the request stays in
  `queue/`. `BATT_WALK_UNREAD` is set in `battery_unreadable`, and it survives
  across requests because `serve_one` and `serve_queue` run in the worker's own
  shell, not a subshell (`dispatcher.sh` worker loop, `serve_queue
  "${reqs[@]}" && served=1`). `serve_queue` resets it per walk. The empty level
  is not cached (`battery_level` writes the cache only on a non-empty read), so
  the next walk does read again. The selftest's count of 3 dumpsys calls over
  3 walks would catch a cached empty.
- **Episode state.** `BATT_UNREAD_SINCE` is a worker global. It is set once
  and cleared on the first readable level, so the start and recovery lines are
  one each per episode. A re-exec resets it, which costs one extra line at
  most.
- **Absent device.** Before this change, an absent device was admitted,
  built, and then requeued by `device_present` with `sleep 30`. Now the empty
  read refuses it before the build. The request stays queued either way, and
  the new path skips the build.
- **Other `serve_one` drivers.** `desktop_channel.sh` has its own
  `dc_serve_one`, with no battery path. The only selftest that drives
  `serve_one` with a fake adb that has no battery level is
  `51-dispatch-hardening`, and it now sets `BATTERY_ADMIT=off`.
- **Helper failure.** `floor_for` runs inside `check`, under `__main__`'s
  `except Exception` → exit 2, so a malformed `BATTERY_FLOOR_nova` admits the
  run unchecked and logs it. It does not refuse forever. This matches the
  documented contract for exit 2.
- **Floor.** `floor` replaces `FLOOR` in both `need` and the recorded
  `battery.json`. The nova case (53.3 / 39.8) and the thor case (15) each have
  a mutant that the selftest turns red. The `fits` mutant moved from FLOOR to
  MARGIN because `ba_walk` pins `BATTERY_FLOOR_nova=15`. That is correct:
  FLOOR no longer reaches the nova in those cases.

## Findings

### L1 (LOW): link_floor.py can count one link error against two runs, and crashes on an untimestamped line

`link_floor.py` gives each run the window `[t0 - 60, t1 + 120]`. When two
Nova runs are less than 180 s apart (the device part of one ends, and the
next claim's build is cached), a single `ee317437 ... terminated` line falls
in both windows. Both runs then count as "with a link error". Back-to-back
drain soaks sit in adjacent low bands, so this inflates exactly the numerator
the floor of 30 rests on (8 of 17 below 30). Separately, a line that contains
`ee317437` and `terminated` but does not start with `MM-DD HH:MM:SS` makes
`m` None, and `m.group` raises AttributeError, so the whole table is lost.

Scenario: runs A (ends 16:40:00) and B (first sample 16:41:30), with one
error at 16:41:17 → A and B both count 1 error.

The blast radius is bounded. It is analysis, not the gate. The PR already
calls the result a rate, not a threshold, and `BATTERY_FLOOR_nova` overrides
the floor. Fix: attribute each error to the one run whose window is nearest,
or report the number of distinct errors per band; skip a line that does not
match.

### L2 (LOW): a long unreadable episode is silent after its first line

`battery_unreadable` logs when an episode starts and `battery_admit` logs
when it recovers. Nothing is logged in between, and `dispatcher.sh status`
does not show the episode. `adb devices` can still list a Nova whose shell
fails, so `status` says `device: present`.

Scenario: the link dies at 16:41 and stays dead for three hours. The queue
does not move, the last BATTERY line is three hours old, and status shows a
present device. The operator sees an idle worker, not a refusing one.

Fix: repeat the line at a coarse interval (for example hourly, with the
elapsed time), or have `status` print `battery: unreadable since <t>`. The
state lives in a worker global, so a status reader would need it on disk,
for example `$D/.battery_unread.<label>`.

### L3 (LOW): a cached level still admits after the link has died

`battery_level` returns a cached level for up to `BATTERY_CACHE_S` (60 s)
without touching adb. Fail-closed therefore covers a fresh read only.

Scenario: the level is read at t, the link dies at t+30, and a request walks
at t+40. It is admitted on the cached level, and the run then fails at
install or voids, which is the failure mode this PR set out to close.

This is older than this diff and bounded to 60 s. It is worth one sentence in
the comment that says "fail closed", or a cache invalidation on any failed
`adb_call` for the device.

## For pass 2

Verify L1-L3 were either fixed or explicitly declined with a reason. None of
them blocks the fold.
