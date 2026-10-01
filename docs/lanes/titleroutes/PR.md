# titleroutes: session 48 -- six pending results read, Castlevania reaches gameplay, Sonic Heroes flagged racy

State: ready

Lane: titleroutes          Issue: #397 (per-title gameplay fps; 0.5 tracking #433)
Base: master @ 99256a4f47 (origin/master merged in session 48; session 47's PR folded there)
Files: docs/lanes/titleroutes/NOTES.md, docs/lanes/titleroutes/OUTBOX.md, docs/lanes/titleroutes/PR.md,
       docs/testing/titles/targets.toml, docs/testing/titles/routes/castlevania-cod.route
Prediction: none: no arm (route data and screening soaks, not A/B arms)
Needs device: yes, queued requests only (Thor cold-slot runner at 300 s); no held session

## What changed

**Read the six requests session 47 left pending** (same method as session 47: `logs/thor-coldconfirm.log`
and a targeted `Grep` across `/home/justin/hakux-work/dispatch`, since a flat `Glob`/`ls` of
`dispatch/results` misses hits in its 233k-file listing). Opened every mark frame before writing
anything, per the lane's own "do not repeat" lesson -- and that check caught a real problem this time:

- **187: Ride or Die (Nova retry):** ran the full 300s with no stop. Mark frame (002517-gameplay.png)
  is a confirmed night street race. **Re-nominated for #433** -- this resolves session 47's open
  question (the prior VOID was an unrelated focus bug, not a route problem).
- **Super Monkey Ball Deluxe, Tony Hawk's Pro Skater 2x:** both routes CONFIRMED a second time
  (same in-level frames as their first confirmation), but both heat-stopped again (51s and 102s
  scored respectively). Two heat stops on a confirmed route, per the Thor screening program's own
  rule -- **both nominated for the Nova**, not a third Thor try.
- **Tony Hawk's Pro Skater 3 (own route, first replay):** heat-stopped at 97s before its own mark
  frame could show more than THE FOUNDRY's level-splash card -- one frame short of confirmed control,
  though consistent with the generic survey's earlier confirmed frame from the same level.
  **Nominated for the Nova with a caveat**: the confirmation should check its own frames for live
  play, since this route has never shown a post-splash control frame on its own.
- **Castlevania: Curse of Darkness (generic survey):** ran 284/300s and reached a gothic courtyard
  under player control -- the first confirmed gameplay this title has ever shown, after three failed
  guess-route attempts since session 44. Authored `routes/castlevania-cod.route` from this evidence
  (14 START/A cycles, then the proven attack/camera/walk loop). DRAFT until its own replay is checked.
- **Sonic Heroes:** re-screened with the exact same route and cycle count as session 47's confirmed
  run -- and this run's entire scored window sat frozen on the pause menu (timer and ring count
  identical across the mark frame and every frame after it). The route presses START on a fixed
  schedule that can land after the level has already started, pausing it, and its one recovery
  attempt did not resume play this time. **NOT nominated.** A route confirmed by one run is not
  proven reliable; this is flagged for a route fix, not a re-screen.

`targets.toml` carries a session-48 sentence on every title above.

**All five Thor requests this batch heat-stopped** (worse than session 47's 3 of 5) -- more evidence
the Thor's dead fan is degrading further, not a one-off.

**Queued next** (ref `d7791f6c0a`, `--device thor --hard-pin --seconds 300`): `1790846753-titleroutes-
3234529`, the first replay of `routes/castlevania-cod.route`. No Nova work queued directly by this
lane; the four #433 nominations above go to lane.local/lane.verdict433 to copy and confirm.

**Offline protocol note:** GitHub has returned `403` ("account was suspended") continuously since
about 2026-09-29 19:40 PDT (36+ hours into this session). The PR-parking waiter that arms from GitHub
PR comments cannot arm itself during the outage, which stranded the previous two sessions' finished
batches until hostops resumed them by hand. This session's `waiting:` line names the queued request id
directly so a successor can poll `dispatch/results`/`logs/thor-coldconfirm.log` without relying on
that waiter.

## Local checks (no CI while GitHub is suspended)

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks passed.
- `targets.toml` parses with tomllib: 78 titles.
- No harness files changed, so `docs/testing/jobs/selftest.sh` does not apply.
- One device request queued from this head's ref (`d7791f6c0a`); result pending, named as `waiting:`
  on #397/OUTBOX.md.

Release note (none): route data, targets.toml and lane notes only; no emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
