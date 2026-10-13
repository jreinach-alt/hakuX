# issuemirror1013: the issue mirror waits out the gateway lock; a cap refusal is its own outcome (#433, 0.5)

State: ready

Lane: issuemirror1013          Issue: none (harness defect, dispatched directly)
Base: master @ dd5e3cb3c6
Files: docs/lanes/issuemirror1013/**
Prediction: none (tooling; no live calls)
Needs device: no    Needs NDK: no

## The defect this fixes

lane.issuemirror1012 made `issue_mirror.py` safe to run on a 10-minute timer (one state
lock, an incremental sync, a budget-true pre-check, a read-only `github_gateway.py
budget`). lane.local did not install it, for one reason: `github_gateway.py` takes its
own non-blocking flock for *every* command, `budget` included (`main()`, ~line 837). On
contention it prints "another gateway run is in progress" and exits 75 having done
nothing. In round-1's staged `issue_mirror.py.new`, every gateway call
(`GH._get_raw`/`budget_remaining`/`create`/`patch`/`comment`) raised `RuntimeError` on
*any* non-zero rc, 75 included. So a 10-minute unattended `sync` that landed on the push
timer's hold (seconds to minutes, every 15 minutes) failed outright for a collision that
cost nothing. It happened live: 2026-10-12 23:01 PDT, the backfill stopped at forge #853
(`logs/issue_mirror.log` line 224).

A second, related case: the gateway's daily read cap refuses via
`sys.exit('REFUSED: N GitHub reads today (cap M)')` -- rc 1, same code path a real crash
uses. It happened live too: 00:15 PDT 10-13, a one-time backfill (334 items, one
pre-check read each) spent the UTC day's 600 reads. lane.local raised the cap to 1200
directly on the live file (`MAX_READS_DAY`, `host-tools/github_gateway.py` line 51) --
this lane's staged gateway copy is rebased onto that live file, not round-1's stale
600-cap version.

## Change 1: every gateway call goes through one retry-on-75 helper

`issue_mirror.py.new` adds `_run_gateway(args)` (right after the existing `MirrorStop`
exception, before the secret-scan section). It is now the *only* place that spawns a
`github_gateway.py` subprocess -- `GH._get_raw`, `budget_remaining`, `interaction_limits`,
`create`, `patch`, `comment`, and `cmd_close_pr`'s two `pr-patch`/`issue-patch` calls were
all switched from a direct `subprocess.run` to it.

Backoff schedule: `GATEWAY_RETRY_BACKOFFS_S = (5, 10, 20, 40, 60)` -- 5 retries, ~135s of
sleep total, comfortably over the push timer's normal hold (seconds to minutes) and under
the brief's "up to about 3 minutes" bound. It is a module-level tuple specifically so a
selftest can shrink it to `(0, 0, 0, ...)` without touching the real timing code or
waiting out the real delay.

**Why a write retried on 75 is safe**: `github_gateway.py`'s `main()` takes its flock
immediately after validating the subcommand name, *before* doing anything else -- a read,
an API call, a write-budget charge (`main()`, the `fcntl.flock` call right inside the
first `try`, before any `cmd_*` dispatch). Returning 75 means the command never ran at
all, so retrying it cannot double a create/patch/comment. `_run_gateway`'s docstring says
this explicitly, citing `main()`. No other exit code is retried -- a write that actually
ran and then failed (a 5xx, a secret-scan refusal) is never replayed blindly.

On bound exhaustion, `_run_gateway` raises `GatewayBusy` (not a `RuntimeError` subclass,
deliberately -- see below). On exhaustion the *whole command* ends with exit 75 and the
status line `skipped: gateway busy -- ...`, reusing the tick script's existing skip code:
`hourly_report.sh`'s issue-mirror section already excludes 75 from its ALARM check (grep
for "want 0 or 75"), so a bounded-out retry reads exactly like today's lock-refusal, not a
new crash.

## Change 2: a day-cap refusal is its own outcome, never retried

`_run_gateway` also matches the gateway's own cap-refusal text -- combining stdout+stderr,
since the read cap's `sys.exit(str)` lands on stderr but the write caps' `print('REFUSED:
...')` lands on stdout -- against two regexes (`_READ_CAP_RE`, `_WRITE_CAP_RE`, built from
the live gateway's exact strings) and raises `GatewayCapRefused(cap, message)`
*immediately*, before any retry: waiting cannot make today's cap bigger.

`GatewayBusy`/`GatewayCapRefused` are plain `Exception` subclasses, not `RuntimeError` --
on purpose, so they pass straight through the existing `except (MirrorStop, RuntimeError)`
blocks scattered through `cmd_sync`'s/`cmd_backfill`'s per-pair loops instead of being
swallowed as "one pair's failure." A shared `_gateway_outcome_rc(e)` prints the line and
picks the code:

- `GatewayBusy` -> exit **75**, `skipped: gateway busy -- <detail>`
- `GatewayCapRefused` -> exit **76** (new; not 0, 1, or 75), `ALARM: hit the GitHub
  <reads|writes> cap for today (resets 00:00 UTC) -- <gateway's own text>`

`cmd_sync` and `cmd_backfill` each catch `(GatewayBusy, GatewayCapRefused)` right next to
their existing `except StateLockHeld:`, so they're directly testable the same way the
existing selftests already call them (`silent(im.cmd_sync, ...)`, no need to go through
`main()`). `main()` wraps every dispatch in the same catch as a backstop for the commands
that don't take `state_lock()` themselves (`plan`, `mirror-down`, `seed`, `new`, `check`,
`close-pr`) -- `cmd_new`'s own separate allocator flock is released via its existing
`try/finally` regardless, so nothing leaks there either.

## Change 3: `budget` needs no lock

`github_gateway.py.new`'s `main()` now dispatches `budget` to `cmd_budget()` *before* the
flock is taken, with a comment citing why: `cmd_budget()` only reads
`.gateway-state.json`, which every writer replaces atomically with `os.replace()`, so a
reader never needs the flock to see a consistent file. `status` reads the same file the
same way and could arguably move too -- left after the lock this round, per the brief,
since nothing depends on it being lock-free. `budget_remaining()`'s docstring in
`issue_mirror.py.new` notes this but still routes through `_run_gateway` for the one case
that would still matter: a stale gateway copy that hasn't picked up the reordering yet.

## hourly_report.sh.new: the cap gets its own ALARM line

The existing issue-mirror section's single combined check (`im_age > 1800` *or*
`im_ec not in (0, 75)`) is split in two: a staleness check, and an exit-code check that
now special-cases 76 first -- `ALARM: issue-mirror hit a GitHub day cap today (see the
status line above for which one); resets 00:00 UTC, not retried until then` -- falling
through to the old generic `ALARM: issue-mirror exit=$im_ec (want 0 or 75)` line for
anything else. The cap name and reset time are already in the status text itself (the
tool's own `ALARM: hit the GitHub <cap> cap...` line, captured verbatim in
`status/issue-mirror.txt` by the tick script), so the report doesn't need to re-derive
them.

## Tests

Four new cases added to `issue_mirror_selftest.py.new` (live `host-tools/issue_mirror_selftest.py`
has 24 tests, predating round-1 entirely; round-1's staged copy added 5 for its own
features, bringing it to 29; this lane adds 4 more, for 33 total), using the same
`im.subprocess.run = <lambda returning a fake CompletedProcess>` pattern already
established in `host-tools/github_gateway_selftest.py`:

- `test_gateway_retry_recovers_from_two_busy_responses` -- a fake gateway busy for exactly
  2 calls then free; `GH.budget_remaining()` (a read) and `GH.comment()` (a write) each
  succeed, each sent exactly 3 times total (2 busy + 1 landing).
- `test_gateway_retry_exhausts_bound_and_skips` -- a fake gateway that is *always* busy;
  `cmd_sync(gh, fg, True)` exits 75 with `gateway busy` in its output, and
  `.issue-mirror.json` (redirected to a temp dir via the existing `isolated()`) is never
  created at all -- `cmd_sync`'s only `save_state()` call is at the very end of a full
  pass, never reached when the very first gateway call (the issue listing) never answers.
- `test_gateway_read_cap_refusal_is_distinct_and_not_retried` -- a fake gateway that
  always returns the cap-refusal text; `GH.budget_remaining()` raises
  `GatewayCapRefused(cap='reads', ...)` after exactly 1 call (never retried), and
  `cmd_sync` exits 76 with both `reads` and `00:00 UTC` in its output, again after exactly
  1 call.
- `test_budget_answered_while_gateway_lock_held` -- loads the *staged*
  `github_gateway.py.new` via `importlib` (explicit `SourceFileLoader`, since
  `spec_from_file_location` can't infer a loader from the `.new` extension), points its
  `H`/`STATE`/`WINDOW`/`LOG` globals at a scratch temp dir, takes a real `flock` on a
  scratch `.gateway.lock` to simulate another run holding it, and confirms `budget`
  (`sys.argv = ['github_gateway.py', 'budget']`) still returns rc 0 with
  `reads_remaining=` in its output. Never touches the live `.gateway.lock` or
  `.gateway-state.json`.

### Results

Ran from a scratch dir (`/tmp/issuemirror1013-test-run/`, holding copies of
`issue_mirror.py.new` as `issue_mirror.py`, `issue_mirror_selftest.py.new` as
`issue_mirror_selftest.py`, and `github_gateway.py.new` unchanged) so nothing under
`host-tools/` was ever touched or imported:

```
issue_mirror_selftest: 33/33 passed
```

`issue_mirror_rehearsal.py.new` is **byte-identical** to the live
`host-tools/issue_mirror_rehearsal.py` -- round-1 never changed it, and nothing in this
round needed to either (its `cmd_sync(gh, fg, yes)`/`cmd_check(gh, fg)` call sites still
match, and it never collides with the gateway lock at all: it runs entirely against
in-memory fakes after one read-only snapshot step). Run from its cached snapshot (no
`--refresh-snapshot` -- zero live calls, confirmed by reading `snapshot_live()`, which
only touches the network when the cache file is missing or `--refresh-snapshot` is
passed):

```
issue_mirror_rehearsal: all required counts held
```

## Staged files (`docs/lanes/issuemirror1013/`, mirroring `/home/justin/hakux-work/lanes/issuemirror1013/`)

- `issue_mirror.py.new` + `.diff` (against the live file) -- `_run_gateway`,
  `GatewayBusy`/`GatewayCapRefused`, `_gateway_outcome_rc`, every gateway call site
  switched over, `cmd_sync`/`cmd_backfill`/`main()` catches. (The diff is 593 lines
  because round-1 was never installed -- it carries round-1's whole feature set plus this
  round's fixes, all relative to the live pre-round-1 file.)
- `github_gateway.py.new` + `.diff` (against the live file, `MAX_READS_DAY=1200`) --
  `cmd_budget()` plus the reordered `main()` dispatch. Rebased onto the live file, not
  round-1's stale 600-cap version (`github_gateway.py.new.OLDBASE` in the lane dir, for
  reference only, not copied into this PR).
- `issue_mirror_selftest.py.new` + `.diff` (against the live file, 24 tests) -- round-1's
  5 additions plus this round's 4, 33 total.
- `issue_mirror_rehearsal.py.new` -- unchanged from the live file; no `.diff` (would be
  empty).
- `hourly_report.sh.new` + `.diff` (against the live file) -- the split ALARM check.
- `hakux-issue-mirror-tick.sh.new`, `hakux-issue-mirror.service`, `hakux-issue-mirror.timer`
  -- unchanged from round-1 (no live counterpart to diff against; still staged, not
  installed or enabled by this lane).

## Install steps for lane.local (supersedes issuemirror1012's -- these files replace its staged copies)

1. Copy `issue_mirror.py.new` -> `host-tools/issue_mirror.py`, `github_gateway.py.new` ->
   `host-tools/github_gateway.py`, `issue_mirror_selftest.py.new` ->
   `host-tools/issue_mirror_selftest.py`, `hourly_report.sh.new` ->
   `host-tools/hourly_report.sh`. Skip `issue_mirror_rehearsal.py.new` -- it's already
   live, unchanged. Not while `sync`/`seed`/`backfill` is actively running against the
   real files -- land between ticks, same reasoning as round-1's PR ("never edit a running
   script in place").
2. Copy `hakux-issue-mirror-tick.sh.new` -> `host-tools/hakux-issue-mirror-tick.sh`,
   `chmod +x` it.
3. Copy `hakux-issue-mirror.service` and `.timer` into `~/.config/systemd/user/`,
   `mkdir -p /home/justin/hakux-work/status`, `systemctl --user daemon-reload`,
   `systemctl --user enable --now hakux-issue-mirror.timer`.
4. Run `python3 host-tools/issue_mirror_selftest.py` once more against the installed
   copies before enabling the timer, to confirm the install didn't introduce a copy error.
5. Watch the first few ticks' `status/issue-mirror.txt` and the next hourly report's
   issue-mirror section. Expect `exit=0` most ticks; `exit=75` only while an actual
   collision with the push timer is in progress (now absorbed inside one tick's ~135s of
   retry rather than failing the whole run); `exit=76` only if today's UTC read/write cap
   is genuinely spent -- that one clears itself at 00:00 UTC, nothing to do but wait.

## Anything that could still turn a harmless collision into an ALARM

Checked each `cmd_*`'s own lock handling for a leak or a swallowed `GatewayBusy`/
`GatewayCapRefused`: `cmd_new`'s separate allocator flock is released via its existing
`try/finally` regardless of which exception passes through it, `cmd_mirror_down`/
`cmd_seed`/`cmd_backfill`/`cmd_sync` all take `state_lock()` as a context manager, whose
`__exit__` releases it the same way for any exception. `GH.reachable()` (used once, by
`cmd_new`'s pre-flight check) explicitly re-raises `GatewayBusy`/`GatewayCapRefused`
before its catch-all `except Exception: return False`, so a busy/capped gateway there
still surfaces as 75/76 through `main()`'s backstop rather than silently reporting
"unreachable." Found nothing left that would turn a plain lock collision into a crash-looking
exit code.

Release note (none): internal tooling.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
