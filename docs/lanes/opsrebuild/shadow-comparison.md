# ops_tick.py --shadow vs. the current state (#433, step 5)

## What was run

```
env OPS_STATE_DIR=<scratch dir under this worktree> python3 docs/testing/jobs/ops/ops_tick.py --shadow
```

Every other path (`HAKUX_WORK`, `HAKUX_REPO_DIR`, `DISPATCH_DIR`, the fold-failures log, the
device-reality file, `briefs/`) was left at its real default, so the detectors read the actual
host state. `--shadow` guarantees nothing was written outside `OPS_STATE_DIR` and nothing was
run against a lane, a hold, or `claude -p` -- see `run()`'s `if jam.remedy and not shadow` and
the escalation branch's `if shadow: ... else: run_escalation(...)` in `ops_tick.py`. This is a
genuine run against production local state, not a simulation.

## Tick 1 -- 2026-10-02 10:51 PDT

9 jams after the stale-head fix below (11 before it; see "what the shadow run found" below):

| class | subject | would-be remedy |
|---|---|---|
| `stranded-lane` | `bf2ubosize433` | append addendum, `lane.sh resume bf2ubosize433` |
| `stranded-lane` | `verdict433` | append addendum, `lane.sh resume verdict433` |
| `fold-failure:territory` | `lane/uberspike569-gpl` | write `hostops-inbox.md` request |
| `fold-failure:no-device-run` | `lane/forzadecay414-fix` | route to the lane (addendum + resume) |
| `fold-failure:rowless` | `lane/titleroutes` | write `hostops-inbox.md` request |
| `fold-failure:territory` | `lane/routedriver` | write `hostops-inbox.md` request |
| `fold-failure:territory` | `lane/ibcache` | write `hostops-inbox.md` request |
| `fold-failure:territory` | `lane/snapdrive` | write `hostops-inbox.md` request |
| `fold-failure:territory` | `lane/stopmarker` | write `hostops-inbox.md` request |

Nothing from `hold-overbound`, `queue-stale`, `timer-unanchored`, `failed-unit`, `battery-floor`/
`battery-lift`, `disk-low`, or `stopped-lane-queued`: checked, clean. (`stranded-lane` for
`titleroutes2` was also checked and correctly NOT reported -- see below.)

## Tick 2 -- 2026-10-02 10:56 PDT (independent run, five minutes later)

Identical 9 jams, same classes and subjects, nothing added or dropped. **This was not evidence of
stability.** Shadow mode did not persist its jam rows, so both ticks announced every jam as NEW. The
two runs agreed only because they shared the same bug. See "Overnight run" below.

## Cross-check against `status/local-board.md` (hakux-local-board.timer, lane.local's own
model-free script, last written 2026-10-02T17:20:18Z -- 30 min before this tick)

- local-board.md's stranded-draft list: `bf2ubosize433`, `titleroutes2`, `verdict433` (3).
  ops_tick found 2 of the 3 -- it correctly EXCLUDES `titleroutes2`, because
  `briefs/titleroutes2.md.STOPPED-by-owner-20261002-0825` exists. local-board.md's own listing
  does not make this distinction (it reports "DRAFT, no unit running" for all three alike); its
  text even says "This script does not resume lanes; see the report" -- it is a report, not an
  actor, so it never needed the STOPPED check. ops_tick.py is the first of the two to actually
  decide whether to act, and it decides correctly: a STOPPED lane is never resumed, so excluding
  it from the jam list in the first place (rather than opening a jam and then refusing its own
  remedy) is the right shape.
- local-board.md flags `titleroutes` (fa4312e821) as "ready, BLOCKED: fold-failed, see
  fold-failures.log". ops_tick classifies the SAME branch/head as `fold-failure:rowless` (its
  failure reason is "no [lane.titleroutes] row on origin/board") and would write the inbox note
  that names exactly what is missing, instead of leaving a person to open fold-failures.log.

## A real defect the live data surfaced and the fix it produced

The first tick (before the fix below) reported 11 jams, including `fold-failure:territory` for
`lane/hitchwatch` and `fold-failure:no-device-run` for `lane/forzadecay414-fix-notes`. Both
branches have pushed new commits since the recorded failure (visible in `git log
origin/lane/hitchwatch` etc.) -- the fold-failures.log line is stale: the lane may already have
fixed what failed and be waiting on a fold retry, not stuck on the old problem. The first cut of
`det_fold_failures` treated a branch as open forever once logged, until a `FOLDED <branch>` line
appeared -- which never happens for an abandoned attempt that a NEWER commit superseded without
ever folding. Fixed before this run: the detector now drops a branch whose current
`origin/<branch>` head no longer starts with the failure's recorded head
(`docs/testing/jobs/ops/ops_tick.py`'s `det_fold_failures`, the loop right after the cursor
advance). Covered by a new selftest leg ("a fold-failure jam whose branch has since moved on is
dropped, not kept open"). This is exactly the kind of thing a >= 2 h shadow run is for: it was
found in the FIRST five minutes against real data, not in the fixture tree.

A second real bug surfaced while hardening the test suite, not from the live shadow data: the
first cut of `det_battery_floor`'s `hold.sh take` reason string embedded a bare `<` and
`(ops_tick)` -- both shell metacharacters under `ops_tick.py`'s `shell=True` `sh()` (a
redirection, and a syntax error as a bare word; `bash -c 'echo ... < 15% (ops_tick)'` fails
outright). The live shadow run never exercised this path (neither handheld was below its
battery floor), so it was caught only by adding a battery-floor/lift selftest leg and testing it
-- confirmed by reverting the fix and re-running, which fails loud. A third: `jams.tsv` is
tab-separated, but `remedy_tried` stores a command's raw (truncated, not scrubbed) stdout --
caught the same way, by writing a direct `save_jams`/`load_jams` round-trip leg with an embedded
tab and newline in it, confirmed likewise by reverting the fix. None of the three would have
shown up in a read-only code review; each needed something to actually execute the path.

## What this lane could NOT do: the full >= 2 h side-by-side

The brief asks for `ops_tick.py --shadow` run for >= 2 h alongside hostops, with the comparison
posted. This session cannot block for 2 h: every foreground Bash call is capped at 10 minutes,
and ending a session waiting on a background timer across turns is exactly the failure mode this
project's own memory warns about (a lane's `run_in_background` work dies with the session; see
`roles/lane.md` and the "lane background task dies with session" note). What IS done: the
detectors, remedies, and escalation wiring are implemented and unit-tested
(`selftest.d/87-ops-tick.sh`, 28 legs), and the run above is a genuine (if short) shadow tick
against live production state that already caught the stale-head bug before any device or lane
was touched. **For lane.local, before cutover:** run
`env OPS_STATE_DIR=$HAKUX_WORK/host-tools/ops-shadow python3 docs/testing/jobs/ops/ops_tick.py
--shadow` on a 5-minute timer (the same cadence the real timer will use) for >= 2 h, diff
`ops-shadow/shadow.log` against what hostops did over the same window (`hostops-inbox.md`'s new
entries, any lane it resumed), and only then flip `hakux-ops-tick.timer` on and whatever currently
fires hostops off.

## Overnight run (lane.local's timer, 10-02 22:19 onward) and what it found

`hakux-ops-shadow.timer` ran `ops_tick.py --shadow` from this worktree every 5 minutes into
`host-tools/ops-shadow` (101 ticks logged in `logs/ops-shadow.log`). It showed three faults, fixed in
attempt 2 (see NOTES.md, "Attempt 2"):

- Every jam was announced `NEW JAM` on every tick: 594 announcements for the six fold jams, 99 for the
  stranded lane. Cause: shadow never persisted its rows.
- Six fold-failure jams for branches already in master (snapdrive, usagemode, ibcache, routedriver,
  stopmarker, uberspike569-gpl). Cause: no ancestry check against `origin/master`.
- `failed-unit ●`. Cause: the bullet glyph was taken as the unit name.

## Attempt 2 check, scratch state dir, same host state

| tick | jams open | NEW announced |
|---|---|---|
| 1 | 6 | 6 |
| 2 | 6 | 0 |

The six jams on tick 1: `stranded-lane tronhang672`, `stranded-lane verdict433`,
`fold-failure:rowless lane/titleroutes`, `fold-failure:territory lane/savestate433`,
`failed-unit hakux-local-issue-audit.service`, `failed-unit hakux-nightly.service`.

The two failed units are real. The old parse could not have shown them.

The clean 2-hour run on this head is still to come. It is lane.local's to compare against hostops, per
OUTBOX.md's waiting entry.
