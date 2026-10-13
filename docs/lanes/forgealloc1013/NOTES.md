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

## Task 4: forge-ahead alarm in `idlewatch.py`

Staged as `docs/lanes/forgealloc1013/idlewatch.py.new` (a full copy of the
installed 239-line file, one new jam-class block added) plus
`idlewatch.py.diff` (unified diff against the installed copy, relabeled
`a/idlewatch.py` / `b/idlewatch.py.new` so it reads clean without leaking
host paths). Not installed by this lane -- `idlewatch.py` is a running
host-tools script I must never edit in place; PR.md's install section
has the `.bak`/`.new`/`mv` sequence for lane.local to run after fold.

### Candidates considered

Two ways to detect "forge ahead of GitHub" with zero GitHub reads of my
own, since `cmd_new` in `issue_mirror.py` always pays that read itself and
prints the result:

1. **The mirror's own state/pair data.** Ruled out two ways in:
   - Raw `.issue-mirror.json`: PR-shaped `last_synced` entries never carry
     `gh`/`fg` sub-keys at all (by design, confirmed by inspecting several
     paired vs. unpaired entries) -- there's no field here that means
     "unpaired", so this file can't answer the question directly.
   - `check_report`'s real drift classification, surfaced via
     `status/issue-mirror.txt`: this only runs on a FULL sync
     (`_cmd_sync_full`), which the 10-minute tick
     (`hakux-issue-mirror-tick.sh`) only does once a day -- every other
     tick is `_cmd_sync_incremental`, which only re-checks pairs already
     in `last_synced` and would miss a brand-new forge-only number for up
     to 24 h. Too slow next to the other jam classes in this file (all
     10-minute-tick latency).
2. **The two existing allocator callers' own logs** (chosen): both
   `forge_prsync.py` (PRs, `logs/forge/prsync.log`, 5-min timer) and
   `issue_sync.py` (issues, logged into `pm/lanelocal-log.md` on failure,
   10-min timer) call the same `cmd_new`/`level_check` and get the exact
   same fixed REFUSED line verbatim regardless of kind. Reading their logs
   costs no GitHub read of my own (already paid), catches an
   issue-flavored refusal and not just a PR-flavored one (the brief's
   stated preference), and has 5-10 min latency, not 24 h.

### Design

`FORGE_AHEAD_RE` matches the fixed `forge is ahead of GitHub (forge max
#N, GitHub max #M)` substring. `_latest_run_lines(path, boundary)` bounds
the read to "since the run before last" using `prsync.log`'s own
`EXECUTED: ...` summary lines as run boundaries (a run's FAILED lines
print before that run's own `EXECUTED:`, confirmed from a live
`tail -100` of the real log) -- this is what makes an old, already-
resolved REFUSED line stop mattering within one run (5 min), with no
timestamp parsing needed, matching the file's existing model-free style.
`pm/lanelocal-log.md` has no such per-run marker, so that side just takes
the last 200 lines. `prsync.log` is checked first (cheaper, 5-min vs.
10-min granularity); `pm/lanelocal-log.md` is the fallback, so a
PR-shaped refusal that already shows in `prsync.log` doesn't need the
second read.

For "forge user" and "creating branch" in the jam message: live,
read-only curl tests against the real local forge (`http://127.0.0.1:3330`,
`jobs` token) showed `GET /pulls/{n}` has both `user.login` and
`head.ref`, while `GET /issues/{n}` has `user.login` only (no branch
concept for a plain issue) -- confirmed on real forge PR #970
(`user='lanes'`, `head.ref='lane/rootclean1013'`). The new code tries
`/pulls/{n}` first, falls back to `/issues/{n}` on 404, and on any other
failure just prints `?` rather than raising -- this alarm must never
itself become the jam.

### Selftest

`idlewatch.py` has no `__main__` guard (every jam check is top-level code
against hardcoded `/home/justin/hakux-work` paths) and makes live
systemctl/forge/network calls on import, so it can't be unit-tested by
importing it, and it doesn't fit `selftest.sh`'s `$T`-fixture harness
(built for `jobs/*.sh`'s relocatable paths, not a host-tools script's
hardcoded ones). Wrote `docs/lanes/forgealloc1013/forge_alloc_selftest.py`
instead: pulls just the three new pure nodes (`FORGE_AHEAD_RE`,
`_latest_run_lines`, `_forge_ahead_in` -- none of which touch `W`, the
forge API, or anything else in the file) out of the staged `.new` file via
`ast`, execs them into a throwaway namespace, and feeds them fixture
files built to match the real log's line order. Covers: a bare match, last-
match-wins across several lines, the latest-run window excluding an
older already-resolved run's forge-ahead line, the latest-run window
including the newest run's own line, a fully-resolved log not firing, the
`pm/lanelocal-log.md` tail-window shape, and a missing file returning `[]`
rather than raising.

```
python3 docs/lanes/forgealloc1013/forge_alloc_selftest.py
```

11 passed, 0 failed. The per-number forge lookup (the `/pulls`/`/issues`
urllib calls) isn't covered by this selftest -- it needs a live forge, and
was instead exercised with the same live read-only curl calls used to
confirm the field shapes above; its own failure modes already degrade to
`?` rather than raising. Also ran the whole detector read-only against
the real installed `prsync.log` and `pm/lanelocal-log.md` (no jam
currently live, since the 10-13 incident was already resolved by hand
before this lane started) to confirm it doesn't fire on real, clean data.

## Task 5: `fleet.py`'s "READY with no pipeline label" FAIL

### Root cause

`fleet.py`'s FAIL fired on any non-draft PR whose labels missed the whole
`IN_FLIGHT` set (`needs-audit-1/2`, `needs-remediation`, `fold-ready`,
`folded`, `needs-rebase`, `claimed:cloud`), reasoning "nothing else will
pick it up." That's false: `foldqueue.sh`
(`~/hakux-work/offline-git/foldqueue.sh`, run by `hakux-foldqueue.timer`
every 15 min) folds a `lane/*` branch straight off its own
`docs/lanes/<lane>/PR.md` `State: ready`, reading git/territory.toml/PR.md
state directly -- it never calls `gh`, never touches a label, and doesn't
know `IN_FLIGHT` exists. A PR mid-fold, already folded (but not yet closed
on GitHub), or already FAILED-and-routed-to-`hostops-inbox.md` by
`foldqueue.sh` itself can sit with zero labels indefinitely while
`fleet.py` FAILs on it every 20-minute board poll for something no label
fix can ever clear -- the exact kind of "FAIL that cannot be cleared by
the board" the file's own comment above `fold_watch()` warns against. The
Task 4 allocator hop (`forge_prsync.py`, also every 5 min) adds one more
tick of normal propagation delay in front of this, making stale false
positives more likely, not less.

### Design

Added `foldqueue_status(branch)` (right after the existing `FOLD_STUCK_S`
constant): reads `FOLDQUEUE_LOG` (`$HAKUX_WORK/offline-git/foldqueue.log`,
honoring the file's existing `HAKUX_WORK`-env-with-production-default
convention, already used at `branch_lane()` and already globally
test-isolated to `$T/work` by `selftest.sh`) and returns the newest
`(verb, age_s)` for lines naming that branch, regardless of verb -- the
same branch can show `FAILED` then, after a push, `WAITING` again. The old
`unfolded` list (still used unchanged for the informational "READY, NOT
FOLDED" display section) now feeds a new `unaddressed` filter before the
FAIL fires:
- no foldqueue.log entry at all -> still unaddressed (genuinely nobody's).
- `FOLDED` or `FAILED` (a terminal state; `FAILED` is already routed to
  `hostops-inbox.md`/`fold-failures.log`, already lane.local's job) ->
  suppressed.
- any other verb (`WAITING`, `GATE QUEUED`, `MOVED`, `RACED`,
  `SELFTEST-RETRY` -- all actively retried every tick) younger than
  `FOLDQUEUE_STALE_S` -> suppressed, an active retry within grace.
- the same non-terminal verbs, but older than `FOLDQUEUE_STALE_S` -> still
  unaddressed: foldqueue.sh itself has stopped making progress on it.

`FOLDQUEUE_STALE_S = 3 * FOLDQUEUE_TICK_S` (45 min = three missed 15-min
ticks) rather than one tick, since `FOLDQUEUE_TICK_S` is the timer's
*interval*, not a latency bound -- a branch that moved just after one tick
started waits almost a full extra interval for the next, and the Task 4
allocator hop stacks one more normal delay in front of it; three ticks
absorbs that without hiding a real stall for too long against the board's
own 20-minute poll.

### Selftest

`96-fleet-registry.sh`: added three more PRs to the existing fixture
(`#9507` foldqueue.log says `FOLDED`, `#9508` a fresh `WAITING` inside
grace, `#9509` a `WAITING` 61 minutes old, past `FOLDQUEUE_STALE_S`) and a
matching `foldqueue.log` fixture under `$HAKUX_WORK/offline-git/` (built
with `date`/`date -d '... ago'`, the suite's existing relative-timestamp
convention). New checks: `#9507` and `#9508` do not appear in the FAIL
line, `#9509` still does. Updated the pre-existing `#9502` check's count
from "1 lane PR(s)" to "2 lane PR(s): #9502, #9509" since the fixture now
has two genuinely-unaddressed PRs, not one -- the only change to a
prior-passing assertion, and it's a count/list update, not a logic
reversal.

`98-lane-shape.sh`: `foldqueue.sh` folds by branch name alone, with no
concept of "remote lane" or "suffixed head," so the suppression needs to
hold there too. Appended one more line to the *same* shared
`foldqueue.log` (HAKUX_WORK is exported once, globally, for the whole
selftest run, so 96's fixture lines are still present when 98 runs; no
collision since the branch names differ) marking a suffixed branch
(`claude/elsewhere-u1-782p4`) `FOLDED`, added a PR on that branch alongside
the pre-existing `#779` (left untouched, still on a bare `headRefName`
with no foldqueue.log entry), and checked `#782` does not appear in the
FAIL line while `#779` still does -- proving the pre-existing "the
READY-with-no-label FAIL names it" check for `#779` is unchanged, and that
suppression keys off the literal `headRefName`/branch string, not off
`lane/*`-shaped names only.

```
SELFTEST_ONLY="96-fleet-registry.sh 98-lane-shape.sh" bash docs/testing/jobs/selftest.sh
```

123 passed, 0 failed (96: 2s, 98: 15-19s). Grepped the rest of
`selftest.d` for `"pipeline label"`/`unfolded`/`foldqueue`: the other two
hits (`86-fold-regressed.sh`'s `fr_unfolded` helper, about `fold.sh`'s
`regressed` label gate; `64-status-html.sh`, an unrelated substring) are
unrelated to this check -- nothing else needed updating.

## Why there was no PR for this branch until just now

`forge_prsync.py`'s main loop skips any `lane/*` branch with no `PR.md` --
so until this file (and `PR.md`) are pushed, no forge PR opens for this
lane at all, independent of everything else being done. Writing and
pushing `PR.md` is the first thing after this, ahead of Tasks 4 and 5.
