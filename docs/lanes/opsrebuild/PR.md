# opsrebuild: replace hostops's model tick with a model-free ops layer

State: draft

Lane: opsrebuild             Issue: #433 (0.5: 50 Playable)
Base: origin/master
Files: docs/lanes/opsrebuild/NOTES.md, docs/lanes/opsrebuild/WAITING, docs/lanes/opsrebuild/OUTBOX.md, docs/lanes/opsrebuild/PR.md, docs/lanes/opsrebuild/shadow-comparison.md, docs/testing/jobs/ops/allowed-tools.ops-escalate, docs/testing/jobs/ops/escalate-role.md, docs/testing/jobs/ops/ops_escalate.sh, docs/testing/jobs/ops/ops_tick.py, docs/testing/jobs/ops/units/hakux-ops-tick.service, docs/testing/jobs/ops/units/hakux-ops-tick.timer, docs/testing/jobs/selftest.d/87-ops-tick.sh
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

**Attempt 2 (Addendum 2, lane.local 10-03): three shadow faults fixed.** The overnight shadow timer
exposed them. (1) Every jam was announced NEW on every tick, because shadow mode never persisted its
rows; shadow now keeps its own `jams.shadow.tsv` and `escalations.shadow.json`. (2) Six fold-failure
jams for branches already in master; a failed head that is an ancestor of `origin/master` is now
dropped. (3) `failed-unit ●`; the unit is the `hakux-*` token. Each has a selftest leg that fails on
the old code (legs h, i, j). `NOTES.md`'s "Attempt 2" section has the table, the evidence and why
attempt 1 did not finish.

**Attempt 3:** the attempt-2 work was uncommitted, so it is committed now; `origin/master` merged; a fourth fault (a live lane session read as stranded) is fixed. See NOTES.md "Attempt 3".

**Attempt 4:** the first ten minutes of the 08:45 window showed four more faults, now fixed with
selftest legs (l, m, n). (5) A jam re-escalated every 30 min with no limit; each jam instance now
gets at most two sessions, Sonnet then Opus. (6) `disk-low` escalated to a model; it now routes to
lane.xbox and never escalates (brief addendum 1). (7) A territory fold gap escalated, though no
session may edit the board; it now never escalates. (8) `stranded-lane` fired on lanes with a
WAITING file, on folded heads, and minutes after a session ended; those are skipped now, with a
90-min idle grace. (9) A detector that raised cleared its open jams, so the next tick would
re-run their remedies; its jams are kept open now (leg o). NOTES.md "Attempt 4" has the table.
The clean window restarts on `4ab2956d8a` (ticks 09:48 to 11:48).

**Cutover gap for lane.local:** the PM's DO items in `hostops-inbox.md` are executed by hostops
today. ops_tick does not execute them. OUTBOX.md files it as a NEW ISSUE.

**Not finished here**: the brief's clean 2 h `--shadow` run on this head, and the cutover. The timer
runs the worktree, so the run has started; this session cannot block for 2 h. Cutover (installing the
units, stopping hostops) is lane.local's to run. `OUTBOX.md` carries the waiting entry.
`shadow-comparison.md` and `NOTES.md`'s "Units" section give the commands.

**Why still draft**: `State: ready` waits on the shadow comparison the brief requires. That
comparison is the 2 h run above, which this session cannot produce. Per the lane protocol this is a
waiting state, not a failure.

## Verification run locally (no CI while GitHub is suspended)

- `python3 -m py_compile docs/testing/jobs/ops/ops_tick.py` -- clean.
- `env SELFTEST_ONLY="87-ops-tick.sh" bash docs/testing/jobs/selftest.sh` -- 51 passed, 0 failed. Legs k, l, m, n, o falsified: each fails with its fix reverted.
- `bash docs/testing/jobs/selftest.sh --check-shards 4` -- all 121 fragments still covered.
- Full `bash docs/testing/jobs/selftest.sh`, attempt 4 (09:12 to 10:35 PDT): **3051 passed, 0 failed,
  all 124 fragments**, exit 0. Its tree is `4ab2956d8a`'s harness content: fragment 87 ran after the
  last ops_tick.py/87 edit (it includes leg o), and no other harness file changed during the run.
- A real `ops_tick.py --shadow` tick against live host state (`OPS_STATE_DIR` redirected to a
  worktree-local scratch dir; every other path left at its real default) -- see
  `shadow-comparison.md`.

Release note: none (no `hw/`/`target/`/`accel/`/`android/`/`tcg/`/`ui/`/`audio/` files touched --
tooling/instrumentation only, nothing a player would notice).
