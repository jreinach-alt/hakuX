# titleroutes: session 45 -- stale work list refreshed (389 ISOs, 327 unrouted), seven Thor requests queued

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 70c9e96876 (already an ancestor of this branch's tip; no merge needed this session)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/PR.md, docs/lanes/titleroutes/OUTBOX.md,
       docs/testing/titles/targets.toml
Prediction: none: no arm (route validation + pass-1 surveys, not A/B arms)
Needs device: no new held session this session -- two prior results read (one voided, one stuck),
       seven new Thor surveys queued (not waited on)

## What this session found

Session 44 ended correctly on `waiting: none` with PR.md `State: ready` after
pushing fresh work -- not a failure, the harness's routine quiet-clock resume.
`git merge-base --is-ancestor origin/master HEAD` confirmed `origin/master`
(`70c9e96876`) is already an ancestor of this branch, so no merge was needed.

Read session 44's two readable pending requests (the other two, Ninja Gaiden
Europe and Deathrow, are still working through the Thor cold-slot queue):

| title | request | outcome |
|---|---|---|
| Phantom Dust | `1790822578-titleroutes-2819133` | voided at the old 480s cap: `logs/thor-coldconfirm.log` reads "HEAT STOP at xo 70 C -- run voided (no result)", no result dir exists at all |
| Psychonauts | `1790822573-titleroutes-2818801` | landed; never passed its title screen -- see below |

**Psychonauts hit a NEW focus-steal defect, not a menu problem.** `run.log`
shows a clean boot into the title screen ("Press START to begin"), then 7
cycles of the standard survey's START/A loop -- every route-frame from
`194441-menu-start.png` to `194548-menu-start.png` shows the identical title
card, so no press advanced it. At 136s of 300s the route engine logged
`ROUTE STOPPED: ... not-foreground: com.android.launcher3 (input focus is on
display 4...)` -- Android's own launcher took focus, not the Thor's
Daijishou launcher this time (the defect flagged in session 44, still filed
on `dispatch/board-requests/titleroutes.md`, now confirmed broader than one
launcher). 7 cycles at ~14s is ~98s -- the run died well inside its 300s
budget, so this is evidence of another focus-steal hit, not evidence the
title screen needs different input. Requeued the identical survey rather
than hand-authoring a new route.

**The 48-title work-list table (NOTES section 1, built 2026-09-26) is
exhausted.** Refreshed it by listing both Thor ISO roots directly (plain
`adb shell ls`, no hold needed, per Build step 1): 42 titles on the external
card and **347 on the internal-storage root** added since lane.xbox started
copying from the owner's PC library (addendum 4, GTA:SA onward) -- 389 ISOs
total, matching the scale lane.local's 12:40 PDT addendum already named
("321 titles, only 23 routed"). Cross-referenced both lists' title_id
prefixes against `targets.toml`'s 70 entries with a throwaway script
(`scratch/diffwork.py`, `scratch/rank_untouched.py`, not committed; not a
file this lane owns to commit) and found **327 internal-root titles with no
targets.toml entry at all**. The external root's 24 "untouched" hits were
mostly false positives (titles already routed under a canonical id that
doesn't match their own filename, e.g. JSRF, Tork, Psychonauts); three real
gaps there (RalliSport Challenge (1), Whacked!, Aliens Versus Predator:
Extinction) are noted in NOTES for a later batch.

Ranked the 327 against `xemu-compat-2026-09-25.csv` (rating, then numeric
xemu_rank) and checked `host-tools/blocked-titles.txt` (only Galleon is
blocked; none of these are). Queued this session's Thor batch -- the top
five ranked candidates plus the two requeues, seven requests total, all
`--route survey --device thor --hard-pin --seconds 300 --issue 397`:

| title | title_id | request |
|---|---|---|
| Super Monkey Ball Deluxe | 53450038 | `1790823793-titleroutes-2949342` |
| Family Guy: Video Game! | 545400B0 | `1790823797-titleroutes-2950719` |
| Gauntlet: Dark Legacy | 4D57000E | `1790823800-titleroutes-2951589` |
| Sonic Heroes | 5345002B | `1790823803-titleroutes-2951964` |
| Bistro Cupid | 53550001 | `1790823806-titleroutes-2952343` |
| Phantom Dust (requeue, 300s cap) | 4D530046 | `1790823811-titleroutes-2952744` |
| Psychonauts (requeue, same input) | 4D4A0012 | `1790823861-titleroutes-2960863` |

GitHub is still suspended (`gh pr view` fails: no known GitHub host on the
remote), so these queued at plain priority like every offline-mode request
this lane has made; the pilot gate's own check ("reviewed pilot ...
(5.1 h old) admits it") stayed satisfied for the whole batch.

`targets.toml` updated: Psychonauts added fresh (no entry existed before),
Phantom Dust's notes extended with the void-and-requeue. Did not touch the
Nova (session 44's Nova nominations are lane.local's/lane.verdict433's to
action; saw an unrelated `shaderprebuild569` request running and left it
alone).

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks pass.
- `python3 -c "import tomllib; tomllib.load(open('docs/testing/titles/targets.toml','rb'))"`: parses, 70 titles.

## Device proof

- Phantom Dust's void: `dispatch/results/` has no directory for
  `1790822578-titleroutes-2819133` at all; `logs/thor-coldconfirm.log` lines
  1029-1030 are the only record.
- Psychonauts's stall: `dispatch/results/1790822573-titleroutes-2818801/run.log`
  and its `route-frames/194441-menu-start.png` through `194548-menu-start.png`
  (all seven frames visually identical to the title card), plus the
  `ROUTE STOPPED: ... not-foreground: com.android.launcher3` line at 19:46:01.

Release note (performance|stability|rendering|other|none): none -- this PR
touches only route data, lane bookkeeping, and `targets.toml`; no emulator
code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
