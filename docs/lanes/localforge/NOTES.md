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
