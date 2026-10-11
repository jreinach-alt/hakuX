# opsrebuild: replace hostops's model tick with a model-free ops layer

State: ready

Lane: opsrebuild             Issue: #433 (0.5: 50 Playable)
Base: origin/master @ bc2bced563 (merged at 96dc9a7bfd)
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

**Attempts 2 to 4** fixed nine shadow faults, each with a selftest leg that fails on the old code:
jam identity across ticks, folded branches dropped, the `failed-unit ●` parse, the per-jam session cap,
disk and territory gaps never escalating, stranded-lane skips for WAITING, folded and recent lanes,
and open jams kept open when a detector raises. NOTES.md "Attempt 2" to "Attempt 4" have the table.

**Attempt 5 (2026-10-03 11:50): the clean-window comparison is posted, and the verdict is NOT CLEAN.**
The 09:48 to 11:48 window on `4ab2956d8a` (25 ticks, none missed) had no repeated announcements and no crash.
Against hostops's own entries for the same window:

| | what | verdict |
|---|---|---|
| shadow only | `queue-stale` on memfast's request at 11:18 (nova free); cleared 11:23 with no action | harmless |
| shadow only | `stranded-lane routefix1002` at 11:48; its next step is a queued Gunvalkyrie v5 device run that the owner's 10-02 order suspends | **blocks cutover**: the remedy would resume it into that run. Needs lane.local to mark it `STOPPED-by-owner`, or the owner to say resume. NEW ISSUE in OUTBOX |
| hostops only | lanewaker named near30 and savestate433 stranded (11:09, 11:14); both PR.md are `State: ready` | ops_tick is right to skip finished PRs. The lanewaker check reads no PR state. NEW ISSUE in OUTBOX |
| hostops only | four board-coverage and territory reds (09:15, 09:33, 09:51, 11:10) and a Nova device collision (09:51) | no ops detector. NEW ISSUE in OUTBOX |
| agree | titleroutes rowless fold: ops cleared it at 11:13; hostops folded it at 11:09 | |

`shadow-comparison.md`, "The 09:48-11:48 window", has the full table. `NOTES.md`, "Attempt 5", ranks the
next candidates (P x win). An attempted change to the idle rule (commit age only) was tried and reverted:
it would resume a lane about 10 minutes after its session ended, which races handback.

## Cutover steps (lane.local's to run; split per ADDENDUM 4, lane.local 10-03 10:55)

Preconditions, none met yet: the routefix1002 decision; one clean window after it (`WAITING`: time 14:00
reads 11:48 to 14:00 for a second comparison).

1. `hakux-hostops.timer` stops its model tick. Hostops stays the **inbox executor** under JAM DUTY: it runs
   when an inbox item arrives, plus a 4-hour heartbeat. The PM's `## <time> PM:` items and lane.local's
   requests keep going to hostops.
2. `hakux-ops-tick.timer` (5 min, model-free, `docs/testing/jobs/ops/units/`) takes **detection and the
   scripted remedies**. It stops raising inbox items for jams it fixed itself. It raises one only for a
   jam its remedy did not clear, or for a class with no remedy (disk-low goes to lane.xbox, once per instance).
3. `hakux-idlewatch` keeps running as the independent backstop until a week of ops-tick runs without a missed jam.
4. Set `OPS_STATE_DIR` to a durable path before enabling the timer (the default is `host-tools/ops-state`).

## Verification run locally (no CI while GitHub is suspended)

- `python3 -m py_compile docs/testing/jobs/ops/ops_tick.py` -- clean, attempt 5, on the merged tree.
- `env SELFTEST_ONLY=87-ops-tick.sh bash docs/testing/jobs/selftest.sh` -- **51 passed, 0 failed**, on the
  merged tree (attempt 5, 10 s).
- Full `bash docs/testing/jobs/selftest.sh`, attempt 4 (09:12 to 10:35 PDT): **3051 passed, 0 failed, all 124
  fragments**, on `4ab2956d8a`'s harness content. The merge of `origin/master` changed harness files, so the
  fold runs the full suite again on this head.
- Live-state shadow ticks, scratch state dir (attempts 2 to 5): see `shadow-comparison.md`. The 11:54 tick on
  the merged tree names one jam, routefix1002.

Release note (none): tooling and instrumentation only (no `hw/`/`target/`/`accel/`/`android/`/`tcg/`/`ui/`/`audio/`
files touched). Nothing a player would notice.
