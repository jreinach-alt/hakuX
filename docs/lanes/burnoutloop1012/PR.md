# burnoutloop1012: Burnout Revenge's play loop presses Retry so a run stuck on RESULTS keeps racing (#433, 0.5)

State: ready

Lane: burnoutloop1012      Issue: none (#433 umbrella, dispatched directly by lane.local)
Base: master @ 00fde8afb3
Files: docs/lanes/burnoutloop1012/NOTES.md, docs/lanes/burnoutloop1012/PR.md,
docs/testing/titles/routes/burnout-revenge.returning.route
Prediction: none: route data (inputs) and notes, no emulator code; this is a route fix, not a
performance change, so it is not a `docs/testing/ab_compare.py --register` candidate. lane.local
queues the next confirmation after the fold, per the brief.
Needs device: no (this lane)    Needs NDK: no

## Why

Confirmation `1-1791785532-lane.local-2130848` (route `burnout-revenge.returning`, 840 s) scored
`fps_ok 0.9956` but only 475.6 s of gameplay -- short of the 600 s a Playable needs. Its frames
show why: `mark gameplay` lands inside a short "Traffic Attack" timed event (`f00014`, timer
11.43 and counting down). The event ends within the next ~15 s and the game drops to a **RESULTS
[TRAFFIC ATTACK]** screen (Retry B / More details Y / Continue A) that every remaining frame
(`f00015`-`f00028`, 410 s) still shows -- a replay moves behind the panel, which is why the
liveness check (`static_frac 0.07`) passed anyway. The old play loop after `mark gameplay` only
holds `RT max` and steers with `LX`; it never presses anything that dismisses RESULTS, so once the
event ends the run sits there for the rest of the confirmation. Full frame-by-frame account,
including what's on disk for the earlier screening of the same route (no `frames/` dir, so RESULTS
can't be confirmed either way there), is in `NOTES.md`.

## What changed

Only the play loop after `mark gameplay` (verified: `git diff` shows no change above it). The
inner drive pattern (`RT max` / `LX min` / `LX max` / `LX mid`, 1.5 s steps) is unchanged and now
runs three times (18 s) per outer iteration; then `RT` is released to `mid`, a short 0.3 s
settle, and `press B` (Retry) -- restarting the same event if the run is sitting on RESULTS, a
no-op otherwise. Cadence: ~19.3 s per outer iteration, so a run on RESULTS restarts within "about
20 s" as the brief asked.

There is no frame evidence in either run of what B does during a live race (it was never pressed).
Since that's unknown, the fix is built to bound the downside: at most one `press B` can land per
18 s of racing (not every 6 s loop iteration), and the race itself only runs ~25-30 s per the
frames, so at most one stray press per race if B does turn out to be a live control (e.g. a
handbrake). `NOTES.md` has the full reasoning.

## Checks

```
$ bash docs/testing/titles/route.sh --check docs/testing/titles/routes/burnout-revenge.returning.route
route ok: docs/testing/titles/routes/burnout-revenge.returning.route (150 lines)
$ echo $?
0

$ ROUTE_DRY=1 SERIAL=dryrun timeout 400 bash docs/testing/titles/route.sh docs/testing/titles/routes/burnout-revenge.returning.route
...
ROUTE 00:42:45.903 mark gameplay
...
ROUTE 00:43:04.539 press B        # mark + 18.6 s
...
ROUTE 00:43:25.088 press B        # mark + 39.1 s (20.5 s gap)
$ echo $?
124   # timeout, expected: the loop is `forever`
```

Both ran against this worktree's own copy. No device run: per the brief, lane.local queues the
next confirmation after the fold, and that run's frames are the proof this actually clears
RESULTS in play.

Full account in `docs/lanes/burnoutloop1012/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
