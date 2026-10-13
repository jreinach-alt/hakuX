# issuemirror1012: the issue mirror on a timer: one lock, incremental sync, budget-true pre-check (#433, 0.5)

State: ready

Lane: issuemirror1012          Issue: none (harness defect, dispatched directly)
Base: master @ 2117d4e3cb
Files: docs/lanes/issuemirror1012/**
Prediction: none (tooling; no live calls)
Needs device: no    Needs NDK: no

## Background

lane.issuesync1012 built `host-tools/issue_mirror.py`, folded as 2117d4e3cb. lane.local
installed it live on 10-12 (seed, sync, and a backfill that is still running in the
`hakux-issuesync-backfill` unit as of this writing). Nothing runs `sync` on a schedule yet.
Reading the code for that turned up three gaps that make a timer unsafe or unaffordable.
This lane closes all three and stages a timer, entirely against fakes and a cached live
snapshot -- no live GitHub or forge call of any kind was made.

## Gap 1: only `new` took the state lock

`cmd_new` held `.issue-mirror.lock`; `backfill`, `sync`, `seed` and `mirror-down` called
`load_state()`/`save_state()` with no lock at all. A timer `sync` starting mid-backfill
could load the state, let the backfill advance `backfill_last_done`, then save sync's own
stale copy over it -- rolling the cursor back and making a resumed backfill re-create
already-spent GitHub numbers. GitHub numbers can never be reused.

**Fix** (`issue_mirror.py.new`): a new `state_lock()` context manager wraps the same
`.issue-mirror.lock` with a non-blocking `fcntl.flock`. Every state-writing command
(`backfill`, `sync`, `seed`, `mirror-down`) now has a thin top-level wrapper that takes the
lock and delegates to a `_locked` body (`_cmd_backfill_locked`, `_cmd_sync_full`/
`_cmd_sync_incremental`, `_cmd_seed_locked`, `_cmd_mirror_down_locked`); a refusal raises
`StateLockHeld` and the wrapper prints and returns exit 75. `new`'s own lock handling is
untouched. A `sync --yes` that finds the lock held prints the literal text `skipped:
another run holds the lock` (not an error); a dry-run `sync` or any other locked command
prints `REFUSED: another run holds the lock`.

Only top-level `cmd_*` functions acquire `state_lock()` -- nested helpers (`do_mirror_down`,
`sync_normal_pair`, the backfill per-item loop) trust it is already held. This matters
because `flock()` is per-open-file-description: a second `os.open()` of the same path in
the same process would conflict with the lock that process already holds via the first fd,
which would make a command deadlock against itself the moment any helper re-acquired it.

**Tests** (`issue_mirror_selftest.py.new`):
- `test_lock_refuses_concurrent_sync_during_backfill` -- a fake backfill holding the lock
  makes `sync --yes` refuse (75, "skipped"), with the state file byte-for-byte unchanged;
  sync recovers once the lock is released.
- `test_sync_cannot_reverse_backfill_cursor_while_locked` -- a `backfill_last_done` written
  while the lock is held survives a concurrent `sync --yes` attempt untouched; a real sync
  afterward, with the lock free, still sees it.

## Gap 2: every sync listed all of GitHub

`GH.all_issues()` pages through everything -- about 10 gateway reads once the backfill
ends -- and `check` cost the same again as a separate listing. A 10-minute timer at that
rate would spend about 2,900 reads a day against a 600/day cap that the push timer already
spends ~96 of.

**Fix** (`issue_mirror.py.new`):
- `GH.changed_issues(since_iso)` -- `GET /issues?since=<ISO8601>&sort=updated`, paginated.
- `FG.changed_issues(since_iso)` -- confirmed against the cached Forgejo swagger spec (zero
  network cost) that the forge's `/issues` also takes `since`, but its "by update time" sort
  value is `recentupdate`, not GitHub's `updated`.
- `GH.get_issue(n)` / `FG.get_issue(n)` -- single-item fetch, used only for an item that
  changed on one side but wasn't in that side's own `changed_issues()` page (comments bump
  `updated_at` too, so this is rare, not the common path).
- `st['last_sync_started_utc']` persists the wall-clock time a sync began. The incremental
  pass lists only items updated since then minus `OVERLAP_S` (600s), to cover clock skew and
  updates whose timestamp lands slightly before the write that caused them completes.
- `cmd_sync` is now a lock-wrapping dispatcher with a `full` argument (function default
  `True`, so every one of the 24 pre-existing call sites -- selftests and the rehearsal --
  keeps the original full-listing behavior unchanged); the CLI's own `--full` flag defaults
  to `False`, so real use (the timer) gets the incremental path unless it asks for `--full`.
  `sync --full` is the full pass, unchanged in behavior from before this lane except for the
  lock and the folded check below.
- **Scope, by design**: the incremental pass only updates pairs already known to both sides
  (present in `st['last_synced']`). A brand-new GitHub-only or forge-only item is left for
  the next daily `sync --full` (or a manual `mirror-down`) rather than probed for per item --
  that would cost a read per unknown number and defeat the saving. This is the one thing a
  full listing catches that the incremental pass does not.
- `check` is folded into `sync`: both the full and incremental paths print a check-style
  line and the command's own exit code reflects it, so a 10-minute tick is one listing, not
  two. The full pass reuses `check_report()` (the standalone `cmd_check` logic, extracted
  unchanged into a pure(ish) function over already-fetched `gh`/`fg`) purely for its
  printed text -- `only_gh`, the backlog ceiling, a raw state/content scan, exactly what
  `cmd_check` would print standalone -- but the *exit code* is driven by `conflicts` (the
  three-way-merge's own unresolved-conflict list) instead of `check_report`'s return code.
  Reason: `check_report` compares `gh`/`fg` as fetched *before* `apply_sync_actions` runs, so
  a title/state difference this very tick is about to fix would otherwise print as one tick
  of spurious `DRIFT` on every sync that does anything at all. The incremental pass prints
  its own narrower "CHECK (incremental, partial)" line, scoped to only the pairs it looked at
  this tick, and also exits non-zero only on `conflicts`.

**Measured**: `test_incremental_sync_steady_state_reads_at_most_two` -- once a full sync has
set `last_sync_started_utc`, a steady-state incremental sync with nothing changed costs
**2 GitHub reads** against the fakes (1 for `changed_issues()`, 1 for `repo_labels()` via
`compute_shared_vocab`), meeting the brief's "at most 2" target exactly.
`test_incremental_sync_applies_changed_forge_pair` confirms the cheap pass is still correct:
a forge-only title edit made after the baseline full sync is carried to GitHub by the next
incremental `sync --yes`.

## Gap 3: the backfill pre-check compared against the wrong budget

`needed <= GITHUB_READ_BUDGET_DAY` compared a per-run estimate against the *whole day's*
cap, not what's actually left today; `ISSUE_MIRROR_READ_BUDGET` defaulted to a stale 300.

**Fix**: `github_gateway.py.new` adds a read-only `budget` subcommand (`cmd_budget()`) that
prints today's UTC reads/writes/pushes and the three caps from `.gateway-state.json`, with
no network call -- it never calls `read_budget()`/the gateway's own throttling path, only
`load_state()`/`day_counts()`. `issue_mirror.py.new`'s `GH.budget_remaining()` shells to it
and parses `reads_remaining=`. `cmd_backfill`'s pre-check now compares its estimate against
that figure; the stale `GITHUB_READ_BUDGET_DAY` constant and `ISSUE_MIRROR_READ_BUDGET` env
var are removed entirely, not just unused.

**Test**: `test_budget_true_precheck_uses_remaining_not_stale_cap` -- 10 items against 15
remaining disables the pre-check (it would have been enabled under the old stale 300/day
default); 1 item against 600 remaining enables it; the test also asserts
`GITHUB_READ_BUDGET_DAY` no longer exists on the module.

**Known limitation, not fixed this lane**: `budget_remaining()` shells out to
`github_gateway.py budget`, which still takes the gateway's own `.gateway.lock` (unconditionally,
for every subcommand including this one) before printing. If that lock happens to be held by
a concurrent gateway write (e.g. the push timer) at the exact moment a backfill's per-item
pre-check calls it, `budget` itself exits 75 and `budget_remaining()` raises rather than
retrying or degrading to "assume disabled". This cannot double-spend a GitHub number -- it
would abort the backfill run with an exception, not proceed unsafely -- but it is a
reliability gap worth a follow-up (treat a 75 from `budget` as "unknown, be conservative"
rather than an unhandled exception).

## The timer (staged, not installed)

- `hakux-issue-mirror.service` / `.timer`: every 10 minutes (`OnUnitActiveSec=10min`), runs
  the new wrapper `hakux-issue-mirror-tick.sh.new`. `SuccessExitStatus=75` so a lock-skip
  tick is not recorded as a systemd failure (keeping it out of hourly_report's failed-units
  recap).
- `hakux-issue-mirror-tick.sh.new` (new file, nothing to diff against): decides incremental
  vs. full by comparing today's date against a one-line marker
  (`status/.issue-mirror-last-full`), which only advances once a full sync actually exits 0
  -- a lock refusal on the day's first tick does not skip that day's full pass, it just
  retries full on the next tick. `PATH` includes `/home/justin/.local/bin`. Writes
  `status/issue-mirror.txt` as: the `date` output, the tool's own sync-summary and
  check-line stdout, and a trailing `exit=<code>` line, all from one capture so the file is
  internally consistent.
- `hourly_report.sh.new` (diff against the live script in `hourly_report.sh.diff`): one new
  section, "--- issue mirror", printed every run. It cats the status file (prefixed), computes
  its age from the file's own mtime (no parsing of the embedded `date` line needed), and
  prints `ALARM: ...` if the file is over 1800s (30 min) old, or if the trailing `exit=` code
  is present and is neither `0` nor `75`. Adds no GitHub reads of its own -- it only reads a
  local status file.

## Read budget

| source | reads/day | basis |
|---|---|---|
| incremental timer ticks (143/day, 1 of 144 is the daily full) | ~286 | measured: 2/tick x 143 |
| daily full sync | ~9-11 | measured by lane.issuesync1012 against the live snapshot refresh: 9 reads (`all_issues()` + `repo_labels()` pagination) |
| push timer | ~96 | measured (brief's own figure) |
| backfill-resume headroom | ~12 | brief's own figure, reserved, not spent by this lane |
| **known total** | **~405** | |
| cap | 600 | `github_gateway.py` `MAX_READS_DAY` (lane.local raised this from 300) |
| **headroom left** | **~195** | after the known total, before counting any release-tick reads |

Release-tick reads are not measured by this lane -- no figure for them is stated in the
brief and none was fabricated here. As a sanity check: lane.issuesync1012's own PR.md
records a live day total of 208-217 GitHub reads *before any of this lane's timer existed*,
which already included that day's push-timer spend and whatever release-tick reads happened
-- comfortably inside the ~195-389 reads of headroom this timer's known total leaves, with
room to spare.

## Staged files (`docs/lanes/issuemirror1012/`, mirroring `/home/justin/hakux-work/lanes/issuemirror1012/`)

- `issue_mirror.py.new` + `.diff` -- gaps 1/2/3's code.
- `github_gateway.py.new` + `.diff` -- the `budget` subcommand.
- `issue_mirror_selftest.py.new` + `.diff` -- fake extensions plus 5 new tests.
- `issue_mirror_rehearsal.py.new` + `.diff` -- copied, unchanged (`.diff` is empty: the
  rehearsal's own `cmd_sync(gh, fg, yes)` / `cmd_check(gh, fg)` call sites already match the
  new signatures, since `full` defaults to `True` and `cmd_check` is untouched).
- `hourly_report.sh.new` + `.diff` -- the new "--- issue mirror" section.
- `hakux-issue-mirror-tick.sh.new` -- new wrapper script (no live file to diff against).
- `hakux-issue-mirror.service`, `hakux-issue-mirror.timer` -- new systemd units (staged, not
  installed or enabled by this lane).

## Install steps (for lane.local)

1. Copy `issue_mirror.py.new` -> `host-tools/issue_mirror.py`, `github_gateway.py.new` ->
   `host-tools/github_gateway.py`, `issue_mirror_selftest.py.new` ->
   `host-tools/issue_mirror_selftest.py`, `issue_mirror_rehearsal.py.new` ->
   `host-tools/issue_mirror_rehearsal.py` (identical to live; a no-op copy), `hourly_report.sh.new`
   -> `host-tools/hourly_report.sh`. Not while `hakux-issuesync-backfill` or any `sync`/`seed`
   call is actively running against the real files -- "never edit a running script in place"
   -- so land these between ticks, not mid-run (the lock means a mid-run copy can't corrupt
   state, but a script replaced mid-execution can still misbehave, e.g. an in-flight `python3`
   import of a file truncated by the copy).
2. Copy `hakux-issue-mirror-tick.sh.new` -> `host-tools/hakux-issue-mirror-tick.sh`,
   `chmod +x` it.
3. Copy `hakux-issue-mirror.service` and `.timer` into the systemd user unit directory
   (`~/.config/systemd/user/`), `mkdir -p /home/justin/hakux-work/status`,
   `systemctl --user daemon-reload`, `systemctl --user enable --now hakux-issue-mirror.timer`.
4. Run `python3 host-tools/issue_mirror_selftest.py` once more against the installed copies
   before enabling the timer, to confirm the install didn't introduce a copy error.
5. Watch the first few ticks' `status/issue-mirror.txt` and the next hourly report's
   "--- issue mirror" section for the expected `exit=0` (or `exit=75` while the backfill is
   still running) before leaving it unattended.

## Anything that could still spend one GitHub number twice

Nothing found that a lock acquired by every state-writing command, held across its own
`load_state()`...`save_state()` span, doesn't already close: the specific race this lane was
asked to close (a sync rolling `backfill_last_done` backwards mid-backfill) is covered by
`test_sync_cannot_reverse_backfill_cursor_while_locked`, and every other state-writing path
(`seed`, `mirror-down`, both sync modes) takes the exact same lock. The one caveat is the
gap-3 limitation above (`budget_remaining()` raising instead of degrading under a held
gateway lock) -- that aborts a backfill run loudly rather than letting it proceed on stale
information, so it cannot itself cause a double-spend.

Release note (none): internal tooling.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
