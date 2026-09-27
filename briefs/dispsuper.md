# lane.dispsuper -- serve a handheld that attaches after the dispatcher started

Lane: dispsuper
Issue: none (harness defect; board row [lane.dispsuper])
Base: origin/master
Files:
- docs/testing/dispatcher.sh
- docs/testing/jobs/selftest.d/98-dispatch-late-device.sh
- docs/lanes/dispsuper/NOTES.md

## Why (evidence)

`dispatcher.sh serve` (docs/testing/dispatcher.sh, the `serve)` case, ~line 1404) lists `adb devices` ONCE and starts a
worker only for the serials present then. The supervise loop (~line 1428) restarts only those serials. A handheld that
is off adb when the dispatcher starts is therefore never served until the next restart.

2026-09-26: the host's update window restarted hakux-dispatcher at 20:12 PDT while the Thor (bdc158a5) was unplugged
for charging. The owner brought it back at 20:35. `ps` showed only `dispatcher.sh worker ee317437`, `dispatch/lanes/thor`
did not exist, and devwatch raised "thor no-worker". The only remedy was a drain-restart
(host-tools/dispatcher_update_window.sh --restart), which holds both devices for up to 30 min. With both handhelds
going on and off adb to charge on their 500 mA ports, this recurs on every restart.

A related edge: with NO known device attached at start, serve exits 2 ("no known device attached").

## Build

1. In the supervise loop, every iteration (or every Nth, at most once a minute), re-list `adb devices` under a timeout
   (`timeout -k 5 30`, adb is Windows adb.exe via interop and can hang or fail with the UtilAcceptVsock transient: a failed
   listing changes nothing). For each serial in state `device` that `device_env` knows and that has no live worker,
   start one (`log "starting worker for $s (attached late)"`) and add it to the arrays.
2. Do not exit 2 when nothing is attached at start: log it and supervise an empty set, so the late-attach path serves it.
   (Keep a clear log line; the unit must not crash-loop.)
3. Never start a second worker for a serial that has a live one. Do not change the worker body or the queue protocol.

## Proof

- New selftest `docs/testing/jobs/selftest.d/98-dispatch-late-device.sh`, modelled on the existing dispatch selftests
  (51-dispatch-hardening.sh, 97-dispatch-deploy.sh): shim `adb` so the first listing shows no known device (or one),
  then a later listing adds the second; assert a "starting worker for <serial>" line for the late device within one
  loop, and that a device already served is not started twice. Shim the worker so no real device is touched.
  Make the loop period overridable by env for the test only.
- A falsifier: the selftest must FAIL on origin/master's dispatcher.sh (say so in NOTES with the output words).
- `bash -n`, and the whole jobs selftest suite green.
- Open a PR, mark it ready when CI is green. It is the dispatcher serve path, so it goes needs-audit-1; the host folds
  it and restarts the dispatcher through its update window.

## Do not

- Do not touch a real device, adb holds, or dispatch/ (no requests; this is offline work).
- Do not restart hakux-dispatcher or edit $DISPATCH_DIR/bin (a snapshot).
- Do not edit board files (territory.toml, nv2a_issues.toml).
- Do not widen scope beyond the supervisor.
