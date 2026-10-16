# burnoutunlock1012: Burnout Revenge's play loop can't get back into a race after a medal (#433, 0.5)

State: ready

## What changed

`docs/testing/titles/routes/burnout-revenge.returning.route`: only the comment block right after
`mark gameplay` changed. It corrected a stale claim (that RESULTS shows Retry/More
details/Continue together on one screen -- no frame on disk ever showed that) with the actual
two-variant breakdown, and documented the new failure mode confirmation 2 hit. **The play loop
itself is unchanged.** Full state table, analysis and the reasoning for not changing the loop are
in `docs/lanes/burnoutunlock1012/NOTES.md`.

## Why

Confirmation `1-1791800854-lane.local-2819291` (Nova, 1600s) FAILed on fps (`fps_ok_share
0.8172` vs the 0.90 bar). The existing loop (burnoutloop1012's `press B`, burnoutbrief1012's
`press A` 0.3s later) worked for the first ~16 minutes, racing and retrying normally at
42-58fps. Then Traffic Attack awarded a medal: once a medal is earned, Burnout Revenge's RESULTS
screen drops its Retry prompt entirely (`frames/f00044.png`, "MEDAL AWARDED BRONZE", prompts
More details/Continue only). The loop's `press A` is still Continue there, same as it is on the
no-medal event brief -- but Continue off a *medalled* RESULTS leaves the event for WORLD TOUR's
location-select screen, not back into a race. Every frame for the rest of the 1600s run
(`f00045` through `f00053`) shows that same location-select screen at 18-27fps; the loop's B/A
pair never escapes it.

## Why no code fix to the loop

`route.sh`'s grammar has no conditional/branch primitive. Its only screen-aware constructs are:

- `waitfor`/`press-until`, which **hard-abort the entire route** if their one expected screen
  doesn't show up in time (confirmed in `route.sh` lines 301-360/420-423) -- unusable inside
  `repeat forever`, since a normal racing cycle would trip the timeout the instant it runs long
  and abort the whole confirmation, which is worse than today's fps FAIL.
- `drive <profile> <seconds>`, the one non-aborting screen-aware construct, but every existing
  drive-profile was built from a Nova path-finding session, and the screens a correct Burnout
  Revenge profile would need past World-Tour location-select (event-type select, car select, now
  that Motor City has a second event unlocked) are **unrecorded** -- no frame on disk shows them
  in this state. This lane has no device.

Adding blind presses for those unrecorded screens, inside a loop that also runs during every
normal racing cycle, is the guess the brief said not to make.

## The bigger finding

Even a correct fix likely can't pass the fps bar as currently sized. The route's own recorded
`wait` values for the World-Tour-entry-to-gameplay path (the only path ever recorded, auto-skip,
best case) sum to **188.5s** (lines 84-122), and every sampled route-frame FPS overlay across
that stretch reads 26-29fps -- below the 30fps bar throughout. A 600s confirmation allows only
60s below-bar to clear 0.90; even the 1600s run here (`gameplay_s 1256.7`) allowed only 125.7s,
less than one recovery's minimum cost. See NOTES.md "Step 4" for the full math. That's stated as
a finding, not solved here -- the decision on confirmation length / route strategy belongs to
lane.local or the owner.

## Checks

- `route.sh --check`: `route ok: ... (192 lines)`, exit 0.
- `git diff origin/master`: first changed line is right after `mark gameplay`; nothing above the
  mark differs.
- `ROUTE_DRY=1 SERIAL=dryrun timeout 395 route.sh ...`: reaches the mark, runs two full loop
  cycles, no `ROUTE FAIL`, killed by the timeout as expected (`repeat forever`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
