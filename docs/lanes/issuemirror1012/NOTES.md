# issuemirror1012

Scope: `docs/lanes/issuemirror1012/**` only. Base: master @ 2117d4e3cb. No live GitHub or
forge call of any kind was made -- all work against `issue_mirror_selftest.py`'s fakes and
`issue_mirror_rehearsal.py`'s cached snapshot (loaded without `--refresh-snapshot`, 0 reads).
The tool itself lives outside the repo; nothing under `/home/justin/hakux-work/host-tools/`
was edited in place, only read and copied. See `PR.md` for the full writeup; this file is
the working log.

## What I did

Staged everything in `/home/justin/hakux-work/lanes/issuemirror1012/`, then copied the
finished `.new` files, diffs, and the two new systemd units into
`docs/lanes/issuemirror1012/` so the record is in git. Three gaps:

1. **One lock.** Added `state_lock()` (non-blocking `fcntl.flock` on `.issue-mirror.lock`)
   and made `backfill`, `sync` (both full and incremental), `seed`, and `mirror-down` each a
   thin top-level wrapper that takes it and delegates to a `_locked` body. `new`'s existing
   lock handling is untouched.
2. **Incremental sync.** `GH.changed_issues()`/`FG.changed_issues()` via `since=`
   (`sort=updated` on GitHub, `sort=recentupdate` on the forge -- confirmed via the cached
   Forgejo swagger spec, not a live probe). `cmd_sync(..., full=True)` -- function default
   `True` for backward compatibility with every pre-existing call site, CLI `--full` flag
   defaults `False`. `check` folded into both sync paths.
3. **Budget-true pre-check.** `github_gateway.py budget` (read-only, no network), and
   `cmd_backfill`'s pre-check now reads it instead of the removed stale
   `GITHUB_READ_BUDGET_DAY`/`ISSUE_MIRROR_READ_BUDGET`.

Plus the staged (not installed) timer: `hakux-issue-mirror.service`/`.timer`,
`hakux-issue-mirror-tick.sh.new` (new wrapper deciding full-vs-incremental by date, writes
`status/issue-mirror.txt`), and `hourly_report.sh.new`'s new "--- issue mirror" section.

## What I measured

- 29/29 selftests pass (24 original + 5 new), run against the staged copy in a scratch
  directory (`/tmp/issuemirror1012-run/`, files copied under their real module names since
  Python imports need exact filenames).
- `issue_mirror_rehearsal.py` from the cached snapshot (0 reads) prints exactly
  `issue_mirror_rehearsal: all required counts held`.
- Steady-state incremental sync: **2 GitHub reads** (measured, matches the brief's "at most
  2" target exactly). Full sync: ~9-11 reads (lane.issuesync1012's own prior live
  measurement: 9, for `all_issues()` + `repo_labels()` pagination). Daily known total with
  the timer running: ~405 reads/day against the 600 cap -- see PR.md's table.

## What went wrong, and what the next lane (or I, resuming) should not repeat

The first selftest run after folding `check` into `_cmd_sync_full` came back 27/29: two
pre-existing tests (`test_three_way_sync_echo_suppression`,
`test_failed_forge_write_then_retry_never_reverses`) failed with a spurious
`DRIFT: 1 content conflict(s)` line that didn't exist before this lane. Root cause: I called
`check_report(gh, fg, st)` using the *same* `gh`/`fg` dicts fetched before
`apply_sync_actions` ran -- so the check saw the pre-write mismatch the sync was in the
process of fixing, and reported it as drift one tick early, every time. Don't re-fetch a
second full listing to fix this (that's exactly the cost gap 2 is trying to avoid) and don't
try to patch the local `gh`/`fg` dicts in place from `apply_sync_actions`'s effects either --
that gets tangled fast once you account for title-prefix-stripping, label-shape differences
between a baseline entry and a raw item, and partial per-field success. The fix that held:
keep printing `check_report`'s full text every tick (useful to a human reading the status
file or the hourly report, and it's the same text `cmd_check` prints standalone, so nothing
regresses there), but drive the *exit code* off `conflicts` -- the three-way-merge's own
already-correctly-scoped unresolved-conflict list, computed in the same pass, which does not
re-examine fields this run just wrote. The incremental path already worked this way by
construction; this made the full path consistent with it.

One limitation I chose not to fix, documented in PR.md: `GH.budget_remaining()` shells out
to `github_gateway.py budget`, which still takes the gateway's own unconditional
`.gateway.lock` before printing (even though `budget` makes no network call and needs no
lock in principle). If that lock happens to be held by a concurrent gateway write at the
exact moment a backfill's per-item pre-check calls it, `budget` exits 75 and
`budget_remaining()` raises an unhandled exception rather than degrading to "assume
disabled". This aborts a backfill loudly, it does not let one proceed on stale information,
so it cannot cause a double-spend -- but it's a reliability gap worth a follow-up lane:
treat a 75 from `budget` as "unknown, be conservative" instead of raising.

Scope choice, not a bug: the incremental sync pass only updates pairs already present in
`st['last_synced']`. A brand-new item on either side waits for the next `sync --full` (or a
manual `mirror-down`). This keeps the incremental path's read cost provably bounded without
per-item existence probing; it's the one thing the daily full pass catches that 143 of every
144 ticks do not.

## Not done / explicitly out of scope

- The timer units are staged, not installed or enabled -- lane.local does that (see PR.md's
  install steps).
- No live read was made against GitHub or the forge; `GH.changed_issues()`/`get_issue()`/
  `budget_remaining()`'s actual network behavior is unverified beyond the cached swagger spec
  and the fakes' simplified `updated_at`-string filtering.
