# lane.affinitybatt (toolsmith): rule 3 blind to the battery gate

Harness defect, dispatched directly by hostops on 2026-09-29. PR #611.

## The defect

The dispatcher asks `battery_admit.py` only about requests that `affinity.py`
already sent to its own device (`serve_one`: affinity first, then battery).
So when a handheld refuses a request on battery, no other handheld ever sees
that refusal. On 09-28 three arm pairs were queued with no `device`, because
arms.sh's `--choose` returned "" with one device serving. Rule 3 then hashed
them over nova and thor, and all four of their prediction names hash to the
nova:

| prediction | rule-3 hash |
|---|---|
| ibcache-probe-pixels.json | nova |
| ibcache-probe-band.json | nova |
| gpl569-pixels-inert.json | nova |
| tcg424flip-pgraph.json | nova |

The nova hovered at 35-39 % on its 500 mA port and refused them on every walk
(`level 35 < need 49.6`, floor 30), for 8-14 h. The thor sat at 80-83 % and
would have admitted them at need 29.9, but it never checked them. This is the
same failure as #502 (a hash blind to the queue), this time blind to the
battery gate.

## The fix

- `battery_admit.py` records each refusal in `.battery_refused.<label>`:
  `{id: {since, t, need, level}}`. `since` is the first refusal of an
  unbroken run of them. An admission removes the id, and every write prunes
  ids that are no longer in `queue/` or `running/`. The file has one writer
  (the device's own worker) and is replaced atomically. `need_for()` is the
  need computation, split out with no side effects so that affinity can ask
  it about a device that was never offered the request. `level_now()` reads
  the dispatcher's `.battery_level.<label>` cache. The `BATTERY:` lines are
  unchanged and still name the id and the device.
- `affinity.py` passes over a device D for a request whose key D has refused
  for `AFFINITY_REFUSED_MOVE_S` (600 s). That applies only while D's current
  level, or its level at the refusal if it has read none since, is still
  below the need it refused at, and only when another pooled device neither
  refuses the key nor reads a level below its own need. It applies in three
  places:
  - rule 3: the hash pick moves to the alternative, and the move is noted
    once in `$D/moves/<id>.battery.txt`. It is not written to `splits/`,
    because status.sh reads everything there as "may span two devices";
  - an arms-job load pin, which falls through the same way a pin to a held
    device does;
  - rule 2b: a queued sibling's load pin that is refused this way is not
    followed.

  Rule 2 (a sibling that has landed) and hand pins (rule 1) are unchanged.
  With no refusal recorded, or with every alternative refusing, the answer
  is exactly what it was before.
- Pairs: both arms share the key, so they read the same records, the same
  level files and the same need, and they get one answer. That answer can
  change only when a level file changes, at most once a minute. An arm
  claimed within that minute is in `running/`, and rule 2 pulls its partner
  after it. The only gap left is the rename-to-owner-write instant that the
  rule-2 docstring already names.
- If a device has no fresh level (nothing asked it anything for 15 min), it
  counts as admitting. It reads its level when it is offered the request.
  If it refuses, that refusal is recorded and the request goes back to the
  hash device.
- Fail-open: a lone copy of affinity.py with no battery_admit.py beside it
  (the fleet selftests copy it that way) keeps the old rule 3. The dispatcher
  snapshot deploys both files into one directory (SCRIPT_DEPS).

## Item 2: arms.sh does not pin to a lone serving device

This is decided and recorded in arms.sh at the `--choose` call. A pin to the
one serving device buys nothing now, because with one pooled device rule 3
leaves the pair free and that device takes it anyway. It costs balance later.
When the other handheld returns, a pin holds the pair behind whatever is
queued on the first device (#502's stall). An unpinned pair is decided at
claim time, and rule 3 now also passes over a battery refusal. The cause
was the hash's blindness, so the fix went where every free request gets it.

## Proof (local, not CI)

`selftest.d/99-affinity-battery.sh` builds a fixture from the real ids
(`1-1790639762-arms-ibcache-base-184395`, `...-fix-184418`), the real
prediction name (it hashes to the nova), the nova at 35 refusing at 49.6, and
the thor at 80:

- no refusal: nova nova. Refused for 15 min: thor thor, and the move is noted.
- MUTANT, affinity.py without battery_admit: nova nova.
- Controls:
  - refused for only 5 min: nova nova;
  - the thor refusing too: nova nova;
  - the thor below its own need: nova nova;
  - the nova's level recovered to 55: nova nova;
  - the thor not serving: free;
  - a sibling that ran on the nova: nova;
  - a hand pin: nova.
- A load pin to the refusing nova: thor thor.
- The writer: it records on refusal (including a refusal behind the head),
  keeps its first `since`, clears one id on admission, and prunes.
- End-to-end replay: the nova's own `check` writes the refusal, then with
  the age gate at 0 both arms go to the thor, and the thor's `check` admits
  at 80.

Run with `SELFTEST_ONLY` alongside 95-affinity, 99-affinity-backlog,
99-battery-admit, 55-affinity-offpool, 56-desktop-worker,
98-fleet-queue-stall, 99-fleet-battery-gate, 99-fleet-absent-device,
99-arms-confounded-pair, 97-dispatch-deploy and 97-dispatch-snapshot-rename:
274 passed, 0 failed.

## Not done, for the next lane

- A request held behind the head (exit 3: it fits but the head reserves the
  device) is not recorded as refused. If a long head starves a short run on
  one handheld while the other is idle, that is a separate case.
- A hard pin (`--hard-pin`, the confound re-run) stays absolute and can
  still wait on a refusing device. That is by design: falling through would
  recreate the confound.
