# localjobs: local, model-free replacements for the five GitHub-bound timers (#433)

State: ready

Lane: localjobs                Issue: #433 (0.5: 50 Playable)
Base: origin/master @ 0f07dbfede
Files: docs/lanes/localjobs/**
Prediction: none: analysis/host-infrastructure, no arm
Needs device: no

## Summary

GitHub suspended jreinach-alt on 2026-09-29; the owner (2026-10-01 21:40
PDT) asked for the five stopped GitHub-bound timers (`hakux-board`,
`hakux-pr-sweep`, `hakux-issue-sweep`, `hakux-comments`, `hakux-fold`) to
get local, repo-reading replacements. Full per-job table (what each did,
what still matters with no GitHub, what replaces it) is in
`docs/lanes/localjobs/NOTES.md`.

**Model-free first, as instructed, and most of the five jobs turned out not
to need a replacement at all** once GitHub's part of each outcome is
subtracted: the audit-label pipeline (`needs-audit-*`, `claimed:cloud`)
does not exist locally, GitHub open/closed issue state cannot be read
locally, and `hakux-fold`'s job is already done locally
(`foldqueue.sh`/`offline_fold.py`, since 2026-09-30 -- untouched by this
lane, per the brief's constraint). What was genuinely left and genuinely
decidable from files:

- **`host-tools/local_board.sh`** (new, timer `hakux-local-board.timer`,
  20 min) -- board's and pr-sweep's "which lane is in what state, what is
  blocked" outcome: reads every unfolded `origin/lane/*` branch's
  `docs/lanes/<lane>/PR.md`, whether its unit is running, and whether
  `foldqueue.sh`'s own `foldqueue.tried`/`foldqueue.waiting` already has an
  opinion on its head. Live run found 2 real stranded drafts
  (`lane.ibcache`, `lane.verdict433`) and 4 unfolded-looking-but-already-
  merged branches whose territory row nobody has retired (board is offline).
- **`host-tools/local_issue_audit.py`** (new, timer
  `hakux-local-issue-audit.timer`, 2x/day) -- issue-sweep's two classes that
  need no GitHub: tracker rows still `unclassified`, and territory rows
  claiming an issue for a lane that no longer exists locally (unit gone AND
  branch gone-or-merged), explicitly exempting `remote`-tagged lanes (a
  cloud lane's liveness cannot be read from a local unit or branch -- same
  caution the GitHub version needed, and this host has less visibility
  into one, not more). Live run found 4 ghost rows, all cross-checked
  against `foldqueue.log` FOLDED entries.
- **`hakux-comments`**: nothing uncovered. The lane->owner direction is
  already `offline_status.py`'s OUTBOX relay; the owner->lane direction and
  the fold-failure-routing direction already have their own mechanisms.
  Documented, not built.
- Both new timers are present under `~/.config/systemd/user/` **installed
  disabled** (not enabled, not started -- this lane ran neither
  `daemon-reload` nor `enable`). `lane.local` enables them after reading
  this report. Re-enable order for the original five units, once GitHub is
  back, is in NOTES.md section 3 (local replacements stop first).
- Selftest: `host-tools/local_jobs_selftest.sh`, a scratch bare repo with a
  branch in every state both tools must distinguish (including one that
  genuinely conflicts with master, verified by a real merge attempt then
  aborted, and one already folded into master) plus a scratch
  territory/tracker fixture. 14 checks, all green. Not wired into
  `docs/testing/jobs/selftest.sh` (that harness is for the `gh`-dependent
  jobs and is already near its CI time budget; neither new tool calls `gh`).

## What this PR touches in git, and what it does not

**Files: `docs/lanes/localjobs/**` only** -- this NOTES.md and this PR.md.
Every operational artifact (the two scripts, the selftest, the four
systemd unit files, the one new line-pair in `offline_hourly.sh`) is a host
file under `/home/justin/hakux-work`, **not tracked in this git
repository** -- the same place every prior piece of this offline layer
already lives (`foldqueue.sh`, `offline_fold.py`, `offline_status.py`,
`offline_hourly.sh`, `lanewatch_once.sh` are all untracked host files, not
`hakuX.git` commits). This is not a scope-reduction after the fact: it is
the existing, established home for this exact kind of tool, and putting a
`gh`-free local script into `docs/testing/jobs/` beside the five
GitHub-bound ones it replaces would be the inconsistent choice.

Exact paths, for the audit trail:
- `/home/justin/hakux-work/host-tools/local_board.sh` (new)
- `/home/justin/hakux-work/host-tools/local_issue_audit.py` (new)
- `/home/justin/hakux-work/host-tools/local_jobs_selftest.sh` (new)
- `/home/justin/hakux-work/offline-git/offline_hourly.sh` (edited: two new
  summary lines; this file is explicitly NOT in the forbidden list --
  `offline_fold.py`, `foldqueue.sh` and the fold timers are)
- `/home/justin/.config/systemd/user/hakux-local-board.{service,timer}` (new, disabled)
- `/home/justin/.config/systemd/user/hakux-local-issue-audit.{service,timer}` (new, disabled)

## Local checks run (no CI available, per the offline protocol)

- `bash /home/justin/hakux-work/host-tools/local_jobs_selftest.sh` -- 14/14 checks pass.
- `bash -n` on both new shell scripts; `python3 -c "import ast; ast.parse(...)"` on the new Python script.
- Ran both tools live (read-only; `list` mode for the board tool, default
  mode once for the issue audit) against the real stand-in and the real
  `origin/board`; findings cross-checked by hand against `foldqueue.log`
  and `fold-failures.log` (see NOTES.md).
- No harness files under `docs/testing/` changed, so
  `docs/testing/jobs/selftest.sh` does not apply.
- No emulator code changed; no device run needed to fold this PR
  (`offline_fold.py`'s device-run check is N/A for a docs-only change).
- Confirmed territory: only `docs/lanes/localjobs/**` touched in git; no
  edits to `territory.toml`, `nv2a_issues.toml`, `offline_fold.py`,
  `foldqueue.sh`, the fold timers, or `host-tools/hostops-inbox.md`.

Release note (none): offline host-infrastructure tooling only; no emulator
code changed, nothing a player would notice.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
