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

## Round 3 (2026-10-12/13): the first live sync would rewrite the forge

lane.local reviewed round 2 (3199461b49); the self-test passed 12/12 on
lane.local's run too. Reading `seed` and `sync` against **real data**
(the forge snapshot's import headers, and its `github-import`/`github-pr`/
pipeline labels) showed that `seed --yes` followed by `sync --yes` would make
about 1,250 destructive forge writes: round 1-2's fakes gave both sides equal
labels and bodies, so no test could see it. Five numbered defects, all fixed
in this staged copy:

1. **`seed` recorded the forge's values as the baseline for *both* sides**
   (`record_baseline(st, n, fg[n], gh[n])`), so on the first real sync any
   field where GitHub differed from the forge looked like "GitHub changed" —
   about 626 bodies would have been overwritten (losing the import
   provenance) and about 629 label sets dropped (`github-import` and every
   pipeline label gone). Backfill had the same bug in miniature.

   **Fix: a separate baseline per side.** Every pair's `last_synced` entry
   now carries `gh`/`fg` sub-dicts, one value per field, per side
   (`sync_normal_pair`'s `bgh`/`bfg`, persisted via `entry.setdefault`, not a
   throwaway local copy). A side has "changed" only against *its own* last
   recorded value (`three_way_merge`); if exactly one side changed, the other
   gets written and then *both* sides' new values are recorded — never
   before the write actually succeeds (see gap 4). `seed`/backfill/`new`/
   mirror-down all record each side's own actual value through
   `record_baseline(..., shared_vocab)`. A representational difference
   (header, prefix, label vocabulary) is structurally excluded from the
   comparison, not merely absent by coincidence.

2. **Labels needed a shared vocabulary.** Chosen rule (`compute_shared_vocab`
   in `issue_mirror.py`): **shared = GitHub's own repo label list (one
   cached read via `GH.repo_labels()`) minus this tool's explicit
   denylist** — `TOOL_LABELS_DENY = {github-import, github-pr,
   reserved-number, fold-ready, folded, needs-remediation, backfill}` plus
   anything matching `needs-audit-\d+`. Every forge-only process label that
   isn't already a GitHub repo label (`0.5`, `lane:*`, `claimed:*`,
   `blocked:*`, `decision-needed`, ...) is excluded automatically by the same
   rule, with no need to hand-enumerate the forge's full vocabulary.
   `extract_side`/`sync_normal_pair` compare only the shared subset on each
   side; `apply_sync_actions` writes the forge's **local-only labels stay,
   only the shared subset is replaced** (`set_labels` gets
   `local_only | new_shared`); a write to GitHub carries the shared subset
   only, never the forge's pipeline labels. `build_backfill_body` sends only
   the shared subset plus this tool's own `backfill` tag (previously: every
   forge label, unfiltered).

3. **A dry-run `sync` wrote comments.** `sync_comments()` ran regardless of
   `--yes`. Now every write (`fg_client.comment`/`gh_client.comment`) is
   gated on a `yes` parameter; a dry run still detects and reports a new
   comment on either side (so `plan`/dry-run output stays informative) but
   writes nothing and never advances the comment-count baseline. Covered by
   `test_dry_run_sync_writes_nothing_with_new_comments`.

4. **The baseline advanced before the write succeeded.** `sync_normal_pair`
   no longer touches `last_synced` for a field with a pending write at all —
   that happens only in the new `apply_sync_actions`, strictly *after* the
   real `gh_client.patch`/`fg_client.patch`/`set_labels` call returns without
   raising; a failed write leaves the baseline untouched, so the next run
   retries the same direction instead of reverting it. (A field that needs
   *no* write — already settled, or a first-ever pair that already agrees —
   has nothing to defer and is recorded immediately; conflating that case
   with "defer" was a bug caught by this round's own self-test, see below.)
   Covered by `test_failed_forge_write_then_retry_never_reverses`.

5. **The Forgejo label API.** Confirmed live and read-only: `GET
   /api/v1/version` → `16.0.5+gitea-1.22.0`; `/swagger.v1.json` confirms
   `EditIssueOption` (the PATCH body) has **no `labels` property at all** —
   the real API silently drops a `labels` key sent through `PATCH
   /issues/{n}`. The correct path is `PUT /issues/{n}/labels`
   (`IssueLabelsOption.labels`: "a list of integers representing label IDs
   or a list of strings representing label names"); PRs share the issues
   labels endpoint, there is no separate `/pulls/{n}/labels`. `FG.patch` no
   longer accepts a `labels` key; `FG.set_labels()` is the only path, and the
   fake (`FakeFG.patch`) *raises* rather than silently no-opping on a
   `labels` key, so a caller's mistake fails the test instead of passing
   quietly. Bonus finding: `CreateIssueOption.labels` /
   `CreatePullRequestOption.labels` are strictly `int64` arrays (label IDs,
   not names) — `FG.repo_labels()`/`FG.label_ids()` resolve names to IDs
   inside `FG.create()` for this reason.
   Covered by `test_forgejo_label_api_contract_enforced_in_fake` and
   `test_label_sync_keeps_forge_local_only_labels`.

**A sixth defect, found by the rehearsal itself (below), not in the numbered
list but exactly the kind of thing it was for:** `sync_comments`'s baseline
advance was `base['gh_comments'] = prev_gh + added_gh` (and the `fg`
mirror of it) — it should be `cur_gh + added_gh`. The existing
`test_comment_mirroring_both_ways_once_each` never caught it because it adds
one comment on *each* side, which makes `added_gh`/`added_fg` numerically
coincide with `cur_gh-prev_gh`/`cur_fg-prev_fg` by the test's own symmetry.
The rehearsal's synthetic-edit phase added a comment on only one side at a
time and caught it immediately: a "settle" sync after a successful comment
mirror still showed 1 write per side instead of 0 — the just-mirrored
comment was being silently re-mirrored every run, forever. Fixed to
`cur_gh + added_gh` / `cur_fg + added_fg`; a new regression test,
`test_comment_baseline_advances_past_cur_not_prev`, exercises the asymmetric
case the old test was blind to (three consecutive syncs, asserting the
mirrored copy count stays at 1 throughout). This is the exact failure mode
the brief's closing line names: *"Any non-zero count where zero is required
is a defect: fix the tool, not the assertion"* — the assertion (a second
sync is silent) was already correct; the first implementation of it was not.

**`issue_mirror_selftest.py`**, run just before this report:

```
issue_mirror_selftest: 17/17 passed
```

The 5 new round-3 cases (plus the sixth, found via the rehearsal):
`test_dry_run_sync_writes_nothing_with_new_comments`,
`test_failed_forge_write_then_retry_never_reverses`,
`test_forgejo_label_api_contract_enforced_in_fake`,
`test_label_sync_keeps_forge_local_only_labels`,
`test_comment_baseline_advances_past_cur_not_prev`.

### The proof: `issue_mirror_rehearsal.py`, run against a live, read-only snapshot

New file, staged beside the self-test. It snapshots live GitHub (through the
staged gateway copy's read-only `get --out`, which also carries this round's
`/labels` `GET_OK` addition) and the live forge (read-only curl via `FG()`)
into deep-copied, write-counting fakes (`FakeGH`/`FakeFG`, reused from the
self-test; a `RehearsalGH` subclass replicates the real gateway's two-HTTP-
call shape for a closed-kind create — POST open, then a separate PATCH —
so the write count for a closed backfill item is counted the way the real
system actually spends it). It then runs, in memory, with pacing sleeps
patched to a no-op: `seed --yes` → `backfill --yes` (all of it) → a
pre-leveling `mirror-down --yes` → `sync --yes` → a dry-run `sync` → `check`
→ ten synthetic edits (one field each — title/body/state/labels/a comment —
five on GitHub, five on the forge) → `sync --yes` → `sync --yes` again. No
GitHub or forge write happens anywhere in this script: the fakes hold the
snapshot in plain dicts, there is no subprocess, no curl, no socket, past the
snapshot step. It makes no GitHub/forge writes and never runs with real
`--yes`. State is redirected to a scratch temp dir for the run (`isolated()`),
so it never touches the real persisted baseline either.

Live snapshot at run time: 626 GitHub items, 958 forge items (two more lane
PRs opened on the forge since round 2's plan run; the counts below reflect
that natural drift, not a defect). Required counts, all held, quoted
verbatim:

```
SUMMARY: seed: baseline written for 625/625 common pair(s)
  OK   seed: exactly 25 forge writes (brief: 25; got 25)
  OK   seed: 0 GitHub writes (got 0)

SUMMARY: backfill: 332 items done, resume cursor now #961
  OK   backfill: GitHub creates == backfill count (332, got 332)
  OK   backfill: GitHub writes == creates + closes (332 creates + 155 closes = 487, got 487)
  OK   backfill: 0 forge writes (got 0)

SUMMARY: mirror-down drained 0 GitHub-only number(s), 0 forge write(s) (not a round-3 required-zero count)

SUMMARY: sync: 958 pairs, 0 field actions, 0 conflicts, 0 comment(s) mirrored
  OK   first sync --yes: 0 GitHub writes (got 0)
  OK   first sync --yes: 0 forge writes (got 0)

SUMMARY: sync: 958 pairs, 0 field actions, 0 conflicts, 0 comment(s) mirrored (dry run)
  OK   dry-run sync: 0 actions (got 0)
  OK   dry-run sync: 0 conflicts (got 0)
  OK   dry-run sync: 0 writes either side (got gh=0 fg=0)

SUMMARY: OK: github max=961 forge max=961, 0 backfill-pending, no conflicts
  OK   check: clean (no DRIFT line)

edited: github side of #2(title) #3(body) #4(state) #5(labels +0.5) #80(comment)
edited: forge side of #6(title) #7(body) #8(state) #9(labels +0.5) #14(comment)

SUMMARY: sync: 958 pairs, 8 field actions, 0 conflicts, 2 comment(s) mirrored
  OK   edit sync: exactly 5 forge writes (one per GitHub-side edit, got 5)
  OK   edit sync: exactly 5 GitHub writes (one per forge-side edit, got 5)
  OK   forge-side title edit landed on GitHub #6
  OK   GitHub-side title edit landed on the forge #2

SUMMARY: sync: 958 pairs, 0 field actions, 0 conflicts, 0 comment(s) mirrored
  OK   settle sync: 0 writes either side (got gh=0 fg=0)

issue_mirror_rehearsal: all required counts held
```

(Backfill's 332 vs round 2's reported 331, and 155 closed-kind items, reflect
the live population at rehearsal time, not round 2's plan snapshot — one
more forge-only item appeared in the interval. The first run of this
rehearsal, before the sixth defect above was fixed, failed exactly the two
counts the comment bug predicts: the post-edit "settle" sync showed 1 write
per side instead of 0. That failing run is not reproduced here; the fix and
the new regression test are.)

### Optional: shrink the race window

Added, and self-disabling rather than hardcoded. `cmd_backfill` now computes
`needed = listing_reads_estimate(12) + len(todo)` fresh on every call and
prints whether the per-item pre-check (re-check GitHub's max before each
create, refusing with nothing spent if it moved) is enabled against
`GITHUB_READ_BUDGET_DAY` (300/day, `github_gateway.py`'s own `MAX_READS_DAY`).
For today's real ~332-item batch:

```
backfill: per-item race-window pre-check DISABLED -- would exceed the daily budget (est. 344 GitHub read(s) this run vs. a 300/day budget)
```

**Read budget**: the gateway's `.gateway-state.json` showed 169 GitHub reads
used today (UTC 2026-10-13) before this round's snapshot calls, 205 after —
two rehearsal runs' `all_issues()`/`repo_labels()` pagination cost about 36
reads combined, well inside the 300/day budget, with 95 left for the rest of
the day. The pre-check stays disabled for the real backfill batch as sized
today; it would self-enable on a smaller batch or a raised budget without any
code change.

### Not closed

- A future GitHub-side body edit that propagates onto the forge does not
  re-prepend the forge's own import-header text (`<!-- forge-import:
  github#N -->` and its `> **GitHub issue #N**...` line) — the written forge
  body becomes exactly GitHub's new body, losing that header permanently on
  the first such edit. This is a pre-existing limitation (round 1/2 already
  stripped the marker both ways for comparison; nothing in round 1-3
  re-synthesizes the import header specifically), out of this round's
  explicit scope (the five numbered defects), and is called out here rather
  than silently left for a future round to rediscover.

## Round 4 (2026-10-12/13): two write-safety defects, a size limit, a header, and a read-only preflight

Four numbered items from the round 4 brief, plus one addendum delivered mid-round. None of these change what round 1-3 already decided; all are write-path hardening found by reading the staged gateway/tool against real constraints (GitHub's actual per-run/per-day limits, its 65536-char body cap, the forge import header) rather than by the fakes, which couldn't see any of them.

1. **The gateway's "per-run" write cap was actually a per-day cap of 20.** `_write_budget()` stored `run_writes` inside the same persistent day bucket as the day total, so two separate invocations of the real tool (for example, a stopped-and-resumed backfill) sharing one day would hit the old cap at the day's 21st write, not each invocation's 21st. **Fix:** the run cap now lives in a process-local global (`_RUN_WRITES` in `github_gateway.py`, naturally 0 at every fresh `python3 github_gateway.py ...` process start — no reset logic needed); the day total is now its own persisted field (`day_counts(s)['writes']`) checked against a new, separate `MAX_WRITES_DAY = 600` (sized for the ~487-write backfill with headroom for sync/new/mirror-down the same day). Tested against the **real** gateway functions, not the issue_mirror.py fakes — `github_gateway_selftest.py` (new file) stubs only `token()` and the HTTP call, and redirects state/window/log to a temp dir, then calls `cmd_issue_create` directly: two invocations of 15 writes each (run cap 20 each) both complete in full (30 total — the old bug would have refused the 2nd invocation's 6th write); one invocation over a run cap of 3 refuses on the 4th write; a day cap of 5, already at 5, refuses write #1 of a brand-new invocation whose run cap is nowhere close to being hit.

2. **A create whose follow-up close fails lost the spent GitHub number.** The old `GH.create()` only looked at the subprocess's exit code; a successful `POST /issues` (which actually spends GitHub's next number) followed by a failing `PATCH` to close it made the whole call raise, so backfill never recorded the number, never advanced its cursor, and the next run would try to create it again — desyncing GitHub's counter from the forge's permanently. **Fix:** `GH.create()` now parses `CREATED #N` out of stdout via regex regardless of the subprocess's return code; it returns `(n, close_err)` — `close_err=None` on full success, or the failure text when create succeeded but the follow-up close didn't — and only raises when no `CREATED #N` appears at all (a genuine create failure, nothing spent). Callers (`_new_issue`, `_new_pr`, `cmd_backfill`'s create loop) advance the cursor and record GitHub's actual (open) state on a close failure, and append the number to a new `st['pending_close']` list. Every `backfill --yes` and `sync --yes` run now retries any queued pending closes first, before creating or syncing anything of its own, clearing each on success. Tests: `test_create_close_failure_then_resume_clears_pending` (forces one close failure mid-backfill, asserts the cursor still advanced and nothing was REFUSED, then resumes with an empty todo list and confirms the retry fires, clears the pending entry, and costs the following `sync --yes` exactly 0 writes) plus two gateway-level unit tests of `GH.create`'s stdout parsing (`test_gh_create_parses_created_number_even_when_close_fails`, `test_gh_create_raises_when_no_created_number_at_all`). Also fixed in the same pass: `cmd_backfill`'s "nothing to backfill, resume cursor at #N" early-return previously skipped the pending-close retry entirely on a no-op resume — moved the retry call inside that branch too.

3. **GitHub's 65,536-character body limit.** Nothing in round 1-3 bounded an outgoing body; a sufficiently long forge body (or a long comment thread folded into one) would have had the write refused by GitHub outright with no useful message. **Fix:** `truncate_for_github(body)` cuts to `GITHUB_BODY_LIMIT` (including the marker/status line already appended) and appends a plain `\n\n(truncated)` line — never mentioning the forge, since that's not public. The truncated text, not the original, is recorded as GitHub's own baseline (`entry['gh']['body']`), so a later sync never sees a spurious "GitHub changed" diff against text it never actually stored; the forge's own baseline still records the untruncated value it actually has. Covered by `test_truncate_for_github_caps_at_body_limit` (length/suffix/no-forge-mention checks on the function directly, then an end-to-end backfill+sync confirming the truncated text settles as the baseline with no drift on the next run).

4. **A forge-import header must survive a GitHub-side body edit.** 629 forge items carry a `<!-- forge-import:github#N -->` header block (plus a `> **GitHub issue #N**...` line) that round 1's import wrote; nothing in round 1-3 protected it once `sync` started propagating GitHub-side body edits onto the forge — the old code would have overwritten the whole body, including the header, with GitHub's new text verbatim, destroying the import provenance on the first such edit (this was called out as a known, out-of-scope gap in round 3's "Not closed" section above). **Fix:** `apply_forge_body(current_fg_body, new_body)` reads the *forge's own current body*, extracts its header via `forge_import_header()`, and prepends it onto the new content before writing — the header is never sourced from GitHub, only preserved from what the forge already had. `apply_sync_actions()`'s `to_forge` path now calls this instead of writing GitHub's body straight through; the forge-side baseline records the header-preserved text, GitHub's own baseline still records its own (truncated-if-needed) value. One rehearsal addition: `pick_plain_pairs(..., body_gh_header=True)` now forces the GitHub-side body-edit synthetic edit onto a real header-bearing 1-629 pair found in the live snapshot (pair #2 in the rehearsal run below) instead of a random pick; `run()` asserts the header block is still present after the sync and that the new body still contains the actual edited content, and that the **next** sync after that is 0 actions / 0 writes.

**Addendum, same round (owner, mid-round): a read-only GitHub interaction-limit preflight before backfill.** The owner noted the repo's GitHub interaction limit is currently on, that these limits are temporary (24 hours to 6 months) and lapse, and that the tool should read the live setting rather than trust memory. Added `/interaction-limits` to the gateway's `GET_OK`; `cmd_backfill`, after the existing level check and before its first create, calls `GH.interaction_limits()` (one `GET /repos/{owner}/{repo}/interaction-limits`) and prints one line: the limit, its `expires_at`, and whether that's after the run's estimated end (`len(todo) * 60/pace_per_min` seconds out). Three outcomes: **active and long enough** → proceeds; **absent** (GitHub returns an empty body when no limit is set) or **expires before the run would finish** → `REFUSED`, nothing spent; **403** (token lacks permission to read the setting) → printed plainly, treated as unknown, also `REFUSED`. A new `--no-interaction-limit` flag skips the check entirely — the owner's call, not this tool's. Tested against `FakeGH` for all three outcomes (`test_interaction_limit_active_and_long_enough_allows_backfill`, `test_interaction_limit_absent_refuses_backfill`, `test_interaction_limit_forbidden_refuses_backfill`), including confirming `--no-interaction-limit` overrides each refusal. **No live call was made to the real endpoint this round** — per the brief's own instruction not to spend read budget on it unless the rehearsal's dry path already covered it for free, and this round's one live read was spent on refreshing the rehearsal snapshot instead (see below); the endpoint's real shape (200 with a body vs. 204 empty vs. 403) is inferred from GitHub's documented REST conventions, not independently observed, and is listed under "Not closed" below.

**`issue_mirror_selftest.py`**, run just before this report:

```
issue_mirror_selftest: 22/22 passed
```

**`github_gateway_selftest.py`** (new file, round 4 — tests the real `github_gateway.py` functions directly, not the issue_mirror.py fakes, since the fakes never exercise the gateway's own subprocess/state-file path at all):

```
github_gateway_selftest: 5/5 passed
```

### The rehearsal, re-run against the round 4 changes

`issue_mirror_rehearsal.py` now caches its live snapshot (`--refresh-snapshot` to force a fresh read; otherwise it loads the cached JSON, 0 GitHub reads) so repeated reruns during this round's development didn't keep spending the read budget. Re-run in full, once with a fresh snapshot and once from cache, both producing the same result:

```
issue_mirror_rehearsal: all required counts held
```

with the gap-4 header check now part of the synthetic-edit phase: the forced GitHub-side body edit landed on a real header-bearing pair, the header block was confirmed present after the sync, the edited content was confirmed present too, and the following sync was 0 actions / 0 writes.

**Read budget this round:** the gateway's `.gateway-state.json` showed 208 GitHub reads used today (UTC 2026-10-13) before this round's one live snapshot refresh, 217 after — 9 reads for the rehearsal's `all_issues()`/`repo_labels()` pagination, well inside the round's 40-read cap and the day's 300-read cap (83 left today outside this round's spend). No other live GitHub call was made this round, including for the interaction-limits addendum — see above.

**Day write cap chosen:** `MAX_WRITES_DAY = 600` (gateway, replacing the old de-facto per-run-counted-as-per-day cap of 20) — sized for the ~487-write real backfill (333 creates + 156 closes per the latest rehearsal count) with headroom for sync/new/mirror-down traffic the same day, while the per-run cap (unchanged default, still caller-supplied) now actually resets every invocation as intended.

### Not closed

- The real GitHub `/interaction-limits` endpoint's response shape (active-with-body vs. absent-with-empty-body vs. 403) was never observed live this round; the three-outcome contract in `GH.interaction_limits()` is inferred from GitHub's documented REST conventions and exercised only against `FakeGH` in the selftest. The first live `backfill` run (without `--no-interaction-limit`) will be the first real observation of it.

## Round 5 (2026-10-12/13): three fixes from lane.local's review of ae2cf78e90

No GitHub reads needed for this round; all three were found and fixed by reading the round 4 code, not by a live call.

1. **`new --kind pr` could lose a queued close.** `cmd_new` called `st = load_state()` *before* calling `_new_pr`; `_new_pr`'s close-failure path does its own `load_state()`/append-to-`pending_close`/`save_state()` when the follow-up close fails. `cmd_new` then called `record_baseline(st, ...)` and `save_state(st)` using that stale, pre-call `st` — silently overwriting the file without the `pending_close` entry `_new_pr` had just written. The twin stayed open on GitHub with nothing queued to close it. **Fix: reload after `_new_*` returns**, not a single object threaded through — `cmd_new` now calls `load_state()` fresh, right before `record_baseline`/`save_state`, instead of before the `_new_pr`/`_new_issue` call. Test: `test_new_pr_close_failure_queues_and_resume_clears_pending` — forces the close failure during `new --kind pr`, confirms `pending_close == [6]` survives `cmd_new`'s own save, then runs `sync --yes` and requires the close is retried exactly once and cleared, and that a following `sync --yes` makes 0 writes.

2. **`new` didn't truncate long bodies.** Round 4's gap 3 (`truncate_for_github`) only ever ran on the backfill/sync write paths. `_new_issue` passed `body` straight to `gh_client.create`; `_new_pr`'s `gh_client.patch(n, body=build_pr_twin_body(...))` was unguarded too — either would have had GitHub refuse the write outright on a body over 65536 characters. **Fix:** both now route their GitHub-bound body through `truncate_for_github()`; the forge side still gets the full, untruncated body in both cases. Since `cmd_new` always re-reads both sides (`gh2 = gh_client.all_issues()`) before recording the baseline, no special-casing was needed there — the baseline naturally reflects whatever GitHub actually ended up storing. Test: `test_new_issue_truncates_long_body_for_github_only` — a body 5000 chars over the limit; confirms GitHub's copy is capped at exactly `GITHUB_BODY_LIMIT` with the plain `(truncated)` suffix (no mention of the forge), the forge's copy keeps the full length, and both recorded baselines match what each side actually holds.

3. **An exit status is 8 bits.** The staged gateway's `cmd_get` returned the raw HTTP status (`e.code`) on an `HTTPError`, but `sys.exit()` truncates a process's real exit status to its low 8 bits — `sys.exit(403)` actually exits `147` (`403 & 0xFF`), `404` exits `148`. `GH.interaction_limits()`'s `r.returncode == 403` check could therefore never match a real 403; it still ended up refusing, but only by falling through to the generic `RuntimeError` branch (treated as "unknown" the same way), not by the explicit check it was written to use. **Fix:** `cmd_get`'s `HTTPError` branch now maps the status to a small, documented exit code instead of passing it through raw — **3 for 403** (matching this file's own existing "REFUSED" convention, used elsewhere for a refused read/write), **1 for every other HTTP error**. `GH.interaction_limits()` now checks `r.returncode == 3`, with its docstring updated to say why. No other caller uses the gateway's `get` (lane.local checked host-tools, docs/testing and jobs), so this is contained to this one path. Test: `test_cmd_get_403_exit_status_is_the_mapped_code_not_the_raw_http_status` in `github_gateway_selftest.py` — spawns a **real subprocess** (`python3 -c ...` importing the actual `github_gateway.py`, with `token()` and `urllib.request.urlopen` stubbed and `STATE`/`WINDOW`/`LOG` redirected to a temp dir — no network, no real token, no write to the real gateway state) and asserts the real OS-level exit status is `3`, not `147`. This had to be a real subprocess: a test that calls `cmd_get()` directly in-process sees Python's raw `int` return value and would never show the 8-bit truncation, which only happens at the actual OS exit boundary — confirmed by temporarily reverting the fix and watching this specific test fail with "got 147", then restoring it and re-confirming green.

**`issue_mirror_selftest.py`**, run just before this report:

```
issue_mirror_selftest: 24/24 passed
```

**`github_gateway_selftest.py`**, run just before this report (now including the subprocess-based test for item 3):

```
github_gateway_selftest: 6/6 passed
```

**Rehearsal**, re-run from the cached snapshot (0 GitHub reads — none of this round's three fixes touch anything the rehearsal exercises; `cmd_new`/`_new_issue`/`_new_pr` are not part of its replayed path):

```
issue_mirror_rehearsal: all required counts held
```

**GitHub reads used this round: 0.** All three fixes were found by reading round 4's own code (per lane.local's review), not by any live call; every test above runs against fakes or a subprocess with `token()`/the HTTP call stubbed and state redirected to a temp directory — none of it touches the real `host-tools/.gateway-state.json`.

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

- `issue_mirror.py` — the tool, round 5. Subcommands: `plan`, `mirror-down
  [--yes]`, `backfill --yes [--max N] [--pace-per-min N] [--comments
  now|later] [--no-interaction-limit]`, `sync --yes`, `seed [--yes]`,
  `new --kind issue|pr ...`, `check`, `close-pr N --comment TEXT`. Round 4
  added: `GH.create()` returning `(number, close_err)` instead of raising on
  a failed follow-up close; a `pending_close` retry at the top of every
  `backfill --yes`/`sync --yes`; `truncate_for_github()` applied to every
  outgoing GitHub body with a per-side baseline split; `apply_forge_body()`
  preserving a forge-import header on a GitHub-side body edit;
  `GH.interaction_limits()` and the `interaction_limit_preflight()` gate in
  `cmd_backfill`. Round 5 fixes three gaps in `new` that round 4 only closed
  for backfill/sync: `cmd_new` now reloads state after `_new_pr`/`_new_issue`
  return instead of saving a copy loaded before they ran (losing a queued
  pending close); both `_new_issue` and `_new_pr` route their GitHub-bound
  body through `truncate_for_github()` too.
- `issue_mirror_selftest.py` — round 5. Runs every write path against
  in-memory fakes implementing the real `GH`/`FG` client interface; no
  network calls. `issue_mirror_selftest: 24/24 passed` (quoted in full
  above, in the round 5 section).
- `issue_mirror_rehearsal.py` — round 3, extended round 4. The live-snapshot
  rehearsal described above: read-only GitHub/forge reads only, then every
  write path replayed in memory against write-counting fakes loaded from
  that snapshot. No GitHub or forge write, ever; no `--yes` against a live
  service. Round 4 adds a JSON snapshot cache (`--refresh-snapshot` to force
  a live re-read; otherwise 0 GitHub reads) and forces one synthetic edit
  onto a real forge-import-header pair to exercise gap 4. Unchanged in round
  5 (`cmd_new` is not part of its replayed path) — re-run from cache as a
  confirmation, still "all required counts held".
- `github_gateway_selftest.py` — round 4, extended round 5. Tests the real
  `github_gateway.py` functions directly (run cap, day cap, `GH.create`'s
  stdout parsing) against a temp state file with `token()`/the HTTP call
  stubbed — no network call, nothing written to the real
  `host-tools/.gateway-state.json`. Round 5 adds a real-subprocess test for
  `cmd_get`'s HTTP-error exit-code mapping (item 3 above) — the one case in
  this file that cannot be caught by calling the function directly in-process.
  `github_gateway_selftest: 6/6 passed` (quoted in full above, in the round 5
  section).
- `github_gateway.py.diff` — the gateway additions `issue_mirror.py` needs,
  as a diff against the live `host-tools/github_gateway.py`: four new
  subcommands (`issue-create`, `issue-patch`, `issue-comment`, `pr-patch`),
  each going through the existing `open_window()`/`close_window()`/`token()`
  machinery, a write cap, and a secret scan (the existing `SECRET_RES`
  patterns plus new `key.properties`-content patterns and a scan of
  `forge/tokens/*.token` contents) that refuses any outgoing body containing
  one; round 3 added `/labels` to `GET_OK`; round 4 adds `/interaction-limits`
  to `GET_OK`, splits the write cap into a process-local per-run counter and
  a separate persisted `MAX_WRITES_DAY = 600`, and fixes `cmd_get`'s
  HTTPError path to return the real HTTP status instead of falling through
  to success, plus the `if __name__ == '__main__':` guard needed so
  `github_gateway_selftest.py` can import this module directly.
  The staged, already-patched copy (not just the diff) is at
  `/home/justin/hakux-work/lanes/issuesync1012/github_gateway.py` if a
  side-by-side read is easier than applying the diff. The **installed**
  copy at `host-tools/github_gateway.py` still lacks the `/labels` and
  `/interaction-limits` entries, the run/day cap split, and the `cmd_get`/
  `__main__` fixes — confirmed via `diff -q` — so step 1 below must still be
  done before any of this round's live calls work against the installed
  gateway.
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
2. Install `issue_mirror.py` (and `issue_mirror_selftest.py`,
   `github_gateway_selftest.py`, for future re-verification) at
   `host-tools/`.
3. Run `issue_mirror_selftest.py` once against the newly-installed copy —
   it only touches its own in-memory fakes, so this is safe before any live
   call — and confirm it still reports 24/24 passed in this environment.
   Run `github_gateway_selftest.py` too — it stubs the token/HTTP call and
   redirects state to a temp dir, so it is equally safe before any live
   call — and confirm 6/6 passed. Then run `issue_mirror_rehearsal.py` once
   against the newly-installed gateway: it makes read-only GitHub/forge
   calls only (no `--yes`, no write of any kind) and replays
   seed/backfill/sync/check in memory against a live-shaped snapshot
   (`--refresh-snapshot` to force a fresh read; omit it to reuse a cached
   one at 0 GitHub reads); confirm it prints `issue_mirror_rehearsal: all
   required counts held` before trusting the next steps against live data.
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
   level invariant (gap 2) before its next create. Round 4: this is also the
   first live call to `GET /interaction-limits` — if the token can't read it
   (403) or no limit is active, `backfill` now refuses before creating
   anything; the owner decides whether `--no-interaction-limit` is
   warranted, not this tool.
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
