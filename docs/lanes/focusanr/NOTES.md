# lane.focusanr (#513): hakux_in_front reads only the live dispatcher block

## The bug

`dumpsys input` prints the live `Input Dispatcher State:` block and then
`Input Dispatcher State at time of last ANR:`, laid out the same way, with its
own `FocusedDisplayId`, `FocusedApplications` and `FocusedWindows`. The awk in
`hakux_in_front` kept the last value of each. So the stale ANR snapshot
decided every read. The column-0 ANR header is dropped by the adb-side grep, so
the awk never saw where the live block ended.

## The fix (awk-side, not device-side)

The awk now stops at `  ANR:`, the first line of the ANR block's body, which the
grep keeps because it is at two spaces. It also stops at a second
`FocusedDisplayId:` line, in case a build prints that block without an `ANR:`
line. The stop line is also skipped, so the first FocusedDisplayId is never
overwritten.

Why not `sed '/at time of last ANR/q'` on the device? The fixtures' fake adb
does not run the shell pipeline. It serves the fixture text straight to the
awk, so a device-side cut would go untested by the selftest. The awk stop is
what the new legs exercise and what the ANR mutant removes. The exit codes
(0/1/2), the per-display arrays (display 4 listed first) and the
FocusedWindows / NotificationShade handling are unchanged. The fix only
drops lines after the live block.

## Proof

Fixtures in `jobs/selftest.d/99-display-covered.sh` (`fg_anr`): the existing
live-block fixture, then an ANR block copied from the Thor's real layout
(`ANR:` / `Time:` / `Reason:` / `Window:`, then the dispatcher fields).

| leg | live block | ANR block | fixed | master @ 57e2a710 |
|---|---|---|---|---|
| anr-ours | hakuX on 0 | Daijishou on 0 | `0 in-front` | `1 not-foreground: com.magneticchen.daijishou` |
| anr-daijishou | Daijishou on 0 | hakuX on 0 | `1 not-foreground: com.magneticchen.daijishou` | `0 in-front` |

Master fails both legs, and the second one is the dangerous direction: when
the ANR snapshot has hakuX, master lets a route drive whatever the live focus
is. The fragment run alone (a local wrapper, not committed, that sources
99 with `ok`/`bad`):

- fixed devices.sh: `frag: 23 passed, 0 failed`
- master devices.sh: `frag: 21 passed, 2 failed`. The fails are
  `FAIL anr-ours: [1|not-foreground: com.magneticchen.daijishou (the focused
  application on display 0 of ee317437, not hakuX)]`, `FAIL anr-daijishou:
  [0|in-front: ee317437 app=com.jreinach.hakux.debug ...]`, and the ANR
  mutant's missing-anchor check.

The ANR mutant deletes the `stop { next }` line. Both ANR legs then turn red,
and the fragment asserts that they do.

## The real Thor (read-only, 2026-09-27 22:27:45 UTC / 15:27 PDT)

No input and no hold. One `dumpsys input` grep and one `hakux_in_front bdc158a5`
from each tree:

```
593:Input Dispatcher State:
597:  FocusedDisplayId: 0
813:Input Dispatcher State at time of last ANR:
821:  FocusedDisplayId: 0
-- fixed:
in-front: bdc158a5 app=com.jreinach.hakux.debug focus=com.jreinach.hakux.debug display=0
rc=0
-- master:
not-foreground: com.magneticchen.daijishou (the focused application on display 0 of bdc158a5, not hakuX)
rc=1
```

hakuX held display 0 at that moment, so this read reproduces #513 exactly.
Master names the ANR snapshot's Daijishou. The fix reads the live block. An
earlier read at ~15:24 PDT, before hakuX was in front, showed the live block
with Daijishou on display 0 and `FocusedWindows: <none>`. The ANR block's
`Time:` had moved to 12:42:10, so the snapshot is replaced on each new ANR,
and any stale state can win on master.

## Do not repeat

- Do not match the column-0 `... at time of last ANR:` header in the awk. The
  adb-side grep (`^  [A-Za-z]...:`) drops it.
- A device-side cut is invisible to these fixtures. If you add one, add a
  fixture path that runs the real shell pipeline too.
- Running the whole `jobs/selftest.sh` takes more than 10 minutes, so it does
  not fit one foreground Bash call.
