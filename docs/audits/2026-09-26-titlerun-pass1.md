# Audit pass 1: PR #307, lane/titlerun

Head audited: 094fff110c.  Diff read: `gh pr diff 307` (title_verdict.py,
soak_title.sh, titles/route.sh, perf/pad.sh, request.sh --route, dispatcher.sh
snapshot and LOGCAT_SPEC lines, titles/table.py, targets.toml, the three
routes, selftest.d/89, the real-run artifacts).

**Verdict: no HIGH.  Two MEDIUMs.  Four LOWs.  -> needs-remediation.**

Both MEDIUMs come from the same WSL `UtilAcceptVsock` adb drop that the lane
already fixed in the liveness probe and in pad detection.  In each case a
title that plays correctly gets a FAIL verdict, and the verdict gives no sign
that the instrument lost data.

## MEDIUM

### M1. A logcat restart loses lines, and the verdict scores the gap as a guest hang or as slow frames

`soak_title.sh` restarts a dropped stream with `logcat -T 1`, which prints only
the newest line in the ring and then streams.  Every line the device logged
between the drop and the reconnect is lost.  `title_verdict.py` builds its
windows (l.230-234) and its hang gaps (l.238-245) from consecutive
`hakuX-perf` lines, and it never reads the `LOGCAT: stream ended` line that
the soak writes to run.log.  A capture gap therefore counts as time with fewer
than 60 guest flips.  The soak comment says "each gap is written to run.log so
the verdict's reader can see it", but the verdict does not read that line.

Falsifier, run against this head.  The fixture is a run at 30 fps from the
mark to `soak end`, with no guest stall.  The capture loses 12 s once (a slow
reconnect) and 5 s eight times (quick reconnects), and run.log carries the
`LOGCAT: stream ended ... restart 1` line.  The verdict is:

    FAIL(hang: 14.0 s without 60 guest flips after the mark)  fps_ok=0.9058

That is a false hang.  The fps share also falls from 1.0 to 0.906 on capture
loss alone, so a few more quick reconnects would push it under the 90% bar
even with no long gap.  The soak allows 30 restarts per run.

`-T 1` also re-prints the last captured line.  A duplicated `hakuX-perf` line
is harmless, because the `dt_s > 0` check skips it.  A duplicated
`hakuX-pace` line is counted twice in `late_per_100`.

Remedy, either of:
- restart with `-T '<timestamp of the last captured line>'` so the ring
  replays the gap, and drop exact duplicates;
- have the verdict read the restart lines and exclude any window or hang gap
  that spans one, and report `capture_gaps`.

A selftest fixture should carry a capture gap with no guest stall and assert
that the verdict does not report a hang.

### M2. The `mark gameplay` logcat write gets one try, and a lost mark fails a playing title with the wrong reason

`route.sh` l.156 writes the mark with a single `adb shell log` call.  It has
no retry.  The mark is the one line that the whole scored window depends on
(l.196-205).  The real run's run.log shows three vsock failures and one
failed `pad.sh press` in the 40 s before `mark gameplay`.  If the mark write
lands on such a failure, the verdict reports
`reached_gameplay: no mark gameplay in logcat`.  The diagnostic that is
meant to catch this (l.322, "the route marked ... in run.log, but logcat has
no hakuX-route line") only fires when `marks` is empty.  `mark booted` has
normally already got through, so that branch is skipped and the reason
printed is wrong.  The verdict also never reads route.sh's own
`mark <x>: logcat write FAILED` line.

The probe comment in soak_title.sh says a vsock failure can also show up as
output with no `NAME` header, which suggests that exit status alone may not
catch the failure.  If `adb shell log` exits 0 on that failure, the
`logcat write FAILED` line is never printed either.

Remedy: retry the mark write as `probe` does (three tries, 2 s apart).  Have
the verdict name `logcat write FAILED` for a mark in run.log as the reason,
whether or not other marks exist.  Add a fixture: `mark booted` present,
`mark gameplay` present only in run.log with a FAILED line.

## LOW

- **L1. Key-up and recentre calls are single-shot.**  `pad.sh press` sends
  down and then up as two adb calls.  If the up call fails, the button stays
  down in evdev until the next press of that button.  The next press's
  key-down is then a duplicate value and is dropped.  `route.sh` removes a
  button from `HELD`, and an axis from `MOVED` on `mid`, whether or not the
  pad call succeeded.  `cleanup` makes one attempt per input.  The windows
  are narrow with the shipped routes (generic re-sends `LY min` every
  cycle), so the risk is a stuck input, not a wrong measurement.  Retry the
  release half.
- **L2. `fps_tolerance = 0.95` lets 28.5 fps count as "at 30".**  The stated
  reason, NTSC 59.94, needs only 0.999 (29.97/30).  With 60-flip windows timed
  by millisecond logcat stamps, jitter is well under 1%.  At 0.95, a title
  that runs at a steady 29 fps passes the owner's 30 bar.  This is a policy
  value, so name it in the PR for the owner rather than change it silently.
- **L3. `table.py` picks "latest" by `judged_utc` before the request id.**
  The documented generic-route step (`--reviewed-gameplay yes|no`) re-judges
  an older run.  That run then displaces a newer run of the same
  (title, device, ref).  Order by request id, which starts with the queue
  time.
- **L4. `probe` can hold the lease untouched for up to about 6 minutes.**
  That is three tries at `ADB_TIMEOUT` 120 s plus the sleeps, where it used
  to be 120 s.  This only happens when adb hangs rather than fails fast;
  vsock drops fail fast.  Consider a shorter per-probe timeout.

## What was checked and is right

- `snapshot_scripts`: the `local SRC/SNAP` shadowing is scoped to the
  function.  Nothing after the loop reads them.  Subdirectory files keep
  write-beside-and-rename in one directory.  `src_hash`'s `cat $SCRIPT_DEPS`
  resolves `titles/route.sh` and `perf/pad.sh` from `$SRC`.
  `soak_title.sh` resolves both from its own snapshot dir.  `route.sh`
  reaches pad.sh as `$HERE/../perf/pad.sh`, which is inside the snapshot.
- A missing snapshot subdir is reported as `ROUTE NOT PLAYED`, and the
  verdict carries that line into its reason.
- `soak_title.sh` clears the ring (`logcat -c`) before the first stream, so
  an earlier run's `mark gameplay` or crash lines cannot enter this run's
  capture.
- The liveness change is correct.  Unknown (2) keeps holding.  Only a
  working probe that finds no process ends the hold.  The loop is on wall
  clock.  `adb_failures=` is written, and the verdict reads it.
- route.sh parses the whole file before it sends any input.  Its TERM trap
  interrupts `nap`, and `stop_route` kills by PID.
- request.sh embeds the route text, so a queued run cannot be changed by a
  later edit.  `--check` refuses a malformed route at queue time.
- Verdict windows start after the mark.  The window that straddles the mark
  is excluded, and fps is time-weighted.  The trailing gap counts as a hang
  unless the process died.  `pace` skips `f<=60` first windows.  Each is
  covered by a fixture and a mutant in selftest.d/89.
- The branch is 16 commits ahead and behind origin/master, and GitHub reports
  it MERGEABLE.  The full selftest was not rerun here: CI is the gate of
  record, and the PR reports 1501/0 at this head.
