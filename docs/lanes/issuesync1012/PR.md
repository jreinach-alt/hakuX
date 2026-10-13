# issuesync1012: one issue number space, mirrored both ways (#433, 0.5)

State: ready

Lane: issuesync1012          Issue: none (harness defect, dispatched directly)
Base: master @ c6e0a63852
Files: docs/lanes/issuesync1012/**
Prediction: none (tooling; dry run only)
Needs device: no    Needs NDK: no

## What this is

Build-and-dry-run only. **No writes were made to GitHub or the forge.** The tool
(`issue_mirror.py`) and the gateway write-path additions it needs are staged
outside the repo at `/home/justin/hakux-work/lanes/issuesync1012/`, reviewed
here as copies plus diffs against the live files. `plan` (read-only) was run
against live, freshly-refreshed data; its full output is
`docs/lanes/issuesync1012/plan_report.md` and summarized below. lane.local
reviews and installs; the backfill, sync, PR closes and allocator wait for
that go-ahead.

## The decision (owner 10-12)

One number per item, GitHub allocates. The forge is never renumbered — that
would orphan the 117 commit subjects on master that already cite forge
numbers >=630 in their forge meaning, and commit messages can never be
rewritten.

1. **Backfill**: create GitHub twins for forge #630..max, in order. Each must
   come back with the identical number.
2. **Lockstep after that**: nothing creates an issue or PR on either side
   except through one allocator (`issue_mirror.py new`): lock, create on
   GitHub first, read back N, then create the forge item and refuse/alarm
   unless the forge number is also N. If the forge is behind, mirror those
   first, in order. A side may be caught up; it is never ahead.
3. **2-way field sync** (`issue_mirror.py sync`) for existing pairs: state,
   title, body, labels, comments — a three-way merge against a stored
   last-synced snapshot. A side that changed propagates; both sides changed
   differently is a conflict (reported, newer side wins once a baseline
   exists). Mirrored writes carry a marker
   (`<!-- hakux-mirror:v1 src=<side>#<N> -->`) so the syncer never echoes its
   own writes back as a conflict.

## Staged files

In `/home/justin/hakux-work/lanes/issuesync1012/` (copied here as the record):

- `issue_mirror.py` — the new tool. Subcommands: `plan`, `backfill --yes
  [--max N] [--pace-per-min N] [--comments now|later]`, `sync --yes`, `new
  --kind issue|pr ...`, `check`, `close-pr N --comment TEXT`.
- `github_gateway.py.diff` — the gateway additions `issue_mirror.py` needs,
  as a diff against the live `host-tools/github_gateway.py`: four new
  subcommands (`issue-create`, `issue-patch`, `issue-comment`, `pr-patch`),
  each going through the existing `open_window()`/`close_window()`/`token()`
  machinery, a per-run write cap, and a secret scan (the existing
  `SECRET_RES` patterns plus new `key.properties`-content patterns and a scan
  of `forge/tokens/*.token` contents) that refuses any outgoing body
  containing one. The staged, already-patched copy (not just the diff) is at
  `/home/justin/hakux-work/lanes/issuesync1012/github_gateway.py` if a
  side-by-side read is easier than applying the diff.
- `issue_sync.py.new` + `issue_sync.py.diff` — `issue_sync.py` now files a
  lane's `NEW ISSUE:` OUTBOX.md block through `issue_mirror.py new` instead of
  the forge shim directly, so a lane-filed issue can never again land on the
  forge with no GitHub number reserved for it. If the allocator refuses (for
  example GitHub unreachable), the item is left unfiled and un-deduplicated,
  so the next timer tick retries it, rather than silently falling back to a
  forge-only create.
- `forge_prsync.py.new` + `forge_prsync.py.diff` — `forge_prsync.py` now
  allocates a brand-new PR's number through `issue_mirror.py new --kind pr`
  instead of POSTing `/pulls` directly. Updating an existing PR, closing a
  folded one, and the "PR.md is gone" case are unchanged.
- `plan_report.md` — the full output of the live `plan` run below.

## Plan summary (live data, refreshed just before this run)

GitHub: 626 items (1-629, minus 119-121, deleted). Forge: 958 items (1-958;
grew from ~952 while this lane worked — five more lane PRs opened). Next
GitHub number: 630.

### 1. Backfill: 329 forge-only numbers (630-958) need a GitHub twin

| kind | state | count |
|---|---|---|
| issue | open | 177 |
| PR | closed | 122 |
| PR | open | 16 |
| issue | closed | 14 |

329 total. (3 more forge-only numbers, 119-121, are *not* backfill: GitHub
deleted those, and the forge keeps them as placeholders from the original
import — recreating them would reintroduce items GitHub chose to remove.)

**Estimated GitHub requests and hours**, paced at 4/min (240/hr — about 5% of
GitHub's 80/min secondary limit and 48% of its 500/hr limit, with slack for
other gateway traffic sharing the same budget):

- Without historical comments: **481 requests, ~2.0 hours** (issues/open PRs
  cost 1 request each; closed-kind items cost 2: create, then PATCH to
  close, since the create API has no `state` field).
- With historical comments mirrored now: **649 requests (168 comments), ~2.7
  hours**. 67 of the 329 backfill items have ≥1 comment (max 11 on one item).
- **Recommendation: mirror comments going forward only, not during backfill.**
  The extra 0.7 hours buys nothing — nobody is waiting on history that is
  already visible on the forge — and `sync` will pick up any comment posted
  after the backfill cutover without special-casing it.

### 2. The 22 state conflicts (closed on GitHub, open on the forge)

#16, 34, 66, 71, 74, 81, 87, 89, 90, 92, 99, 439, 513, 557, 583, 591, 592,
598, 605, 607, 618, 627 — **proposed winner for all 22: GitHub's `closed`.**

Reasoning, from reading each item's latest forge comments and both sides'
`updated_at`:

- #16, 34, 66, 71, 74, 81, 87, 89, 90, 92, 99: GitHub closed these in
  September, **before the forge import ever ran**. The forge's "open" is an
  import artifact, not a later reopen — there is no forge comment or edit
  after the import that would indicate a deliberate reopen.
- #439, 513, 557, 583, 591, 592, 598, 605, 607, 618, 627 (the `[GitHub PR]`
  imported issues): GitHub closed the real PR on/around 2026-10-05, and the
  forge was simply never told. This is exactly the gap `sync` closes going
  forward.
- **#583 is the one to double-check by hand**: its forge `updated_at` (10-09)
  is newer than GitHub's close (10-05), the only one of the 22 where that's
  true. Its forge comments show no post-close activity either, so the
  timestamp looks like metadata churn rather than a real reopen, but it's
  the closest call here.

### 3. The 4 content divergences

- **#1, #161, #568**: the forge import never recovered the original content
  (`"#N: not recovered"`); GitHub has the real item in each case. **Winner:
  copy GitHub's title/body onto the forge record.**
- **#107 is not a conflict to resolve — it's a permanent sync exception.**
  GitHub's #107 is the gateway's own deliberately-maintained static pointer
  at STATUS.md (`cmd_pointer`, `STATUS_ISSUE = 107`, owner-approved
  2026-10-05). The forge's #107 is a different, independently useful,
  live-updating status board maintained by a separate job. Syncing either
  onto the other destroys the one it overwrites. `issue_mirror.py sync`
  hard-codes `NEVER_SYNC = {107}` rather than trying to merge it.

### 4. Three sample backfill bodies, exactly as they would be posted

See `plan_report.md` section 4 for the full text (a reserved-number
placeholder for #630, a closed PR-record for #641, and a closed PR-record for
#643). Every backfill body/title ends with
`<!-- hakux-mirror:v1 src=forge#N -->`.

## How a forge lane PR gets its GitHub twin

**Recommendation: a closed record issue, not a live GitHub PR.**

The brief named two options and asked for a reason tied to the gateway's
`.github/workflows` skip. The gateway's `build_plan()` deliberately skips any
head that touches `.github/workflows` (a fine-grained token without the
Workflows permission would make GitHub refuse the whole atomic push) — so a
"real GitHub PR pushed from the branch" has **no twin at all** for any lane
that touches a workflow file, which is exactly the kind of lane most likely
to need a visible, reviewable GitHub-side artifact. A closed record issue has
no such dependency: it costs the same one GitHub number either way, needs no
branch push, and is the same pattern `backfill` already uses for every
closed/folded forge PR today — one rule instead of two. The forge PR stays
the live, open, reviewable thing; GitHub gets a closed pointer at the same
number, titled `[GitHub PR] <title>`, recording the branch and body.
`issue_mirror.py new --kind pr` implements exactly this.

## Install steps (lane.local)

1. Diff-review `github_gateway.py.diff` against the live
   `host-tools/github_gateway.py` and apply it (or copy
   `/home/justin/hakux-work/lanes/issuesync1012/github_gateway.py` over the
   live file after a final read) — `issue_mirror.py backfill/sync/new/close-pr`
   all call the four new subcommands and do nothing useful without them.
2. Install `issue_mirror.py` at `host-tools/issue_mirror.py`.
3. Create `forge/tokens/jobs.token` readability for the gateway user running
   this if it does not already exist with write scope (it should — `jobs` is
   the same user `forge_prsync.py` already writes PR state through).
4. Before the **first** `sync --yes`: there is no `last_synced` baseline yet,
   so a cold `sync` reports every one of the 25 real differences above (22
   state + 3 content, #107 excluded) as a "conflict" needing a human, rather
   than auto-resolving per the judgment in section 2/3 above. Either
   hand-apply those 25 first (as judged above) and let the first `sync` run
   establish the baseline from a now-quiet state, or treat the first run's
   conflict list as exactly this report and apply it once, deliberately.
5. Apply the diffs to `issue_sync.py` and `forge_prsync.py` (or install the
   `.new` files in their place) only *after* `issue_mirror.py new` is live —
   both now depend on it.
6. Run `backfill --yes --max 20` first as a small, resumable batch; confirm
   every returned number matches the forge number before raising `--max` or
   dropping it. The resume cursor lives in `host-tools/.issue-mirror.json`
   (`backfill_last_done`); a stopped run restarts after it.
7. Wire `check`'s exit code into whatever reads the hourly report.

## What would make the identical-number backfill unsafe

- **Anything that creates a GitHub issue outside this tool between now and
  the backfill run.** The whole guarantee rests on GitHub's next number
  being exactly forge's first backfill number (630) at the moment backfill
  starts; one issue filed by hand in between shifts every number after it by
  one and the backfill stops on the first mismatch (by design) — but a
  stopped backfill mid-run needs a human to decide whether to re-plan from
  there or abandon the run, not a blind resume.
- **The gateway `get` subcommand's print-truncation bug**: it prints
  `r.read()...[:600000]`, which silently truncates a large `/issues` JSON
  listing mid-object on some pages even at `per_page=40` (observed during
  this lane's own refresh, at `per_page=50`). `issue_mirror.py`'s
  `fetch_github_issues()` retries a page that fails to parse at a quarter
  the page size rather than trusting a truncated read, but this is a
  work-around in the caller, not a fix in the gateway — any other caller of
  `get` on a large listing needs the same caution, and the gateway itself
  should probably stream to a file instead of capping a `print()`.
- **Pacing discipline during backfill**: 481-649 requests at 240/hr is 48% of
  GitHub's 500/hr secondary limit on its own; if anything else sharing the
  gateway's token (releases, pushes) runs during the same hour, the combined
  rate could trip the limit. Running backfill during a quiet window, or
  lowering `--pace-per-min`, removes the risk.
- **#583** (see section 2) is worth a human glance, not an automatic
  resolution, before `sync` takes GitHub's `closed` for it.

Release note (none): internal tooling.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
