# lane.selftestclean1011

## Why (#433 umbrella, no separate issue)

`docs/testing/jobs/selftest.sh` made its own fake host with
`T=$(mktemp -d "${TMPDIR:-/tmp}/hakux-selftest.XXXXXX")` and never removed it; the
last line printed `(fake host in $T)` and exited. Every run -- every lane, every
fold tick, every CI shard -- left one behind. Measured on the host 2026-10-11
15:05 PDT: 256 of them under `/tmp` since the 10-09 20:13 boot, 1.58M files,
27.7 GB, about 50 new a day (~14 GB/day). lane.local deleted the 240 older
than 3h on the owner's word around 15:4x; this lane stops the leak itself.

## The change

1. `selftest.sh`: near the top, `T`'s assignment now also sets `T_OWNED` --
   `1` when selftest.sh made `$T` itself (no `SELFTEST_DIR` given), `0` when
   the caller supplied `SELFTEST_DIR` (nothing does today; the contract
   stays for a future caller). At the very end, right after the summary
   line is composed and just before it is printed: if `fail` is 0 **and**
   `T_OWNED` is 1, `rm -rf "$T"` and say so on the last line (`fake host
   removed, was $T`); otherwise keep `$T` and print `(fake host in $T)` as
   before. The final `[ "$fail" -eq 0 ]` is unchanged.

2. **No EXIT trap.** The brief flagged two fragments that set `trap ... EXIT`
   (`99-release-note-line.sh:25`, `84-perf-regimen.sh:194`) as fragments that
   could clobber a top-level trap set before the fragment loop. Checked both:
   neither actually sets a trap *in selftest.sh's own shell*. Line 25 of
   `99-release-note-line.sh` is text inside a heredoc (`round_trip.sh`) that is
   later run with `bash "$RN/round_trip.sh" ...` -- a **child process**, whose
   own EXIT fires on its own exit, never touching the parent. Line 194 of
   `84-perf-regimen.sh` is a string literal being grep'd/replaced as a mutant
   body for `soak_title.sh`, which also runs via `bash "$s" ... &` -- again a
   child process. So today nothing sourced into selftest.sh's shell sets an
   EXIT trap. Even so, I did **not** rely on a top-level trap for the
   removal: a future fragment that legitimately needs its own EXIT trap
   (sourced fragments share the shell, so there's exactly one EXIT trap slot)
   would silently disable cleanup again. Doing the removal explicitly, once,
   after the summary line, has no such failure mode and needs no
   coordination with fragment authors. **A run killed by a signal**
   (foldqueue's timeout sends one) never reaches that line and keeps its
   dir -- accepted, not handled, per the brief. The same is true of every
   `exit 2` earlier in the file (bad fragment name, `--check-shards`,
   `SELFTEST_SHARD` malformed, `SELFTEST_ONLY` matching nothing): those all
   happen before or without reaching the final block, so they also keep
   `$T`. That is consistent with "a run that didn't finish cleanly keeps its
   debugging copy," not a gap in the fix.

3. New fragment `docs/testing/jobs/selftest.d/99-tmp-cleanup-selftestclean1011.sh`,
   proving the fix with a REAL nested `selftest.sh`, not a stub:
   - **(a)** pass: `SELFTEST_ONLY` narrowed to one fragment, a private
     `TMPDIR`; after the nested run exits 0, no `hakux-selftest.*` remains
     under that `TMPDIR`.
   - **(b)** fail: same, but the probe is told to fail; the nested run exits
     non-zero and leaves exactly one `hakux-selftest.*` dir.
   - **(c)** `SELFTEST_DIR` given: the nested run passes, but the given dir
     survives (never removed) and no `mktemp` dir is made alongside it.
   - **The fragment narrows to is itself.** A real production fragment's
     pass/fail can't be flipped from outside without mutating a real job
     script, which I didn't want to do even transiently. So
     `SELFTEST_ONLY=99-tmp-cleanup-selftestclean1011` selects this very
     file in the nested run, and the env var `SELFTEST_TMPCLEANUP_PROBE`
     (set only by this fragment's own `tc_run` helper, never by a real
     invocation) tells the nested copy of itself to act as a two-line
     pass/fail probe instead of recursing into the meta-test. That is the
     "guard against the fragment selecting itself" the brief asked for --
     it doesn't need a separate recursion counter because the probe branch
     never calls `tc_run` itself.
   - Cost: sharded in at `SHARD_SECS` weight 2 (measured alone, see below);
     total wall time for the whole fragment (3 real nested runs + 2 mutant
     runs, all `SELFTEST_ONLY`-narrowed) was 2-3s.

4. Mutants, both run against a **copy** of the whole `jobs/` directory (not
   the real one): `selftest.sh` resolves `$HERE`/`$TESTING`/`$REPO` from its
   own `BASH_SOURCE` path with no override hook, so a mutant has to keep the
   same `docs/testing/jobs/` depth to resolve correctly; copying just
   `selftest.sh` elsewhere breaks fragment discovery. `cp -a` of the ~3MB,
   189-file `jobs/` dir is instant.
   - **Mutant 1** (`tc_mutant_noremove`): reverts the ending to the literal
     pre-#433 line (`echo "... (fake host in $T)"`, no removal at all).
     Check (a) catches it: the nested pass run now leaves a dir, confirmed
     with the path printed in the failure message.
   - **Mutant 2** (`tc_mutant_removefail`): drops the `[ "$fail" -eq 0 ]`
     half of the condition, so it removes `$T` whenever `T_OWNED` -- even on
     a failing run. Check (b) catches it: the nested failing run now leaves
     nothing.
   - Ran both by hand first (see "Verification" below) before trusting them
     inside the fragment.

## Verification

Isolated fragment run (`SELFTEST_ONLY=99-tmp-cleanup-selftestclean1011`,
private `TMPDIR`): 8/8 passed, including both mutant falsifications, and the
outer run's own fake host was removed afterward (confirmed empty `TMPDIR`
after exit). `--check-shards 4` still reports all 137 fragments covered
exactly once (136 existing + this one; `SHARD_SECS` carries its own
`:2` entry so a stale default doesn't skew balance).

Full unsharded `bash docs/testing/jobs/selftest.sh` (no shard, no
`SELFTEST_ONLY`): see the result below -- `docs/lanes/selftestsplit/NOTES.md`
and `docs/lanes/soakvideo1011/NOTES.md` both note this host is slow enough
that a single CI shard alone has taken 23-24 minutes real time against a
5-9 min CI estimate, so the full unsharded run was expected to run well past
the Bash tool's 10-minute per-call cap; ran it as a tracked
`run_in_background` call (the harness's own backgrounding, not a
self-managed `nohup`) and waited for its notification in this same session,
per the "never end a turn while a job of yours is still running" rule --
nothing here used a detached/untracked process.
