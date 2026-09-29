# lane.toolsmith -- fleet.py cannot tell a battery-gated queue from a stalled one

Issue: none (harness defect, dispatched directly). Do not open a tracker issue;
put `Issue: none (harness defect, dispatched directly)` on the PR.
Base: origin/master.
Files: docs/testing/battery_admit.py, docs/testing/fleet.py (both free; fleet.py
was released from lane.remote this tick -- PR #604 folded, its grant was
OPTION-1 only and is fulfilled), a new
docs/testing/jobs/selftest.d/99-fleet-battery-gate.sh, docs/lanes/battgate/NOTES.md.
Needs device: no. Needs NDK: no. Prediction: none, this is harness work.

## The defect

`fleet.py`'s `queue_stall()` (docs/testing/fleet.py, function starting ~line
316) walks the queue and, for each request, checks whether every live claimer
has gone quiet for `settle_s` (120s) with no claim and no result. If so it
reports the request as **stalled** -- "passed over by every live claimer,
nothing will claim it" -- which is a board FAIL every tick until someone
intervenes.

It has no idea `battery_admit()` exists (dispatcher.sh, ~line 686, calling
`docs/testing/battery_admit.py`'s `check()`). #507 added PER-REQUEST battery
admission: a live, healthy worker can legitimately refuse *every* queued
request because the device's charge is below the computed need (`floor 30 +
margin 5 + rate * dev_s/3600`). That is not a stall, it is the gate doing
exactly its job -- but `queue_stall()` cannot distinguish "no live claimer will
ever take this" from "the live claimer took one look and correctly declined
until it has more charge", so it reports both identically.

Measured this tick (board, 2026-09-29T06:53Z UTC): nova at 36% battery,
`dispatch/logs/dispatcher.log` full of lines like
`BATTERY: skip z-30695ba1a9-001-2D_Lines: level 36 < need 39.7 (floor 30 +
margin 5 + rate 10.5 %/h fallback n=0, 1 x (0s + overhead 1607s learned n=10))`
for every queued request, `dispatch/running/` empty, `dispatch/hold/thor`
present (a separate, already-handled coldslot hold) -- and `fleet.py` reported
"FAIL: 42 dispatch request(s) passed over by every live claimer ... Nothing
will claim it", which is false: nova will claim them the moment its charge
clears the need, exactly as designed. `grep -c battery docs/testing/fleet.py`
is 0 -- confirmed nothing there knows this mechanism exists.

## Part 1 -- battery_admit.py cannot even be attributed to a device

`check(d, label, req_path, level, head)` (battery_admit.py:244) is passed
`label` and never uses it in what it prints. Its three log lines --
`BATTERY: skip %s: ...` (line 281), `BATTERY: hold for head %s ...` (line
289), `BATTERY: admit %s ...` (lines 294, 301) -- name the request but not the
device. `dispatcher.sh`'s `log()` writes all of this into ONE shared
`dispatch/logs/dispatcher.log` for both handheld workers (nova's and thor's
`dispatcher.sh` instances both call `log "$line"` on this file). So today,
with both devices live, a reader (a human, or fleet.py) cannot tell which
device's gate refused a given request from the log alone.

Fix: include `label` in all three format strings, e.g.
`"BATTERY: skip %s on %s: level %d < need %.1f (%s)%s" % (rid, label, level,
need, inputs, ...)`. Keep the JSON record line (`print(json.dumps(rec))`)
byte-for-byte except adding `device=label` to `rec` -- readers of that JSON
line may already index on the existing keys.

`battery_unreadable` in dispatcher.sh (line 679) already includes
`$DEVICE_LABEL`; that one is fine as-is and is your reference for the wording.

## Part 2 -- fleet.py must not call a battery-gated queue a stall

In `queue_stall()`'s evidence loop (~line 469-482), a live claimer that has
been quiet for over `settle_s` currently always produces
`"%s idle, nothing claimed or finished for %s" % (lane, ...)`, which feeds
straight into `stalled`. Before accepting that as evidence, check whether
`dispatch/logs/dispatcher.log` has a `BATTERY: skip <rid> on <lane>` (or, after
Part 1, `BATTERY: hold for head ... on <lane>`) line newer than `written`
(the request's queue mtime) naming this exact `lane`. If it does, the lane's
silence is an answer, not an absence of one: exclude that request from
`stalled` and put it in a new bucket, `battery_gated`, the same shape as
`on_hold`: `[(id, age_s, reason)]`, oldest first, where `reason` is something
like `"nova: level 36 < need 39.7"` (reuse the line's own numbers, do not
re-derive them).

`main()`'s printer (~line 1358-1368) must treat `battery_gated` the way it
already treats `on_hold` (~line 1369-1374): print it on stdout, do not fail
`rc`, word it "Deliberate, not a stall" the same way. Do not merge it into
`on_hold` itself -- `on_hold`'s reader-facing line says "only a held device can
take these" and names `hold/<label>`, which is a different, specific
mechanism; a battery-gated request is not held, it is refused per-request and
will be picked up the instant the level clears.

Reading the whole log file on every `queue_stall()` call is fine: it is
already read start-to-tail nowhere else in this file, and the log rotates at a
size this project has not hit. If you want to bound the read, the last
`settle_s`-worth of lines is enough since anything older cannot be "newer than
`written`" for a request queued within the stall window anyway -- your call,
say which in NOTES.md.

## Falsify before claiming

- Part 1: run `battery_admit.py check` (or its `main`) against a fixture
  request with a level under need, for two different `label`s, and grep the
  two outputs -- they must differ by device, and must have differed by NOTHING
  ELSE before your fix (paste both, old and new).
- Part 2, the actual bug: build a scratch `$DISPATCH_DIR` (selftest.d style,
  see 98-fleet-queue-stall.sh for the existing fixture shape) with one queued
  request, one live lane (a `lanes/<label>` file with this process's own pid),
  an empty `running/`, and a `dispatcher.log` carrying a `BATTERY: skip <rid>
  on <label>` line newer than the request's mtime. On the OLD `queue_stall()`
  this must land in `stalled` (reproduce the false FAIL). On your fixed code it
  must land in `battery_gated` and NOT in `stalled`, and `fleet.py`'s exit code
  for that scenario must be 0. Also test the negative: the same fixture with
  NO matching `BATTERY: skip` line in the log must still land in `stalled` --
  you are narrowing the false positive, not disabling the check.
- Run `docs/testing/jobs/selftest.sh` (or at least `selftest.d/98-*.sh` and
  your new fragment) against a scratch copy per the runner's own convention;
  it must stay green.

## Done when

Both files patched, both falsifiers above actually run with pasted output (not
asserted), the new selftest fragment exists and passes against new code /
fails (for the right reason) against a checkout of the old code, NOTES.md
records the two fixtures and why the log-read approach was chosen over
threading battery state through a new file, and the PR is marked ready with
`Issue: none (harness defect, dispatched directly)` and `Files:` matching
`git diff --stat origin/master...HEAD`.
