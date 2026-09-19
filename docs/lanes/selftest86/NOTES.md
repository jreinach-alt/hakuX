# lane.selftest86 -- `selftest.d/86-fold-regressed.sh` was red on every run

Brief: `briefs/selftest86.md`. Harness defect, no tracker issue.
Files: `docs/testing/jobs/selftest.d/86-fold-regressed.sh` (the only change),
`docs/lanes/selftest86/NOTES.md`. `docs/testing/jobs/fold.sh` was NOT touched.

## The state before

`bash docs/testing/jobs/selftest.sh` on `origin/master` (`732b97e2df`):
**516 passed, 10 failed**, all ten in fragment 86, with twelve copies of

    error: src refspec lane/foldreg does not match any

interleaved. `selftest` is a required check, so this was red on master and on
every open harness PR at once; PR #152 and #155 were `fold-ready`, green on
both `build` jobs, and could not fold.

## The cause, and the general shape of it

Fragment 86 builds its own repository and its own `lane/foldreg` at setup, then
`fr_reset()` put the world back between ticks with

    git -C "$FR/repo" push -q -f origin master lane/foldreg

which reads the LOCAL `refs/heads/lane/foldreg` in `$FR/repo`. `fold.sh`'s
`prune_branch()` deletes that ref -- `fold.sh:170` on origin and `fold.sh:178`
locally, in `$d` = `$REPO`, and this fragment sets `$REPO` to its own fixture
repo through `HAKUX_REPO_DIR`. So the first tick that really folded (the
positive control at what is now line ~124) destroyed the fixture every later
check needed, and each later `fr_tick` ran against an origin that still carried
the previous fold.

`prune_branch` is not the bug and was not changed: deleting the local branch is
deliberate and `fold.sh:176-178` says why. The fixture predates the feature.
The shape is worth naming because it will recur: **adding a step to a job's
tick makes every existing fixture for that job drive the new code.** Fragment
86 was written against a `fold.sh` that never deleted anything, and it was
correct until the tick it drives grew a cleanup phase.

## The change

Two lines of mechanism in `86-fold-regressed.sh`, plus one new check.

1. `FR_LANE_SHA` is captured once at setup, right after the branch is pushed.
2. `fr_reset()` recreates the ref unconditionally --
   `git update-ref refs/heads/lane/foldreg "$FR_LANE_SHA"` -- before the
   force-push, and the force-push now reports through `bad` if it fails
   instead of writing to stderr and letting the checks below misfire.
   Unconditional, not "if missing": it restores the exact state the checks were
   written against whatever the tick did to the ref.
3. New check, `fr_fixture_intact`, run at the first `fr_reset` that follows a
   folding tick: both refs are back and origin's master carries no fold. The
   lost state used to be visible only as a git stderr line in the middle of a
   run that was still printing check names; now it is a check with a name.

## What was proved, and how

`bash docs/testing/jobs/selftest.sh` on this branch: **527 passed, 0 failed**
(516 + the 10 recovered + the 1 new check). Whole suite, not fragment 86 --
fragment 85 is the other fold-gate fragment and is green in that run.

A green fixture that has merely stopped erroring is not a fixture that tests
anything, so four mutants were run. Each was applied to a **copy** of `fold.sh`
inside a symlink farm of the repository (`.scratch/mkmirror.sh`, not committed)
whose `selftest.d` holds only fragment 86 -- the real `fold.sh` never left the
tree, and the verdict is that fragment's alone. Control: the unmutated copy,
47 passed, 0 failed.

| mutant | reds | which |
| --- | --- | --- |
| the `regressed` gate removed entirely (`if false`) | 26 | the whole gate, both comments, list mode |
| `has_label` matches a substring | **1** | "a label that merely CONTAINS the word is not the verdict" |
| a bare `regression-accepted` taken as an override | 13 | the malformed-override family only |
| `fr_reset` no longer recreates the ref (the fixture itself) | 24 | the new self-check, the loud `fr_reset` FAIL, and the original ten |

The second row is the one that matters most: one mutant, exactly one red, and
not the same red as the others. Three mutants with one shared cause would show
only that the gate exists; these separate its cases. The fourth is the
falsifier for the new check -- without the `update-ref`, `fr_fixture_intact`
goes red and the original ten failures come back, so the fix is load-bearing
and the check is not a tautology.

Checks that run AFTER the first fold (`regression-accepted:none`,
`regression-accepted:91x`, the list-mode pair, the whole-label one) were
failing unconditionally before this change and are now live: they pass on a
correct `fold.sh` and go red on a mutant. That is the difference between
"no longer erroring" and "testing something".

## For the next lane

- The territory row was already there. The board wrote `[lane.selftest86]` at
  its own tick, naming exactly the two files this brief told the lane to claim,
  before the lane got to it -- so nothing was pushed to `origin/board`. If you
  are briefed to write your own row, read it first: `.scratch/claim.py` in this
  lane's history refused to write a second one, which is the right outcome.
- `[lane.cloudterritory]` holds the glob `docs/testing/jobs/selftest.d/**`.
  `check_territory.py` compares file claims by **exact string**, so that glob
  collides with nothing and protects nothing. It is not this lane's to narrow,
  but the next lane to touch a fragment should know the glob is not a fence.
- `[lane.nightlynotes]` claims `docs/testing/jobs/selftest.d/86-nightly-notes.sh`
  (PR #152, fold-ready). That is a **second fragment numbered 86**; both will
  source, `86-fold-regressed.sh` first by `LC_ALL=C sort`. Nothing breaks, but
  the numbering is no longer unique and a reader who greps for "86" gets two.
- **The same trap is latent in `91-fold-transient.sh`.** It also drives the
  real `fold.sh` with `HAKUX_REPO_DIR` pointed at its own fixture repo
  (`lane/foldtr`, `lane/foldtr-board`), and its `ft_reset` restores nothing at
  all. It is green today only because every tick in it is *meant* to fail a
  preflight gate, so nothing ever folds and `prune_branch()` never runs. The
  day 91 grows one successful-fold case it inherits this bug exactly. Not
  fixed here: 91 is not this lane's file and changing it would be a claim on
  somebody else's fragment for a failure that does not exist yet. Whoever adds
  that case should capture the sha at setup the way `fr_reset` now does.
  Checked the rest: no other fragment force-pushes a lane ref it assumes
  survived a tick.
- Do not chase this class of failure by reading the check names. The run
  printed plausible check names for forty lines while measuring a fixture that
  had already collapsed; what identified it was the git stderr line nothing
  had turned into a check. The rule that follows is in the fix: a fixture's
  restore step should FAIL loudly, not on stderr.
