# localforge OUTBOX

## #433 -- 2026-10-02 10:10 PDT

[lane.localforge] Steps 1 and 2 of the local forge are up.

- **Forgejo 16.0.5 at http://127.0.0.1:3330/** (loopback only, no SSH, no registration, sign-in required).
  - Unit: `hakux-forge.service`. Data is in `~/hakux-work/forge/`.
  - Users: forgeadmin, lane.local, hostops, lanes, owner, jobs. Tokens and passwords are in `~/hakux-work/forge/tokens/` (mode 600).
  - The owner's web login is user `owner`, with the password in `tokens/owner.password`.
- **Repo `jreinach-alt/hakuX`** holds all 105 branches of the bare repo.
- **Recommendation: (b). The bare repo stays origin and the forge follows it.** `hakux-forge-sync.timer` pushes heads and tags into the forge about once a minute.
  - Nothing a lane or foldqueue does changes, so there is no cutover and no window to announce.
  - Forgejo's built-in pull mirror was not usable: a mirror cannot hold PRs.
  - Cost: up to about 60 s of lag.
  - The rule that follows: nobody pushes code to the forge and nobody merges a forge PR. Merges stay with foldqueue.
  - Moving to (a) later means repointing the 4 insteadOf entries. If you want that, give me a time.

## #433 -- 2026-10-02 10:50 PDT

[lane.localforge] Steps 3-6 of the local forge are in place: the gh shim, the issues, the PRs, the jobs and CI. **Two actions are lane.local's.**

**What is live now**
- **The gh shim** is at `~/hakux-work/forge/shim/bin/gh`.
  - It fails loudly: nonzero exit and one stderr line. Unknown operations exit 64.
  - Every call is logged to `~/hakux-work/logs/forge/shim.log`.
  - It covers every gh operation the harness scripts use, with their exact `--json`/`--jq` forms. A live smoke test passes 81 of 81 checks.
- **Issues #1-#640 keep their GitHub numbers.**
  - 165 are seeded from `origin/board:nv2a_issues.toml`. The other numbers up to #629 are closed "not recovered" placeholders. #630-#640 are reserved.
  - Forge-native issues and PRs start at #641.
  - When lane.issuerecon posts its import set ready, run:
    `python3 docs/lanes/localforge/forge_import.py --recon ~/hakux-work/forge-import --execute`
    It is idempotent, never downgrades recovered text, and never posts a comment twice.
- **PRs #641-#653:** one per unfolded `lane/*` branch that has a PR.md.
  - `hakux-forge-prsync.timer` keeps each one's title, body and draft state equal to the branch's PR.md, every 5 min.
  - It closes a PR once its branch is folded.
- **Local CI:** `hakux-forge-runner.service`, capacity 1.
  - `.forgejo/workflows/forge-selftest.yml` and `forge-android.yml` run only on non-draft (ready) PRs and on manual dispatch.
- **Phase 1 of the job routing is on:** hakux-comments, hakux-issue-sweep, hakux-pr-sweep and hakux-arms now use the forge. I ran hakux-comments once and it was green.

**For lane.local**
1. **After this PR folds:**
   - Fast-forward `~/hakuX`. The handback pacer runs that checkout's copy.
   - Then run `bash docs/testing/jobs/gh-shim/route.sh on phase2`. It refuses until both are done, and `route.sh status` says what is missing.
   - Phase 2 routes status, board, fold, foldpace and handbackpace. Under the forge:
     - board.sh is **dry-run** (`BOARD_DRY_RUN`): it logs what it would start and keeps the brief in `logs/board/dry-run/`.
     - handback.sh and fold.sh are list-only (`HANDBACK_DRY_RUN`, `FOLD_DRY_RUN`).
     - status.sh never pushes to github.com.
   - To enable one, set `<X>_DRY_RUN=0` in that unit's `zz-forge-shim.conf`.
2. **Lane sessions:**
   - They get the shim only if `lane.sh start/resume` passes `--setenv=PATH=$HOME/hakux-work/forge/shim/bin:...`. lane.sh is not in my territory.
   - Under the offline protocol they do not need it: PR.md stays the PR, and prsync publishes it.
   - I did not use the global alternative (`systemctl --user set-environment`): it would also route hakux-cloud, which claims work and starts sessions.
3. **Origin:** recommendation (b) stands, because nothing a lane or foldqueue does changes. No cutover time is needed.
