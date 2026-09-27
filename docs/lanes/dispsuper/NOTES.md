# lane.dispsuper -- serve a handheld that attaches after the dispatcher started

## Defect

`dispatcher.sh serve` listed `adb devices` once, started workers for those
serials, and its supervise loop restarted only those. A handheld off adb at
start (charging on its 500 mA port) was never served until the next restart.
2026-09-26 20:12 PDT: the update window restarted serve with the Thor
(bdc158a5) unplugged; it came back at 20:35 and got no worker (devwatch
"thor no-worker") until a drain-restart. With no known device attached at all,
serve exited 2.

## Change (supervisor only; worker body and queue protocol untouched)

- `attach_workers` (inside `serve)`): lists `adb devices` under
  `timeout -k 5 30`; a failed or hung listing returns and changes nothing.
  For each serial in state `device` that `device_env` knows and that is not
  already in `serials[]`, starts a worker and appends to `workers[]`/`serials[]`.
  An unknown serial is logged once per serve, not once a minute.
- Called at start (log line `starting worker for <s>`, as before) and from the
  supervise loop at most once per `DISPATCH_RESCAN_SECS` (default 60 s) with
  the log line `starting worker for <s> (attached late)`.
- No device at start: logs `no known device attached; supervising none until
  one attaches` and supervises an empty set instead of `exit 2`.
- `DISPATCH_SUPERVISE_SLEEP` (default 20) and `DISPATCH_RESCAN_SECS` (default
  60) exist for the selftest only.
- A serial with a worker in `serials[]` is never started again by the rescan;
  a dead worker stays the existing restart loop's job. The INT/TERM trap is
  single-quoted, so it kills late workers too.

Not changed: a device that DETACHES keeps its worker (it was already that way;
the worker's own device checks handle absence). Out of scope per the brief.

## Proof

`docs/testing/jobs/selftest.d/98-dispatch-late-device.sh` runs the real
`dispatcher.sh serve` in its own DISPATCH_DIR with a scripted `adb` and a stub
worker (DISPATCH_SRC holds only a dispatcher.sh that records `<serial> <pid>`
and sleeps, so the snapshot the supervisor execs is the stub). 12 checks, ~12 s:
start worker; a FAILED listing naming the Thor starts nothing; the Thor
attaching later gets `(attached late)` and a running worker; neither serial is
started twice across several rescans; an unknown serial is logged once and
gets no worker; an `unauthorized` one gets none; an empty start keeps running,
logs "supervising none", and serves the first device to attach.

Falsifier: the same fragment against origin/master's dispatcher.sh
(e5db66fa37, symlink tree, nothing in docs/testing written) gives
`pass=5 fail=7`:

```
FAIL a handheld attached after serve started gets a worker -- serve.out:
     09-26 20:54:34 starting worker for ee317437
     09-26 20:54:34 === supervising 1 device worker(s) ===
FAIL the late handheld's worker actually ran
FAIL the late handheld is started once, not once per rescan
FAIL an unknown serial is logged once, not once per rescan
FAIL serve keeps supervising with no device attached -- it exited: no known device attached
FAIL serve logs that it is supervising none
FAIL the first handheld to attach to an empty serve gets a worker -- no known device attached
```

The five that pass on master are the negative checks (no double start, no
worker for unknown/unauthorized/failed listing), which master satisfies by
never rescanning at all -- the positive checks are what separate the two.

## Do not repeat

- Do not shim the worker by editing `$SNAP`: point `DISPATCH_SRC` at a stub
  directory and let `snapshot_scripts` copy it; missing siblings are skipped.
- The Bash tool rejects a heredoc containing `${...}` with quotes; write
  scratch runners to files.

## Deploy

Takes effect only after the host folds this and restarts hakux-dispatcher
through its update window (a running serve holds the old supervisor; the
worker re-exec does not reach the supervisor process).
