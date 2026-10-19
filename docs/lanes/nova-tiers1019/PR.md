# Nova priority tiers that actually hold: screening yields to FPS and release-fix work

State: draft

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
outside this git tree) also gets the new tier/age/oldest-blocker
watch line and JAM row, per the project's edit-the-live-file-with-a-
dated-backup convention; it won't show in this PR's diff since it
isn't part of the repo.

Release note (none): testing-harness infrastructure, not emulator code.
