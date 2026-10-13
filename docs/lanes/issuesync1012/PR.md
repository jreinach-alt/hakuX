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

## Round 2 (2026-10-12): gaps closed before any live write

lane.local reviewed round 1 (9de0a50e8f) and approved the design, but found
eight gaps that would have broken the one-number invariant, or the sync, on
its first live run. All eight are closed in this staged copy:

1. **Mirror-down.** Nothing in round 1 brought a GitHub-only number (anyone
   can file one once the repo is public) down to the forge, so the next
   allocation would have landed on GitHub #N+1 against forge #N and alarmed.
   `mirror-down` is now its own subcommand and also runs first inside `sync`
   and inside `new`. For each GitHub-only number, in order: create the forge
   twin (issue → same title/body/labels/state + marker; PR → `[GitHub PR]
   <title>`, as the import did; a GitHub-deleted number → a closed
   placeholder) and verify the forge number came back equal to N. Stops on
   the first mismatch.
2. **Level check before spending a GitHub number.** `new` and `backfill` both
   check, fresh on every call (so a resume after a stop/restart re-checks,
   not just a first call): GitHub ahead → mirror down first; forge ahead
   (a pending backfill, or an item made by hand in the forge UI) → `REFUSED`,
   nothing touched. A mismatch is now caught before a number is spent, not
   after.
3. **One shape for a forge PR's GitHub twin.** Round 1 had three (backfill
   closed, backfill open "reserved" placeholder, `new --kind pr`'s
   `[GitHub PR]`). Now there is one, from creation onward: a closed GitHub
   issue titled `[PR] <title>`, body = the PR's body + branch +
   open/merged(+fold sha)/closed status line + marker. `sync` rewrites the
   status line when the forge PR's state or `folded` label changes.
   PR-twin pairs exclude GitHub's state from sync/check (always closed by
   design) and compare titles with the `[PR] ` prefix stripped. The 16 open
   forge PRs in the backfill get this same shape — no more placeholders.
4. **`sync` now covers body, labels and comments, not just state and title.**
   Body is three-way merged with the marker stripped; labels are compared as
   a set; comments created after cutover are mirrored each way with an
   author line and a per-comment marker
   (`<!-- hakux-mirror:v1 src=<side>#N/c<id> -->`); a comment that already
   carries a marker is never re-mirrored; mirrored ids are recorded in the
   state file. No historical comments, per round 1's recommendation.
5. **`seed [--yes]`** applies the 25 judged resolutions (22 state conflicts
   closed on the forge to match GitHub, including #583 — see below; #1/#161/
   #568 copy GitHub's title+body onto the forge; #107 stays in `NEVER_SYNC`)
   and then writes the `last_synced` baseline for every common pair that
   comes out equal on both sides. After `seed --yes`, a dry-run `sync`
   reports 0 actions and 0 conflicts — verified by the self-test below.
6. **The gateway's `get` truncated at 600000 characters**, silently
   corrupting any large `/issues` page's JSON. Fixed at the source:
   `get PATH --out FILE` now writes the complete, token-redacted body to
   FILE; `issue_mirror.py` always uses `--out` now, and the quarter-page
   retry workaround round 1 needed is gone.
7. **`check` no longer reports drift that isn't, and now catches drift it
   used to miss.** PR-twin state is never reported as drift. A forge item
   past the acknowledged backlog ceiling with no marker, created after
   cutover, is drift ("created outside the allocator"). Forge-ahead beyond
   the pending backfill is drift. GitHub-only numbers are drift until
   mirrored. Still one line for the hourly report.
8. **`issue_mirror_selftest.py`** runs every write path (backfill,
   mirror-down, `new`, `sync`, `seed`, the secret scan) against in-memory
   fakes that implement the same `GH`/`FG` interface as the real
   gateway/forge clients — no network calls, nothing live touched. Run just
   before this report:

   ```
   issue_mirror_selftest: 12/12 passed
   ```

   Covering: backfill happy path; pre-create mismatch refusal (no number
   spent); post-create mismatch stop; resume after a stop; mirror-down of a
   public issue and of a public PR; `new` refusing when the forge is ahead;
   `new` mirroring down first when GitHub is ahead; three-way sync with echo
   suppression; PR-twin status rewrite on fold; comment mirroring both ways
   once each; `seed` followed by a quiet `sync`; the secret scan refusing a
   token-shaped body.

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

- `issue_mirror.py` — the tool, round 2. Subcommands: `plan`, `mirror-down
  [--yes]`, `backfill --yes [--max N] [--pace-per-min N] [--comments
  now|later]`, `sync --yes`, `seed [--yes]`, `new --kind issue|pr ...`,
  `check`, `close-pr N --comment TEXT`.
- `issue_mirror_selftest.py` — round 2. Runs every write path against
  in-memory fakes implementing the real `GH`/`FG` client interface; no
  network calls. `issue_mirror_selftest: 12/12 passed` (quoted in full
  above).
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

## Plan summary (live data, refreshed for round 2, just before this report)

GitHub: 626 items (min 1, max **629** — unchanged from round 1; nothing new
appeared). Forge: 960 items (min 1, max 960; grew from 958 while this lane
worked — two more lane PRs opened). Next GitHub number: 630.

### 0. Mirror-down: GitHub-only numbers needing a forge twin: 0

Nothing to mirror down right now — the repo has had no public filer since
round 1's refresh. `mirror-down` is still wired into `sync` and `new` for
whenever that changes (gap 1).

### 1. Backfill: 331 forge-only numbers (630-960) need a GitHub twin

| kind | state | count |
|---|---|---|
| issue | open | 177 |
| PR | closed | 123 |
| PR | open | 17 |
| issue | closed | 14 |

331 total — up 2 from round 1's 329 (two more lane PRs opened on the forge
while this round's work was in flight; the 119-121 GitHub-deleted gap is no
longer a special case, see below).

**Estimated GitHub requests and hours**, paced at 4/min (240/hr — about 5% of
GitHub's 80/min secondary limit and 48% of its 500/hr limit, with slack for
other gateway traffic sharing the same budget):

- Without historical comments: **471 requests, ~2.0 hours** (issues/open PRs
  cost 1 request each; closed-kind items, including every PR twin now that
  there is one shape, cost 2: create, then PATCH to close/finalize).
- With historical comments mirrored now: **639 requests (168 comments), ~2.7
  hours**.
- **Recommendation unchanged: mirror comments going forward only, not during
  backfill.** `sync` (gap 4) picks up any comment posted after the backfill
  cutover without special-casing it.

### 2. The 22 state conflicts (closed on GitHub, open on the forge) — resolved by `seed`

#16, 34, 66, 71, 74, 81, 87, 89, 90, 92, 99, 439, 513, 557, 583, 591, 592,
598, 605, 607, 618, 627 — **`seed` closes all 22 on the forge to match
GitHub's `closed`.** This is now a judged, applied resolution
(`STATE_CONFLICT_NUMS` in `issue_mirror.py`), not an open question:

- #16, 34, 66, 71, 74, 81, 87, 89, 90, 92, 99: GitHub closed these in
  September, **before the forge import ever ran**. The forge's "open" is an
  import artifact, not a later reopen — there is no forge comment or edit
  after the import that would indicate a deliberate reopen.
- #439, 513, 557, 591, 592, 598, 605, 607, 618, 627 (the `[GitHub PR]`
  imported issues): GitHub closed the real PR on/around 2026-10-05, and the
  forge was simply never told. This is exactly the gap `sync` closes going
  forward.
- **#583**: lane.local read it — forzadecay414's PR, last comment 09-30, the
  fix shipped. Its forge `updated_at` (10-09, now 10-12) is metadata churn,
  not a later reopen; there is no post-close forge comment or edit. Judged
  `closed`, included in the 22 `seed` applies, same as the rest.

### 3. The 3 content divergences — resolved by `seed`

- **#1, #161, #568**: the forge import never recovered the original content
  (`"#N: not recovered"`); GitHub has the real item in each case. `seed`
  copies GitHub's title/body onto the forge record for all three
  (`CONTENT_FIX_NUMS`).
- **#107 is not a conflict to resolve — it's a permanent sync exception.**
  GitHub's #107 is the gateway's own deliberately-maintained static pointer
  at STATUS.md (`cmd_pointer`, `STATUS_ISSUE = 107`, owner-approved
  2026-10-05). The forge's #107 is a different, independently useful,
  live-updating status board maintained by a separate job. Syncing either
  onto the other destroys the one it overwrites. `issue_mirror.py` keeps
  `NEVER_SYNC = {107}` rather than trying to merge it; `seed` leaves it
  untouched.

After `seed --yes` applies these 25 resolutions and writes the baseline for
every common pair that comes out equal, a dry-run `sync` reports 0 actions
and 0 conflicts — this is exactly what the self-test's
`test_seed_then_quiet_sync` checks.

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
number.

**Round 2 (gap 3) unified the twin's shape.** Round 1 had three different
shapes depending on how the twin came to exist; now there is exactly one,
from creation onward: a closed GitHub issue titled `[PR] <title>`, whose
body is the PR's own body, its branch, and an open/merged(+fold sha)/closed
status line, then the marker. `sync` rewrites just the status line when the
forge PR's state or `folded` label changes (`sync_pr_twin`); nothing else
about the twin is ever hand-edited. `issue_mirror.py new --kind pr` and
`backfill` both build it through the same `build_pr_twin_body` /
`pr_twin_title` helpers, so the 16 open forge PRs in the backfill get a real
status line too — no more "reserved" placeholders. This is distinct from
*mirroring down* a real public GitHub PR (gap 1), which keeps the original
import's `[GitHub PR] <title>` convention, since that population already
exists under that title and renaming it would just be churn.

## Install steps (lane.local)

1. Diff-review `github_gateway.py.diff` against the live
   `host-tools/github_gateway.py` and apply it (or copy
   `/home/justin/hakux-work/lanes/issuesync1012/github_gateway.py` over the
   live file after a final read) — `issue_mirror.py backfill/sync/new/
   mirror-down/seed/close-pr` all call the four new subcommands (now
   including `get --out FILE`, gap 6) and do nothing useful without them.
2. Install `issue_mirror.py` (and `issue_mirror_selftest.py`, for future
   re-verification) at `host-tools/`.
3. Run `issue_mirror_selftest.py` once against the newly-installed copy —
   it only touches its own in-memory fakes, so this is safe before any live
   call — and confirm it still reports 12/12 passed in this environment.
4. Create `forge/tokens/jobs.token` readability for the gateway user running
   this if it does not already exist with write scope (it should — `jobs` is
   the same user `forge_prsync.py` already writes PR state through).
5. Run `mirror-down --yes` first, even if `plan` showed 0 GitHub-only
   numbers at review time — the repo is public and time has passed since
   this report. Confirm every created forge number matches before moving on.
6. Run `seed --yes`. This applies the 25 judged resolutions (22 state
   conflicts closed on the forge, #1/#161/#568 content copied from GitHub,
   #107 left alone) and writes the `last_synced` baseline for every common
   pair that comes out equal — so the **first** `sync --yes` is not all
   conflicts. Confirm with a dry-run `sync` (no `--yes`): it should report 0
   actions and 0 conflicts before anything else runs.
7. Apply the diffs to `issue_sync.py` and `forge_prsync.py` (or install the
   `.new` files in their place) only *after* `issue_mirror.py new` is live —
   both now depend on it.
8. Run `backfill --yes --max 20` first as a small, resumable batch; confirm
   every returned number matches the forge number before raising `--max` or
   dropping it. The resume cursor lives in `host-tools/.issue-mirror.json`
   (`backfill_last_done`); a stopped run restarts after it, re-checking the
   level invariant (gap 2) before its next create.
9. Wire `check`'s exit code into whatever reads the hourly report.

## What would make the identical-number backfill unsafe

- **Anything that creates a GitHub issue outside this tool between now and
  the backfill run.** The whole guarantee rests on GitHub's next number
  being exactly forge's first backfill number at the moment backfill starts.
  Round 2 (gap 2) no longer lets this corrupt anything silently: `backfill`
  and `new` both re-check the level invariant fresh on every call — including
  on a resume after a stop or restart — and `REFUSE` before spending a number
  if the sides are no longer level, rather than discovering the mismatch
  after a create. A stopped/refused run still needs a human to decide
  whether to mirror-down and re-plan or hold, not a blind resume.
- **Pacing discipline during backfill**: 471-639 requests at 240/hr is about
  half of GitHub's 500/hr secondary limit on its own; if anything else
  sharing the gateway's token (releases, pushes) runs during the same hour,
  the combined rate could trip the limit. Running backfill during a quiet
  window, or lowering `--pace-per-min`, removes the risk.

The gateway `get` truncation bug (round 1's biggest open risk) is fixed at
the source in this round (gap 6) and no longer needs a caller-side
workaround; the #583 state conflict is judged and applied by `seed`, not a
hand-check (see section 2 above).

Release note (none): internal tooling.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
