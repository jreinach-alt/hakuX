# selftestclean1011: selftest.sh removes its fake host when it passes (#433)
State: ready

Lane: selftestclean1011        Issue: none (#433 umbrella, board row `[lane.selftestclean1011]`)
Base: master @ b73d50a070
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
  afterward.
- `selftest.sh --check-shards 4`: all 137 fragments (136 + this one) covered exactly once.
- Full unsharded `bash docs/testing/jobs/selftest.sh`: **(filled in below once the run -- in progress,
  foreground/tracked-background per the "never end a turn on your own untracked background job" rule --
  finishes; this host has measured 23-24 min for a single CI shard alone, so the unsharded run is long)**.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
