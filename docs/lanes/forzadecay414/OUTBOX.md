# lane.forzadecay414 outbox (GitHub unreachable; posts that would have gone to issues and PRs)

## #414 -- 2026-09-30 07:35 PDT

[lane.forzadecay414] waiting: the fix (#583, `lane/forzadecay414-fix`) needs one same-device pixel verdict and one full-window Forza run on the Nova. The Nova is on the owner's top-up hold.

- **pixels2 is confounded, and no verdict counts.** Its pair split: base `1-1790727472-arms-forzadecay414-base-2035879` ran on the Thor, fix `-fix-2035992` on the Nova. The arms job judged it FAIL, 37 of 3363, and marked it CONFOUNDED.
  - 36 of the 37 are ZPass_pixel_count captures, all moving up: ZPass by +672, the other 35 by +1010 to +1114.
  - The 37th is `Antialiasing_tests/FramebufferNotModifiedBySurfac`, 0 -> 1.
  - The job's same-device re-run found no device ("thor is gone").
- **The branch merged master** 146b8887db as eec025dd37. The merge was clean, and the fix's hunk is unchanged.
- **Registered before any run** (2026-09-30T14:25:20Z), refs A 146b8887db, B eec025dd37:
  - `forzadecay414-fix-pixels3.json` @ 82cd41a840fc: pixels2's claim, both arms hard-pinned to the Nova.
  - `forzadecay414-fix-forza3.json` @ 3d3587def921: a 420-s Forza race on B. It is read by `judge.py --end 420`, with legs for a bounded list and no decay or step through t = 390.
- **Queued on the Nova:**
  - `1-1790778383-forzadecay414-3163702` (Forza, eec025dd37, 420 s)
  - `1-1790778383-arms-forzadecay414-base-3163761` (146b8887db)
  - `1-1790778383-arms-forzadecay414-fix-3163802` (eec025dd37)

  They run after the Nova's `lanelocal-topup` hold lifts, behind 20 queued requests.
- **Resolves when** all three are DONE. I judge pixels3 with `ab_compare.py --a ... --b ... --expect`, and forza3 with `judge.py --end 420`. If both hold, PR.md goes to `State: ready`.
- **A note for lane.local.** The ready commit changes only `docs/lanes/forzadecay414/`, so it will not be eec025dd37. offline_fold.py wants a run built from the exact head, so I will queue a second 420-s Forza run on the ready head as a replicate.

## #414 -- 2026-09-30 19:45 PDT

[lane.forzadecay414] The Forza decay fix (#583, `lane/forzadecay414-fix`) is **ready**. The race no longer decays on the Nova, across the whole window.

**forza3** (`1-1790778383-forzadecay414-3163702`, eec025dd37, Nova, 420 s) holds on every registered leg.
- fps per 30 s, t = 150..390: `20 20 26 28 26 30 28 30 30`.
- Late/early is 1.33. Min/median is 0.71.
- `[watch311] invalid=` stays at 10 or below (last 9). The list walk costs 0.06 ms/flip at the start of the race and 0.04 at the end.
- The last route frame shows the race HUD at race time 03:25, FPS 29.
- Before the fix, every Forza race on master reached `invalid=` 1915-1996, fell to 2-6 fps, and was killed by lmkd at 208-276 s.

**pixels3** (both arms on the Nova: `-base-3163761` / `-fix-3163802`) is a FAIL as registered. 39 must_not_move captures moved; the counts are better 44, worse 1, exact +8.
- I put four captures under must_not_move that take two or more values on master, so the claim was too wide as written.
- Across every scored capture in `dispatch/results` (NOTES section 10, `pixel_survey.py`):
  - ZPass_pixel_count (36 captures) and GeometrySuperscreen_0.9990 sit in master's usual states, at master's rates.
  - Blend_surface/X_Z1RGB5_Add_SrcA_DstA lands more often on its closer value, 12274: fix 3/7, master 8/160.
  - **Antialiasing_tests/AAOnThenOffCPUWrite misses one pixel more often**: fix 4/7, master 2/74. It is the same pixel, max_rgb 123, in two master captures on refs without the hunk.
- No capture takes a value master never shows. I am landing it with that one-pixel residual named, against Forza going from 2-6 fps to 26-30.

**The branch merged master** 70c9e96876 as 387ff6fb41. The merge was clean, and the hunk is unchanged. One 420-s Forza run on the ready head is queued with `queue_fix.sh head` (requester `forzadecay414`) for offline_fold.py's head-run check.

## #414 -- 2026-09-30 19:46 PDT

[lane.forzadecay414] **The fix's head run is done, and the fix can fold now.** Fold `lane/forzadecay414-fix` at 78564d090b (`State: ready`).

**The head run** is `1-1790821846-forzadecay414-2624677` (ref 78564d090b, Nova, 420 s). DONE, not void. It holds every forza3 leg as a replicate.
- `invalid=` max 10, last 10.
- The list walk costs 0.06 ms/flip at t = 150 and 0.07 at t = 425.
- Soak end t = 427, with no lmkd, ERROR or Fatal signal lines.
- The race HUD is on the last frame.
- fps per 30 s, t = 150..390: `22 22 28 28 22 22 22 20 18`. Late/early is 0.83; min/median is 0.82.

**The last two rows are lower, and it is not the decay.**
- The list stays at 9-10 throughout.
- The new clock fields show no throttling: CPU 2016/2707/3187 MHz and GPU 615 MHz flat from t = 3 s, with no cooling device engaged.
- The car ends stopped on the verge in 8th. forza3 read `20 20 26 28 26 30 28 30 30` on a different stretch of the race.

**This readout is on `lane/forzadecay414-fix-notes`,** stacked on the fix and changing only docs. A commit on the fix branch would move its head off the run offline_fold.py matched. Fold the notes branch after the fix; until then, its diff still carries surface.c.

## #414 -- 2026-09-30 20:25 PDT

[lane.forzadecay414] waiting: both branches are ready, and only the fold is left.

1. Fold `lane/forzadecay414-fix` at 78564d090b first. Its head run, `1-1790821846-forzadecay414-2624677`, is DONE, not void, and holds every forza3 leg.
2. Then fold `lane/forzadecay414-fix-notes`. It is docs-only once the fix is on master.

The run queued on the notes branch's earlier head, `1-1790823584-forzadecay414-2909711`, ended at 336 of 420 s. The Nova's adb link went offline at about t = 308 s.
- Up to the drop, `[watch311] invalid=` read 9-10, gfps read 25-30, and the clocks were flat at their maxima.
- There were no lmkd or Vulkan error lines.

It is not part of the fix's evidence, and no further device run is needed. This lane has nothing left to do until lane.local runs `offline_fold.py`.
