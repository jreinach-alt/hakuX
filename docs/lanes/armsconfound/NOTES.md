# lane.armsconfound (toolsmith): a FAIL whose arms ran on two devices is confounded, not regressed

Brief: harness defect, dispatched directly (2026-09-29, hostops). PR #583
(lane.forzadecay414, the #414 Forza fix) was labelled `regressed` from
`forzadecay414-fix-pixels.json`: FAIL, 2 of 3379 checks, with the base arm on
the thor and the fix arm on the nova. ab_compare had already printed "DEVICES
DIFFER ... a FAIL here is NOT attributable". Two defects caused it:
affinity.py split the pair, and arms.sh counted the FAIL anyway.

## What changed

### A. arms.sh: CONFOUNDED

- `build_label_index` now carries each arm's `device_label` (read from
  `$D/results/<id>/result.json`), two more columns. `label_decide` drops a FAIL
  whose two labels are both present and differ, the same way it drops a
  withdrawn FAIL: it neither counts nor supersedes, and it is listed as
  `confounded <prediction> (A x, B y)` straight after `STATE=`. It stays a
  FAIL (it still counts) in three cases: the arms ran on the same device, a
  label is missing ("unknown" is not "different"), or the verdict is a PASS
  (a hold across two devices is the stronger claim, as ab_compare says).
- `samedev_rerun` queues ONE re-run of the whole pair through request.sh with
  `--device <base arm's device> --hard-pin`. If that device is gone (neither
  serving nor held, `affinity.py --available`), it pins to `--choose`'s pick
  instead. The pair record gets `"confounded": [...]`, which holds the old ids,
  devices and verdict, and `"rerun": {device, id_a, id_b}`. `id_a`/`id_b`
  become the new ids, the old verdict files move to
  `pairs/<sha>.confounded-<old id_a>.verdict.*`, and `judged/<sha>` is removed,
  so the judge loop judges the re-run like any other pair. Once `"rerun"` is
  present, no second re-run is ever queued, whether the first was queued,
  refused or not needed.
- **No re-run when a later registration already supersedes the FAIL.** If
  the branch has a newer registration on the same issue (or the same
  prediction), that verdict wins whatever the re-run says, so the re-run is
  skipped and recorded as `"not_queued": "not needed: <newer>"`. That is #583's
  actual state: `forzadecay414-fix-pixels2.json` (pair `388ea55c4b19`) is queued.
  Without this, the fold would spend two full-corpus arms on the thor on a
  verdict that cannot count.
- The PR comment reads `[job.arms] CONFOUNDED FAIL (A thor, B nova): not
  attributable; same-device pair queued as <ida> <idb> (hard-pinned to thor)`,
  or `... no same-device pair queued: <why>`. The label follows `label_decide`:
  `regressed` if another FAIL still counts, `verified` if only PASSes count,
  and otherwise `regressed` is removed.
- Two callers: the judge loop, as a verdict comes in, and a one-time pass
  before it over pairs already judged FAIL with split devices and no
  `"rerun"`. The second pass is how #583's existing verdict is picked up on
  the first tick after the fold.

**How a hard pin is marked:** a request field, `"pin": "hard"`, written by a
new `request.sh --hard-pin` flag, which requires `--device`.
`affinity._is_load_pin` returns False when it is set, so rule 1 returns the
device absolutely. I did not use the requester name. `handback.sh` matches
`arms-<lane>-base|fix` exactly, and `status_html.py` matches `^arms-<lane>-`,
so a marker in the name would break both. This adds `docs/testing/request.sh`
to the brief's file list.

### B. affinity.py: a held device is coming back

**The brief's premise was wrong, and the definition changed because of it.**
The brief defines HELD as "`hold/<label>` exists and the lane is registered"
and GONE as "no lane registration". A held worker removes its own
registration: dispatcher.sh's hold check calls `lane_release` ("affinity must
not pin a pair to a device on hold"). So "held and registered" never happens.
When I read it, both handhelds were held and `lanes/` held only `desktop`. A
rule keyed on the registration would never fire.

So `_held(d, label)` is: `hold/<label>` is a file whose mtime is younger than
`HOLD_WAIT_S` (default 3 h, env `AFFINITY_HOLD_WAIT_S`). `_available` is
`_live or _held`. GONE is neither serving nor held, and it falls through at
once, as before.

Where it applies: only where a sibling has **landed**, i.e. a running
sibling's owner and a completed sibling's `device_label`. A load pin, and a
queued sibling's load pin, still use `_live`. With nothing landed, both arms
can go to a live device together, and making a pure load pin wait would
bring back the #503 H1 split (thor held, nova takes base, hold lifts, thor
takes fix on its own pin). A load pin to a held device also no longer writes
a `splits/` note: the pair is not split, and if a sibling did land on the
held device it is followed.

The 09-13 incident (`_live`'s docstring) was a four-hour hold on the nova.
Under this rule it waits 3 h and then falls through, noted as a split. The
existing `95-affinity.sh` control, a pin to a dead-pid device with no hold,
still falls through at once.

A small window remains that this does not close. A hold is lifted by `rm`,
and the worker re-registers at the top of its next loop, up to 30 s later.
A claim in that window reads the device as gone. That needs the other worker
to claim the exact arm in those seconds.

## Proof

### Fragment `selftest.d/99-arms-confounded-pair.sh`, new code (24 checks)

```
== arms.sh: a FAIL across two devices is confounded; affinity waits for a held device
  ok   (A1) a FAIL with its arms on thor and nova does not label the PR regressed
  ok   (A1) state names it confounded, with both devices
  ok   (A2) CONTROL: the same FAIL with both arms on the thor is still regressed (narrowed, not disabled)
  ok   (A3) the tick queues exactly one same-device pair (two requests) for the confounded FAIL
  ok   (A3) both are HARD-pinned to the thor, where the base arm ran
  ok   (A3) the base and the fix ref are the pair's own
  ok   (A3) the pair record names the re-run, and the judged marker is gone so it is judged again
  ok   (A3) the PR comment says CONFOUNDED FAIL (A thor, B nova) and names the queued ids
  ok   (A3) and regressed comes off #583
  ok   (A3) the same-device FAIL's PR (#584) is not touched
  ok   (A3) the same-device FAIL queued nothing
  ok   (A6) a confounded FAIL already superseded by a later registration queues no re-run
  ok   (A6) and its comment says why
  ok   (A4) a second tick queues nothing more
  ok   (A4) and says nothing more on #583
  ok   (A5) the re-run's hard pin does not fall through when the thor is neither serving nor held
  ok   (B1) sibling ran on the thor, thor freshly HELD: the fix arm waits for the thor
  ok   (B1) --available says a held device is coming back
  ok   (B2) the hold is older than the bound (3 h): the pin falls through as before
  ok   (B3) thor neither serving nor held (gone): falls through at once
  ok   (B3) --available says a gone device is gone
  ok   (B4) CONTROL: a load pin to a held device with NO sibling landed still falls through (#503)
  ok   (B5) a sibling still RUNNING on the held thor pins the fix arm there too
  ok   (B6) CONTROL, 09-13: sibling on a nova that is neither serving nor held falls through, not stalls
selftest: 99-arms-confounded-pair.sh took 81s
selftest: 24 passed, 0 failed, PARTIAL: 1 of 108 fragments
```

### The same fragment against origin/master @ 6af219758f (`CF_ARMS`/`CF_AFF` pointed at a detached worktree of it)

The run below predates the (A6) checks, which were added afterwards and cannot
pass on old code: old code queues nothing and writes no comment.

```
== arms.sh: a FAIL across two devices is confounded; affinity waits for a held device
  FAIL (A1) a FAIL with its arms on thor and nova does not label the PR regressed
  FAIL (A1) state names it confounded, with both devices
  ok   (A2) CONTROL: the same FAIL with both arms on the thor is still regressed (narrowed, not disabled)
  FAIL (A3) the tick queues exactly one same-device pair (two requests) for the confounded FAIL
  FAIL (A3) both are HARD-pinned to the thor, where the base arm ran
  FAIL (A3) the base and the fix ref are the pair's own
  FAIL (A3) the pair record names the re-run, and the judged marker is gone so it is judged again
  FAIL (A3) the PR comment says CONFOUNDED FAIL (A thor, B nova) and names the queued ids
  FAIL (A3) and regressed comes off #583
  ok   (A3) the same-device FAIL's PR (#584) is not touched
  ok   (A3) the same-device FAIL queued nothing
  FAIL (A4) a second tick queues nothing more
  ok   (A4) and says nothing more on #583
  FAIL (A5) the re-run's hard pin does not fall through when the thor is neither serving nor held
  FAIL (B1) sibling ran on the thor, thor freshly HELD: the fix arm waits for the thor
  ok   (B1) --available says a held device is coming back
  ok   (B2) the hold is older than the bound (3 h): the pin falls through as before
  ok   (B3) thor neither serving nor held (gone): falls through at once
  FAIL (B3) --available says a gone device is gone
  ok   (B4) CONTROL: a load pin to a held device with NO sibling landed still falls through (#503)
  FAIL (B5) a sibling still RUNNING on the held thor pins the fix arm there too
  ok   (B6) CONTROL, 09-13: sibling on a nova that is neither serving nor held falls through, not stalls
selftest: 9 passed, 13 failed, PARTIAL: 1 of 108 fragments
```

Old code prints `STATE=regressed` for the split pair (A1, and see the replay
below). B1 fails because old code returns `""`, so the nova would claim the
arm. Old `--available` passes B1 only because old affinity.py ignores the
flag and exits 0; B3's gone-device check fails on it, and that check is the
one that tells the two versions apart. The controls (A2, B2, B3 fallthrough,
B4, B6) pass on both.

### #583's real verdict, replayed read-only

The pair and judged files were copied out of `$WORK/arms` into a scratch
work dir. Device labels were read from the real `$DISPATCH_DIR/results`.
Nothing was written to `$WORK/arms` or the dispatch dir.

```
pairs replayed: 388ea55c4b19...json a4436529a25c...json
judged: VERDICT: FAIL -- 2 of 3379 checks violated:
===== old arms.sh state lane/forzadecay414-fix
STATE=regressed
**PR label: `regressed`** -- 1 of the 1 judged verdict(s) on `lane/forzadecay414-fix` is a FAIL that nothing supersedes. ...
| FAIL | `forzadecay414-fix-pixels.json` | #414 | **yes -- nothing supersedes it** |
===== new arms.sh state lane/forzadecay414-fix
STATE=none
confounded forzadecay414-fix-pixels.json (A thor, B nova)
**PR label: no verdict counts** -- every judged verdict on `lane/forzadecay414-fix` is withdrawn or confounded.
- `forzadecay414-fix-pixels.json` FAILED with its arms on two devices (A thor, B nova), and is **confounded**: ...
```

On the first tick after the fold, the one-time pass will find this pair. It
will not queue a re-run, because `forzadecay414-fix-pixels2.json` supersedes
it (A6). It will post the CONFOUNDED comment and remove `regressed` from #583.
The pixels2 verdict then decides the label.

### Existing fragments

```
selftest, SELFTEST_ONLY batches on this branch (fake host in /tmp):
batch 1: 10-arms-list 20-arms-queue 30-arms-error 40-arms-refusal 50-arms-requeue
         51-dispatch-hardening 55-affinity-offpool 60-status 92-arms-skip-told 94-arms-label-state
         -> selftest: 140 passed, 0 failed, PARTIAL: 10 of 108 fragments
batch 2: 94-arms-disc-narrow 94-arms-verdict-scope 94-arms-withdrawn 95-affinity
         99-affinity-backlog 99-handback-resolved
         -> selftest: 129 passed, 1 failed
            FAIL mutant anchor no longer matches arms.sh   (94-arms-disc-narrow)
batch 3 (after renaming the re-run's array to rnarrow; see below):
         94-arms-disc-narrow 94-arms-idle-tier
         -> selftest: 15 passed, 0 failed, PARTIAL: 2 of 108 fragments
preflight.sh -> preflight passed - safe to push
```

94-arms-disc-narrow's mutant asserts that the queue loop's
`${narrow[@]+...}` expansion occurs exactly twice. The re-run's copy is named
`rnarrow` so that the anchor still names only the queue loop.

## For the next lane

- A hold's registration is removed by the worker itself. Do not key anything
  on `lanes/<label>` to mean "coming back".
- The confounded rule reads `device_label` from `result.json`. A pair whose
  results were pruned from `$D/results` loses its labels and reads as a plain
  FAIL again. That is fail-safe (it keeps the label), but it is a way for a
  confounded FAIL to come back.
- The Stencil_REPLACE_ST/_ZB 0/30000 bimodality (#79 skew) is the lane's
  registration problem and was not touched here.
