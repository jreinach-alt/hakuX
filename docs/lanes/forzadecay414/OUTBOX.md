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
