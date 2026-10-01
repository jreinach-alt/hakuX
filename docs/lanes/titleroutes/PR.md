# titleroutes: sessions 44-46 -- 187's route fixed, a mark audit that withdraws four Thor nominations, three new Thor routes

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 6e07e2d5b6 (origin/master merged in session 46)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md,
       docs/testing/titles/targets.toml, docs/testing/titles/routes/187-ride-or-die.first-run.route,
       docs/testing/titles/routes/187-ride-or-die.returning.route, docs/testing/titles/routes/187-ride-or-die.route,
       docs/testing/titles/routes/castlevania-cod.first-run.route, docs/testing/titles/routes/family-guy.route,
       docs/testing/titles/routes/sonic-heroes.route, docs/testing/titles/routes/super-monkey-ball-deluxe.route,
       docs/testing/titles/routes/thps2x.route
Prediction: none: no arm (route data and screening soaks, not A/B arms)
Needs device: yes, queued requests only (Thor cold-slot runner at 300 s, one Nova replay); no held session

## What changed

**187: Ride or Die's scored window was the profile-name keyboard** (the owner's finding,
`1-1790775886-lane.verdict433-3086875`). titlestate records a 187 profile on the Nova, so the
returning route ran. But the disk built with that save lists four Empty slots
(121939-profile-select.png). The route's A therefore opened Create's keyboard, and `mark gameplay`
landed there (122018-gameplay.png). The first-run/returning pair is replaced by one route,
`187-ride-or-die.route`. It creates profile N every run, accepts the new-profile controller screen,
skips the tutorial clip and marks after 6 s of driving. `titlestate.py choose --title-id 55530036`
now returns `variant: single` with that file. Replay queued on the Nova.

**Mark audit.** The newest run of each of the 45 route names that reached `mark gameplay` was
read frame by frame. 28 marks sit on play. 16 do not, including all four of session 44's Nova
nominations:
- THPS2x: goal checklist.
- Capcom Classics 2: START MENU.
- SMT NINE: name entry.
- Castlevania: Name Entry.

Those were guessed drafts whose placeholder mark was never checked against a frame. The
nominations are withdrawn on OUTBOX #433. THPS2x and Castlevania are re-marked and re-screened.
Every flagged title carries a "Session 46 mark audit" sentence in targets.toml. The full table is
in NOTES.md, session 46.

**Retraction.** Session 44's "Daijishou focus steal, not heat" claim was backwards. The
cold-slot runner logged a HEAT STOP for every one of those runs. The launcher line follows the
force-stop. The correction is on the board request file and OUTBOX #397.

**New Thor routes** come from this batch's surveys. Each replays the survey's own START/A presses
up to the cycle that started play, then never presses START again (START pauses each of these
games). All are drafts until their queued screens replay:
- Family Guy: Stewie's nursery.
- Super Monkey Ball Deluxe: stage 1-1, 59.
- Sonic Heroes: Seaside Hill, 59.

Queued: 7 Thor screens and surveys, 1 Nova replay (ids in NOTES.md session 46, and the `waiting:`
in OUTBOX #397).

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks passed.
- targets.toml parses with tomllib: 76 titles.
- `titlestate.py choose --title-id 55530036` returns `variant: single`, route
  `187-ride-or-die.route`. `--title-id 545400B0` returns `variant: single`.
- No harness files changed, so `docs/testing/jobs/selftest.sh` does not apply.

Release note (none): route data, targets.toml and lane notes only; no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
