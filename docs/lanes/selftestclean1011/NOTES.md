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

## Attempt 2 (resume, 2026-10-16 ~12:0x PDT)

Attempt 1 (started 2026-10-11 15:5x PDT) never finished: the implementation, the
new fragment, and both mutant falsifications were all done and verified in
isolation (see "Verification" below), but the session went idle for 5 days with
that work sitting uncommitted in this worktree -- no crash, just never came back
to run the full unsharded `selftest.sh` or open a PR. hostops found it 2026-10-16
~09:4x PDT, committed the WIP as-is (`bffdbdd8a4`), corrected `PR.md`'s `State:`
back to `draft` (a checkpoint commit had claimed `ready` while its own message
said the opposite), and released `docs/testing/jobs/selftest.sh` /
`selftest.d/89-sign-rotation.sh` from this lane's board row to `[lane.sign1016]`,
which needs them for its own one-line `SHARD_SECS` entry. That is a territory
change, not a defect in this lane's diff.

Checked at resume (fetched `origin/board` and `origin/master` fresh): `territory.toml`
on `origin/board` (`[lane.sign1016]` at line 2762) confirms `docs/testing/jobs/selftest.sh`
is currently owned by `lane.sign1016`, widened into its row at ~09:4x PDT after its
ready PR (`40aeba6fa6`) was first refused by foldqueue at 09:39:32 for touching it
outside that row. But `lane/sign1016` still has not folded: `foldqueue.log` shows a
second, different stall after the territory fix --
`10:41:14 WAITING lane/sign1016 @ 40aeba6fa6: no device run built from the head yet`
followed by `10:41:16 GATE QUEUED lane/sign1016 @ 40aeba6fa6: gate NOT queued /
restore NOT queued` -- and no further `sign1016` line appears through the latest
tick in the log (`11:42:59`, several other lanes folding normally in between). So
`selftest.sh` is not back on this lane's row yet, and per the addendum this lane
must not touch it until it is. Wrote `docs/lanes/selftestclean1011/WAITING` (`grant
docs/testing/jobs/selftest.sh: blocked on lane.sign1016's fold`) and is stopping
here rather than spinning on another lane's fold. Nothing else in this lane's own
diff changed; the Verification section below still describes the last real run.

## Attempt 3 (resume, 2026-10-16, after attempt 2 stopped on its own WAITING)

Attempt 2 did exactly what it should: confirmed `lane/sign1016` had not yet folded,
wrote `docs/lanes/selftestclean1011/WAITING` (`grant docs/testing/jobs/selftest.sh:
blocked on lane.sign1016's fold`), and stopped rather than spin on another lane's
fold -- that is a finished turn, not an unfinished one. It did not fail or go idle;
the fold it was waiting on simply hadn't happened yet at 12:0x PDT.

At this resume: confirmed on `origin/board`'s `territory.toml` that `lane.sign1016`
folded as `56bb989b0c` (12:18:48 PDT) and its row is RETIRED; `docs/testing/jobs/selftest.sh`
is back in `[lane.selftestclean1011]`'s `files` list (line 967) with a note recording
the grant. Deleted the satisfied `WAITING` file. Continuing with the addendum's step 2:
merge `origin/master` (594 commits behind at fetch), confirm the rebase-free merge
picks up `sign1016`'s one-line `SHARD_SECS` entry with no conflict against this lane's
`T_OWNED` diff, then run the real unsharded `selftest.sh` and fill in the still-open
placeholder below.

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
