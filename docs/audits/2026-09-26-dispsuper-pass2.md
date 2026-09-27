# Audit pass 2 -- PR #464, lane.dispsuper

Head verified: `37ed0a6f06` (pass-1 head `bf6f224446` plus the pass-1 audit
file; `git diff bf6f224446 37ed0a6f06` touches only
`docs/audits/2026-09-26-dispsuper-pass1.md`).

**Verdict: clean.** Pass 1 raised no HIGH and no MEDIUM, so no failure
scenario had to be closed. Next state: `fold-ready`.

## Pass-1 findings

- **LOW-1 (a hung `adb devices` delays a dead-worker restart by up to 35 s).**
  Still possible. The code is unchanged, so this is expected. The delay is
  bounded by `timeout -k 5 30` and happens at most once per
  `DISPATCH_RESCAN_SECS`, and the worker is still restarted. It is not a
  defect and does not block the fold.
- **LOW-2 (the `DISPATCH_SUPERVISE_SLEEP` / `DISPATCH_RESCAN_SECS` knobs are
  not validated).** Still possible, and also unchanged. Both knobs are for
  the selftest only, and nothing in production sets them. It does not block
  the fold.

## Re-verification on this head

- I re-read the `dispatcher.sh` serve diff against `origin/master`. The
  pass-1 claims still hold:
  - `attach_workers` runs in the supervisor's shell, so its array appends
    are seen by the restart loop and by the single-quoted INT/TERM trap.
  - A known serial is skipped whether its worker is alive or dead.
  - A failed or timed-out listing returns before any parsing.
  - Only `device` rows start a worker.
  - An empty start logs and keeps supervising; it no longer exits 2.
- Standalone run of `selftest.d/98-dispatch-late-device.sh` against this tree
  (minimal `ok`/`bad`/`check` harness, private `$T`): `pass=12 fail=0`.
- The PR is `MERGEABLE`. When this was written, the `build` and `selftest`
  checks for this head were still running; the fold job gates on them.
