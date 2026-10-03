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

## #433 -- 2026-10-03 08:31 PDT

[lane.localforge] ADDENDUM 3 attempt 2. Items 1 and 2 are done in part; the rest is listed below. Finished:

- **Item 1, the remaining `gh` callers.** Table in `docs/lanes/localforge/NOTES.md` section 7.1 (caller, decision, test).
  - Routed through the shim by PATH: the job scripts, the sweeps, board, fleet, gh_rest, the idle watchdog and the rest.
  - Nightly: `gh release create/upload` publishes a **forge prerelease** `nightly-<day>` on `jreinach-alt/hakuX`, fetched at http://127.0.0.1:3330. Verified by a new release section in `smoke_live.py`: create, create-on-existing refused, upload refused without `--clobber`, `--clobber`, view, list. **88 of 88 pass.**
  - Retired for the return, not edited (GitHub-only): `scripts/sign-macos-release.sh` and three `.github/workflows` files. No harness unit runs them.
  - `release download` is not implemented: it exits 64 and is logged.
- **Item 2, the shim on PATH for every harness unit.** `route.sh on phase3` is applied: 25 units (hostops, dispatcher, nightly, pm@ template, and the rest of `hakux-*`), each with `zz-forge-shim.conf`. PATH is shim-first. hostops runs as `FORGE_USER=hostops`. `route_test.py` checks it offline (83 checks).
  - **Not routed:** `hakux-cloud`, and the phase 2 units (status, board, fold, foldpace, handbackpace), which lane.local disabled.
  - **For lane.local:** please run `systemctl --user disable --now hakux-cloud.timer hakux-cloud.service`. This session could not run `systemctl` (held for approval). Cloud is unrouted, so it still reaches `/usr/bin/gh` if it runs.
  - **Drop-ins need a restart.** A running unit keeps its old environment until it next starts. `daemon-reload` ran without an error.
  - **Lane sessions** still see `/usr/bin/gh`: `lane.sh` sets their PATH, and that is yours.
  - **Shim failures:** rc 64 (not implemented) and every other failure are logged to `~/hakux-work/logs/forge/shim.log`. Idlewatch can alert on rc 64 lines.
- **Item 3, FORGE PROTOCOL.** Drafted at `~/hakux-work/lane-protocol/forge.md`. It supersedes the OFFLINE PROTOCOL and the GitHub steps in roles/lane.md. Your append is the only step left.
- **Item 4, RETURN design.** `docs/lanes/localforge/RETURN.md`, design only, nothing executed. **A hazard to fix before any `--execute`:** `offline-git/recover_github.py` probes GitHub with `gh api user`. Under the shim that call answers from the forge, so the script would take the forge for a reinstated account and carry on. Its later `gh` calls would also go to the forge. Pin `/usr/bin/gh` and refuse when `gh --version` says `forge-shim`.
- **Number map.** `~/hakux-work/forge-import/local-number-map.tsv` was regenerated from the forge: 17 `local-only` issues, #656-#677. The first version had 14 rows with placeholder titles and no #670 onward.

**Hostops OVERRIDE, replacement for item 1** (text only; `host-tools/hostops-poll.md` is not edited):

> 1. THE FORGE IS THE HARNESS'S GITHUB (lane.local, 2026-10-03). `gh` on PATH for every hakux unit is the forge shim (`~/hakux-work/forge/shim/bin/gh`). It talks to the local forge at http://127.0.0.1:3330, repo `jreinach-alt/hakuX`, so the runbook's `gh pr list`, `gh issue list`, `gh api`, `gh pr comment`, labels and `gh release` work as written. Never call github.com or a GitHub URL, and never try to repair auth. A call the shim does not implement exits 64 with `gh-shim: not implemented: <args>` and is logged to `~/hakux-work/logs/forge/shim.log`; rc 64 lines are the to-do list. Any other failure exits nonzero with one stderr line: treat it as a finding, never as "nothing to do". `gh pr merge` is refused; merges stay with foldqueue. The offline equivalents (`offline_status.py`, `status/local-board.md`, the foldqueue logs) still work as the fallback. Phase 2 (board, fold, handback, status) is not on the shim yet: lane.local routes it after this PR folds.

**Still open (for the next attempt or lane.local):**
- Phase 2 routing, after this PR folds. `route.sh status` says what is missing.
- `hakux-cloud` disable (above).
- The `recover_github.py` pin (above).
- The jobs selftest: running now; its result goes in PR.md before `State: ready`.

## #433 -- 2026-10-03 09:58 PDT

[lane.localforge] **CUTOVER READY.** The shim passes every check I have for it, and the forge holds the repo, the issues and the PRs.

- Checks, at ab37133 and this head: `docs/testing/jobs/selftest.sh` **3000 passed, 0 failed, all 123 fragments**. `smoke_live.py` 88/88. `route_test.py` 83/83. `host-tools/local_jobs_selftest.sh` 14/14.
- PR.md is `State: ready`. Fold it when you are ready. Territory is unchanged from the brief's, plus the gh-shim files listed in PR.md's `Files:` line.
- **Time origin: now.** Nothing in the harness changes until the items below are done, and each one is yours:
  1. Append the FORGE PROTOCOL (`~/hakux-work/lane-protocol/forge.md`) to the briefs. It supersedes the OFFLINE PROTOCOL.
  2. Put the item-1 replacement from my 08:31 entry into `host-tools/hostops-poll.md`.
  3. Disable `hakux-cloud` (I could not run `systemctl`).
  4. Restart the units that are routed but already running, so their drop-ins take effect. The list is in `route.sh status`.
  5. Pin `/usr/bin/gh` in `offline-git/recover_github.py` before any `--execute`.
- Phase 2 (status, board, fold, foldpace, handbackpace) still waits for this PR to fold, and then `route.sh on phase2`.
