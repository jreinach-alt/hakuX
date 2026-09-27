# Audit pass 1: PR #496, lane.titlestate (route.sh `flush`, GoldenEye: Rogue Agent save route)

Head audited: `fa9f37de59`. Diff: `route.sh` (+54), `routes/goldeneye-ra.save.route` (+116),
`selftest.d/99-title-state.sh` (+57), `docs/lanes/titlestate/NOTES.md` (+57).

**Verdict: 0 HIGH, 2 MEDIUM, 2 LOW. Goes to `needs-remediation`.**

Checked and sound: the app does log `deferred bdrv_flush_all completed` at tag `hakuX`, INFO
(`ui/xemu.c:1579`), and the display loop runs that flush before its paused branch, so a
backgrounded app does flush. `soak_title.sh`'s liveness probe is a process check
(`soak_title.sh:339`), so a backgrounded app still reads as alive and the hold does not end
early. `goldeneye-ra.save.route` passes `--check`, ends `flush 20 / wait 5 / shot flushed`, and
has no `mark gameplay`. The device-clock filter and the HOME intent are what the PR says.

## MEDIUM 1: a fractional `flush` timeout passes the parser and breaks the wait after one poll

`validate()` checks the timeout with `isnum`, which accepts fractions (`^[0-9]+(\.[0-9]+)?$`,
`route.sh:72`), because `wait` takes them. `flush_disk` compares it with an integer test:
`[ "$waited" -lt "$1" ] || break`.

Scenario: a route with `flush 2.5`. `route.sh --check` prints `route ok` (reproduced).
At run time the first poll misses (the flush takes a moment), then `[ 0 -lt 2.5 ]` fails with
`integer expression expected` (rc 2, reproduced), the `|| break` fires, and the step logs
`flush NOT confirmed` after one poll and zero seconds, whatever the app then does. The route
goes on, the soak force-stops, and the save is lost: the failure this step exists to prevent.

Fix: make the parser require an integer for `flush` (or round in `flush_disk`), and add the
fractional row to the selftest.

## MEDIUM 2: "flush is the last step" is enforced only after the LAST flush

`validate()` sets `FLUSH_AT=$i` on every `flush`, so it holds the index of the last one, and
the post-flush scan starts there. The PR body states "The parser refuses ... any input step
after a flush".

Scenario: `flush 1 / press A / flush 1` passes `--check` (reproduced). At run time the first
flush backgrounds the app, `press A` goes to the home screen (or nowhere), and nothing
reports it. The same holds for a flush followed by a `repeat` block of presses and a second
flush. A route author who adds a mid-route flush to secure an early save gets input that
silently goes nowhere after it.

Fix: record the FIRST flush (`[ -n "$FLUSH_AT" ] || FLUSH_AT=$i`), or reject a second
flush outright; add the row to the selftest.

## LOW 1: the device clock is read in whole seconds

`t0=$(adb shell date +%s)` truncates, and the awk filter is `$1 + 0 >= t0`. A flush line
from an earlier background stamped in the same second as the request (up to ~1 s before it)
counts. No route backgrounds the app just before a flush today, so this does not fire in the
tree. Reading a sub-second clock (`date +%s.%N`, if the device's `date` supports it) would close it.

## LOW 2: selftest coverage

The six checks cover the happy path, the stale line, the poll count and the non-fatal miss.
Neither MEDIUM above is a row. Each fix should come with the row that fails on this head.

## What pass 2 must verify

- `flush 2.5` is either refused by `--check`, or waits its full timeout against the fake adb
  with no `integer expression expected` on stderr.
- `flush 1 / press A / flush 1` is refused by `--check`.
- Both are selftest rows that fail on `fa9f37de59` and pass on the remediated head.
