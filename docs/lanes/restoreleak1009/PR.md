Lane: restoreleak1009            Issue: #433
Base: master @ 96852d8144 (merged origin/master @ current tip, no conflicts)
Files: docs/testing/jobs/device_build.py, docs/testing/jobs/selftest.d/99-build-gate.sh, docs/lanes/restoreleak1009/NOTES.md, docs/lanes/restoreleak1009/PR.md
Prediction: none: analysis/harness-fix, no device arm
Needs device: no    Needs NDK: no
State: ready

## What this fixes

`docs/testing/jobs/device_build.py`'s `cmd_restore` wrote a brand-new
`dispatch.restore-*.req` into `queue/` after EVERY non-master run, with no
check for whether one was already pending. Because a queued (not yet
served) restore writes no `result.json`, `last_run()` kept reading the same
stale off-master result for every later non-master run in a chain, so each
one queued another duplicate restore -- unbounded growth for as long as the
chain continued. Observed on nova 2026-10-09: 14 duplicates piled up in
`dispatch/queue/` between 15:43 and 18:01 PDT (2h18m), none of them served,
because a sustained `1-`-prefixed critical-path chain (ASCII-sorts ahead of
any plain-epoch request) starved them all. hostops withdrew 12 of the 14 as
a one-time cleanup; this PR is the actual fix.

`cmd_restore` now calls a new `restore_pending(dispatch_dir, label)` that
checks both `queue/*.req` and `running/*.req` for an existing
`requester == "dispatch.restore"` request with a matching `device`, and
exits 0 having written nothing if one is found -- the same silent-no-op
contract `restore_needed` already uses for "already on master" and "this
run is itself a restore" (see `dispatcher.sh:1437-1439`'s comment). Verified
the two field names against `restore_request()` (the only writer) and
against `dispatcher.sh:1333`'s `mv "$req" "$D/running/$id.req"`, which
relocates the request file unchanged -- so the same two fields are correct
to check in both directories.

## What this does not fix (left as a documented follow-up)

The brief's second half -- `dispatcher.sh`'s ASCII-priority convention
letting a sustained `1-`-prefixed chain starve a plain-epoch
`dispatch.restore` request indefinitely -- is NOT touched here. After this
fix the backlog is bounded at exactly 1 pending restore per device no
matter how long such a chain runs, which converts the brief's titled defect
("queues an unbounded pile of duplicate ... requests") from unbounded to
bounded. What a starved restore still costs is *latency* to a clean build,
not *queue growth* -- a smaller, separate problem, and every real run
already sets its own ref/env explicitly at soak start regardless of what
the device was last left on, so a starved restore does not corrupt a later
measurement. Touching `dispatcher.sh`'s priority convention also needs an
OUTBOX grant this attempt did not request (full reasoning in NOTES.md).

## Testing

Extended the existing `docs/testing/jobs/selftest.d/99-build-gate.sh`
(did not add a new file) with leg (l): two non-master runs for the same
device, `restore` called back to back -- first call queues a restore and
prints its id, second call prints nothing and queues nothing, exactly one
`dispatch.restore-*.req` survives in `queue/`. Added a mutant (the
`restore_pending` check forced off) confirming the leg goes red without the
fix -- not vacuous.

`SELFTEST_ONLY="99-build-gate.sh" bash docs/testing/jobs/selftest.sh`: 39
passed, 0 failed (includes leg (l) and its mutant, plus all pre-existing
legs (a)-(k) and their mutants, unaffected), re-run in the foreground after
merging origin/master @ 96852d8144. The diff is confined to
`device_build.py`'s restore path and this one selftest fragment, so no
regression elsewhere is expected. The full `selftest.sh` run (all 129
fragments) is not run again here -- the fold runs the whole suite itself
(~60 min) before folding anything, so a red suite still cannot reach
master; a prior attempt's background full-suite run was killed when its
session ended and is not evidence either way.

Release note (performance|stability|rendering|other|none): none -- harness/dispatch bookkeeping only, not emulator code.
