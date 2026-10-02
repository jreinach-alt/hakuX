# opsrebuild: replace hostops's model tick with a model-free ops layer

State: draft

Lane: opsrebuild             Issue: #433 (0.5: 50 Playable)
Base: origin/master
Files: docs/lanes/opsrebuild/NOTES.md, docs/lanes/opsrebuild/OUTBOX.md, docs/lanes/opsrebuild/PR.md, docs/lanes/opsrebuild/shadow-comparison.md, docs/testing/jobs/ops/allowed-tools.ops-escalate, docs/testing/jobs/ops/escalate-role.md, docs/testing/jobs/ops/ops_escalate.sh, docs/testing/jobs/ops/ops_tick.py, docs/testing/jobs/ops/units/hakux-ops-tick.service, docs/testing/jobs/ops/units/hakux-ops-tick.timer, docs/testing/jobs/selftest.d/87-ops-tick.sh
Prediction: none: no arm (model-free tooling change, not a measured performance fix)
Needs device: no

## Summary

Hostops (a `claude -p` session) was ticking 42 times/24h at ~$1.70 each (~$110/day) to do work
that is almost entirely mechanical. This PR builds the **ops** layer the brief asks for:
`docs/testing/jobs/ops/ops_tick.py`, a model-free script with nine detectors (each reading only
local truth: dispatch hold/queue/running files, `fold-failures.log`, `.device-reality.json`,
systemd, `briefs/*.STOPPED-by-owner-*`, lane branches' `PR.md`) and a scripted remedy for each
where one is safe, or none where a remedy needs judgement. `jams.tsv` tracks every jam's
lifecycle (opened/remedy/cleared/time-to-clear); `ops_escalate.sh` spawns exactly one scoped
`claude -p` session per jam that survives its remedy by 30 min or has no remedy at all (Sonnet
first, Opus on a second escalation of the same jam), bounded by its own role file
(`escalate-role.md`) and tool allowlist that drops `gh`/`WebFetch`.

Full inventory of harness_health.py's checks (~118) and hostops-poll.md's runbook items (~29),
one row each, classified SCRIPT/ESCALATE/RESOURCE/DROP, is in `docs/lanes/opsrebuild/NOTES.md`.

A real (if short -- see below) `--shadow` run against this host's current local state found 9
real jams that line up with `status/local-board.md`'s own report, correctly excluding one lane
that report does not filter (a STOPPED-by-owner marker), and in the process surfaced and fixed a
real bug in the first cut of the fold-failure detector (a stale jam that never cleared once its
branch moved past it). See `docs/lanes/opsrebuild/shadow-comparison.md`.

**Not finished here**: the brief's full >= 2 h shadow run alongside hostops, and the actual
cutover (installing the units, stopping hostops). Both are lane.local's to run -- this session
cannot block 2+ hours, and this lane was told not to touch host-tools/ or live units.
`shadow-comparison.md` and `NOTES.md`'s "Units" section give the exact commands.

## Verification run locally (no CI while GitHub is suspended)

- `python3 -m py_compile docs/testing/jobs/ops/ops_tick.py` -- clean.
- `env SELFTEST_ONLY="87-ops-tick.sh" bash docs/testing/jobs/selftest.sh` -- 28 passed, 0 failed.
- `bash docs/testing/jobs/selftest.sh --check-shards 4` -- all 121 fragments still covered.
- Full `bash docs/testing/jobs/selftest.sh` (every fragment, unsharded) -- required because this
  PR changes files under `docs/testing/` (offline_fold.py's own harness-file gate): result below.
- A real `ops_tick.py --shadow` tick against live host state (`OPS_STATE_DIR` redirected to a
  worktree-local scratch dir; every other path left at its real default) -- see
  `shadow-comparison.md`.

Release note: none (no `hw/`/`target/`/`accel/`/`android/`/`tcg/`/`ui/`/`audio/` files touched --
tooling/instrumentation only, nothing a player would notice).
