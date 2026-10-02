## #433 -- 2026-10-02 10:55 PDT

[lane.opsrebuild] Hostops's model tick replaced with a model-free ops layer.

**Built** (`docs/testing/jobs/ops/`): `ops_tick.py` -- nine detectors reading only local truth
(dispatch hold/queue/running files, `fold-failures.log`, `.device-reality.json`, systemd,
`briefs/*.STOPPED-by-owner-*`, lane branches' `PR.md`), each with a scripted remedy where one is
safe (`hold.sh release`, `lane.sh resume` once, an inbox note, `systemctl start`,
`dispatch_jamcheck.sh --nudge`, a battery hold via `hold.sh take`) or none where a remedy would
need judgement (a failed unit, low disk, a STOPPED lane with queued work, an unclassified fold
failure). `jams.tsv` tracks each jam's lifecycle; `ops_escalate.sh` spawns one scoped `claude -p`
session per jam that survives its remedy by 30 min or has none (Sonnet first, Opus if it
escalates twice), with its own role file and tool allowlist that drops `gh` and `WebFetch`.
Inventory of every one of harness_health.py's ~118 checks and every hostops-poll.md runbook item
(~147 total) is in `docs/lanes/opsrebuild/NOTES.md`: roughly 72 map straight to a SCRIPT detector
(mostly local already -- device/adb/dispatch-file checks never touched GitHub), ~44 are RESOURCE
(their purpose holds, their GH-bound implementation needs offline_status.py/local-board.md/
foldqueue.log instead -- not all wired yet), 6 are DROP (the owner's 10-02 device-filling stop,
retired title-batch), 5 are ESCALATE (fleet-stop, void-streak root cause, generic stranded-lane
judgement calls -- genuinely need a human or a model).

**Verified**: `selftest.d/87-ops-tick.sh` (24 checks, own fixture tree) plus the full
`docs/testing/jobs/selftest.sh` (all fragments). A short real `--shadow` run against this host's
actual local state (read-only; writes confined to a scratch state dir) found 9 real jams
(2 stranded lanes, 6 fold failures) that line up with `status/local-board.md`'s own report, MINUS
one lane `status/local-board.md` lists that this script correctly excludes (a STOPPED-by-owner
marker) -- see `docs/lanes/opsrebuild/shadow-comparison.md`. That run also surfaced and fixed a
real bug (a fold-failure jam stayed open forever once logged, even after the branch moved past
it with a new push) before any device or lane was touched.

**Not done in this session**: the brief's full >= 2 h side-by-side shadow run against hostops
(this session cannot block that long; `shadow-comparison.md` hands lane.local the exact command
to finish it and the cutover steps -- install `docs/testing/jobs/ops/units/hakux-ops-tick.{service,timer}`,
point `OPS_STATE_DIR` somewhere durable, stop whatever currently fires hostops). About 44 RESOURCE
items are mapped but not yet wired into a detector (most need a machine-readable
`offline_status.py`, which is lane.localforge/lane.issuerecon territory).

Files: `docs/lanes/opsrebuild/**`, `docs/testing/jobs/ops/**`, `docs/testing/jobs/selftest.d/87-ops-tick.sh`.
No device time used; no host-tools/ or unit files edited (units written for lane.local to install).
