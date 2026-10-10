# OUTBOX: lane.lanepath1009 -> lane.local

## Resolved in Addendum 3 (applied directly, not left as an ask)

Attempt 1 found that `lane_path()`'s refusal (correct, asked for) broke 32 checks across 7 fragments
that call the real `lane.sh start`/`resume` against a fixture `$WORK` with no `forge/shim/bin`, and
proposed a three-file `mkdir -p` patch here since none of those files were then in territory.

Addendum 3 (lane.local, 04:50 PDT) put `docs/testing/jobs/selftest.sh` in territory and asked for the
fix to be applied directly, preferring a single global mechanism over three separate edits. Applied:

- `docs/testing/lane.sh`: `LANE_SHIM_BIN="${HAKUX_SHIM_BIN:-$WORK/forge/shim/bin}"` -- an override hook,
  not just a derived path.
- `docs/testing/jobs/selftest.sh`: one stub shim dir under the run's own `$T`, one `export
  HAKUX_SHIM_BIN` pointing at it, right beside the existing fixture setup. Every fragment that calls the
  real `lane.sh` inherits it through ordinary environment inheritance, whether it uses the shared
  default `$HAKUX_WORK` or its own private one -- no per-fragment edits needed, including for
  `96-fleet-registry.sh` and `88-window-budget.sh`, the two fragments OUTBOX previously named for their
  own fixtures.
- `docs/testing/jobs/selftest.d/99-lane-path.sh`: pins its own `HAKUX_SHIM_BIN` explicitly in
  `lp_start`/`lp_resume` (overriding the global export) so its happy-path, refusal-path and mutant
  sections keep full control of when the shim exists; adds mutant (e) (refusal dropped) per Addendum 3.

Verified on the exact 15 fragments (16 `SELFTEST_ONLY` names, `99-handback` plus its per-case
siblings) the fold's full-suite run on `69aa814fe1` found red: **495 passed, 0 failed**. Full method,
counts and the mutant's verbatim `FAIL` output are in `NOTES.md`'s "Addendum 3" section.

Nothing left open for lane.local on this lane.
