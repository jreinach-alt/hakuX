# nova-tiers1019 (#433): Nova priority tiers that actually hold

## What this lane built

1. **Hold tier.** `docs/testing/jobs/hold.sh take|wait` now accept `--tier
   blocker|fps|sweep` (env `HOLD_TIER` as the fallback; no tier at all = `fps`,
   today's behaviour, byte-for-byte). The tier is recorded in a new
   `hold/<label>.tier` sidecar, written by `take`'s winner, removed by
   `release` under the same rules as `.why`.
2. **A sweep take/wait never beats queued or running higher-tier work.**
   New `sweep_blocker()` helper walks `running/*.req` (by `.owner` sidecar)
   and `queue/*.req`, using `affinity.py` for eligibility -- the same
   device-label rule `dispatcher.sh`'s `serve_one` uses, not a guess from the
   id string. `take --tier sweep` refuses with a new exit code 8 when a
   `0-*`/`1-*` request is in either place for this label; `wait --tier sweep`
   keeps polling on that condition instead of exiting.
3. **Cooperative yield.** New `hold.sh yield-check <label> <tag>`: exit 0 =
   keep going, exit 7 = a `0-*` is queued/running (any age) or a `1-*` has
   been queued 60+ s (`HOLD_YIELD_S`). A sweep hold also self-expires after
   `HOLD_SWEEP_MAX_S` (1800 s default): `take`'s create-race path notices a
   stale sweep tier file past that age and clears it rather than blocking
   forever on a chain that died without releasing.
4. **Chain default -- BLOCKED, not fabricated.** The brief names
   `overnight1018.py`, `title1006.sh`, and "any wrapper under
   docs/testing/" as the tools to default to `--tier sweep`. Checked all
   three:
   - `title1006.sh`: does not exist as committed code anywhere in the repo.
     The only match by that name, `docs/lanes/pathfind/scratch/title1006.sh`,
     was an *uncommitted* scratch file that belonged to the pathfind lane;
     it is not in the tree on this branch or on origin/master, and
     `docs/lanes/pathfind/NOTES.md`/`batch.sh` confirm pathfind's actual
     chain driver is `batch.sh`, which never calls `hold.sh` at all (it runs
     through `request.sh`/the dispatcher queue, already tier-aware via the
     `0-`/`1-`/`z-` id prefixes request.sh writes).
   - `overnight1018.py`: does not exist either, committed or uncommitted.
     No file by that name anywhere under `docs/testing/` or `wt/`.
   - `docs/testing/overnight_19.sh`: exists, but it is the unrelated #19
     regression campaign driver. It leases its device directly
     (`HAKUX_DEVICE_LEASE`, see `devices.sh`) and never calls `hold.sh`
     take/wait/wait-idle at all, tiered or not.
   There is currently no committed screening-chain tool in this repo that
   calls `hold.sh` and would need a `--tier sweep` default. Item 4 is
   reported here as blocked on that absence rather than invented against
   files that don't exist. **The next lane that writes or resurrects a
   screening-chain driver (pathfind-style, title-by-title, calling
   `hold.sh take`/`wait`) must default its hold calls to `--tier sweep`** --
   the mechanism (this lane's items 1-3) is in place and selftest-covered;
   only the caller is missing.
5. **Watch**, outside this git tree (`/home/justin/hakux-work/host-tools/`,
   edited live with dated backups `hourly_report.sh.bak-20261019-novatiers1019`
   / `driver_tick.py.bak-20261019-novatiers1019`, per the project's
   edit-the-live-file convention):
   - `hourly_report.sh` gets a new "HOLD WATCH" section: every currently
     held label (enumerated from `devices.sh`'s own `DEVICE_LABEL=`
     exports, so a sidecar like `nova.battery-override` or the `lifted`
     marker directory is never mistaken for a held device), its tag, tier,
     age, and the oldest queued/running `0-*`/`1-*` request behind it (or
     "nothing ... behind it"). Dry-run against the live dispatch dir
     (read-only) confirmed clean output for `nova` and `thor`, with the
     `lifted` dir and `nova.battery-override` sidecar correctly excluded.
   - `driver_tick.py` gets a new check **g, sweep-hold-stuck**: for every
     held label whose `.tier` file reads `sweep`, it recomputes the same
     blocker set `yield-check` would see and opens a `pm/jams.tsv` row
     (via the existing `row()`/ledger mechanism -- no new ledger) when the
     oldest blocker has been overdue a yield-check release (immediate for a
     `0-*`, 60 s after queueing for a `1-*`) for more than 5 minutes. This
     reuses the brief's named "existing `pm/jams.tsv` driver pattern"
     exactly: same `row()` call shape as checks a-f, same ledger file, same
     hourly-report reader. New pure functions `hold_epoch()` and
     `sweep_hold_overdue()` were unit-tested in isolation (see below) rather
     than by running `driver_tick.py`'s `main()` for real -- `main()`
     mutates the live `.driver.json`/`pm/jams.tsv`/systemd units on this
     shared host, which a lane must not do; `python3 -m py_compile` plus a
     module-level import (which does not call `main()`, guarded by
     `if __name__ == '__main__':`) confirmed syntax, and a standalone
     `importlib` test exercised the two new pure functions' edge cases
     (0-* overdue at 400s past queueing with a 300s grace; 1-* not yet
     overdue at 100s past queueing, 40s short of its own 60s+300s bar;
     1-* overdue at 400s; non-sweep tier never flags; empty blocker list
     never flags).
   - Neither host-tools file shows in this PR's diff since neither is part
     of the git repo; the dated backups are the audit trail.
6. **Docs.** New paragraph in `AGENTS.md` right after the "Working with a
   device" table's closing line, before "Debug builds are debuggable...":
   the three tiers, that a hold carries one, what `yield-check` does, and
   the 30-minute self-expiry. No internal process/incident commentary (no
   mention of the 10-17/10-18 nights that motivated this) -- kept to what a
   reader of public docs needs to use the mechanism.

## Explicit scope boundary (per the brief)

`dispatcher.sh`'s claim order was **not touched**. It already serves
`dispatch/queue/*.req` in ASCII id order, which is what makes the `0-`/`1-`/
plain/`z-` filename-prefix tiering work for queued requests in the first
place; this lane's entire gap was that `hold.sh` had no matching concept for
a *hold* (which blocks the device outright, upstream of anything the queue
order could do). Nothing here suggests `dispatcher.sh` needs a change.

## Falsifier

`docs/testing/jobs/selftest.d/99-hold-tiers.sh`, fake `DISPATCH_DIR` under
the harness's own `$T` scratch dir (never a real dispatch dir). Covers all
five required legs (a: sweep take refused on a queued `1-*`, plus bonus
sub-legs for a queued `0-*` and a *running* `1-*`; b: sweep take succeeds
with only `z-*` queued; c: `yield-check` age/immediate behaviour; d:
untiered take/release unchanged from today; e: `.tier` lifecycle incl.
wrong-tag release) plus two bonus legs (f: `wait --tier sweep` does not
instant-fail, takes once the queue clears) and the required **mutant**:
a sed-patched copy of `hold.sh` with both `if [ "$TIER" = sweep ] &&
blocker=$(sweep_blocker "$label")` gate checks disabled, built with its
`device_build.py`/`affinity.py` neighbours copied into the same relative
layout (`$(dirname "$0")` and `$HERE` resolve against wherever the mutant
script actually sits, not the real repo -- a mutant alone in a bare
scratch dir fails for a missing-file reason instead of demonstrating the
real bug; this cost one debugging pass, see below), demonstrating leg (a)
genuinely fails under it (`take --tier sweep` wrongly succeeds with a
`1-*` queued).

Final count: **35 passed, 0 failed** for this fragment alone
(`SELFTEST_ONLY=99-hold-tiers.sh`).

## Full selftest.sh, all four CI shards

Ran all four shards of `selftest.sh` (`SELFTEST_SHARD=k/4` for k in 0..3,
matching `.github/workflows/jobs-selftest.yml`'s matrix) against this
branch. All four passed with zero failures:

| shard | fragments | checks passed | failed |
|-------|-----------|----------------|--------|
| 0/4   | 13        | 290            | 0      |
| 1/4   | 49        | 1265           | 0      |
| 2/4   | 47        | 1157           | 0      |
| 3/4   | 49        | 1117           | 0      |

3829 passed, 0 failed, across all 158 fragments.

`99-hold-tiers.sh` landed in shard 2/4 (4s) and ran standalone -- it was not
added to `SHARD_CHAINS` because it builds and tears down its own isolated
fake `DISPATCH_DIR` under `$T`, sharing no state with any other fragment
(unlike 10..64's shared dispatcher-queue chain). The pre-existing
`99-hold-take.sh` (untiered take/release, today's behaviour) landed in
shard 1/4 and still passes unchanged, confirming leg (d)'s "run the existing
hold selftest too" instruction without re-sourcing it from inside the new
fragment (see "mistakes avoided" below).

## Mistakes made and avoided, for the next lane touching this area

- **A cosmetic stdout change can break an unrelated exact-match assertion.**
  An early draft of `take`'s success message appended `(tier %s)`; this
  silently broke `99-hold-take.sh`'s anchored regex
  `^taken: nova by lane.titleroutes$`. Fixed by leaving stdout
  byte-for-byte unchanged and keeping the tier fully recoverable from the
  sidecar `.tier` file instead. **Any future hold.sh output change needs a
  full run of `99-hold-take.sh`, not just the new fragment, before trusting
  it.**
- **A mutant script is not just "the file with a line changed" -- it is a
  file at a specific path, and other functions in the same file resolve
  their own neighbours relative to that path.** `build_gate()` resolves
  `device_build.py` via `$(dirname "$0")`; `sweep_blocker`/`yield_signal`
  resolve `affinity.py` via `$HERE` (`dirname "${BASH_SOURCE[0]}"`). A
  mutant copy dropped alone in a bare scratch dir makes the *unrelated*
  `build_gate()` call fail first (file not found), so the mutant "fails"
  for the wrong reason and the test looks like it's proving something it
  isn't. Fixed by mirroring the real repo's relative layout
  (`jobs/hold.sh` + `jobs/device_build.py` + one level up `affinity.py`)
  under the mutant's own scratch root.
- **Never re-source another fragment's file from inside a subshell to
  "double check" it runs.** A draft of this fragment briefly did
  `( . "$HERE/selftest.d/99-hold-take.sh" )` to re-verify leg (d). Caught
  before running it: `ok()`/`bad()` increment `pass`/`fail` in the parent
  shell's variables, and a subshell's variable changes never propagate
  back out -- the re-run's assertions would print PASS/FAIL text but never
  actually move the suite's real counters, which is a false sense of
  coverage, not coverage. Removed; relying instead on `99-hold-take.sh`
  running as its own independent entry in the same `selftest.sh`
  invocation (confirmed above, shard 1/4).
- **Don't run a live host-tools script's `main()` to "test" an edit to
  it.** `driver_tick.py` writes to `/home/justin/hakux-work/host-tools/
  .driver.json`, `pm/jams.tsv`, `pm/lanelocal-log.md`, and can start
  systemd units, on the real shared host, every tick. Verified the new
  code by `py_compile` + importing the module (which does not execute
  `main()`) to unit-test the two new pure functions directly, plus a
  read-only dry run of the *new hourly_report.sh snippet only* (plain
  `glob`/`open`/`os.path.getmtime` reads against the real dispatch dir,
  no writes) to catch the `lifted`-directory / `nova.battery-override`
  false-positive before it ever reached a report.
