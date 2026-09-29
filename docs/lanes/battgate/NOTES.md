# lane.battgate (session lane.toolsmith, PR #606)

Harness defect, dispatched directly (no issue). fleet.py's `queue_stall()`
read a queue that a live worker refuses on battery (#507's per-request
admission) as "passed over by every live claimer ... Nothing will claim it":
on 2026-09-29 06:53Z the nova at 36 % refused all 42 queued requests and the
board FAILed every tick.

## What changed

1. `battery_admit.py`: each of its log lines names the device:
   `BATTERY: skip <id> on <label>: ...`, `BATTERY: hold for head <h> on
   <label> (...)`, `BATTERY: admit <id> on <label>[ as backfill ...]`. The
   JSON record (`battery.json`) gains `device`; no existing key changed.
   Before this, nova's and thor's workers wrote identical lines to the one
   shared `dispatcher.log`. dispatcher.sh's BATT_SAID key still strips the
   running clocks: they sit after the label.
2. `fleet.py`: `battery_refusals()` reads each request's newest battery line
   per device from `dispatcher.log`. In `queue_stall()`, a live claimer that
   passed a request over stops counting as stall evidence when its newest
   line for that request is
   - a skip, stamped no earlier than the request's queue mtime, while that
     device's `.battery_level.<label>` (the level its worker last read) is
     still under the line's need, or
   - a hold for a head that is still queued.
   A request whose passers-over include at least one such refusal goes into a
   new `battery_gated` bucket, `[(id, age_s, reason)]`, oldest first. The
   reason reuses the line's own numbers (`nova: level 36 < need 39.7`, plus
   `(reads N now)` when the cached level has moved). `main()` prints it on
   stdout with "Deliberate, not a stall" and leaves `rc` alone. It is kept
   apart from `on_hold`, whose line names `hold/<label>`.
   `queue_stall()` now returns 5 values. Its callers are updated: `main()`,
   selftest.d/98, and `docs/lanes/dispatch-script-deps/{replay_queue_stall,
   mutate98}.py`. mutate98's `nocall` mutant still matches once and still
   turns 98 red.

## Why read the log, not a new state file

The log line is already the worker's own record of the refusal, written at
the refusal, with the numbers. A state file (for example
`.battery_refused.<label>`) would be a second writer in dispatcher.sh plus a
second format, and it would have to be cleared on admit, on dequeue, and on a
worker restart. The log needs none of that: the newest line per (request,
device) wins, and an admit clears the entry. The one piece of live state read
is the `.battery_level.<label>` cache dispatcher.sh already writes. It catches
a refusal that no longer holds, because the level has since cleared the need
and the worker still has not claimed. That case goes back to being a stall.

## The whole file, not the last settle_s of it

The brief allowed the tail read. It would be wrong here. dispatcher.sh logs a
refusal once, and logs it again only when the words change (BATT_SAID). A
request refused at the same level for six hours therefore has one line, six
hours old, and a tail read would miss it and report the stall again. The live
log was 1.08 MB on 09-29 with 440 BATTERY lines. The scan skips any line
without `BATTERY: ` before running the regex.

## Unlabeled lines are not evidence

A line in the old wording (`skip <id>: level ...`) cannot be attributed to a
device, so fleet.py ignores it. Guessing "the only live claimer" would hide a
real stall whenever the other handheld wrote the line. **Transition:** until
the workers run the new `battery_admit.py` (a fresh `$DISPATCH_DIR/bin`
snapshot, see the memory on new snapshot files), the live log carries only
unlabeled lines and the false FAIL remains. Once the new wording is live,
each refusal's BATT_SAID key changes, so every refused request gets one new,
labelled line on its worker's next walk and is gated from that tick on.

Stamps are `date '+%m-%d %H:%M:%S'` in the worker's local time. fleet.py
parses them in its own local time (same host), takes the year from `now`, and
treats a stamp more than a day in the future as last year's. The comparison
with the request's mtime allows 1 s because the stamps are whole seconds.

## Falsifiers, run

### Part 1: two devices, same inputs (`.scratch/p1.sh`)

Labels handA and handB, which are outside FALLBACK_RATE and FLOOR_BY_LABEL,
so floor and rate are equal and the label is the only input that differs.

Old code: `diff handA handB` differs only in the script's own `--- handX`
headers. The lines, for both devices:

```
BATTERY: skip 0-long: level 20 < need 33.0 (floor 15 + margin 5 + rate 21.0 %/h fallback n=0, 1 x (2100s + overhead 120s fallback n=0)); head, refused for 0s
BATTERY: admit 0-short: level 99 >= need 21.1 (...)
BATTERY: hold for head 0-long (refused for Ns >= 1800s): not backfilling 0-short, level 99 >= need 21.1
```

New code:

```
BATTERY: skip 0-long on handA: level 20 < need 33.0 (...); head, refused for 0s
{..., "t_admit": T, "device": "handA"}
BATTERY: admit 0-short on handA: level 99 >= need 21.1 (...)
BATTERY: hold for head 0-long on handA (refused for Ns >= 1800s): not backfilling 0-short, level 99 >= need 21.1
```

handB's output is the same with `handB` in the place of `handA`.

### Part 2: `selftest.d/99-fleet-battery-gate.sh`

One dispatch dir per leg: 0-long queued 300 min ago, 0-big queued 400 min ago
(the control, with no battery line in legs a to g), the nova live, running/
empty. What varies is `dispatcher.log` and `.battery_level.nova`.

| leg | log | new | master (old fleet.py) |
|---|---|---|---|
| a | `skip 0-long on nova: level 36 < need 39.7`, level 36 | gated=0-long; with 0-big also refused: rc 0, no FAIL, stdout line | **FAIL** (all 4 checks): stalled=0-big,0-long; the false FAIL reproduced |
| b | empty | stalled both, FAIL, rc 1 | ok |
| c | the same skip, `on thor` | stalled | ok |
| d | the old unlabeled wording | stalled | ok |
| e | skip stamped before the request's mtime | stalled | ok |
| f | skip holds, level now 45 >= 39.7 | stalled | ok |
| g | skip, then `admit 0-long on nova` | stalled | ok |
| h | `hold for head 0-big on nova ... not backfilling 0-long` | gated=0-long | **FAIL**: stalled |

Master's code: 9 passed, 5 failed (every leg a check, and leg h). Legs c to g
pass on master because they check behaviour it already has. To show each one
can go red, `.scratch/mut.py` removed one guard at a time from the new code:

```
any-device (c)   FAIL (c) the refusal names another device: stalled -- got: stalled=0-big gated=0-long
unlabeled (d)    FAIL (d) an unlabeled refusal: stalled -- got: stalled=0-big gated=0-long
no-age (e)       FAIL (e) a refusal older than the request: stalled -- got: stalled=0-big gated=0-long
no-level (f)     FAIL (f) the level has since cleared the need: stalled -- got: stalled=0-big gated=0-long
no-admit (g)     FAIL (g) admitted after the refusal: stalled -- got: stalled=0-big gated=0-long
```

The first version of the `unlabeled` mutant only made the label optional. A
None label never matches a lane, so the mutant was inert and every check
stayed green. The mutant that counts also attributes the line to nova. Leg
(g) found a real bug on its first run: `on (\S+)[: ]` captured `nova:` as the
admit's label, so an admit never cleared its skip. The labels are now
`[^\s:]+`.

The 14 fragments that read fleet.py or the battery lines (93, 96, 97-board-
gate/-release, 98-audit-outlet/-fleet-queue-stall/-lane-shape, 99-battery-
admit, 99-fleet-*, 99-handback-draft, 71-cloud-territory): 407 passed,
0 failed. `mutate98.py nocall`: 3 red, as before.

## Next lane: do not repeat

- Do not read a tail of dispatcher.log for battery state. See above.
- Do not treat an unlabeled BATTERY line as a device's refusal.
