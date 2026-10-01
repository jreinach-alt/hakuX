# titleroutes: session 47 -- the eight pending results read, thps3.route authored, six re-screens queued

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 5014d808b0 (origin/master merged in session 47)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md,
       docs/testing/titles/targets.toml, docs/testing/titles/routes/thps3.route
Prediction: none: no arm (route data and screening soaks, not A/B arms)
Needs device: yes, queued requests only (Thor cold-slot runner at 300 s, one Nova replay); no held session

## What changed

**Read the eight requests session 46 left pending** (logs/thor-coldconfirm.log, not a flat
`dispatch/results` listing, was the way to find them -- NOTES.md session 47 explains why). Checked
every mark frame, not just the fps share, per the lane's own "do not repeat" lesson:

- **Family Guy: Video Game!** replayed clean (no heat stop), fps_ok_share 0.9763/189.4s. The mark
  frame is a save-overwrite dialog, one frame early (the disk now carries a prior Family Guy save),
  but real gameplay is confirmed 9s later and dominates the window. Nominated for Nova (#433).
- **Super Monkey Ball Deluxe, Sonic Heroes, Tony Hawk's Pro Skater 2x (re-mark):** all three routes
  are CONFIRMED by their mark frames (real gameplay, 59fps, not a menu), but each run heat-stopped
  at 48-105s, too short to nominate. Clean re-screens queued.
- **Castlevania: Curse of Darkness (re-mark):** still did NOT reach gameplay -- the new mark frame
  is a different menu ("Create new save data?"). Every step of this guess-authored route past boot
  has never been confirmed by a frame. Abandoned as a mark source; a generic `--route survey` soak
  is queued to replace it with evidence.
- **THPS3 (generic survey):** heat-stopped before any route-specific mark existed, but its frames
  show real, unpaused Foundry gameplay by the 3rd START/A cycle. Used that evidence to author
  `routes/thps3.route` (DRAFT, not yet replayed as its own route).
- **SSX Tricky (generic survey):** completed its full 300s with no heat stop, but every "play" frame
  is solid black (`hang=True`, confirmed by eye). Needs its own survey/nav pass; no route yet.
- **187: Ride or Die replay (Nova):** VOID for an unrelated reason -- hakuX never held display-0
  input focus at all, so no input was sent. Not a route finding; retry queued.

`targets.toml` carries a session-47 sentence on every title above, plus two new entries (THPS3,
SSX Tricky).

**Queued next** (ref `2a87446629ae2b801aa4cfe6b14ba8b19fc729f4`, Thor requests
`--device thor --hard-pin --seconds 300`): re-screens for super-monkey-ball-deluxe, sonic-heroes,
thps2x; the first replay of thps3; a generic survey for Castlevania; and a retry of the
187-ride-or-die Nova replay. Ids and purposes: NOTES.md and OUTBOX.md, session 47.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks passed.
- `targets.toml` parses with tomllib: 78 titles.
- No harness files changed, so `docs/testing/jobs/selftest.sh` does not apply.
- Six device requests queued from this head's ref (`2a87446629`); results pending, named as
  `waiting:` on #397/OUTBOX.md.

Release note (none): route data, targets.toml and lane notes only; no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
