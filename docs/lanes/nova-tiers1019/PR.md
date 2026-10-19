# Nova priority tiers that actually hold: screening yields to FPS and release-fix work

State: ready

Lane: nova-tiers1019          Issue: #433
Base: master @ 2e6d29d4f8d2dc81cd9c58c5a5550d458784a1a2
Files: docs/testing/jobs/hold.sh, docs/testing/jobs/selftest.d/99-hold-tiers.sh, AGENTS.md, docs/lanes/nova-tiers1019/**
Prediction: none: analysis-only, no device time
Needs device: no    Needs NDK: no

Claiming files before editing, per brief. Adding a tier concept
(`blocker|fps|sweep`) to `hold.sh take`/`wait`, stored in a new
`hold/<label>.tier` file with the same create/remove lifecycle as
`.why`; a sweep-tier take/wait refuses (new exit code) while a `0-*`
or `1-*` request is queued or running for that device label (checked
via `affinity.py`, the same rule `dispatcher.sh`'s `serve_one` uses);
a new `hold.sh yield-check <label> <tag>` subcommand for a screening
chain already holding the device to release cooperatively; and a
sweep hold self-expires after `HOLD_SWEEP_MAX_S` (30 min default).

Two of the brief's named files do not exist as committed code:
`title1006.sh` and `overnight1018.py` were never committed (the
closest match, `docs/lanes/pathfind/scratch/title1006.sh`, was an
uncommitted scratch file belonging to the now-folded pathfind lane
and isn't in the tree). `docs/testing/overnight_19.sh` exists but is
an unrelated #19 regression campaign with its own device lease and
no `hold.sh` calls at all. Details and the "do not fabricate unused
files" reasoning are in NOTES.md; item 4 of the brief (chain default)
is reported as blocked on there being no such chain tool in the repo
today.

The host-tools hourly report (`/home/justin/hakux-work/host-tools/hourly_report.sh`,
outside this git tree) gets a new "HOLD WATCH" line: current hold,
tag, tier, age, and the oldest queued/running `0-*`/`1-*` request
behind it, read from the real labels `devices.sh` names so a sidecar
like `nova.battery-override` is never mistaken for a held device.
`host-tools/driver_tick.py` (also outside this tree) gets a new check
`g, sweep-hold-stuck`, reusing the existing `pm/jams.tsv`/`row()`
ledger mechanism (no new one): a `--tier sweep` hold whose oldest
0-*/1-* blocker has been overdue a `yield-check` release for more
than 5 minutes opens a jam row. Both edits are live, with dated
backups (`*.bak-20261019-novatiers1019`); neither shows in this PR's
diff since neither is part of the repo. Verified by unit-testing the
two new pure functions in isolation and a read-only dry run against
the real (untouched) dispatch dir -- never by running `driver_tick.py`'s
`main()`, which writes production state on a shared host.

Item 4 (chain default) is **blocked, not fabricated**: neither
`title1006.sh` nor `overnight1018.py` exists as committed code, and
`overnight_19.sh` never calls `hold.sh`. There is currently no
screening-chain tool in this repo that calls `hold.sh` take/wait, so
there is nothing to default to `--tier sweep`. Full reasoning in
NOTES.md.

Falsifier `99-hold-tiers.sh`: 35/35 passed, including the required
mutant (sweep-gate checks disabled -> leg (a) wrongly succeeds).
Full `selftest.sh`, all four CI shards (`SELFTEST_SHARD=k/4`): 0
failures across all 158 fragments. Details and the full shard
breakdown are in NOTES.md.

Release note (none): testing-harness infrastructure, not emulator code.
