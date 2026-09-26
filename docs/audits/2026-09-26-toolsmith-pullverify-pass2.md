# Audit pass 2: PR #369, lane/toolsmith-pullverify (defect 15)

Head verified: `5a672dd663` (pass 1's head `a3f2d528a8` plus the pass-1
audit file; no code changed since pass 1). Pass 1 found no HIGH and no
MEDIUM, and three LOWs.

**Result: clean.** Next state: `fold-ready`.

## L1 (LOW): no-md5 SHORT check sees only file FAT chains

- **Status: not adopted, still LOW.** No commit after pass 1 touches `run_disc.sh`.
- The scenario can still occur, but only on the no-md5 path. That path still announces itself on every run with `pull: NOT VERIFIED -- the device gave no md5 for its image` (`run_disc.sh:263`).
- Pass 1's bound still holds: a zeroed data run reads as `unreadable` or a pixel diff, and missing directory entries read as lost coverage. Nothing is silently scored as exact.
- The wording suggestion stays open as a follow-up. It does not block the fold.

## L2 (LOW): SHORT files that survive every attempt exit 0

- **Status: not adopted, still LOW.** The script is unchanged.
- The bound is still in force on this head: part A of 51 (the `unreadable` → VOID path from #224) passed in CI run 36228278077. A one-cluster PNG cannot count as "repaired to exact".
- Pass 1 called a non-zero exit a design choice. It is left to the lane.

## L3 (LOW, process): red head on a stale base

- **Status: resolved.**
- The `jobs selftest` run at `5a672dd663` (run 36228278077) is green. That includes 51 part I, "check_territory names where it read the tracker", the one check that was red at pass 1. It passes because it reads live `origin/board`, and that input has changed since.
- The head is still 79 commits behind `origin/master`, so I checked what a fold would bring in:
  - `git merge-tree --write-tree origin/master HEAD` merges cleanly, and GitHub reports `MERGEABLE`.
  - Master's side since the merge base (`dc64822787`) touches no file this PR changes. Its selftest changes are `64-status-html.sh`, `75-nv2a-index-drift.sh` and `97-board-release.sh`.
  - No master script is numbered 58, so `58-pull-verify.sh` collides with nothing.
- A fold therefore runs the same `run_disc.sh`, `extract_results.py` and selftest 58 that CI ran green here.

## Selftest 58 at this head

All five cases (a)-(e) are `ok` in run 36228278077, along with the extractor summary checks and the mutants ("the md5 is never compared" is red on (b); "SHORT never forces a second pull" is red on (c)). Case (a) is still the falsifier: the good pull sits in the middle of the sequence.
