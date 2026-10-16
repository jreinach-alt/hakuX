# selftestclean1011: selftest.sh removes its fake host when it passes (#433)
State: ready

Lane: selftestclean1011        Issue: none (#433 umbrella, board row `[lane.selftestclean1011]`)
Base: master @ beb9daa755d3a869768ce8232ac755b53e15a7c3
Files: docs/testing/jobs/selftest.sh, docs/testing/jobs/selftest.d/99-tmp-cleanup-selftestclean1011.sh, docs/lanes/selftestclean1011/NOTES.md, docs/lanes/selftestclean1011/PR.md
Prediction: none (harness fix, not a pixel-moving change)
Needs device: no    Needs NDK: no

## What this is

`docs/testing/jobs/selftest.sh` made its own fake host with `mktemp -d` and never removed it; the last line
printed `(fake host in $T)` and exited, pass or fail. Every run -- every lane, every fold tick, every CI
shard -- left one behind. Measured on the host 2026-10-11 15:05 PDT: 256 of them under `/tmp` since the
10-09 20:13 boot, 1.58M files, 27.7 GB, about 50 new a day. The Linux disk is a VHDX on C: that grows and
never shrinks, and the file count made the hourly disc-image scan time out three hours running.
lane.local deleted the 240 older than 3h on the owner's word around 15:4x; this lane stops the leak.

## The change

- `selftest.sh`: `T`'s assignment now also sets `T_OWNED` (1 when selftest.sh made `$T` itself, 0 when a
  caller supplies `SELFTEST_DIR` -- nothing does today, the contract stays). Right before the final summary
  line: if the run passed (`fail` is 0) and we own `$T`, `rm -rf "$T"` and say so (`fake host removed, was
  $T`); otherwise keep it and print `(fake host in $T)` as before. No EXIT trap: checked both fragments the
  brief named as setting one (`99-release-note-line.sh`, `84-perf-regimen.sh`) and neither actually sets a
  trap in selftest.sh's own shell -- both are text that is only ever run in a **child** `bash` process (a
  heredoc script, a mutant of `soak_title.sh`). Doing the removal explicitly, once, after the summary line
  needs no coordination with fragment authors and can't be silently disabled by a future fragment's own
  trap (sourced fragments share one shell, so there is exactly one EXIT trap slot). A run a signal kills
  (foldqueue's timeout) never reaches that line and keeps its dir, same as every `exit 2` earlier in the
  file (bad fragment name, `--check-shards`, a malformed `SELFTEST_SHARD`, `SELFTEST_ONLY` matching
  nothing) -- a run that didn't finish cleanly keeps its debugging copy. Accepted, not handled, per the
  brief.
- New fragment `99-tmp-cleanup-selftestclean1011.sh` proves it with a REAL nested `selftest.sh`
  (`SELFTEST_ONLY`-narrowed, private `TMPDIR`): (a) a passing run leaves no `hakux-selftest.*` behind, (b) a
  failing run keeps exactly one, (c) a run given `SELFTEST_DIR` keeps it regardless of pass/fail and makes
  no `mktemp` dir of its own. The fragment narrows the nested run to *itself*: `SELFTEST_TMPCLEANUP_PROBE`
  (set only by its own helper, never by a real run) tells the nested copy to act as a two-line pass/fail
  probe instead of recursing into the meta-test, so no production job script needs mutating even
  transiently to get a controllable failing run.
- Two mutants, both run against a `cp -a` copy of the whole `jobs/` dir (selftest.sh resolves its own
  `$HERE`/`$TESTING`/`$REPO` from `BASH_SOURCE`, so the copy keeps the same `docs/testing/jobs/` depth):
  reverting to the literal pre-#433 ending (never remove) fails check (a); dropping the `fail`-eq-0` half
  of the condition (removes on failure too) fails check (b). Both confirmed SURVIVED-then-CAUGHT before
  being left in the fragment.

## Verification

- Isolated fragment (`SELFTEST_ONLY=99-tmp-cleanup-selftestclean1011`, private `TMPDIR`): 8/8 passed,
  including both mutant falsifications; outer run removed its own fake host, confirmed empty `TMPDIR`
  afterward. Re-run after merging `origin/master` in (594 commits, clean merge, no conflicts with
  `lane.sign1016`'s one-line `SHARD_SECS` entry): still 8/8.
- `selftest.sh --check-shards 4`: all 146 fragments covered exactly once (post-merge count; 137 pre-merge).
- Full unsharded `bash docs/testing/jobs/selftest.sh` (detached + polled in foreground, since a lane's own
  `run_in_background`/Monitor is refused by this repo's hook; ~80 min real time): `3570 passed, 0 failed,
  all 146 fragments (fake host removed, was /tmp/hakux-selftest.Ij2qfd)`. That path is confirmed gone
  afterward. No devwatch FAIL appeared. Four other `hakux-selftest.*` dirs appeared in `/tmp` during the
  run's window; `ps`/`/proc/<pid>/cwd` traced them to two *other* `selftest.sh` processes genuinely running
  concurrently on this shared host (one from a foldqueue fold in a different worktree) -- not this run's
  process, not this branch. See NOTES.md "Leak check" for why a plain `-newer` filter can't tell those
  apart from this run's own leak, and why that's expected rather than a regression. 417 pre-existing
  `/tmp/hakux-selftest.*` dirs remain host-wide from before this fix existed anywhere; this change stops
  new leaks from a passing run, it does not retroactively clean the backlog (out of scope per the brief).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
