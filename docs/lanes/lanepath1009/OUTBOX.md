# OUTBOX: lane.lanepath1009 -> lane.local

## 1. Three fixtures need `forge/shim/bin`, now that `lane.sh` refuses to start without it

The brief's `lane_path()` refusal (exit 78 when `$WORK/forge/shim/bin` is missing) is correct and asked
for ("if the shim dir is missing, refuse to start the lane ... do not start it without the shim"). It
also breaks 32 checks across 7 fragments, none in this lane's territory (`docs/lanes/lanepath1009/**`,
`docs/testing/lane.sh`, `docs/testing/jobs/selftest.d/99-lane-path.sh` only) -- every one of those
fragments calls the real `lane.sh start`/`resume` against a fixture `$WORK` that never had a shim
directory, because that requirement did not exist when they were written. Verified as genuine (not
pre-existing) by running each fragment against both this branch's `lane.sh` and the unmodified
`git show HEAD:docs/testing/lane.sh`: the baseline run is clean (0 FAIL) in every one listed below. Full
regression table and method are in `docs/lanes/lanepath1009/NOTES.md`.

- `docs/testing/jobs/selftest.sh` line 170, the shared default `$HAKUX_WORK` every fragment gets unless
  it builds its own:
  ```
  mkdir -p "$T/bin" "$HAKUX_WORK"/{arms,logs/arms,logs/lane,logs/board,logs/fold,logs/cloud,status,briefs,attempts} "$DISPATCH_DIR"/{queue,running,results,expect} "$GOLDENS"
  ```
  needs `forge/shim/bin` added to the brace list:
  ```
  mkdir -p "$T/bin" "$HAKUX_WORK"/{arms,logs/arms,logs/lane,logs/board,logs/fold,logs/cloud,status,briefs,attempts,forge/shim/bin} "$DISPATCH_DIR"/{queue,running,results,expect} "$GOLDENS"
  ```
  Fixes `99-handback-branch.sh` (2), `99-handback-idle.sh` (10), `99-handback-lane-line.sh` (1),
  `99-handback-merged.sh` (2), `99-handback-parked.sh` (8) -- 23 of the 32 checks, since none of those
  five override `HAKUX_WORK` and all run against this shared default.

- `docs/testing/jobs/selftest.d/96-fleet-registry.sh`'s own fixture, `mkdir -p "$LW/briefs" "$LD"`, needs
  `"$LW/forge/shim/bin"` added: `mkdir -p "$LW/briefs" "$LW/forge/shim/bin" "$LD"`. Fixes 7 checks.

- `docs/testing/jobs/selftest.d/88-window-budget.sh`'s own fixture, `mkdir -p "$WB/bin"
  "$WB/work/logs/lane" "$WB/work/attempts" "$WB/work/window"`, needs `"$WB/work/forge/shim/bin"` added.
  Fixes 2 checks.

Not edited here: none of these three files are in this lane's territory, and the brief's territory line
("Nothing else") is unambiguous. Each is a one-line, mechanical addition (a directory a fixture now
needs to exist) with no judgment call left for whoever applies it.

## 2. Read, not edited, and found fine as-is

- `docs/testing/jobs/selftest.d/99-handback-runs.sh` and `99-handback-draft.sh` also showed FAILs when
  run in isolation via `SELFTEST_ONLY`, but the same FAILs reproduce against the unmodified baseline
  `lane.sh` too -- pre-existing, unrelated to this change (most likely a `SELFTEST_ONLY`-subset ordering
  artifact: one fragment's fixture depending on another fragment's setup that an isolated run skips).
  Not counted in section 1, not touched.
- `99-handback-waiter.sh` showed 0 FAILs either way; not touched.
