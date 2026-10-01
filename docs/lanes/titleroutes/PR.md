# titleroutes: session 49 -- gauntlet.route authored from its survey's own trap, capcom-classics2/two new titles surveyed, Sonic Heroes tiebreaker

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ f2da40f0e3 (origin/master merged in session 49; session 48's PR folded there)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md,
       docs/testing/titles/targets.toml, docs/testing/titles/routes/gauntlet.route
Prediction: none: no arm (route data and screening soaks, not A/B arms)
Needs device: yes, queued requests only (Thor cold-slot runner at 300 s); no held session

## What changed

**The castlevania-cod.route replay session 48 queued heat-stopped at 78s of 300s, inconclusive.**
`.hostops-diagnosed` on `0-0-s-1790846753-titleroutes-3234529` confirms a CPU thermal-gate stop
(cpu-1-9 at 91C) two cycles into the route's 14, nowhere near its own mark -- not a route failure.
One heat stop for the named route so far (the generic survey it's built from heat-stopped separately
already, at 284/300s, and was not voided). Re-queued a second replay rather than escalating on one
inconclusive run.

**Gauntlet: Dark Legacy -- authored `routes/gauntlet.route` from its own survey's frames, which
turned out to hide the same bug `sonic-heroes.route` has, found before any route was committed.**
Walking `0-0-s-1790823800-titleroutes-2951589`'s route-frames cycle by cycle (not just the two
frames an earlier note already named) found that by the 8th START/A cycle the wizard was already
under player control in the dungeon (an in-engine tutorial scroll over live 3D, FPS 14), but the
survey's blind 14-cycle default kept pressing START for 6 more cycles into that live play, and its
own `mark play` frame is the in-game pause menu's Audio page, not gameplay -- the
START-during-gameplay trap session 48 named "Gauntlet-class" after finding it in Sonic Heroes,
except this time it was sitting in a survey's own frames. Authored the route at 8 cycles (not 14),
then `mark gameplay`, then a movement loop that never presses START again, same shape as
`castlevania-cod.route`. `targets.toml` gets `route = "gauntlet"` and the frame-by-frame note.
DRAFT until its own replay (queued this session) is checked.

**capcom-classics2: queued a generic survey instead of guessing a second fix.** The withdrawn
nomination's mark frame is a "START MENU (Start Game / Load Game / Game Settings / Exit Game)"
structure the current all-`[guess]` route (an arcade-coin sequence) never anticipated. Queued
`--route survey` instead of a second blind guess -- the method that produced real evidence for
castlevania-cod and surfaced Gauntlet's trap above.

**Two new titles from the ranked untouched list, surveyed generically:** Plus Plumb 2 (544B0004,
rank 101, Perfect) and Petit Copter (41510001, rank 135, Perfect), neither previously touched.
Bare `targets.toml` entries added; no frames yet.

**Sonic Heroes: queued a tiebreaker, not a blind edit.** 1 good (session 47) / 1 bad (session 48) of
the identical route and cycle count is a coin flip, not a verdict. Unlike Gauntlet, there's no
per-cycle frame record for this title's boot timing to ground a cycle-count fix in, so guessing a
new count risks spending a cold Thor slot to learn nothing. Queued a 3rd screen of the existing
route: 2-of-3 good reopens the nomination path under the "two clean confirmations" rule, 1-of-3
confirms it needs a real redesign, not another screen.

`targets.toml` parses (tomllib, 80 titles) and `titlestate_selftest.py` passes (unchanged from
session 48; no harness files touched).

## Queued this session (ref `31dcc755ad`, Thor, `--device thor --hard-pin --seconds 300`)

| title | route | request |
|---|---|---|
| Castlevania: Curse of Darkness | castlevania-cod (2nd replay) | `1790850015-titleroutes-3951103` |
| Gauntlet: Dark Legacy | gauntlet (1st replay, new route) | `1-1790850024-titleroutes-3953302` |
| Capcom Classics Collection Vol. 2 | survey (generic) | `1-1790850027-titleroutes-3953658` |
| Plus Plumb 2 | survey (generic) | `1-1790850029-titleroutes-3954081` |
| Petit Copter | survey (generic) | `1-1790850032-titleroutes-3954284` |
| Sonic Heroes | sonic-heroes (3rd screen, tiebreaker) | `1-1790850035-titleroutes-3954488` |

No Nova work queued by this lane this session.

**Offline protocol note:** GitHub has returned `403` ("account was suspended") continuously since
about 2026-09-29 19:40 PDT (~40 h into this session). The PR-parking waiter that arms from GitHub PR
comments cannot arm itself during the outage. This session's `waiting:` line names the six queued
request ids directly so a successor can poll `dispatch/results`/`logs/thor-coldconfirm.log` without
relying on that waiter, same as the last three sessions.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks passed.
- `targets.toml` parses with tomllib: 80 titles.
- No harness files changed, so `docs/testing/jobs/selftest.sh` does not apply.
- Six device requests queued from this head's ref (`31dcc755ad`); results pending, named as
  `waiting:` on #397/OUTBOX.md.

Release note (none): route data, targets.toml and lane notes only; no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
