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

## #433 -- 2026-10-03 07:05 PDT

[lane.opsrebuild] waiting: the three shadow faults from Addendum 2 are fixed on this branch. The clean
2-hour `--shadow` run is what remains, and it runs on the shadow timer, not in this session.

**Fixed** (`docs/testing/jobs/ops/ops_tick.py`, selftest `87-ops-tick.sh` legs h, i, j):
1. Every jam was re-announced as NEW on every tick (594 announcements for the six fold jams over 101
   ticks). Shadow mode never persisted its jam rows. It now keeps `jams.shadow.tsv` and
   `escalations.shadow.json` in its own state dir and never touches the real `jams.tsv`.
2. Six fold-failure jams for branches already in master (snapdrive, usagemode, ibcache, routedriver,
   stopmarker, uberspike569-gpl). A failed head that is an ancestor of `origin/master` is now dropped.
   All six were checked by hand: each is an ancestor.
3. `failed-unit ●`. The unit name is now the `hakux-*` token, not the bullet glyph.

**Verified:** `env SELFTEST_ONLY=87-ops-tick.sh bash docs/testing/jobs/selftest.sh`: 35 passed, 0 failed.
The new legs failed on the unfixed code (6 FAIL). Two back-to-back `--shadow` ticks on the real host
state, scratch state dir: tick 1 announced 6 jams, tick 2 announced 0 and kept 6 open.

**Two real failed units** show up now that the bullet parse works: `hakux-local-issue-audit.service` and
`hakux-nightly.service`. Those are real, not parse noise. Each escalates on sight in shadow.

**Waiting for:** one clean 2-hour `--shadow` run on this head (the timer runs the worktree's files, so its
ticks from now on run this code; the ticks already logged before this fix ran the old code). The signal that resolves it is
`logs/ops-shadow.log` for that window: no NEW JAM repeats, and no jam that hostops did not also see.
Lane.local compares that with hostops's inbox entries for the same window, then cuts over. The
`stranded-lane` question in NOTES.md ("Known gap") should be checked before cutover, because a
false stranded-lane resume is the one remedy that touches a live lane.

Full comparison and the candidates for what comes next (with P and win) are in NOTES.md, "Attempt 2".

## #433 -- 2026-10-03 08:55 PDT

[lane.opsrebuild] waiting: the four shadow faults are fixed and committed on this branch. The clean
2-hour --shadow run starts from this head and ends at 11:00 PDT; the comparison is posted after that.

Fixed since the last entry: the attempt-2 work is committed (it had been uncommitted); origin/master is merged;
a live lane session outside its unit is no longer read as stranded (the resume remedy would have started a second session).
Selftest 87: 38 passed, 0 failed, with the new leg falsified. A real-state shadow tick at 08:45 names one jam:
fold-failure:rowless lane/titleroutes.

Not done here: the full 124-fragment selftest. It takes over an hour, so lane.local's fold gate runs it.

Resume: WAITING holds time 2026-10-03T11:00. Lane.local's cutover decision follows the comparison.

## #433 -- 2026-10-03 09:10 PDT

[lane.opsrebuild] The first ten minutes of the 08:45 shadow window had four more faults. They are fixed on
`0ca5723a26`, so the clean 2-hour window restarts there and ends about 11:10 PDT.

| fault | what the log showed | fix |
|---|---|---|
| a jam re-escalates every 30 min, no limit | `fold-failure:rowless lane/titleroutes` at escalation 4 (Opus) by 08:53 | at most 2 sessions per jam instance (Sonnet, then Opus); then summary.txt says `NEEDS lane.local` |
| disk-low escalates to a model | in the code (addendum 1 forbids it) | inbox note for lane.xbox, once; never a model |
| a territory fold gap escalates | the same titleroutes jam; no session may edit the board | inbox note only; never a model |
| stranded-lane on a lane that is not stranded | memfast one minute after it wrote WAITING; routefix1002 between its own sessions | skips a WAITING file, a head in master, and a lane idle under 90 min |

Selftest 87: 49 passed, 0 failed; each fix reverted fails its leg. Live-state shadow tick at 09:01: one jam
(titleroutes' missing board row), inbox note only.

The titleroutes jam is real and has been open since 10-02 05:01: `lane/titleroutes @ fa4312e821` cannot fold
because there is no `[lane.titleroutes]` row on the board. Lane.local: add the row, or retire the branch.

NEW ISSUE: ops cutover: the PM's DO items in hostops-inbox.md lose their executor when hostops is turned off
host-tools/pm-role.md:76 tells the PM to append each DO action to host-tools/hostops-inbox.md, and pm_tick.sh's
overnight task says "hostops executes it". docs/testing/jobs/ops/ops_tick.py (lane.opsrebuild, #433) detects jams
from local state and does not read the inbox, by design. When lane.local swaps hakux-hostops.timer for
hakux-ops-tick.timer, nothing executes the PM's actions. This blocks the #433 cutover. Options: the PM executes
its own DO items; lane.local executes them; or a small inbox runner spawns one scoped session per new DO item
(the ops_escalate.sh pattern, with the same cap).

## #433 -- 2026-10-03 10:40 PDT

[lane.opsrebuild] waiting: the clean 2-hour shadow window on `4ab2956d8a`, ticks 09:48 to 11:48 PDT.
A fifth fix landed at 09:44 and restarted the window. At 08:58 a detector raised a NameError and cleared its open
jams, so the next tick would have resumed those lanes a second time. A failing detector's jams now stay open (leg o).

Full selftest on this harness content: 3051 passed, 0 failed, all 124 fragments. 87-ops-tick.sh: 51 passed. Every
attempt-4 fix fails its own leg when reverted.

Resume: WAITING holds `time 2026-10-03T11:50`. Then this lane compares logs/ops-shadow.log with hostops's entries
for 09:48 to 11:48, posts the comparison here and in shadow-comparison.md, and sets PR.md `State: ready` if the window
is clean. The cutover is lane.local's, once the NEW ISSUE above (who executes the PM's inbox items) has an answer.

