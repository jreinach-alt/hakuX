# lane.foldjam1018 -- fix the 2026-10-18 fold jam's three causes so they can't recur

Owner order 2026-10-18 ~20:40 PDT, dispatched directly (no issue): fix the process, not the symptom; owner
does not care about the selftest/process itself, only that this exact failure mode can't recur. Scope: fold
and dispatch tooling only -- no gameplay, no device, no emulator code.

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
