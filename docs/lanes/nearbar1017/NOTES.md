# nearbar1017 -- three near-bar titles on the 0.5.2 build

Issue #433 (0.5: 50 Playable). Brief: run Panzer Elite Action, Aeon Flux, and
Medal of Honor: Frontline on the current build, one 600 s held run each on
the Nova, and report whether they now clear the Playable bar (>= 30 fps,
>= 90% of gameplay). Not a retest: 0.5.2 turned on `HAKUX_S2T_CVT` (the
texture path for 16-bit render targets) by default, so the build under test
differs from every prior run below.

## Step 0: already tried

| Title | ID | Open nv2a_issues.toml defect? | Prior held run (build, date) | Verdict | Path knowledge |
|---|---|---|---|---|---|
| Panzer Elite Action: Fields of Glory (Europe) | 4A570009 | none found (grep for "panzer", "4A570009": only an unrelated substring hit on "Panzer Dragoon Orta" at nv2a_issues.toml:1913, a different title) | `wt/pathfind/docs/lanes/pathfind/runs/n-4A570009-1007`, nova, 2026-10-07 (pre-0.5.2; run.log/verdict carry no build ref/sha, date is the only anchor) | FAIL: fps 89.65% of gameplay >= 30 fps (bar 90%), median 30.41, min 26.56 fps, gameplay 605.7 s, play_share 0.9997 | `docs/testing/titles/pathknow/paths/4A570009.json` + hint `learned-pub-4A57.md`: publisher_logo START A -> intro_video START A -> cutscene START A -> main_menu A -> submenu A -> cutscene A A A A -> cutscene RT:1 LT:1, gameplay in 2.7 min |
| Aeon Flux | 4D4A0014 | none found (grep for "aeon", "4D4A0014": no hits at all in nv2a_issues.toml) | `wt/pathfind/docs/lanes/pathfind/runs/n-4D4A0014-1013r`, nova, 2026-10-13 (pre-0.5.2) | FAIL: fps 84.6% of gameplay >= 30 fps (bar 90%), median 29.96, min 26.04 fps, gameplay 603.6 s, play_share 0.9993 | `wt/pathfind` worktree has `pathknow/paths/4D4A0014.json` (route recorded 2026-10-13, ref `024b1588e9ff` per `compatrefresh1013/registry.tsv`); this lane's own sparse checkout does not carry that path file (lane trees are sparse) -- confirmed present in the sibling pathfind worktree, so `--no-replay`/`--no-guide` are not needed, pathfind.py will find and replay it from the repo once the file is reachable |
| Medal of Honor: Frontline (USA) | 4541001A | none found (grep for "medal of honor", "frontline", "4541001A": no hits in nv2a_issues.toml) | `wt/pathfind/docs/lanes/pathfind/runs/n-4541001A-1007`, nova, 2026-10-07 (pre-0.5.2) | FAIL: fps 85.58% of gameplay >= 30 fps (bar 90%), median 59.88, min 15.9 fps, gameplay 608.0 s, play_share 0.9997 | `docs/testing/titles/pathknow/paths/4541001A.json` + hint `learned-pub-4541.md`: publisher_logo START A -> cutscene START A -> save_load_prompt DOWN DOWN A -> submenu DOWN DOWN A -> submenu A -> cutscene START A, gameplay in 2.7 min |

None of the three has an open nv2a_issues.toml defect naming it, so none is
reported from the issue list alone -- each needs the run.

`docs/testing/compat_notes.tsv` / `docs/compatibility.csv` carry the same
three rows as `below_bar`, same numbers as above (compat_notes dates:
Panzer 10-07, Aeon Flux 10-13, MoH 10-08 [compat_notes] / 10-07 [the run dir
itself] -- compat_notes' date is one day off the run's own timestamp,
noted but not chased since both predate 0.5.2 either way).

Panzer and Aeon Flux both sit at a 30 fps cap (median 30.41 / 29.96), so
their bar share is jitter-sensitive -- a handful of windows either side of
30 fps moves the percentage a lot. MoH runs at a 60 fps cap (median 59.88)
with a much lower min (15.9 fps), so its miss is a real drop, not cap jitter.

## Pre-flight device/queue check (2026-10-17, before any run)

- `dispatch/hold/`: only `thor` (lanelocal-offline, unrelated) and the
  `lifted/` dir. No `hold/nova`.
- `dispatch/running/`: empty. `dispatch/queue/`: only a `withdrawn/` subdir,
  nothing live.
- `. docs/testing/devices.sh && device_list nova` reaches `ee317437 nova`.
- **None of the three titles were present on the Nova's own storage**
  (`device_titles nova` has no 4A570009/4D4A0014/4541001A). All three are
  pre-0.5.2 run artifacts; whatever shuffle put them there earlier moved
  them back off since. All three are cached on D: already (not the Thor):
  `/mnt/d/hakux-staging/shuffle-cache/4541001A-...iso` (3176333312 B),
  `/mnt/d/hakux-staging/shuffle-cache/4A570009-...iso` (1505361920 B),
  `/mnt/d/hakux-staging/xiso/4D4A0014-Aeon_Flux.xiso.iso` (4778360832 B).
  Nova free space: 29 GB (`df -h /storage/E6C6-D7AA`). Total to stage:
  ~9.46 GB, leaving ~19.5 GB free -- under lane.local's own 25 GB shuffle
  floor (`shuffle1011b.sh`), so staged one at a time and removed again after
  its run (see below) rather than left sitting at a reduced floor.
