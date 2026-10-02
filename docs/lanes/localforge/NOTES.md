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
