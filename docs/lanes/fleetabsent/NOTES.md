# lane.fleetabsent -- a handheld off USB is not a stalled queue (#598)

## The problem

`fleet.py`'s `queue_stall()` FAILed every queued request no live claimer
would take, with one exception: a held device. A handheld that is simply
not on USB had none. 2026-09-28 17:40 PDT the owner unplugged both
handhelds to charge, the Thor's worker exited with its device, and 17
Thor-pinned requests read as "Nothing will claim it". The board diagnosed a
dead worker and opened #598. The device was on a charger.

## What changed

- `fleet.attached_labels()`: one `adb devices` (timeout
  `FLEET_ADB_TIMEOUT_S`, default 20 s), each serial mapped to its label by
  sourcing `devices.sh` and calling its own `device_env`. The table is not
  copied. It returns `({label: adb state}, None)`, or `(None, why)` when adb is
  missing, hangs, exits non-zero, or prints no `List of devices` header, or
  when devices.sh is absent or fails.
- `queue_stall()` now returns `(stalled, on_hold, absent, blind)`. A request
  goes to `absent` when it is past the settle window, pinned to a pooled label
  (not `desktop`, which has no serial) with no live worker, and adb does not
  list that label as `device`. That covers a label adb does not list at all
  and one it lists as `offline` or `unauthorized`. adb is read at most once
  per call, and only when such a pin exists, so a healthy fleet never runs
  adb from here.
- adb unreadable: the request stays in `stalled`, as before, and the FAIL
  says so: `... nobody has held (and adb could not be read to tell whether
  thor is on USB: <why>)`. A worker that is dead while its handheld is on adb
  as `device` also stays a FAIL, and the FAIL now says `(thor is on adb as
  `device`)`, which is the real dead-worker case.
- `main()` prints one stdout line per absent label, and it is not a FAIL:
  `queue: N request(s) can only run on thor, which is not on adb -- oldest
  <id>, queued <age> ago. Needs hands or a re-pin, not a claimer fix.`
- Every caller of the return tuple was updated: fleet.py `main()`,
  selftest.d/98 (its adb shim lists both handhelds, so its fixtures are
  unchanged), `docs/lanes/dispatch-script-deps/replay_queue_stall.py`, and
  `mutate98.py`'s `nocall` pattern.

## Proof

`SELFTEST_ONLY=99-fleet-absent-device.sh bash docs/testing/jobs/selftest.sh`:

```
== fleet: a request pinned to a handheld that is not on adb is absent, not stalled
  ok   (a) adb lists nothing: the absent line on stdout
  ok   (a) ...and no stall FAIL
  ok   (b) the Thor on adb as device, its worker dead: the stall FAIL
  ok   (b) ...which says the Thor is on adb
  ok   (b) ...and no absent line
  ok   (c) adb unreadable: the stall FAIL as before
  ok   (c) ...which says adb could not be read
  ok   (c) ...and no absent line
  ok   (d) the Thor on adb as offline: absent, naming adb's word
  ok   (d) ...and no stall FAIL
selftest: 10 passed, 0 failed, PARTIAL: 1 of 105 fragments
```

Step 1 removed (mutant: the `absent.append` branch replaced with
`if False:`, run with `SELFTEST_FLEET_SRC=<mutant dir>`):

```
  FAIL (a) adb lists nothing: the absent line on stdout
  FAIL (a) ...and no stall FAIL
  ok   (b) the Thor on adb as device, its worker dead: the stall FAIL
  ok   (b) ...which says the Thor is on adb
  ok   (b) ...and no absent line
  ok   (c) adb unreadable: the stall FAIL as before
  ok   (c) ...which says adb could not be read
  ok   (c) ...and no absent line
  FAIL (d) the Thor on adb as offline: absent, naming adb's word
  FAIL (d) ...and no stall FAIL
selftest: 6 passed, 4 failed
```

Against master's fleet.py/affinity.py, (a), (d), and both wording checks
(b2, c2) fail: 4 passed, 6 failed. `98-fleet-queue-stall.sh` on this branch:
21 passed, 0 failed.

### Live read (host, 2026-09-28 ~19:15 PDT)

`adb devices` listed nothing, the queue held 17 `thor`, 37 `nova`, and 13
unpinned requests, and `lanes/thor` held a dead pid (serving: `desktop`
only). A plain `python3 docs/testing/fleet.py` exited 0, printed the
held-device line for 50 requests, and printed no absent line and no stall.
The reason is that `$DISPATCH_DIR/hold/` is rewritten every few seconds
(its mtime read 23 s, then 44 s, old), which holds the settle window's
`epoch` open, so no request was judged. Master behaves the same way today.
The same live dir and the real adb with the clock moved 300 s forward
(`queue_stall(now=time.time()+300)`):

| code        | stalled | on_hold | absent |
|-------------|---------|---------|--------|
| master      | 17 (`pinned to thor, which no live worker serves and nobody has held`) | 50 | n/a |
| this branch | 0       | 50      | 17 (`thor`, `absent`) |

`attached_labels()` returned `({}, None)`: adb was read and listed nothing.

Something rewriting `hold/` every few seconds also means fleet.py's
queue check is blind on the live host whenever it happens. I did not trace
the writer (a hold `.why` refresh by hostops is the likely candidate). The
next lane should look at it: `epoch` is taken from the directory mtime, not
from the set of holds.

## For the next lane

- The absent line is on stdout only. board.sh reads `^FAIL` on stderr, so
  nothing wakes for it. harness_health.py `[devices]` and jamcheck's
  `ABSENT:` still own reporting that a device is gone.
- Unpinned requests with no live handheld worker are unchanged: they are
  still "no dispatch worker is alive", or `on_hold` when every handheld is
  held. The brief scoped this to pins.
