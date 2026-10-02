# localjobs (#433): local, model-free replacements for the five GitHub-bound timers

Owner, 2026-10-01 21:40 PDT: GitHub suspended jreinach-alt on 2026-09-29; the
owner is still waiting on support, and restarted sessions at 21:00 wanting
"Github timers will need replacements that point at the local repo instead."
Five units were stopped at that restart: `hakux-board`, `hakux-pr-sweep`,
`hakux-issue-sweep`, `hakux-comments`, `hakux-fold`. This lane reads each,
says what still matters with no GitHub, and builds the local-only,
model-free equivalent for whatever does.

Everything here is **offline, read-only infrastructure**: no device work, no
dispatch requests, no edits to `territory.toml` or `nv2a_issues.toml`, no
edits to `offline_fold.py` / `foldqueue.sh` / the fold timers (lane.local's
alone), no edits to `host-tools/escalations.md` or `hostops-inbox.md` beyond
this lane's own DONE line (there is none needed -- nothing here was routed
through hostops). The deliverable is almost entirely **host files outside
this git repository**, because that is where every prior piece of this
offline layer already lives (`foldqueue.sh`, `offline_fold.py`,
`offline_status.py`, `offline_hourly.sh`, `lanewatch_once.sh` are all plain
files under `/home/justin/hakux-work`, not tracked in `hakuX.git`, and the
five GitHub-bound jobs they replace live in `docs/testing/jobs/` precisely
because they are reviewed-and-folded product code. The new tools below are
the same kind of thing the five prior offline tools are, so they live beside
them, not inside the repo). This PR's git footprint is this directory alone.

## 1. What each job DOES, and what still matters with no GitHub

| Job (unit) | What it did for the harness | Still matters offline? | Local equivalent |
|---|---|---|---|
| `hakux-board` (`docs/testing/jobs/board.sh`, 20 min) | (a) picks a dispatchable issue and starts a lane when there is capacity; (b) sets the first pipeline label (`needs-audit-1`, `fold-ready` on docs-only) on a ready, unlabelled PR; (c) is the one place a person/future reader sees "which lane is in what state" | (a) **No** -- which issue to dispatch is a judgement call (a brief, the owner's focus label, risk), not a fact on disk; a script cannot replace it and none is attempted. (b) **No** -- the local stand-in has no audit-label pipeline at all: a lane's PR.md goes straight from `State: ready` to `foldqueue.sh`'s attempt. (c) **Yes** -- lane state and what's blocking it is exactly what a script can read off git + systemd + foldqueue's own files. | `host-tools/local_board.sh` (new) |
| `hakux-pr-sweep` (`docs/testing/jobs/pr-sweep.sh`, 3 h) | five classes: orphaned `claimed:cloud` (repaired), stranded draft with no lane unit (reported), ready PR with no state label (reported), fold-ready PR whose red predates the current trunk head -- "stale-red" (reported, `fold.sh` owns the fix), `regressed` label disagreeing with `arms.sh state` (reported) | `claimed:cloud`/no-state-label: **No**, GitHub-label pipeline that does not exist locally. Draft-strand: **Yes**, same local facts as board's (c). Stale-red: **partially** -- the local analogue is a FAILED head in `foldqueue.tried` that is never retried until the BRANCH moves, even if master's side of the failure is since fixed; that is real and worth surfacing. `regressed`-vs-`arms.sh state`: **not attempted** -- `arms.sh`'s verdict mechanism and whether it still runs meaningfully with no GitHub PR to comment on is a separate, deeper question than this lane's scope; flagged below as a gap, not answered. | folded into `host-tools/local_board.sh` (same lane-state read, same report) |
| `hakux-issue-sweep` (`docs/testing/jobs/issue-sweep.sh`, 2x/day) | five classes, all computed by comparing `nv2a_issues.toml`/`territory.toml` against live GitHub: no tracker row for an open issue, untriaged (`disposition` unclassified), a `lane:` label or territory row naming a dead lane ("ghost"), a tracker row calling the work done while the issue stays open ("closable"), and `dispatch_state="available"` with nobody on it ("unpicked") | No-tracker-row and closable: **No** -- both need GitHub's open/closed state for an issue, which does not exist locally and this lane was told explicitly not to invent (no local issue tracker). Unpicked: **No**, for a sharper reason than "needs GitHub" -- checked by hand against the live `nv2a_issues.toml` (2026-10-01) and **the `dispatch_state` field this class reads does not exist in the file at all** (zero matches across the whole tracker); `issue-sweep.sh`'s own class 5 is already reading a key the real schema dropped or never had, GitHub or not. Untriaged: **Yes**, a plain field read, no GitHub needed. Ghost: **Yes**, and locally it is *more* complete than the GitHub version, which needed a network call for "is there an open PR"; locally that becomes "is there a pushed, unmerged branch", read for free. | `host-tools/local_issue_audit.py` (new) |
| `hakux-comments` (`docs/testing/comment_sweep.sh`, hourly) | one `gh api .../issues/comments?since=` call surfacing every comment nobody has read, filtered to non-job comments, delivered as a GitHub comment (the owner reads from a phone) | The *lane -> owner* direction is already covered: `offline_status.py`'s OUTBOX relay (`docs/lanes/<lane>/OUTBOX.md`) is exactly this, read at every check-in. The *owner -> lane* direction already has its own mechanism (brief addenda / held messages, per the harness's existing "messages to lane sessions are held" convention) and was never comment_sweep's to cover. The remaining case -- a fold failure or other host-side finding that needs routing to a lane -- is already handled: `foldqueue.sh` on a FAILED head appends to `host-tools/hostops-inbox.md`, which lane.local reads at check-ins. **Nothing uncovered was found.** | none; documented, not built |
| `hakux-fold` (`docs/testing/jobs/fold.sh`, 30 min) | merges ready, green, disjoint PRs into master; resolves the generated-index and root-NOTES.md conflicts; hands back real conflicts; prunes folded branches | **Already local**: `foldqueue.sh` -> `offline_fold.py`, on `hakux-foldqueue.timer` (15 min), since 2026-09-30. This lane touched neither, per the brief's explicit constraint. | n/a (lane.local's) |

## 2. What was built

### `host-tools/local_board.sh` (new; timer `hakux-local-board.timer`, 20 min, installed disabled)

For every `origin/lane/*` branch not yet an ancestor of `origin/master`:
reads whether it carries a `docs/lanes/<lane>/PR.md` (the exact same
`grep -E '^docs/lanes/[^/]+/PR\.md$'` detection `foldqueue.sh` itself uses,
so the two scripts never disagree about which branches have "opened a
PR"), its `State:`, whether a `hakux-lane-<lane>` unit is running, and
whether `foldqueue.sh`'s own `foldqueue.tried` / `foldqueue.waiting` files
already have an opinion on its head. Three buckets in the report:
blocked-ready-or-stranded-draft (needs a look), waiting-on-the-ordinary-cycle
(not stuck, just pending a device run), and other unfolded branches with no
PR.md at all (lowest priority -- mostly pre-dates the offline protocol).

Pure read: no label, no comment, no lane start/resume, so there is nothing
to deduplicate and no "said" cache -- it overwrites
`$WORK/status/local-board.md` every tick, which is the entire side effect.

Run against the live stand-in while writing it (read-only, nothing
committed by the run): 2 genuinely stranded drafts surfaced on the first
pass, **`lane.ibcache`** and **`lane.verdict433`** -- both `State: draft`,
no `hakux-lane-*` unit running, unfolded. Neither this lane nor this script
resumes them; that is for a person or `lane.local` to decide. Also surfaced:
4 branches already fully merged into master whose `territory.toml` row is
still live (see the issue-audit finding below) -- consistent with the board
being the only actor that retires a row, and the board being offline.

### `host-tools/local_issue_audit.py` (new; timer `hakux-local-issue-audit.timer`, 2x/day, installed disabled)

Reuses `docs/testing/board_files.py` (the existing `origin/board`-preferring
loader every other job already depends on -- not reimplemented) to read
`territory.toml` and `nv2a_issues.toml`, and reports:

- **unclassified**: tracker rows with `disposition` empty or
  `"unclassified"`. (0 on the live tracker as of this run -- the class is
  wired and correct, just currently empty.)
- **ghost-owned**: a non-`standing` `[lane.<name>]` territory row claiming
  one or more issues, where lane `<name>` has no running unit AND no
  `origin/lane/<name>` branch carrying a commit master lacks. A row marked
  `remote = "<branch>"` (a cloud lane, e.g. `lane.remote`) is **never**
  judged by this test and is reported in its own, separate line instead --
  this is deliberately the same caution `remote-lane.sh` encodes for the
  GitHub version, because a cloud session's branch is not `lane/<name>` and
  neither a local unit nor a local branch tells you anything about whether
  it is alive. Getting this wrong is exactly the defect that released
  `lane.remote`'s live claims as stale four times on 2026-09-19 (per
  `issue-sweep.sh`'s own header); the offline version has *less* visibility
  into a cloud session than the GitHub one did, not more, so the exemption
  matters even more here.

  Live run, 2026-10-01: **4 ghost rows** --
  `lane.defecttriage433` (#433), `lane.forzadecay414` (#414),
  `lane.shaderprebuild569` (#569), `lane.uberspike569` (#569). Cross-checked
  against `foldqueue.log`: `forzadecay414-fix`, `forzadecay414-fix-notes`,
  `forzadecay414-step` and `shaderprebuild569` all show `FOLDED` entries.
  These are real, retirable rows that nobody has retired because the board
  -- the only actor that edits `territory.toml` -- is the job that is
  stopped. This lane does **not** touch `territory.toml`; it only reports.
- Explicitly **not** attempted, and said so in the script's own docstring
  and in its report every run: "no tracker row for an open issue" and
  "tracker row says done, issue still open" (both need GitHub's open/closed
  state, which this host cannot see), and the `dispatch_state`-keyed
  "unpicked available" class (the field does not exist in the live tracker;
  see the table above).

### Selftest: `host-tools/local_jobs_selftest.sh` (new)

Builds a scratch bare repo standing in for the stand-in (`$T/origin.git`), a
scratch `HAKUX_REPO_DIR` checkout, a scratch `HAKUX_WORK`, and a `systemctl`
shim on `PATH` that reports only units this fixture puts in a plain file --
so "no unit running" is deterministic rather than depending on whatever
happens to be running on this host. Lane branches cover every state both
tools must tell apart: ready-and-healthy, ready-and-blocked
(`foldqueue.tried`), ready-and-waiting (`foldqueue.waiting`), draft with no
unit (stranded), draft WITH a unit (must NOT be flagged), no-PR.md-at-all,
**a branch that genuinely conflicts with master** (verified by a real
`git merge --no-commit`, then aborted -- proving both tools read git
plumbing and never attempt a merge themselves), and a branch already folded
into master (must produce nothing). For the issue audit: a ghost row, a
live row (unfolded branch), a `standing` row, a `remote` row, and one
unclassified / one classified tracker row. 14 checks, run standalone
(`bash host-tools/local_jobs_selftest.sh`), all green.

Not wired into `docs/testing/jobs/selftest.sh`: that harness exists to run
the *GitHub-bound* jobs against faked `gh`/`systemctl`/`adb` shims inside a
shard budget already measured at 18-25 minutes against a 25-minute CI cap.
Neither new tool calls `gh` at all, so reaching into that harness would add
risk (a wrong shard assumption, a budget overrun) for no shared fixture
benefit. A standalone script is simpler and cannot affect that CI job's
timing.

## 3. Re-enabling the five original units when GitHub is restored

In this exact order -- the local replacements must stop FIRST, or a window
exists where both the old and new tooling act on the same state:

```
# 1. stop the local replacements (once lane.local has enabled them -- see below)
systemctl --user disable --now hakux-local-board.timer hakux-local-issue-audit.timer

# 2. restore GitHub auth (gh auth login / token refresh) -- outside this lane's scope

# 3. re-enable the five original units
systemctl --user enable --now hakux-board.timer hakux-pr-sweep.timer \
    hakux-issue-sweep.timer hakux-comments.timer hakux-fold.timer
```

`hakux-fold` was never stopped in the sense that matters: `foldqueue.sh`
already does its job locally, so re-enabling the GitHub `fold.sh` timer
needs its own decision about whether to run both (fold.sh would find
nothing to do once GitHub's own PRs exist again and the stand-in's
`lane/*` branches are already folded by `foldqueue.sh`) -- not addressed
here, left for whoever restores GitHub access to judge against the state
at that time.

## 4. What was NOT built, and why (read this before assuming a gap is a bug)

- **No automatic lane dispatch.** Picking which issue to work on next needs
  a brief and a judgement call; `local_board.sh` reports capacity
  (`$n_units/$LANE_MAX`) and nothing more.
- **No automatic resume of a stranded draft.** `local_board.sh` finds
  `lane.ibcache` and `lane.verdict433` stranded and says so; it does not
  call `lane.sh resume`. The brief's own rule is explicit: a model session
  starts only when a script finds something a script cannot decide, through
  the existing lane/job machinery -- resuming a lane is exactly that kind of
  decision (is the draft actually finished-but-unmark, or genuinely
  abandoned, or does its brief need an addendum first?), and it is not this
  lane's to make unattended.
- **No new issue tracker, and no `dispatch_state`-based "unpicked" class.**
  Per the brief: do not invent one. Said plainly in both the table above and
  the script's own report, every run.
- **No change to `arms.sh`'s regressed-label verification.** `pr-sweep.sh`'s
  fifth class re-reads `arms.sh state <branch>` and compares it to a GitHub
  label; whether `arms.sh` verdicts still mean the same thing with no
  GitHub PR to comment results onto is a question this lane did not open --
  it would need its own investigation of `arms.sh`'s current behavior
  offline, which is out of scope for a timer-replacement lane and is left
  as a named gap rather than guessed at.
- **Timers are written to `~/.config/systemd/user/` but never enabled or
  started by this lane**, per the brief's explicit instruction. Both
  `.timer` units are present on disk and inert; `lane.local` runs
  `daemon-reload` and `enable --now` after reading this report.
