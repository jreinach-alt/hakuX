# lane.forzadecay414: the ready head's Forza run reads clean; notes after #583 (#414)
State: ready

Lane: forzadecay414-fix-notes   Issue: #414
Base: lane/forzadecay414-fix @ 78564d090b (stacked; fold it after lane/forzadecay414-fix)
Files: docs/lanes/forzadecay414/NOTES.md, docs/lanes/forzadecay414/OUTBOX.md, docs/lanes/forzadecay414/PR.md
Prediction: none: analysis-only (the head run was queued with --no-expect as a replicate of forzadecay414-fix-forza3.json)
Needs device: no    Needs NDK: no

Release note (none): documentation only

**Fold order.** Fold `lane/forzadecay414-fix` first, at 78564d090b. Until it is on master, this
branch's diff also carries the fix's 16 files. offline_fold.py's head-run check then refuses it,
because no run was built from this head. After the fix folds, the diff is the three files above
under `docs/lanes/`, and no device run is needed.

## What it adds (NOTES section 11)

The head run that offline_fold.py needed for the fix, `1-1790821846-forzadecay414-2624677`
(ref 78564d090b, Nova, 420 s), finished, and it holds forza3's legs as a replicate:

| leg | read |
|---|---|
| W0 | soak end t = 427.3; no ERROR, VOID, lmkd or Fatal signal |
| M0 | race HUD on the last `play` frame: LAP 1/2, RACE 02:49 |
| B1/B2 | invalid= max 10, last 10 |
| B3 | walk 0.06 -> 0.07 ms/flip |
| D1 | late/early 0.83 |
| D3 | min/median 0.82 |

fps rows t = 150..390: `22 22 28 28 22 22 22 20 18`. The last two rows are lower, but the list holds at
9-10 and the clocks are flat at 2016/2707/3187 MHz CPU and 615 MHz GPU, with no cooling device engaged
(#588's fields). The car is stopped on the verge in 8th at the end, a different scene from forza3's.

The readout is on this stacked branch, not on the fix branch. A commit there would move the head
off 78564d090b, and offline_fold.py would then need another 420-s Nova run before folding the fix.

## NOTES section 12

A run on this branch's earlier head, `1-1790823584-forzadecay414-2909711` (ref 089378374c), is DONE
but short: the Nova's adb link dropped at about t = 308 s. Up to the drop, `invalid=` read 9-10 and
gfps 25-30. It is not needed: under the fold order above, this branch is docs-only by the time it
folds.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
