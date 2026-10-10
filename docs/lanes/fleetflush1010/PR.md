# lane.fleetflush1010 -- fleet.py's FAIL lines land mid-line when stdout and stderr share a file (#433, 0.5)

State: ready

Lane: fleetflush1010       Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 9fd2608f8f, merged forward to 67187f9574 (no conflicts; nothing upstream touched fleet.py or its selftest fixtures)
Files: docs/testing/fleet.py, docs/testing/jobs/selftest.d/96-fleet-flush.sh, docs/lanes/fleetflush1010/NOTES.md, docs/lanes/fleetflush1010/PR.md
Prediction: none: harness fix, no pixels/performance involved
Needs device: no    Needs NDK: no
Release note (none): harness

## Cause, in two lines

`fleet.py` never configured its own stdout, so off a tty it block-buffers at 8 KB while `sys.stderr` stays
line-buffered; a caller merging both into one file (every selftest `fleet_run`, `session-start.sh`'s `2>&1 | grep
'^FAIL'`) got stdout's buffered chunks and stderr's lines ordered by flush time, not print time, once the inventory
grew past 8 KB. Fix: `sys.stdout.reconfigure(line_buffering=True)` as the first line of `main()` -- fleet.py has no
`print(..., end="")` anywhere (checked), so every print() is already a whole line and this is sufficient; no caller
needed to change.

## Mutant

`docs/testing/jobs/selftest.d/96-fleet-flush.sh` pads a scratch territory.toml with 400 dummy `[lane.ghostN]` rows
(past 8 KB) and runs a copy of fleet.py with one real unclassified issue (#9401) as the probe, stdout+stderr merged
into one file. With the fix: 4/4 checks pass. With the fix commented out (ran by hand, reverted, not committed): the
checks **"every FAIL: in the merged output starts at column 0 (no mid-line splice)"** and **"the one real issue's
FAIL is still found by a ^FAIL grep"** both go red, reproducing the exact fold-log splice
(`...an open issue no lane ownsFAIL: 1 open issue(s)...`).

## Item 3 (isolate 96-fleet-registry.sh from the live board): declined, live read kept

`96-fleet-registry.sh`'s `fleet_run` leaves `HAKUX_BOARD_REF` unset, so it reads the real `origin/board`
territory.toml (~38 KB) and nv2a_issues.toml (~509 KB) -- confirmed with `git show origin/board:...`. Two reasons for
keeping it:

1. The fix removes the size dependency that made this dangerous: line-buffered stdout flushes every line as it's
   printed, so no board size can corrupt the order anymore. Verified: `SELFTEST_ONLY=96-fleet-registry` against the
   current live board now gives **28 passed, 0 failed**, up from the brief's reported 27/1 on the same board before
   the fix.
2. Isolating it for real means reconstructing a fixture territory.toml/nv2a_issues.toml that satisfies every one of
   this fixture's ~30 checks across two `==` sections (RUNNING, READY-NOT-FOLDED, LANE-CLAIMED-WITH-NO-AGENT,
   DISPATCHABLE, NEITHER-BLOCKED, the `lane.sh` registry mechanics...) without colliding with its existing synthetic
   names. That is a fixture redesign, not an output-order fix, and out of this lane's territory ("output order
   only"). `fleet.py` and its fixtures are on loan from [lane.toolsmith]; said here and in NOTES.md per the brief's
   fallback clause.

## Verification

- Whole suite, unsharded (`-u DISPATCH_DIR -u HAKUX_WORK -u SELFTEST_DIR -u SELFTEST_SHARD`): **3227 passed, 0
  failed, all 131 fragments.**
- `SELFTEST_SHARD=3/4` (the shard that failed in the fold): **992 passed, 0 failed.** (96-fleet-flush/registry did
  not land in this particular shard-3/4 draw -- sharding groups by chain, not `i % n` -- but both ran clean above and
  in isolated `SELFTEST_ONLY` runs against the live board.)

Details and the manual repro steps are in `docs/lanes/fleetflush1010/NOTES.md`.
