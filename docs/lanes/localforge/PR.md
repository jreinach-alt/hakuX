# localforge: a local Forgejo stands in for GitHub, and a gh shim that fails loudly (#433)

State: draft

Lane: localforge            Issue: #433
Base: master @ 66bce0c222
Files: .forgejo/workflows/forge-android.yml, .forgejo/workflows/forge-selftest.yml, docs/lanes/localforge/NOTES.md, docs/lanes/localforge/OUTBOX.md, docs/lanes/localforge/PR.md, docs/lanes/localforge/forge_import.py, docs/lanes/localforge/import_smoke.py, docs/testing/comment_sweep.sh, docs/testing/jobs/board.sh, docs/testing/jobs/fold.sh, docs/testing/jobs/gh-shim/forge_prsync.py, docs/testing/jobs/gh-shim/gh, docs/testing/jobs/gh-shim/install.sh, docs/testing/jobs/gh-shim/route.sh, docs/testing/jobs/gh-shim/smoke_live.py, docs/testing/jobs/handback.sh, docs/testing/jobs/status.sh
Prediction: none: no arm. Harness infrastructure only (a local forge, a gh shim, job gates); no emulator pixels or speed.
Needs device: no    Needs NDK: no

Release note (none): test harness only. No emulator code changes.

## What this is

GitHub suspended the account on 09-29. Every `gh` call has returned 403
since, and most callers read that as "nothing to do". This PR, together with
host setup (listed in NOTES.md), stands up a local GitHub alternative:

1. **Forgejo 16.0.5** runs as `hakux-forge.service` on **127.0.0.1:3330
   only**. It has SQLite data in `~/hakux-work/forge/`, one user per actor
   (forgeadmin, lane.local, hostops, lanes, owner, jobs, ghimport), and
   tokens in `forge/tokens/`, mode 600.
2. **The repo**, `jreinach-alt/hakuX`, holds every branch of the bare repo.
   It is fed by `hakux-forge-sync.timer` (about 60 s lag). Origin stays the
   bare repo (option (b)), so no lane or foldqueue push changes.
3. **The gh shim** is `docs/testing/jobs/gh-shim/gh`.
   - It covers every gh operation the harness uses, against the forge's API,
     keyed on `GH_REPO`.
   - Every failure exits nonzero with one stderr line. Unknown operations
     and flags exit 64, `gh-shim: not implemented: <args>`.
   - Every call goes to `~/hakux-work/logs/forge/shim.log`.
4. **Issues #1-#640 keep their GitHub numbers.** `forge_import.py` seeds
   them from the board tracker today and takes lane.issuerecon's set when
   it is ready. The 13 unfolded lane branches with a PR.md are forge PRs
   #641-#653, kept equal to their PR.md by `hakux-forge-prsync`.
5. **Jobs:**
   - Under `HAKUX_FORGE=1`, board.sh is **dry-run**: it starts no session
     and no cloud claim, and logs what it would start. handback.sh and
     fold.sh are list-only. status.sh never pushes to github.com and keeps
     its forge issue state apart from GitHub's.
   - comment_sweep.sh keeps forge state and no longer POSTs to
     `issues/null`.
   - board.sh's gh reads log their failures.
   - `route.sh` routes units by drop-in. It refuses a unit until the code
     that unit runs carries its gate. Phase 1 (comments, issue-sweep,
     pr-sweep, arms) is routed. Phase 2 waits for this fold.
6. **Local CI** runs on `hakux-forge-runner.service`: host executor,
   capacity 1. `forge-selftest.yml` and `forge-android.yml` run on
   non-draft PRs only, which are the fold candidates.

## Local checks (no GitHub CI while offline)

- `python3 docs/testing/jobs/gh-shim/smoke_live.py` (live forge, scratch
  repo; the harness's own command lines and jq filters, plus every failure
  mode): **81 passed, 0 failed**.
- `python3 docs/lanes/localforge/import_smoke.py` (importer: numbering,
  idempotence, recon upgrade, no downgrade, job labels kept, forge-native
  issue untouched): **all passed**.
- `bash ~/hakux-work/host-tools/local_jobs_selftest.sh`: **14 checks passed**.
- `docs/testing/jobs/selftest.sh` (all shards) on the forge runner:
  forge-selftest run 17 on 5a798fda81. Result: pending, see below.
- Live: hakux-comments ran one routed tick against the forge, green.
