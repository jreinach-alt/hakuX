# localforge: a local Forgejo stands in for GitHub, a gh shim that fails loudly, and the harness on it (#433)

State: ready

Lane: localforge            Issue: #433
Base: master @ 9d1155f919 (merged to origin/master @ bc2bced563 on 2026-10-03)
Files: .forgejo/workflows/forge-android.yml, .forgejo/workflows/forge-selftest.yml, .github/workflows/android.yml, .github/workflows/build-xemu-win64-toolchain.yml, .github/workflows/desktop.yml, .github/workflows/jobs-selftest.yml, .github/workflows/nv2a-index.yml, AGENTS.md, docs/lanes/localforge/NOTES.md, docs/lanes/localforge/OUTBOX.md, docs/lanes/localforge/PR.md, docs/lanes/localforge/RETURN.md, docs/lanes/localforge/forge_import.py, docs/lanes/localforge/import_smoke.py, docs/testing/comment_sweep.sh, docs/testing/desktop-gate-warnings.md, docs/testing/jobs/board.sh, docs/testing/jobs/fold.sh, docs/testing/jobs/gh-shim/forge_prsync.py, docs/testing/jobs/gh-shim/gh, docs/testing/jobs/gh-shim/install.sh, docs/testing/jobs/gh-shim/route.sh, docs/testing/jobs/gh-shim/route_test.py, docs/testing/jobs/gh-shim/smoke_live.py, docs/testing/jobs/handback.sh, docs/testing/jobs/status.sh, docs/testing/systemd/README.md
Prediction: none: no arm. Harness infrastructure only (a local forge, a gh shim, job gates, unit routing); no emulator pixels or speed.
Needs device: no    Needs NDK: no

Release note (none): test harness only. No emulator code changes.

## What this is

GitHub suspended the account on 09-29. Every `gh` call has returned 403 since, and
most callers read that as "nothing to do". This PR, with the host setup listed in
NOTES.md, gives the harness a local GitHub alternative and moves every harness unit
onto it.

1. **Forgejo 16.0.5** runs as `hakux-forge.service` on **127.0.0.1:3330 only**. Its
   SQLite data is in `~/hakux-work/forge/`. Users: one per actor, and tokens are mode 600.
2. **The repo**, `jreinach-alt/hakuX`, holds every branch of the bare stand-in. It is
   fed by `hakux-forge-sync.timer` (about 60 s lag). Origin stays the bare repo (option
   (b)), so no lane or foldqueue push changes.
3. **The gh shim** is `docs/testing/jobs/gh-shim/gh`. It implements every gh operation
   the harness uses, against the forge's API, keyed on `GH_REPO`. Every failure exits
   nonzero with one stderr line. Unknown operations exit 64 (`gh-shim: not implemented:
   <args>`). Every call is logged to `~/hakux-work/logs/forge/shim.log`.
4. **Issues #1-#640 keep their GitHub numbers.** `forge_import.py` seeds them from the
   board tracker. The 13 unfolded lane branches with a PR.md are forge PRs, kept equal
   to their PR.md by `hakux-forge-prsync`. Forge-native issues are numbered from #641. The
   17 created after the suspension (#656-#677) carry the `local-only` label and are in
   `forge-import/local-number-map.tsv`.
5. **Unit routing** (`route.sh`, one drop-in per unit):
   - Phase 1 (comments, issue-sweep, pr-sweep, arms) is routed.
   - **Phase 3 (new):** every other harness unit gets the shim first on PATH and its
     actor as `FORGE_USER`: hostops, dispatcher, nightly, pm@, the job timers and the rest.
     Phase 3 does not set `HAKUX_FORGE`, which is phase 2's dry-run switch.
   - Phase 2 (status, board, fold, foldpace, handbackpace) is not routed. It waits for this
     PR to fold, because `route.sh` refuses a unit until master carries its gate. Those
     units are disabled.
   - `hakux-cloud` is not routed and is to be disabled. `hakux-forge*` never get the shim.
6. **The jobs under the forge:** `board.sh`, `handback.sh` and `fold.sh` are dry-run under
   `HAKUX_FORGE=1`, and `status.sh` never pushes to github.com. `comment_sweep.sh` keeps
   its own forge state and no longer posts to `issues/null`.
7. **Nightly publish:** `nightly_build.sh` publishes its APK as a forge prerelease
   `nightly-<day>` (create, or upload with `--clobber` if the tag exists).
8. **Local CI** runs on `hakux-forge-runner.service` (host executor, capacity 1).
   `forge-selftest.yml` and `forge-android.yml` run on non-draft PRs only.
9. **Protocol and return** (documents, nothing executed): the FORGE PROTOCOL is at
   `~/hakux-work/lane-protocol/forge.md`, outside the repo. `RETURN.md` designs the
   return to GitHub, and records a hazard in `offline-git/recover_github.py`, which probes
   GitHub with the `gh` on PATH. Under the shim that probe answers from the forge.
10. **No GitHub workflow starts itself.** android, desktop, nv2a-index, jobs-selftest and
    build-xemu-win64-toolchain are `workflow_dispatch`-only. A push to GitHub on the return
    cannot restart the old CI. On the forge, a branch without `.forgejo/workflows` no longer
    queues runs that wait for an `ubuntu-latest` runner that does not exist. The other 13
    workflows were already `workflow_dispatch` or `workflow_call`.
11. **`gh pr list --search`** takes qualifiers (`head:`, `base:`, `author:`, `label:`, `is:`).
    It used to exit 64, which `hardware/xbox_check.sh` hid with `2>/dev/null`, so that
    check read "no open PR" on every run.

Caller decisions for every remaining `gh` call on master are in NOTES.md section 7.1.

## Local checks (no GitHub CI while offline)

- `python3 docs/testing/jobs/gh-shim/smoke_live.py` (live forge, scratch repo created and
  deleted by the test): **88 passed, 0 failed**. Includes a release section (create,
  create-on-existing refused, upload refused without `--clobber`, `--clobber`, view, list,
  `release download` exits 64).
- `python3 docs/testing/jobs/gh-shim/route_test.py` (phase 3 drop-ins, in a temporary units
  directory): **83 passed, 0 failed**.
- `bash ~/hakux-work/host-tools/local_jobs_selftest.sh`: **14 checks passed**.
- `docs/testing/jobs/selftest.sh` (all shards, run locally at ab37133): **3000 passed, 0 failed, all 123 fragments.** Log: `~/hakux-work/logs/forge/selftest-localforge-ab37133.log`.
- Re-run at this head (attempt 3, after the merge with origin/master at a143aa5db8 and the addenda 4-7 changes): `selftest.sh` in the four CI shards, `SELFTEST_SHARD=k/4` for k = 0..3: **284 + 865 + 967 + 884 = 3000 passed, 0 failed, all 123 fragments.** `smoke_live.py`: 88 passed, 0 failed. `route_test.py`: 83 passed, 0 failed.
- `python3 docs/lanes/localforge/import_smoke.py` (importer): all passed, unchanged this attempt.
- Attempt 4 (after the merge with origin/master at bc2bced563, the workflow edit and the shim's
  `--search`): `smoke_live.py` **92 passed, 0 failed** (adds three `--search` checks and the
  `issue comment N --body` form). `route_test.py` **83 passed, 0 failed**. `selftest.sh
  --check-shards 4`: passes. RETURN.md 2a's workflow check prints nothing at this head and
  prints the five files on origin/master. The territory check `offline_fold.py` runs, applied to
  this head: 27 files, none outside `[lane.localforge]`. Selftest shards: SELFTEST_RESULT.

## Not done in this PR

- Phase 2 routing (after this PR folds). `route.sh status` says what is missing.
