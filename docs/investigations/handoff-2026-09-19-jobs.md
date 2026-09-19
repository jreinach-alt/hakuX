# Hand-off: the job harness, from the remote session to a local one (2026-09-19)

Written by the remote session that built the job harness today, for the local
Claude Code session on the host (`/home/justin/hakuX`) that takes it over.
The reason for the hand-off is stated first because it is the lesson.

## Why the hand-off

Every script under `docs/testing/jobs/` runs only on the host: systemd user
units, `gh`, `adb`, the dispatch directory, the goldens tree. The remote
session could not execute any of it. So every defect surfaced on the host,
the owner carried the error text back by hand, and the owner was the merge
step for every fix. Four cycles of that in one evening. A local session can
run the scripts, read the dispatcher log, and fix in place; that is the whole
point of moving.

**Rule from here on:** nothing under `docs/testing/jobs/` is pushed without
`docs/testing/jobs/selftest.sh` passing. It runs the real scripts against a
fake host and is also a CI workflow (`.github/workflows/jobs-selftest.yml`).

## Where things stand

**Merged to master (PRs #96, #97, #98, #100, #103, #105, #106, #108):**

- `master` is the trunk. Lane branches `lane/<name>`; folds are `--no-ff`
  merges; the board files live on the orphan `board` branch.
- Board job (`jobs/board.sh`, `hakux-board.timer`, every 20 min, Sonnet,
  70 turns): script-first, starts a model tick only when `fleet.py` or the
  coverage gate reports something. Role file `jobs/roles/board.md`.
- Lanes (`docs/testing/lane.sh`): worktree from `origin/master`, transient
  unit `hakux-lane-<name>`, Opus, attempt counter, fourth attempt on Fable,
  cap `LANE_MAX=2`, role file `jobs/roles/lane.md` (PR template, definition
  of done: mark the PR ready).
- Arms job (`jobs/arms.sh`, `hakux-arms.timer`, every 30 min, a script):
  queues both arms of every registered prediction on master, any lane
  branch, or `$D/expect` whose refs resolve and whose `b_ref` is an ancestor
  of a live tip; judges finished pairs with `ab_compare.py`; posts
  `[job.arms]` verdicts on the lane's PR; `verified`/`regressed` labels.
  Watermark `$WORK/arms/since`; refusals in `$WORK/arms/skipped/<sha>`.
- Fold job (`jobs/fold.sh`, every 30 min, a script): one `fold-ready`,
  non-draft, CI-green PR per tick, merged `--no-ff` in `$WORK/fold-wt`,
  index regenerated if moved, preflight `--allow-tracker`, push, `folded`.
- Cloud-class job (`jobs/cloud.sh`, `hakux-cloud.timer`, hourly, `CLOUD_MAX=1`,
  audit model): claims one no-device unit (remediation on `lane/cloud-*`,
  audit pass 2, audit pass 1, a `cloud` issue), role `jobs/roles/cloud.md`.
  Runs on the host because a Routine fired from a session has no repo, no
  GitHub tooling and stalls on a permission prompt (four diagnostic
  sessions, zero branches pushed).
- Status roll-up (`jobs/status.sh`, after every tick and every 30 min):
  one comment on issue #107 (`harness-status`), plus `$WORK/status/STATUS.md`.
- `jobs/run-trunk.sh`: every script unit runs from `$WORK/jobs-wt`, a
  detached worktree of `origin/master`, so the host checkout's branch does
  not matter. `install-host.sh` installs units, timers, labels, watermark.

**On PR #113, not yet merged (branch `claude/hakux-orchestration-design-e663m8`):**

- The fix for the first real refusal: a prediction without `runs_per_arm`
  was handed to `request.sh` as `--runs ""` and its JSON writer died on
  `int("")`. This refused #89's arm at 02:56Z. Fixed and self-tested.
- `request.sh` refusals are posted on the lane's PR as `[job.arms] REFUSED`.
- A refusal recorded by an older `arms.sh` is retried automatically when
  the script changes (the skipped marker carries `arms=<md5>`), so nobody
  has to `rm` a marker on the host.
- Status page: job-errors section, full refusal text, eight-column index
  rows read correctly, no abort on a `?` field.
- `jobs/selftest.sh` and its CI workflow.

## The immediate goal, in order

1. Merge #113 (or let the fold job do it, see the open decision below).
2. On the host: `docs/testing/jobs/selftest.sh` must pass. Then
   `systemctl --user start hakux-arms.service` and watch
   `$WORK/logs/arms/tick.log` for `queued base <id> fix <id>` and
   `$D/logs/dispatcher.log` for a build of `3f2563d6e9` (PR #102's
   prediction for #89, suites `Blend surface,Color mask blend,Color zeta
   overlap`). Both APKs are uncached: 2 to 5 minutes each, then the discs.
3. Within the hour after the runs: `[job.arms] VERDICT` on PR #102, the
   `verified` or `regressed` label, and the verdict on #107.
4. Then the fold path end to end: PR #101 is docs and a falsifier only; mark
   it ready (`gh pr ready 101`), the board should label it `fold-ready`
   (doc-only rule) or do it by hand, and the fold job folds it. First fold.
5. Then the audit path: PR #102 marked ready gets `needs-audit-1`; the
   cloud-class tick claims it; pass 1 lands as a review and a file under
   `docs/audits/`.

## Known gaps and open decisions

- **Owner decision, asked and pending:** may harness PRs (touching only
  `docs/testing/jobs/**`, `docs/testing/systemd/**`, docs) be labelled
  `fold-ready` by the session that opened them, so the fold job merges them
  and the owner is not a step? Units still need `install-host.sh` by hand.
- **No hardware listener** for the `xbox-hardware` issues (#109 to #112).
- **Triage Routine, lane Stop hook, device-health timer, bot account** are
  still unbuilt (design doc §13 Phase 1).
- **Real cloud Routine:** would run `roles/cloud.md` unchanged, but has to be
  created from the claude.ai Routines UI with the repo, a GitHub connector
  and a non-prompting permission mode. Not doable from a session.
- `hakux-comments.timer` (the old comment sweep) still runs hourly; the
  board reads its report only if told to. Fold into the board tick or retire.
- The board's tick hit the 70-turn cap once; if it repeats, raise
  `BOARD_TURNS` in `$WORK/limits.env` or split its brief.

## Invariants that must survive any change

- Never `pkill -f` a pattern that matches your own shell; kill by PID.
- Never `pm uninstall` the release package; never `adb shell input keyevent`.
- The board branch is the board job's only push target; lanes never edit
  `nv2a_issues.toml` or `territory.toml`.
- A prediction is registered before the run, committed with its refs, never
  rebased after. The arms job refuses a `b_ref` that is not an ancestor of a
  live tip on purpose.
- Folds are `--no-ff`. Commits keep their shas; that is what keeps every
  registered `b_ref` bound.
- Models: bookkeeping on Sonnet, lanes on Opus, fourth attempt on Fable,
  audits on Opus (`jobs/models.env`, overridden by `$WORK/limits.env`).

## Paste prompt for the local session

```
You are taking over the hakuX job harness from the remote session. Read
docs/investigations/handoff-2026-09-19-jobs.md first, then AGENTS.md's
transition note and docs/ORCHESTRATION-DESIGN.md §4, §9, §13.

Your first job is to make the pipeline demonstrably move end to end on
this host, fixing defects in place and pushing each fix through a PR
that passes docs/testing/jobs/selftest.sh:

1. Merge or fold PR #113, then run docs/testing/jobs/selftest.sh here.
2. Get #89's arm (PR #102's prediction) queued, built and run on the
   handhelds: systemctl --user start hakux-arms.service, then watch
   ~/hakux-work/logs/arms/tick.log and
   ~/hakux-work/dispatch/logs/dispatcher.log. Fix whatever stops it.
3. Confirm the verdict lands on PR #102 and on issue #107.
4. Take PR #101 through the fold path (ready, fold-ready, folded).
5. Take PR #102 through audit pass 1 via the cloud-class tick.

Rules: never AskUserQuestion; ask in plain text at the end of a message
and keep working. Never push to master by hand; the fold job does that.
Every change under docs/testing/jobs/ ships with selftest.sh green.
Report each stage as a comment on issue #107's thread only if the
status roll-up cannot show it; otherwise let the roll-up speak.
```
