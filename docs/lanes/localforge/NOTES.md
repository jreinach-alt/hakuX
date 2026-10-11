# localforge: a local Forgejo stands in for GitHub

Lane: localforge. Issue: #433. Brief: `~/hakux-work/briefs/localforge.md` (owner 2026-10-02).

## 1. The forge (step 1, done 2026-10-02 ~10:00 PDT)

| what | where |
|---|---|
| binary | `~/hakux-work/forge/bin/forgejo` -> `forgejo-16.0.5-linux-amd64` (sha256 and the Forgejo release key EB11 4F5E ... C592 3710 both verified) |
| config | `~/hakux-work/forge/custom/conf/app.ini` (mode 600, holds secrets) |
| data | `~/hakux-work/forge/data/` (SQLite `forgejo.db`, repos under `data/repos/`) |
| log | `~/hakux-work/forge/log/` |
| listen | **http://127.0.0.1:3330/** only (`HTTP_ADDR = 127.0.0.1`); no SSH server; registration off; sign-in required to view anything |
| unit | `~/.config/systemd/user/hakux-forge.service` (enabled, `Restart=on-failure`, `Nice=5`) |
| setup scripts | `~/hakux-work/forge/setup/*.py` (idempotent; print no secrets) |

Users: `forgeadmin` (site admin), `lane.local`, `hostops`, `lanes` (every lane
session), `owner`, and `jobs` (the systemd job scripts: board, status, fold,
arms, handback, the sweeps; the harness signs their comments `[job.<name>]`,
a distinct actor from the four in the brief). Org `jreinach-alt` owns the
repo, so the harness's default `GH_REPO=jreinach-alt/hakuX` resolves
unchanged. All five non-admin users are in team `actors` (write on every
repo).

Secrets: `~/hakux-work/forge/tokens/<user>.token` and `<user>.password`,
directory 700, files 600. Never committed, never printed.

WSL note: WSL2's localhost forwarding makes 127.0.0.1:3330 reachable from
the Windows host's own loopback too. It is not on the LAN: Windows forwards
loopback to loopback only.

## 2. The repo (step 2, done 2026-10-02 ~10:05 PDT): option (b), the bare repo stays origin

`jreinach-alt/hakuX` in the forge holds all 105 branches of
`~/hakux-work/offline-git/hakuX.git` (board, master, 75 `lane/*`, ...),
copied by `~/hakux-work/forge/bin/forge-sync.sh`, which
`hakux-forge-sync.timer` runs 60 s after the previous run finishes. The
script pushes `+refs/heads/*` and `+refs/tags/*` with `--prune` from the bare
repo into the forge as `forgeadmin`, logs every changed ref to
`~/hakux-work/logs/forge/sync.log`, and exits 1 with a stderr line when the
push fails.

**Why (b) and not (a):**
- (b) changes nothing a running lane or foldqueue touches. No insteadOf
  entry moves, no remote URL changes, no push can break mid-flight. (a)
  needs a cutover window and a changed failure mode for every lane at once:
  a forge restart would then refuse lane pushes.
- `offline_fold.py`, `foldqueue.sh`, `recover_github.py` and the GitHub
  baseline all read the bare repo by path. Under (a) every one of them would
  have to move or read a forge-owned repo dir.
- It is not Forgejo's built-in *pull mirror*: a mirror repo is read-only
  and cannot hold pull requests, and step 4 needs PRs. The forge repo is a
  normal repo that only the sync writes.
- Cost: up to ~60 s of lag between a lane's push and the forge seeing it.
  Nothing in the harness needs it faster. A `post-receive` hook in the bare
  repo calling `forge-sync.sh` would make it immediate. I left the bare
  repo's hooks alone, because the bare repo is lane.local's.
- Moving to (a) later is one step: point the insteadOf entries at
  `http://127.0.0.1:3330/jreinach-alt/hakuX.git` and stop the timer.

Rule that follows from (b): **nobody pushes code to the forge and nobody
merges a forge PR.** The next sync would overwrite a forge-only commit.
Merges stay with `foldqueue.sh`.

## 3. The gh shim (step 3)

`docs/testing/jobs/gh-shim/gh` (python3, one file). It is installed by
`docs/testing/jobs/gh-shim/install.sh` to `~/hakux-work/forge/shim/bin/gh`,
an atomic copy. Its header lists the rules. In short:

- **Loud failures.** Every failure exits nonzero and prints one stderr line
  naming the operation (HTTP status, forge unreachable, missing token, bad
  jq). Unknown operations and unknown flags exit 64 with `gh-shim: not
  implemented: <args>`. `pr merge` exits 2 and says merges go through
  foldqueue.
- **Logging.** Every call appends one JSON line to
  `~/hakux-work/logs/forge/shim.log`: argv, rc, ms, forge user, calling
  systemd unit, cwd and the error. `rc == 64` lines are the to-do list.
- **Repo.** `--repo` > `$GH_REPO` > `jreinach-alt/hakuX`.
- **Account.** `$FORGE_USER` > `$HAKUX_ROLE` (lane/cloud -> `lanes`) > `jobs`.
- **What it implements.** Every operation the inventory found in harness code:
  - `pr list/view/comment/create/ready/checks/diff/review/edit/close/reopen`
  - `issue list/view/create/comment/edit/close/reopen/pin/unpin`
  - `label create/list/delete`
  - `release list/view/create/upload`
  - `run list`
  - `auth status`
  - `api`: REST with `-f/-F` (including `@file`, `k[]=`, `k[sub]=`),
    `--input`, `-X`, `--paginate`, `--jq` and `--silent`.
- **Differences from GitHub that it hides:**
  - **`per_page`.** Forgejo pages by `limit`, so `per_page` is translated.
    Without that, gh_rest.py's "page < 100 rows means last page" would have
    stopped after 30 rows. That is the silent-truncation version of the bug.
  - **Timestamps.** Forgejo's are local time. They are normalised to
    GitHub's `...Z`; jq's `fromdateiso8601` needs that exact form.
  - **`mergeable`.** Forgejo reports `false` for every WIP (draft) PR. The
    shim computes MERGEABLE/CONFLICTING itself with `git merge-tree
    --write-tree` against the forge repo dir. New objects go to a scratch
    dir, and results are cached per (base, head) in
    `~/hakux-work/forge/cache/`.
  - **`statusCheckRollup`.** Built from Forgejo commit statuses as
    StatusContext objects. `commits/<sha>/check-runs` is synthesised from
    the same statuses, so fold.sh's TRUNK_CI_JQ works.
  - **Issue events.** `issues/<n>/events` is synthesised from the timeline
    (labeled/unlabeled/closed/...).
  - **Repo-wide comments.** `issues/comments` honours `sort`/`direction`,
    which Forgejo ignores. PR comments get the `issue_url` Forgejo leaves
    empty, and `/pulls/N#` html links become `/issues/N#`, so status.sh's
    `(issues|pull)` regex still matches.
  - **Labels.** Labels are addressed by name. An unknown label is created on
    first use, as GitHub does. Forgejo silently drops an unknown label name;
    measured in the importer test.
  - **Drafts.** A draft is the `WIP: ` title prefix, stripped on output.

Tests:
- `python3 docs/testing/jobs/gh-shim/smoke_live.py` runs against the live
  forge on a throwaway repo, `jreinach-alt/shim-smoke`. It runs the
  harness's own command lines with the exact `--json` lists and `--jq`
  filters from board, status, fold, handback, arms, pr-sweep, issue-sweep,
  comment_sweep, gh-label.sh and gh_rest.py, plus the failure modes.
  **80 passed, 0 failed.**
- Labels: `ensure-labels.sh`, run through the shim, created its 16 labels in
  `jreinach-alt/hakuX`. Others (`lane:<x>`, `0.5`, `release-blocker`, ...)
  are created on first use.

## 4. Issues and PRs (step 4)

**Issues.** `docs/lanes/localforge/forge_import.py` (dry run unless
`--execute`):
- It walks #1..#640 in order, so every forge number is GitHub's.
- A number with a lane.issuerecon record gets its title, body, state,
  labels and comments, each comment with an author/time header.
- A number with only a board row (`origin/board:nv2a_issues.toml`) is
  seeded from that row: its title, plus a rendering of status,
  disposition, blocker and notes. State is open unless the row's status is
  `closed` or `closed-duplicate`.
- Any other number up to #629 (the highest GitHub number git history names:
  hddcrash's PR) becomes a closed "#n: not recovered" placeholder.
- #630..#640 are closed "reserved" placeholders, so forge-native numbers
  start at #641 and cannot collide with a GitHub number found late.
- It is idempotent and keyed on a body marker. It never touches an
  unmarked (forge-native) issue. It keeps labels a job added. It never
  downgrades recovered text to the seed. It never posts a comment twice
  (`github-comment:<id>` marker).
- Test: `docs/lanes/localforge/import_smoke.py`, all passed.

**Run 2026-10-02 ~10:50 PDT:** 640 created. 165 were seeded from the board;
6 non-numeric board rows (apu-*, aci-vmstate) have no GitHub number and were
not imported. 139 are open. Verified with `gh issue view 433` through the
shim.

**When issuerecon posts its import set ready:**
`python3 docs/lanes/localforge/forge_import.py --recon ~/hakux-work/forge-import --execute`.
Recovered PRs become issues titled `[GitHub PR] ...`, labelled `github-pr`,
at their own numbers.

**PRs.** `docs/testing/jobs/gh-shim/forge_prsync.py`, installed to
`~/hakux-work/forge/bin/`, run by `hakux-forge-prsync.timer` (5 min, after
a sync):
- One forge PR per `lane/<x>` branch that has `docs/lanes/<x>/PR.md` and
  commits master lacks. PR.md's line 1 is the title, `State: draft` makes it
  a WIP draft, and the whole PR.md is the body. It is opened as the `lanes`
  user.
- It updates the PR when PR.md changes. It closes the PR with a
  `[job.forge-prsync]` comment once the branch is in master.
- First run: 13 PRs, #641..#653.

## 5. The jobs (step 5): routed in two phases

**What would have happened.** I had the side effects audited before routing
anything. Once `gh` answers again, with today's forge content:
- **board.sh** would start a model session (the 5-6 ready PRs carry no state
  label) and run cloud.sh every tick.
- **handback.sh** (fold's tail, and the 10-minute pacer) would `lane.sh
  resume` drafts whose CI reads NONE. That races lanewatch_offline.
- **fold.sh** would merge anything labelled `fold-ready`.
- **status.sh** would force-push Pages to **github.com**. Its remote is
  `https://github.com/...` whenever `gh auth status` succeeds, and the
  insteadOf rewrite covers only `~/hakuX`.

**So, in the jobs (this PR):**
- `HAKUX_FORGE=1` is set by the drop-in.
- **board.sh:**
  - `BOARD_DRY_RUN` defaults to `HAKUX_FORGE`. When it is 1 the tick
    computes its triggers and writes the brief, but it starts no session
    and runs no `cloud.sh` (it logs `cloud.sh list` instead). It keeps the
    brief under `logs/board/dry-run/` and marks nothing read.
  - lane.local turns it on by setting `BOARD_DRY_RUN=0` in the board
    drop-in.
  - The two positive-gate reads now *say* a gh failure in the tick log
    (`gh_or_say`) and still read it as empty. The 403s since 09-29 printed
    exactly what "nothing actionable" prints.
- **handback.sh:** `HANDBACK_DRY_RUN` defaults to `HAKUX_FORGE`. A `run`
  becomes a `list`.
- **fold.sh:** `FOLD_DRY_RUN` defaults to `HAKUX_FORGE`. A `run` becomes a
  `list`. Merges stay with foldqueue.
- **status.sh:**
  - It never defaults its Pages remote to github.com under the forge.
  - Its issue pointer and comment id move to `$S/forge/`. The forge gets its
    own live-status issue, created once with the `harness-status` label. The
    GitHub #107 bookkeeping stays untouched for GitHub's return.
  - The comment link uses `HAKUX_WEB_URL`.
- **comment_sweep.sh:**
  - Its watermark and comment id get `forge-` files.
  - It treats jq's literal `null` as "no status issue". On the first forge
    sweep it POSTed to `issues/null`; the shim refused loudly with a 404.
    The same latent bug existed on GitHub.

**Routing is a drop-in per unit, written by `docs/testing/jobs/gh-shim/route.sh`:**
- The file is `~/.config/systemd/user/<unit>.service.d/zz-forge-shim.conf`.
- It sets PATH with the shim first, `HAKUX_FORGE=1`, `HAKUX_WEB_URL` and
  `FORGE_USER=jobs`.
- `route.sh status` shows every unit.
- `route.sh on/off <unit|phase1|phase2>` changes them.
- **`on` refuses a unit until the copy of the code it will run carries its
  gate.** It checks the bare repo's master for run-trunk jobs and board's
  re-exec, and `~/hakuX` for the handback pacer.

| phase | units | state (2026-10-02 ~10:40 PDT) |
|---|---|---|
| 1 | hakux-comments, hakux-issue-sweep, hakux-pr-sweep, hakux-arms | **routed**. Their master code only reads or posts comments. Measured: hakux-comments ran green against the forge; every call is in shim.log. |
| 2 | hakux-status, hakux-board, hakux-fold, hakux-foldpace, hakux-handbackpace | **waiting for this PR's fold** (route.sh refuses until then). The handback pacer also needs `~/hakuX` fast-forwarded. Then: `bash docs/testing/jobs/gh-shim/route.sh on phase2`. |
| never | hakux-cloud, hakux-hostops | not routed: they start model sessions. board.sh's dry run already stops its board-tick call to cloud.sh. |

**Lane sessions** get the shim only by an edit outside my territory:
- `lane.sh start/resume` would pass `--setenv=PATH=<shim>:...`.
- The alternative, `systemctl --user set-environment`, would also route
  cloud and every unrouted job at once, so I did not use it.
- Under the offline protocol lanes do not need gh. PR.md is their PR and
  prsync publishes it.
- This is listed for lane.local in OUTBOX.

## 6. Local CI (step 6)

- **Runner:** `forgejo-runner` 13.2.0 (sha256 and signature verified) as
  `hakux-forge-runner.service`.
  - Host executor, label `host`, **capacity 1**.
  - `Nice=15`, idle IO, `MemoryMax=8G`.
  - Its cache server is disabled; it would bind a port on the host's LAN
    address.
  - Registered on `jreinach-alt/hakuX` as `hakux-host`. Config and state are
    in `~/hakux-work/forge/runner/`.
- **Workflows:** `.forgejo/workflows/forge-selftest.yml` (the jobs selftest,
  all shards in one job, 120 min) and `forge-android.yml` (unit tests plus
  assembleDebug with the host's JDK 21 and SDK).
  - They run on `pull_request` (opened/synchronize/reopened/edited) and
    `workflow_dispatch`, and **skip WIP (draft) PRs**. CI therefore runs
    only on fold candidates, whose PR.md says ready. An `edited` event
    fires when prsync drops the WIP prefix.
  - No `uses:` actions. The checkout is a `--shared` clone of the bare
    repo.
- **Forgejo falls back to `.github/workflows/`** on any branch without
  `.forgejo/workflows/`, which today is every branch but this one. Those
  runs ask for `ubuntu-latest`, which no runner serves, so they sit PENDING
  for ever. Measured: #650 showed 4 PENDING `jobs selftest` checks. A
  cancelled run turns its commit status into FAILURE, and deleting the run
  leaves the status behind (measured on #641).
  - So the shim counts **only contexts starting `forge `** (workflows
    `forge-*.yml`) in `statusCheckRollup`, `check-runs` and `run list`. The
    knobs are `FORGE_CI_CONTEXT_RE` and `FORGE_CI_WORKFLOW_RE`.
  - The junk runs stay queued and harmless. They disappear as branches
    merge master and gain `.forgejo/`.
- First dispatch: run 10, `jobs-selftest` (pre-rename name) on
  `lane/localforge` @ 463dd6b0ea, via `workflow_dispatch`.

## 7. Attempt 2 (2026-10-03): why attempt 1 did not finish, and the cutover

**Why attempt 1 did not finish.** Attempt 1 built steps 1-6 and routed phase
1 (the four comment/PR/arms units). It was paused at 11:58 on 10-02 for token
burn, with phase 2 and the whole cutover still open (lane.local's ADDENDUM 3).
Nothing was lost, but while it was paused the GitHub-bound jobs still ran
against nothing, which is why lane.local disabled them. Attempt 2 starts from
that state. The branch was 133 commits behind master; it was merged with
`git merge origin/master` (not rebased, because prediction refs are not
involved here, but a merge keeps the PR's history stable).

**Scope of this attempt (ADDENDUM 3).** Every remaining `gh` caller on master
works locally or is retired with its replacement named; the shim is on PATH for
every harness unit; the FORGE PROTOCOL is drafted; RETURN.md is the design for
the return to GitHub. Each finished item gets an OUTBOX entry.

### 7.1 Caller table (master code; prose in notes, audits and fixtures excluded)

Grep: `git grep -n -E '(^|[[:space:]|(;&`$]|timeout [0-9]+ )gh (api|pr|issue|run|label|release|auth)( |$)'`
over `docs/testing`, `scripts`, `.github/workflows`, `host-tools` and `AGENTS.md`,
with comment-only lines dropped. Table filled in as each item is tested.

| caller (master) | gh operations | decision | test |
|---|---|---|---|
| `docs/testing/jobs/{board,status,fold,handback,arms,pr-sweep,issue-sweep,cloud,gh-label,ensure-labels,board-status,deliver,status_html}.{sh,py}`, `selftest.d/*` | pr list/view/comment/create/checks/edit, issue list/create/comment/view, api, label, run list | **shim, by drop-in**. Phase 1 (comments, issue-sweep, pr-sweep, arms) routed. Phase 2 (status, board, fold, foldpace, handbackpace) unrouted: disabled by lane.local, and route.sh refuses until this PR folds. `hakux-cloud` unrouted, see 7.2 | `smoke_live.py` (every op form, 88 checks); `local_jobs_selftest.sh` 14 |
| `docs/testing/comment_sweep.sh` | api `issues/comments`, issue list `--label harness-status`, api PATCH/POST | **forge** (phase 1; its watermark and comment id are `forge-*`) | smoke: comment_sweep jq (A)-(D) |
| `docs/testing/nightly_build.sh:323` | api `pulls/N` (PR body for `Release note:`) | **shim** via `hakux-nightly` (phase 3). Reads the forge PR body, which is PR.md | smoke: api `pulls/N --jq .body` form |
| `docs/testing/nightly_build.sh:481/486` | `release create --prerelease --notes-file`, fallback `release upload --clobber` | **forge prerelease** `nightly-<day>` on `jreinach-alt/hakuX`, fetched from http://127.0.0.1:3330. Publishing needs the shim on PATH (`hakux-nightly`) | **smoke: release section** (create, create-on-existing refused, upload refused without `--clobber`, upload `--clobber`, view, list). Found and fixed: none needed, the shim already had these; the smoke test did not cover them before |
| `docs/testing/request.sh:788` | api `issues/N --jq .labels[].name` (release priority) | **shim** via the caller's PATH. Not a unit. Without the shim, the read fails and the script warns "could not read #N's labels; queueing at normal priority" (its existing fallback, now loud) | smoke: api labels form |
| `docs/testing/gh_rest.py`, `fleet.py`, `check_coverage.py`, `backlog-gate.sh`, `ab_run.sh`, `pr_comment.sh`, `watch_remote_lane.sh`, `idle-watchdog.sh` | pr list, api, issue list | **shim** via the caller's PATH (the owning unit under 7.2, or the session's env) | smoke: pr list, issue list and api forms |
| `scripts/sign-macos-release.sh`, `.github/workflows/{bump-subproject-wraps,delete-prerelease,update-ppa}.yml` | release download/view/delete/upload, pr create | **retired for the return.** GitHub-only: a macOS signing script and GitHub Actions. No harness unit runs them. Not edited (outside territory). Forgejo would queue a `.github/workflows` run on a branch with no `.forgejo/`, as a pending job (section 6) | none (no caller). `release download` exits 64 in the shim, loud and logged |
| `docs/testing/jobs/roles/{lane,cloud,board}.md`, `AGENTS.md` (lines 44, 459) | prose and examples | **superseded** by FORGE PROTOCOL (`~/hakux-work/lane-protocol/forge.md`), which lane.local appends. Not edited (roles/ is outside territory) | n/a |
| `gh release download` (`update-ppa`, macOS signing) and `gh repo`, `gh workflow` | — | not implemented: exit 64 and logged. Nothing harness-side calls them | smoke: `release download` 64 |

Territory: the caller changes above that fall outside the brief's territory are **none**. The
only harness-code edits in this attempt are in `docs/testing/jobs/gh-shim/**` (route.sh,
smoke_live.py, route_test.py) and `docs/lanes/localforge/**`. `route.sh` routes units that the
brief did not name; that is the addendum 3 scope, flagged in OUTBOX.

### 7.2 Routing: which units see the shim

`route.sh` now has three phases. Phase 3 is new (ADDENDUM 3, "the shim on PATH for every harness unit").

| phase | units | state (2026-10-03) |
|---|---|---|
| 1 | comments, issue-sweep, pr-sweep, arms | ROUTED (10-02). Comments, issue-sweep and pr-sweep are disabled (addendum 1 and 3); arms runs |
| 2 | status, board, fold, foldpace, handbackpace | **not routed.** Disabled by lane.local (addendum 3). `route.sh` refuses until this PR folds (`master` must carry the gate) |
| 3 | hostops, dx, dispatcher, desktop, jamcheck, manifest, recover, holdlease, devwatch, defrag, usbdialog, tmpclean, foldqueue, lanewatch, lanewaker, autoverdict, local-board, local-issue-audit, hourly, pm@ (template), nightly, thor-suites, ops-shadow, usage-meter, idlewatch | **ROUTED** 2026-10-03: `zz-forge-shim.conf` in each `~/.config/systemd/user/<unit>.service.d/` (`hakux-pm@.service.d` for the template). Each sets `PATH` (shim first) and `FORGE_USER` (`hostops` for hostops, `jobs` otherwise). **No** `HAKUX_FORGE`: that is phase 2's dry-run switch, and these units do not use it |
| never | `hakux-cloud` | **not routed, disable requested.** A claim starts a cloud session; the owner did not ask for cloud sessions on the forge. Disable: `systemctl --user disable --now hakux-cloud.timer hakux-cloud.service` (lane.local's call; this session could not run `systemctl`, see 7.4) |
| never | `hakux-forge`, `hakux-forge-sync`, `hakux-forge-prsync`, `hakux-forge-runner` | the forge's own units; they are not clients |

The drop-ins take effect when a unit next starts. Running units keep their environment until then.
`route_test.py` checks the phase 3 drop-ins offline (83 checks, against a temporary units directory).

Not done here: the phase 2 units and `hakux-cloud` (above). Lane sessions (`hakux-lane-*`) are not
units in this table; their PATH is set by `lane.sh`, which is lane.local's, and so they still
see `/usr/bin/gh` until it changes.

### 7.3 Protocol and return

- **FORGE PROTOCOL:** `~/hakux-work/lane-protocol/forge.md` (new directory; lane.local appends it to briefs).
- **Return design:** `docs/lanes/localforge/RETURN.md`. Design only. It records a hazard in `offline-git/recover_github.py`: its GitHub probe (`gh api user`) answers from the forge under the shim, so the script would mistake the forge for a reinstated account. Fix before the first `--execute`.
- **Number map:** `~/hakux-work/forge-import/local-number-map.tsv` regenerated from the forge: 17 `local-only` issues (#656-#677). The first seed had 14 rows with placeholder titles.

### 7.4 What could not be done from this session

- `systemctl --user list-units`, `list-unit-files` and `is-enabled` were held for approval in this sandbox, so I read the unit files from disk instead. I did not attempt `disable`, so hakux-cloud is not disabled from here. The phase 3 drop-ins are on disk; `route.sh` ran `daemon-reload` with no error printed, but a running unit does not pick up a drop-in until it restarts. Both are for lane.local.
- The jobs selftest (`docs/testing/jobs/selftest.sh`) runs detached; its result is recorded in PR.md.

## 8. Attempt 3 (2026-10-03, resumed from the brief's addenda 4-7)

**Why attempt 2 did not finish.** Attempt 2 posted CUTOVER READY at 09:58 PDT and
marked the PR ready. The brief had gained addenda 4-7 between 09:00 and 09:55, and
attempt 2's entries never mention them. It worked from the brief as it stood at
08:31, and did not re-read the addenda before it declared the cutover done. So four
things the addenda asked for were not in its finished work:

1. **The addendum 7 bypass list.** Its caller table (7.1) covered the grep scope it
   had chosen, not the named files, and it missed `status.sh`'s default link base,
   which fell back to `https://github.com` whenever `HAKUX_WEB_URL` was unset.
2. **The AGENTS.md and docs/testing rewrite** (addendum 5). Attempt 2 wrote
   "not edited" for `AGENTS.md` and the roles docs, and did not touch the
   `docs/testing/*.md` prose.
3. **The lane-side checks** (addenda 4-5): whether `Bash(gh:*)` reaches the forge
   from a lane session, and whether `harness_health.py`'s calls go through the shim.
4. **The return gate for `.github/workflows/`** (addendum 6): nothing recorded what
   must be true before the first push to GitHub.

Attempt 3 does those four, plus the addendum 7 table below. Nothing from attempt 2
was lost: the merge with `origin/master` (21 commits, now `2fb6087a09`) is clean.

**Changes in this attempt**

| file | change | why |
|---|---|---|
| `docs/testing/jobs/status.sh` | the link base is `$WEB_DEFAULT`: the forge while `HAKUX_FORGE=1`, else github.com; `HAKUX_WEB_URL` still wins | the one bypass in the addendum 7 list (the others are in the table below) |
| `AGENTS.md` | new "The forge" section; the intro's CI sentence; the start-here comment; the public-facing list; the CI non-negotiable (rewritten, the `[skip ci]` rule is gone); two conventions lines | addendum 5 |
| `docs/testing/systemd/README.md` | `gh` on the units' PATH is the shim, with the `jobs` token | addendum 5 |
| `docs/testing/desktop-gate-warnings.md` | CI is the forge's and runs on ready PRs only | addendum 5 |
| `docs/lanes/localforge/RETURN.md` | section 2a: the CI gate for the return (no workflow may start itself) | addendum 6 |

**Addendum 7 table.** Every file the addendum names, and every other path the scan of
`docs/testing`, `scripts`, `host-tools`, `.github` and `AGENTS.md` found that reaches
GitHub. "shim" means the file calls `gh` by name, so it reaches the forge when the
caller's PATH has the shim first. The smoke columns name the test that covers the form.

| path | GitHub reach (measured) | decision | test |
|---|---|---|---|
| `docs/testing/gh_rest.py` | `gh api` REST calls, 13 mentions | **shim** by PATH | `smoke_live.py` api and pr list forms |
| `docs/testing/jobs/status_html.py` | 2 `gh` calls; links use the `html_url` the gh JSON carries; prose says "GitHub" | **shim** by PATH; the shim returns the forge's `html_url`, so the links are the forge's. Prose left for the return | selftest 64-status-html |
| `docs/testing/check_coverage.py` | `gh issue list` (REST, comment only) | **shim** by PATH | smoke issue list form |
| `docs/testing/fleet.py` | `gh pr list`, `gh api` | **shim** by PATH; no hard-coded host | selftest 96-fleet-registry |
| `docs/testing/jobs/gh-label.sh` | `gh api -X POST/DELETE repos/.../labels` | **shim** by PATH | smoke api labels form |
| `docs/testing/jobs/ensure-labels.sh` | `gh label create --force` (16 labels) | **shim** by PATH; ran through the shim in attempt 1 | smoke label create |
| `docs/testing/jobs/cloud.sh` | 18 gh calls (claims, comments, labels, `pr diff`) | **shim** by PATH. `hakux-cloud` stays off and unrouted; it claims work and starts sessions | selftest 72-cloud-tail (fixture) |
| `docs/testing/jobs/deliver.sh` | `gh auth status`, `gh api` POST and `--paginate` | **shim** by PATH. Lane messages are forge comments; the fallback in addendum 3 is not needed | selftest 66-deliveries |
| `docs/testing/jobs/selftest.d/66-deliveries.sh` | github.com URLs in fixture bodies | **fixture only** | n/a |
| `docs/testing/jobs/selftest.d/98-coverage-rest.sh` | `api.github.com` and the GraphQL 403 text, in fixture | **fixture only** (the 403 is the case the fixture reproduces) | n/a |
| `docs/testing/jobs/selftest.d/99-handback-draft.sh` | `gh pr <verb>` text grep | **fixture only** | n/a |
| `docs/testing/jobs/selftest.d/72-cloud-tail.sh` | a fake `gh` that logs its argv | **fixture only** | n/a |
| `docs/testing/jobs/roles/{board,lane,cloud}.md` | gh command lines, unchanged, and GitHub-era prose | **shim** (the command lines run unchanged on the forge). The prose is superseded by the FORGE PROTOCOL that lane.local appends; the files are outside this lane's territory and were not edited | n/a |
| `docs/testing/pgraph-harness.md` | 7 github.com links to upstream repos (`abaire/*`) | **upstream, kept**: those repos live on GitHub, and the harness does not reach them through this file | n/a |
| `docs/testing/desktop-runs.md` | link to `.github/workflows/desktop.yml` | **kept**: it names a file; the workflow is retired for the return (below) | n/a |
| `docs/testing/jobs/harness_health.py` | not in the repo: `~/hakux-work/host-tools/harness_health.py`, `gh` by name (`sh('gh %s')`) | **shim** by PATH, on the hourly unit (phase 3). Two checks read the forge as GitHub: see NEW ISSUE in OUTBOX | n/a in repo |
| `docs/testing/jobs/allowed-tools.lane` | `Bash(gh:*)` and `WebFetch` | `Bash(gh:*)` **reaches the forge**: `~/.config/environment.d/50-hakux-forge.conf` puts the shim first on the user manager's PATH, which transient units inherit. Not verified by a launch (`systemd-run` was held for approval). `WebFetch` is not gated by PATH and still reaches the internet: lane.local's call, flagged in OUTBOX. The file is not edited | n/a |
| `AGENTS.md` | 18 hits, 2 `gh` lines | **rewritten** (see the changes table) | n/a |
| `scripts/bump-subproject-wraps.py` | `api.github.com` for upstream tags (SDL and others) | **retired for the return**: only `bump-subproject-wraps.yml` calls it, and that workflow is retired. Run by hand, it still reaches github.com | none (no unit calls it) |
| `scripts/sign-macos-release.sh`, `.github/workflows/{bump-subproject-wraps,delete-prerelease,update-ppa}.yml` | `gh release`, `gh pr create` | **retired for the return** (section 7.1) | none |
| `.github/workflows/*.yml` (five files with `push` or `pull_request` triggers: android, desktop, nv2a-index, jobs-selftest, build-xemu-win64-toolchain) | would start CI on a push to GitHub | **gate for the return** (RETURN.md 2a). Not edited: master is outside this lane's territory | the grep in RETURN.md 2a prints five files today |

**What was checked and not changed.** The `gh` operations the scripts use are
implemented by the shim, with one exception found by this scan: `gh issue lock`
(`status.sh:660`, the Pages move) is **not** implemented, so it exits 64 and is
logged. The caller discards its output, so the failure is silent in the job's own
log. It runs only when the roll-up moves to Pages, which the forge never does, so it
is a finding and not a live fault: see NEW ISSUE in OUTBOX. The operations the shim
does not implement are `issue lock`/`unlock`, `release download` and `release
delete`, `workflow run`, `repo` and `workflow` browsing. The callers of the release
ones are in the retired files above.

## 9. Attempt 4 (2026-10-03, resumed for addendum 8)

**Why attempt 3 did not finish.** It did finish the brief as it stood: PR.md ready, checks
recorded, OUTBOX entries posted, ending about 10:30 PDT. Addendum 8 was written at 11:00,
after that session ended. It answered attempt 3's open decisions and granted the five
`.github/workflows` files, so this attempt exists to do that edit. One item from addendum 5
was also missed by attempt 3 and is done here: lane.xbox's two scripts through the shim.

**Changes**

| file | change | test |
|---|---|---|
| `.github/workflows/{android,desktop,nv2a-index,jobs-selftest,build-xemu-win64-toolchain}.yml` | `on:` is `workflow_dispatch` only. android.yml keeps the `hakux-ci-throttle` comment (`recover_github.py` `THROTTLE_MARKER` is a substring check) | RETURN.md 2a check: prints nothing at this head, prints these five on origin/master. `selftest.sh --check-shards 4` passes (it reads jobs-selftest.yml's matrix, which is unchanged) |
| `docs/lanes/localforge/RETURN.md` | 2a's check parses each workflow's `on:` key instead of grepping | see below |
| `docs/testing/jobs/gh-shim/gh` | `pr list --search` takes qualifiers only: `head:`, `base:`, `author:`, `label:`, `is:open/closed/merged/draft`. Free text still exits 64; a qualifier that contradicts a flag exits 2 | `smoke_live.py` 92/92 (3 new search checks, 1 new `issue comment` check) |

**The 2a grep was wrong.** It printed `build-xemu-win64-toolchain.yml` after the edit, because
line 58 has `push: ${{ ... }}`, an input of a docker step under `with:`, not a trigger. The new
check reads the YAML `on:` key (and `True`, which is how YAML reads a bare `on:`), and lists
any key other than `workflow_dispatch` or `workflow_call`. The other 13 workflows were already
`workflow_dispatch` or `workflow_call`.

**lane.xbox through the shim (addendum 5).** Both scripts live in `~/hakux-work/hardware/`,
not in the repo.

| call | through the shim, before | after |
|---|---|---|
| `xbox_check.sh:26` `gh pr list --search 'head:lane/xbox' --json number --jq` | **exit 64**, and the script discards stderr, so it read "no open PR" every run: the silent-empty pattern | rc 0; empty today, which is correct (no `lane/xbox` branch exists on origin) |
| `xbox_check.sh:27` `gh api -X GET repos/.../issues/comments -f since= -f per_page=100 --paginate` | rc 0 | unchanged |
| `title_push_xbox.sh:433` `gh issue comment N --body` (no `--repo`; default repo) | implemented, not in the smoke test | smoke check added, passes |

The installed shim (`~/hakux-work/forge/shim/bin/gh`) was byte-identical to the committed one
before `install.sh` replaced it with this version.

**Addendum 8's other items**, recorded as lane.local reported them (not re-checked here
except where noted): WebFetch to GitHub hosts is denied host-wide in `~/.claude/settings.json`;
hakux-cloud is disabled; `recover_github.py` is pinned to `/usr/bin/gh` and refuses a
forge-shim `--version`; harness_health.py is retired from hostops; lane sessions get the shim
(`systemd-run ... command -v gh`). This session's own `gh --version` prints the shim.

**Not changed (outside territory):** `docs/testing/jobs/selftest.sh:14,47` still say the
selftest "is in CI (.github/workflows/jobs-selftest.yml)", and `fold.sh:898,1034` and
`ROADMAP.md:89-94` describe the old triggers. They are prose; nothing reads them.

## Host files this lane added (outside the repo)

| path | what |
|---|---|
| `~/.config/systemd/user/hakux-forge.service` | Forgejo web (enabled) |
| `~/.config/systemd/user/hakux-forge-sync.{service,timer}` | bare repo -> forge, every ~60 s |
| `~/.config/systemd/user/hakux-forge-prsync.{service,timer}` | PR.md -> forge PR, every 5 min |
| `~/.config/systemd/user/hakux-forge-runner.service` | Actions runner (enabled) |
| `~/.config/systemd/user/hakux-{comments,issue-sweep,pr-sweep,arms}.service.d/zz-forge-shim.conf` | phase-1 routing (route.sh) |
| `~/hakux-work/forge/` | binaries, `custom/conf/app.ini`, `data/`, `log/`, `tokens/` (600), `runner/`, `shim/bin/gh`, `bin/forge-sync.sh`, `bin/git-askpass.sh`, `bin/forge_prsync.py`, `setup/*.py`, `cache/` |
| `~/hakux-work/logs/forge/` | `shim.log` (every gh call), `sync.log`, `prsync.log` |

Undo everything:
1. `route.sh off all`.
2. `systemctl --user disable --now hakux-forge-runner hakux-forge-prsync.timer hakux-forge-sync.timer hakux-forge`.
3. Remove the unit files.
4. The data stays in `~/hakux-work/forge/` until deleted.

## Do not repeat

- Don't create a test issue or PR in `jreinach-alt/hakuX`. Issue numbers are
  the import's: one stray issue before the import would have shifted every
  GitHub number. The smoke tests use their own throwaway repos.
- Don't cancel or delete junk Actions runs to clean a PR's checks. The
  commit status outlives the run; filter by context instead (the shim does).
- `git merge-tree --quiet` does not exist in git 2.43, the host's version.
- Forgejo ignores `per_page`, sort/direction on repo comments, and unknown
  label names, all silently. Each looked like success until checked.
- Don't check workflow triggers with a text grep for `push:`: a step input
  can be named `push`. Parse the `on:` key (RETURN.md 2a).
- A caller with `2>/dev/null` turns the shim's exit 64 back into silent
  empty. Run each named caller's exact command line through the shim, not
  just the operation name (xbox_check.sh's `--search`).
