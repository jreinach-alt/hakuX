# titleroutes: session 44 -- six Thor screens read, a harness misdiagnosis found, four surveys queued

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 70c9e96876 (fast-forward merge, session 44; sessions 39-43 already folded here)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/PR.md, docs/lanes/titleroutes/OUTBOX.md,
       docs/testing/titles/targets.toml
Prediction: none: no arm (route validation + same-pass fps benchmark soaks, not A/B arms)
Needs device: no new held session this session -- six prior results read, four new Thor surveys queued
       (not waited on)

## What this session found

Session 43's own work had already folded cleanly into `origin/master` as
`70c9e96876` before this session started -- not a failure recovery, the
waiter's routine resume (session 43 ended correctly on a `waiting:` naming
exactly the six requests below, with PR.md `State: ready`). Merged
`origin/master` (fast-forward, no conflicts).

All six pending Thor/Nova requests from session 42-43's screening batch had
landed and were read in full with `docs/testing/title_verdict.py`:

| title | device | reached gameplay | fps median | share at 28.5+ | crash/hang | real cause |
|---|---|---|---|---|---|---|
| THPS2x (v1, 480s) | thor | yes | - | 0.961 | crash/no | Daijishou focus steal at 260s |
| THPS2x (retry, 300s) | thor | yes | 59.82 | 0.976 | no/no | clean |
| Capcom Classics 2 (v1, 480s) | thor | yes | - | 1.0 | crash/no | silent exit at 390s, xo-therm 70.1C -- plausibly real heat |
| Capcom Classics 2 (retry, 300s) | thor | yes | 59.94 | 1.0 | no/no | clean |
| Castlevania: CoD | thor | yes | 59.94 | 1.0 | crash/no | Daijishou focus steal at 381s |
| SMT: NINE | thor | yes | 29.96 | 0.967 | no/no | clean |
| Tork | thor | yes | 29.96 | 0.585 | crash/no | Daijishou focus steal at 290s; also genuinely marginal fps |
| Dead or Alive 3 (v2) | thor | yes | 52.22 | 0.605 | crash/hang | Daijishou focus steal at 475s |
| Burnout Revenge | nova | yes | 39.45 | 0.972 | no/no | clean, BENCHMARKED |

**Defect found and filed** on `dispatch/board-requests/titleroutes.md` (not my
file): the dispatcher's Thor cold-slot auto-diagnoser (harness_health.py)
labeled 5 of these runs `.hostops-diagnosed` "HEAT STOP at xo 70 C". Four of
the five actually logged an explicit `not-foreground:
com.magneticchen.daijishou` -- the Thor's own launcher regained display-0
focus and killed xemu, caught correctly by the route engine's foreground
guard, with xo-therm nowhere near 70C in `thermal.jsonl` at the time. Only
the fifth (Capcom2's first attempt) has thermal evidence consistent with a
real heat stop (xo-therm 70.1C in its last sample, but no explicit
not-foreground or heat line in its own log either). This undermines the
evidence behind lane.local's 09-30 15:40 PDT addendum that cited three of
these runs as heat stops to justify dropping the Thor screening cap to 300s
-- the cap may still make sense for cooling cadence, but the real,
reproducible failure (Daijishou stealing focus, independent of duration) is
still live and the shorter cap does not reliably prevent it (it struck at
260s, 290s, 381s and 475s). Full evidence in NOTES.md, "Session 44".

**Nova nominations posted to #433**: Tony Hawk's Pro Skater 2x (97.6%),
Capcom Classics Collection Vol. 2 (100%) and Shin Megami Tensei: NINE
(96.7%) are clean, no-caveat nominations. Castlevania: Curse of Darkness
clears the written bar (100% fps, no hang) but its run ended in the
Daijishou crash rather than completing, so it's nominated with that caveat.
Dead or Alive 3 and Tork are not nominated (well below the 90% bar); both
now have two failed Thor runs each and I am not sending either a third blind
retry. DOA3 is Thor-only so a Nova reading needs a copy decision outside
this lane's authority (owner's amended one-copy-per-title rule) -- flagged,
not acted on.

`targets.toml` updated for all seven titles with these results, replacing
"not yet replayed"/stale notes. Still parses with `tomllib` (unchanged
title count) and `titlestate_selftest.py` passes (all checks).

**Kept the Thor queue fed**, per the "batch the Thor work per session"
addendum: queued the next four routeless Thor-only titles from the work
list as blind pass-1 surveys (300s, `--route survey --device thor
--hard-pin`, not waited on): Psychonauts (`1790822573-titleroutes-2818801`),
Phantom Dust (`1790822578-titleroutes-2819133`), Ninja Gaiden (Europe)
(`1790822580-titleroutes-2819211`), Deathrow
(`1790822581-titleroutes-2819301`). GitHub is still offline so release
labels can't be read; these queued at plain priority like every other
offline-mode request this lane has made.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks pass.
- `targets.toml`: parses with `tomllib`.

## Device proof

- All nine rows in the table above are backed by a read `verdict.json` and
  `route-frames/*gameplay*.png` in their own `dispatch/results/<id>/`
  directory (ids given in the table and in NOTES.md "Session 44"); the four
  Daijishou-stop runs are additionally backed by the literal
  `not-foreground: com.magneticchen.daijishou` line in each one's `run.log`.

Release note (performance|stability|rendering|other|none): none -- this PR
touches only route data, lane bookkeeping, and a board-request writeup; no
emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
