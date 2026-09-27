# Audit pass 1 -- PR #464, lane.dispsuper

Head audited: `bf6f224446`. Diff: `docs/testing/dispatcher.sh` (serve
supervisor), new `docs/testing/jobs/selftest.d/98-dispatch-late-device.sh`,
`docs/lanes/dispsuper/NOTES.md`.

**Verdict: no HIGH, no MEDIUM. Two LOW.** Next state: `needs-audit-2`.

## What was checked

- `attach_workers` is called in the supervisor's own shell (not a subshell),
  so `workers+=`/`serials+=` reach the arrays the restart loop and the
  INT/TERM trap read. The trap is single-quoted, so it expands
  `${workers[@]}` at signal time and kills late workers too. With an empty
  set, `kill` gets no pids, fails silently, and serve still exits 0.
- Dedupe: a serial already in `serials[]` is skipped whether or not its
  worker is alive, so the rescan never starts a second worker next to one
  the restart loop is about to restart. The restart loop still owns dead
  workers, as before.
- `device_env` (devices.sh) is a static `case` with no adb call, so running it
  in a subshell once per rescan per unknown serial costs nothing and cannot
  hang.
- A failed listing (`timeout` non-zero, including the 30 s deadline) returns
  before parsing. Only state `device` rows are taken, so `unauthorized` and
  `offline` start nothing.
- Nothing else depends on serve's old `exit 2` / "no known device attached"
  text. The only other `exit 2` is line 45 (`device_env` of the default
  serial), and that path is unchanged.
- Late workers exec `$SNAP/dispatcher.sh`, the same path the restart loop
  already uses. The worker registers itself with affinity, so a late worker
  enters the device count the same way a start-time worker does.

## Fragment run

Standalone run of `98-dispatch-late-device.sh` against this head (a minimal
`ok`/`bad`/`check` harness, `$TESTING` = this tree): `pass=12 fail=0`, ~12 s.

Mutant check: I removed `|| return 0` from the listing so a failed
`adb devices` is parsed anyway. The fragment then gave `pass=11 fail=1`, and
the failing check was "a failed adb listing starts nothing". That negative
check does catch a real regression. It does not pass only because the code
never rescans.

## Findings

### LOW-1: a hung listing stalls the dead-worker restart by up to 35 s

`dispatcher.sh` supervise loop: `attach_workers` runs in the foreground
before the `kill -0` sweep. If `adb devices` hangs (the interop transient),
each rescan can take up to 30 s plus the 5 s `-k` grace. A worker that died
in that window is restarted up to 35 s later than before, and this can
happen at most once per `DISPATCH_RESCAN_SECS`. The delay is bounded and the
worker is still restarted, so this is not a defect.

### LOW-2: the two tuning knobs are not validated

`DISPATCH_SUPERVISE_SLEEP` and `DISPATCH_RESCAN_SECS` are used unchecked.
Setting `DISPATCH_SUPERVISE_SLEEP=abc` in the unit's environment would make
`sleep` fail at once and turn the supervise loop into a busy spin. A
non-numeric `DISPATCH_RESCAN_SECS` would make the `-ge` test error every
pass, so the rescan would never run. The comment says both knobs are for the
selftest only and nothing in production sets them, so this is a quality
note.

## Not a finding

A device that detaches keeps its worker, and the restart loop keeps
restarting that worker if it exits. This behaviour predates the PR, and
NOTES.md declares it out of scope.
