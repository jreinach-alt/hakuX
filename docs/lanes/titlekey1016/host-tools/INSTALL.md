# host-tools copies for #433 (one display name per title_id)

This directory holds lane-owned copies of host-only scripts. Nothing here
writes to the real `/home/justin/hakux-work/host-tools/` -- the brief says
not to -- these are drop-in replacements / additions for whoever installs
this lane (lane.local, or the `host-tools` maintainer).

## status_page.py -- item 3 (README Playable count must follow the ledger)

Full modified copy of the live `/home/justin/hakux-work/host-tools/status_page.py`.
The only change is in `main()`, the `home_page.update()` call site: it now
passes `playable=len(led)` (the ledger row count already loaded earlier in
the same function) instead of calling `home_page.update(home_blobs or None)`
with no `playable=` argument.

Why: `home_page.update()` only derives `playable` from the ledger when the
caller omits it AND a freshly rendered `STATUS.md` blob is present; if
`dashboard_blobs()` returns `{}` (a stale or crashed render), `update()`
falls back to regex-parsing `Playable **N**` out of the EXISTING home-branch
`STATUS.md` blob -- i.e. whatever number was last published, however old.
That is the exact mechanism of the 10-14/10-16 incident (README and Wall
said 87, the status page's own STATUS.md said 77 for 32 hours). Passing
`playable=len(led)` explicitly means the published count always comes from
the live ledger, render or no render.

**Install**: replace the live file with this copy.
`/home/justin/hakux-work/host-tools/status_page.py` -> this file.
`home_page.py` itself needs no change: `update()` already accepts an
explicit `playable=` and only used its own fallback when the caller didn't
supply one.

## status_alarm.py + status_alarm_selftest.py -- item 4 (hourly alarm)

New script, not yet wired into `hourly_report.sh`. `status_alarm.py` reads
the `home` branch's published `STATUS.md` (via
`git --git-dir=/home/justin/hakux-work/offline-git/hakuX.git show home:STATUS.md`)
and the live ledger (`pm/playable-accepted.tsv`), and prints one `ALARM:`
line for each of:
  - the `_updated ...` stamp is more than 2 hours old;
  - the `Playable **N**` count in STATUS.md differs from the ledger's actual
    row count.
Exits 0 always -- an hourly section reports, it does not fail the run.
Verified RED against today's live data (10-16, run from this lane):

```
  ALARM: home:STATUS.md is 33.5 h stale (cap 2h, updated 2026-10-14 22:39 PDT)
  ALARM: home:STATUS.md says Playable 77, ledger has 87
```

`status_alarm_selftest.py` proves the quiet (green), stale-only, mismatch-only
and both-at-once cases against a throwaway bare git repo (4/4 pass).

**Install**: copy both files into the real
`/home/justin/hakux-work/host-tools/`, then add one section to
`/home/justin/hakux-work/host-tools/hourly_report.sh` in the same style as
the existing `echo "--- <section>"` blocks -- for example right after the
`"--- PLAYABLE"` line (currently line 33):

```bash
  echo "--- public status alarm (home:STATUS.md vs ledger, #433)"
  timeout 30 python3 $H/host-tools/status_alarm.py --git-dir "$H/offline-git/hakuX.git" --ledger "$H/pm/playable-accepted.tsv" 2>&1
```

No other change is needed: the script takes `--git-dir`/`--ledger` with
defaults that already match `hourly_report.sh`'s own `$H` paths, and fails
soft (one `ALARM: ... unreadable` line, exit 0) if the home ref or the
ledger can't be read.
