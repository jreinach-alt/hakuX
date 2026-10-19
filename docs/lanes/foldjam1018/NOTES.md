# lane.foldjam1018 -- fix the 2026-10-18 fold jam's three causes so they can't recur

Owner order 2026-10-18 ~20:40 PDT, dispatched directly (no issue): fix the process, not the symptom; owner
does not care about the selftest/process itself, only that this exact failure mode can't recur. Scope: fold
and dispatch tooling only -- no gameplay, no device, no emulator code.

## Attempt 3 (resumed 2026-10-19 06:50 PDT): why attempt 2 didn't finish

Attempt 2 (06:16-06:31 PDT) did the actual fix work -- `shard_chains()`/`close_chains()`/`fold_fail_message()`
in `offline_fold.py`, the SHARD_CHAINS falsifier, the investigation doc section 6 writeup -- and verified it
for real (`SELFTEST_ONLY=98-foldjam1018` + `66-status-titles`, 0 failures). But its last action was to say it
would "wait for the background verification task to finish; it will notify me automatically" and end the
turn there. This is a headless `claude -p` session: nothing started with `run_in_background` or left running
survives the session ending, so that notification was never coming, and the session ended with four files
modified and never committed or pushed (`git status` showed the same four files still modified when this
attempt started, 24 minutes later, with origin/master unchanged at f3eb1122b0). hostops caught this at 06:50
PDT and resumed attempt 3 to finish the mechanical part: re-verify nothing drifted, commit, push, in one
turn, no background wait.

Re-verification this session: `SELFTEST_ONLY="98-foldjam1018 98-foldjam1018-territory 66-status-titles" bash
docs/testing/jobs/selftest.sh` -- 40 passed, 0 failed (same result PR.md already claims). origin/master is
still f3eb1122b0, matching `PR.md`'s `Base:` line, so no rebase/re-merge was needed. Re-ran the falsifier
(`SELFTEST_ONLY="51-dispatch-hardening" bash docs/testing/jobs/selftest.sh` alone, bypassing the fix) and it
still hangs as the investigation doc describes -- confirms the bug is real and the fix (which lives in
`offline_fold.py`'s fragment-selection path, not in a bare `SELFTEST_ONLY` invocation) is what actually
closes it, not that the hang went away on its own.

## Attempt 2 (resumed 2026-10-19 06:13 PDT): why attempt 1 didn't finish

Attempt 1 shipped D, B, A (the auto-widen) and part of C, marked the PR ready, and was then blacklisted by its
own fold: commit `aa99e3acc4` failed `selftest failed (rc 1)` at 23:58:18 PDT, and again at two later master
shas (per hostops's 06:13 resume note) -- not from a defect in the PR's actual diff, but from a bug in item A's
own widening logic, found by hostops and root-caused in their 00:11 PDT addendum: `mentioning_fragments()`
correctly pulled in `51-dispatch-hardening.sh` (it mentions `check_territory.py`, a file this PR changes), but
51 calls `clear_markers`/`finish_queue`, which are only DEFINED in `50-arms-requeue.sh` -- a full suite run
only works because bash sources every fragment, in file order, in one shell, before 51 runs. A
`SELFTEST_ONLY=51-dispatch-hardening` run never sources 50, so both calls fail open (`command not found`,
non-fatal under `set -u`), corrupting fixture state and cascading into unrelated FAILs instead of a clear
error. This session (attempt 2) fixes that gap: see investigation doc section 6 for the full root-cause
writeup and the fix (`shard_chains()`/`close_chains()` in `offline_fold.py`, closing a widened fragment set
over `selftest.sh`'s own `SHARD_CHAINS` array, plus `fold_fail_message()` to name the undefined command loudly
if a future gap isn't yet in `SHARD_CHAINS`). Reproduced the real failure directly
(`SELFTEST_ONLY="51-dispatch-hardening" bash docs/testing/jobs/selftest.sh` hangs/fails exactly as described)
before writing the fix, and confirmed the fix closes it (`close_chains` pulls in the full 13-fragment chain).

## What I found (re-verified from logs, not assumed from the brief)

The brief's open question ("why didn't compat1017b's own fold run fragment 66?") had a wrong suspected
answer. It assumed a named `Selftest:` subset omitted the fragment; the actual journal entry
(`journal.jsonl:243`) shows compat1017b declared `Selftest: none -- ... title_registry_selftest.py covers
the new README check` -- an explicit, unchecked "nothing applies" claim, not a subset. `offline_fold.py`
never checked that claim against what the suite's fragments actually cover. Full writeup:
`docs/investigations/foldjam1018.md` section 1.

A second thing I found while building the fix: a naive "does the fragment's text contain the changed file's
full repo-relative path" grep would still have missed this exact case -- `66-status-titles.sh` mentions the
changed file (`docs/testing/title_registry.py`) only by basename (`title_registry.py`) in a comment. The
auto-widen helper (`mentioning_fragments`) matches on both the full path and the basename; verified against
a reconstruction of the real fragment text and compat1017b's real changed-file list in
`/tmp/foldjam-test/frag/`.

## What shipped (tested; see the investigation doc's summary table for detail)

- **D** `offline_fold.py --owner-order "<reason>"`: skips the suite, keeps the device-run requirement, runs
  py_compile/bash -n on changed files, journals `checks.selftest.skipped`.
- **B** blacklist keyed to master sha (`head@master:sha`, one retry per master advance) in
  `foldqueue.sh`/`foldqueue.tried`; `driver_tick.py`'s `blacklist_status`/`blacklist_reason` make the jam row
  say `blacklisted: <reason>, since <time>` instead of `watching`.
- **A** (part 1) `mentioning_fragments()` in `offline_fold.py`: a `Selftest: none` claim is now checked
  against the suite's own fragments (by path or basename) before being trusted, and a named subset is
  widened the same way -- both were already live code from before compaction; this session corrected the
  comment that mis-attributed the compat1017b mechanism, and fixed the `none`-claim path to actually run the
  auto-detected fragments instead of only widening an explicit named list (the `none` path previously had no
  widening at all -- it is the path compat1017b actually took).
- **A** (part 2) `master_health_check.sh` (new) + `foldqueue.sh`'s background `systemd-run` trigger after
  each FOLDED + `driver_tick.py`'s `master_red_status`: full suite against the new master after every fold,
  jam `master-red:<fragment>` if it goes red and the checked sha is still live.
- **C** (partial) `check_territory.py`'s FREE-but-claimed message now names the exact fix.
- Two new repo selftest fragments, run for real (not just isolated units):
  `docs/testing/jobs/selftest.d/98-foldjam1018.sh` (mirrors foldqueue.sh's master-keyed skip-check and
  offline_fold.py's path/basename fragment-matching, since both tools live outside the repo and can't be
  imported) and `98-foldjam1018-territory.sh` (drives the real, in-repo `check_territory.py` against a
  synthetic overlap).

## Not done

- **C** (territory-at-ready check, fold-to-running-lane notification): spec only, investigation doc section
  3. `lane.sh` is sparsewt1017's; the notification channel (PR comment vs. a polled file) is a
  dispatch-ownership decision, not mine to make unilaterally.
- **E** (hold visibility, one-command battery override): spec-only by design -- `hold.sh` is holdcap1018's,
  `battery_admit.py` is toolsmith's.

## Correction made mid-session

My own first pass at the investigation doc said `check_territory.py` "was not found as a named script" and
treated item C's FREE-widen exact-fix message as unbuildable without guessing at a file. That was wrong --
`docs/testing/check_territory.py` exists in this repo (231 lines) and is already granted in this lane's own
territory row. Fixed the FREE-but-claimed message (line ~139) to name the exact fix
("release it from [free] in the same commit that adds it to [lane.X]'s files"), added
`docs/testing/jobs/selftest.d/98-foldjam1018-territory.sh` to test it, and ran it for real through
`docs/testing/jobs/selftest.sh` -- 5/5 pass, plus `66-status-titles.sh` itself re-run clean (22/22) to rule
out a regression. If you hit a "can't find X" wall in this codebase, grep before writing it off as spec-only
-- the row that was pre-written for this lane (`[lane.foldjam1018]` on origin/board, by lane.local at
dispatch time) had already scoped `check_territory.py` in, which was the signal I missed the first time.

## Verification approach (and why it's syntax + isolated units, not an end-to-end run)

Every edited/created file lives outside this repo (`offline-git/`, `host-tools/`), and all three
(`offline_fold.py`, `foldqueue.sh`, `master_health_check.sh`) run git against the live
`/home/justin/hakuX` dispatcher tree. Per "never run git in a tree that is not your worktree," I did not
invoke any of them for real. Verification was `python3 -m py_compile` / `bash -n` on every file, plus
isolated unit tests of each new function/branch against synthetic fixtures (including, for the auto-widen
fix, a reconstruction of the real compat1017b scenario), plus `driver_selftest.py`'s full suite (24/25 pass;
the 1 failure is pre-existing and unrelated -- reproduced identically against the pre-edit
`.bak-20261018-foldjam1018` backup).

## For the next lane

- If you pick up item C: the blocking unknown is locating the actual FREE-widen refusal site (not found in
  this repo, `offline-git/`, or `host-tools/` under the name `check_territory.py` in this session's time
  budget) and the lane.sh ready-step owner's preferred notification channel (PR comment vs. polled file) --
  resolve those before writing code, not after.
- `foldqueue.tried`'s territory-keyed entries (`head@territory-sha`) were untouched by this work; only the
  selftest-failure keying changed shape (bare `head` -> `head@master:sha`).
- No live incident state needed fixing: the real stuck lanes (fpsdiag1018, localdrive1018) were already
  folded/un-blacklisted by hand by lane.local before this session started. This is forward-looking
  prevention, not an unstick job.
