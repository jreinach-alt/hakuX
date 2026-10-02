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
