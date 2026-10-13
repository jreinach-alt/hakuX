# lane.forgealloc1013 -- lanes stop opening forge PRs directly (#433)

## Step 0: sync repo copies with the installed ones

`docs/testing/jobs/gh-shim/forge_prsync.py` and `docs/testing/jobs/gh-shim/gh`
were older than `~/hakux-work/forge/bin/forge_prsync.py` and
`~/hakux-work/forge/shim/bin/gh`. Copied both verbatim (`cmp` confirmed
byte-identical before editing anything else), committed alone
(`450dc43abb`), so every later diff in this lane is against the version
actually installed on the host, not a stale repo copy.

The installed `gh` already carried a working `repo view` (`cmd_repo`) the
repo copy didn't have. That flipped one assumption in `smoke_live.py` (see
below) before I'd touched the file for my own reasons.

## Task 1: `roles/lane.md`

Rewrote "Your PR is your claim" to write `docs/lanes/<lane>/PR.md` (title,
`State: draft|ready`, the existing body fields) and push, instead of
`gh pr create --draft --base master`. Added:
- why: a direct POST has no allocator and can take a PR number GitHub
  hasn't given out, which is the #433 jam itself.
- what a lane does before `forge_prsync.py` has opened a PR: there's
  nothing to `gh pr comment`/`gh pr ready` yet, so the `waiting:`/`blocked:`
  word goes in `NOTES.md` and as the session's own last words first, and
  as a PR comment once a PR exists to comment on.
- which signal `handback.sh` actually honours, in order: first the
  session's own final words (`$WORK/logs/lane/<name>.<stamp>.json`'s
  `result` field, via `last_session_of()`) -- works with no PR at all --
  then, once a PR exists, its newest `[lane.<name>] ...` comment
  (`pr_declared_wait()`). I'd first written that handback reads `NOTES.md`
  itself; re-reading `last_session_of()`/`pr_declared_wait()` before
  committing showed that's wrong -- it reads the session's own captured
  output, not the file. Corrected before commit (`48f2e07b26`).
- definition-of-done item 5: `State: ready` + push, not `gh pr ready`.

## Task 2: `handback.sh`

`resume_merged()` (~839) and `resume_idle()` (~882) told a resumed lane to
run `gh pr create --draft --base $TIP`. Changed both to say what
`roles/lane.md` now says: write `docs/lanes/$4/PR.md` (`$4` is the lane
name -- confirmed from the call site,
`"$act" "$pr" "$branch" "$head" "$name" "$cause" >> "$WORK/briefs/$name.md"`)
with `State: draft` and push, and explicitly not to run `gh pr create`.

No `selftest.d/99-handback*.sh` or `98-lane-shape.sh` fragment hardcoded
the old string (grepped first), so nothing else needed to change for this.
Ran the two fragments that actually exercise these resume prompts:

```
SELFTEST_ONLY="99-handback-idle.sh 99-handback-merged.sh" bash docs/testing/jobs/selftest.sh
```

44 passed, 0 failed (idle fragment 97s, merged fragment 14s). Committed as
`34a724e940`.

## Task 3: the shim

`cmd_pr`'s `create` branch and `cmd_issue`'s `create` branch in
`docs/testing/jobs/gh-shim/gh` now both raise `Fail(1, ...)` before
constructing a `Forge()` or making any network call:
- `pr create` names the replacement: write `docs/lanes/<lane>/PR.md` and
  push; `forge_prsync.py` opens it through the allocator.
- `issue create` names the replacement: an `ISSUE-REQUEST:` line in
  `docs/lanes/<lane>/OUTBOX.md` (title + evidence path); lane.local runs
  the allocator and adds the tracker row.

Both exit 1, both messages name a working replacement exactly, and neither
depends on which flags were passed (checked bare and fully-flagged calls).
`label create` and `release create` are different subcommands in the same
dispatch style and were left untouched -- confirmed by reading, not just by
name match.

### Every other caller of `pr create` / `issue create` under `docs/testing`

Scoped grep (`grep -rn "pr create\|issue create" docs/testing`), each hit
checked in context, not just by string match:

| File | What it does | Action |
|---|---|---|
| `docs/testing/jobs/gh-shim/forge_prsync.py` | Mentions both subcommands only in its own docstring/comments, explaining what it replaces. No call. | none |
| `docs/testing/jobs/gh-shim/gh` | The two refusal branches themselves. | fixed (this task) |
| `docs/testing/jobs/gh-shim/smoke_live.py` | Used `gh pr create`/`gh issue create` as test *fixture setup* for ~190 lines of downstream list/view/comment/label/check assertions. | fixed: switched to raw Forgejo API POSTs via the test's own `api()` helper (see below) |
| `docs/testing/jobs/gh-shim/create_refusal_test.py` | New file, asserts the refusals. | added (this task) |
| `docs/testing/jobs/handback.sh` | Built resume prompts naming `gh pr create --draft`. | fixed (Task 2) |
| `docs/testing/jobs/roles/lane.md` | Told every lane to run `gh pr create --draft --base master`. | fixed (Task 1) |
| `docs/testing/jobs/selftest.sh` | Its fake `gh` shim (used by the harness itself) answers a canned `"issue create"` case for fragments that stub it, e.g. status.sh's. Not a real caller. | none |
| `docs/testing/jobs/selftest.d/77-issue-sweep.sh` | Asserts `issue-sweep.sh`'s own log never contains `"issue create"` -- the opposite of a caller, a check that nothing calls it. | none |
| `docs/testing/jobs/selftest.d/62-status-freshness.sh`, `64-status-html.sh` | Stub `gh issue create` to test `status.sh`'s real, legitimate call (below). Not my territory (brief says so explicitly). | none -- `status.sh` not touched |
| `docs/testing/jobs/status.sh` (line ~674) | A genuine, rare, self-healing caller: creates the recurring "harness: live status (auto-updated)" issue only when the query for it comes back empty (i.e., once, ever, until someone deletes it). Not my territory per the brief. | **WAITING**, see below |

**WAITING: `status.sh`'s `gh issue create` call (line ~674) will now be
refused by the shim.** This is a legitimate caller outside my territory —
the brief says explicitly not to edit `status.sh`, and to write a
`WAITING:` line instead. It needs its own small fix (most likely: write
an `ISSUE-REQUEST:` line to some fixed-location OUTBOX the way a lane
would, or be granted a narrow exemption from the refusal) from whoever
owns `status.sh`/`jobs/roles/*` next. Until then, if the harness-status
issue is ever deleted, `status.sh` will log "could not create the status
issue" and move on (its own code already tolerates create failure) rather
than recreating it -- a silent, low-severity gap, not a jam.

### `smoke_live.py` fixture rework

Replaced the `gh pr create`/`gh issue create` fixture setup with raw
Forgejo API POSTs (via the file's existing `api()` helper, already used
for repo/content setup) against `jreinach-alt/shim-smoke` (the test's own
throwaway repo, per its docstring -- "never touches jreinach-alt/hakuX").
Confirmed by reading `is_draft()`/`clean_title()` in `gh` that both look
only at the title's `WIP: ` prefix (or Forgejo's native `draft` flag), so
a raw-API PR titled `"WIP: smoke PR"` is indistinguishable from one made
with `--draft` for every downstream assertion in the file. Dropped the
now-nonexistent "pr create duplicate refused" check.

Also found and fixed a test the Step 0 sync broke before I'd made any
Task 3 edit: `gh("repo", "view")` used to genuinely be unimplemented
(expected exit 64); the installed `gh` I synced in Step 0 added a working
`cmd_repo`, so that assertion started failing on its own. Switched the
"unknown op" check to `gh("frobnicate")`, a definitely-bogus top-level
command that exercises the same `NotImpl` path regardless of future
subcommand additions.

Ran live against the real local forge (`http://127.0.0.1:3330`, reachable,
tokens present): 94 passed, 0 failed (was 93/1 before the `repo view` fix).

### `create_refusal_test.py` (new)

Offline-only (no `FORGE_URL`/token, confirmed neither refusal branch
touches the network before raising): checks both refusals' exit code (1)
and message content, bare and fully-flagged, plus confirms `pr list`/
`issue list` are not refused the same way (dispatch-table integrity, not
just the two touched branches). 14 passed, 0 failed.

`route_test.py` (tests `route.sh`/systemd routing, unrelated) re-run
unchanged for regression: 83 passed, 0 failed.

## Tasks 4 and 5

Not started yet in this session. Task 4: a zero-GitHub-read forge-ahead
alarm in `idlewatch.py`. Task 5: replace `fleet.py`'s stale "READY with no
pipeline label" FAIL with a foldqueue.log-based staleness/refusal/timer
check, and update the two selftests that assert the old text.

## Why there was no PR for this branch until just now

`forge_prsync.py`'s main loop skips any `lane/*` branch with no `PR.md` --
so until this file (and `PR.md`) are pushed, no forge PR opens for this
lane at all, independent of everything else being done. Writing and
pushing `PR.md` is the first thing after this, ahead of Tasks 4 and 5.
