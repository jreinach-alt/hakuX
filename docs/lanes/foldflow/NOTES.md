# lane.foldflow -- the fold pipeline must not freeze the backlog

Brief: `briefs/foldflow.md` (host, 2026-09-26). Files: `docs/testing/jobs/fold.sh`,
`docs/testing/jobs/selftest.d/73-fold-repair.sh`, `74-fold-multi.sh`, this file.

## What was wrong (measured in `$WORK/logs/fold/tick.log`)

- The CI gate came before the conflict path. GitHub runs no CI on a PR that
  does not merge, so a conflicting PR read `CI is NONE ... waiting` on every
  tick and never reached the index resolver. Examples: #268 and #321 from 21:00
  to 21:46 PDT on 09-25, and #317 at 22:06 and 22:15.
- The fold loop stopped after one fold per tick (`[ "$folded" -eq 0 ] || ... one fold per tick`).
  At 22:26 four PRs (#352 #353 #355 #359) were ready and waiting behind one fold.

## What fold.sh does now

1. **Conflict pass, first thing each tick** (`conflict_pass`). It checks every
   open, non-draft PR labelled `fold-ready`, `needs-audit-1`, `needs-audit-2`
   or `needs-rebase`. The list API's `mergeable` is used, and an UNKNOWN is
   asked again per PR with `gh pr view`. A CONFLICTING or still-UNKNOWN PR is
   then checked with `git merge-tree --write-tree --name-only` against a
   fresh fetch of the trunk. merge-tree has the last word: when GitHub says
   CONFLICTING and merge-tree says clean, the PR is logged as stale and
   waits.
   - **Index-only conflict** (`repair_index_conflict`). These are the host's five
     steps, in `$WORK/fold-wt`:
     1. Merge the lane into origin/master with `--no-ff --no-commit`.
     2. `resolve_index_only` (unchanged), then commit.
     3. `regen_index` over the pins, which also runs `check`.
     4. Check the lane head is an ancestor and that `ls-remote` still shows it.
     5. Push `HEAD:refs/heads/<branch>` without force, so origin rejects
        anything that is not a fast-forward.

     It refuses and waits a tick when the lane's unit is active (checked
     before and after the repair), when the branch moved, or when the push
     is rejected. It refuses and hands back when the resolver refuses (two
     tests_commits, no pins), when the regen fails, or when the branch is a
     remote lane's. `lane/*` and `claude/*` branches are repaired. A `claude/*`
     branch has no local unit to check, so the fast-forward-only push is the
     guard there.
   - **Any other conflict** (`conflict_handback`). It calls `hand_back` (sets
     `needs-rebase` and writes the cause file listing the files) and comments.
     handback.sh runs at the end of the same tick and resumes the lane. When
     `$WORK/attempts/<lane>` is at least `LANE_MAX_ATTEMPTS` (4), the PR gets
     a `[job.fold] decision-needed:` comment instead of a resume that would
     be refused. The PR's audit label is kept.
   - Each head is acted on once (`$F/failed/<pr>-<head>-conflict`). A PR the
     pass answered for is skipped by the CI gate that tick, so it never gets
     the misleading "no CI run exists / skip marker" comment.
2. **Up to `FOLD_MAX_PER_TICK` (3) folds per tick.** The gate loop now
   collects READY rows, and the fold body is `fold_one`, unchanged except
   that each `continue` became `return 1`.
   - Order: a score, then PR number. The score counts board issues with
     `dispatch_state = "available"` that no lane row claims and whose files
     intersect the PR's diff. An issue's files are the ones nv2a_index.json
     puts its suites' register sites in (`fold_priority`).
   - That score is a proxy: no structured issue-to-file map exists on the
     board, and `fleet.py` has none either. This is where the brief's premise
     that "fleet.py knows the holders" did not hold.
   - A PR folds only if its files, the index excepted, are disjoint from the
     PRs already folded this tick. A PR whose files cannot be read folds only
     as the first of a tick.
3. **A red trunk after a multi-fold tick** (`attribute_multi`). Each tick
   with two or more folds writes `$F/multi/<tip>`. Later ticks read master's
   CI on that tip through `gh api .../check-runs`, classified by
   `TRUNK_CI_JQ`, which ignores CANCELLED runs.
   - While that CI is pending, at most one fold per tick.
   - On RED, if the base was not already red, the last fold of the tick (its
     merge plus any index commit) is reverted and pushed, and nothing folds
     until the revert's CI answers.
   - If the revert is GREEN, the PR is named "red together with" the others
     in a comment and in the tick log. It is not labelled: the fold deleted
     its branch and GitHub closed it as merged, so re-landing it means a new
     PR, and the comment gives the steps.
   - If the revert is RED, the fold is re-landed and the other PRs are named
     as suspects for a person to decide.
4. **One summary line per tick** in tick.log:
   `tick: repaired #..; folded #..; handed back #..; waiting #..(why)`.
5. A PR that carries an audit label as well as `fold-ready` does not fold.
   This can happen when an audit PR is handed back and handback.sh later
   swaps `needs-rebase` for `fold-ready`. The audit label counts, and nothing
   is removed.

## Proof

- `selftest.d/73-fold-repair.sh`, 30 checks. They drive real ticks against a
  scratch origin:
  - An index-only conflict is repaired and pushed: fast-forward, master's
    index taken, then regenerated.
  - A code conflict is handed back, and handback.sh resumes the lane in the
    same tick.
  - The refusals: unit running, attempt 4 of 4, and mismatched
    tests_commits.
  - Mutants: no conflict pass; no unit check.
- `selftest.d/74-fold-multi.sh`, 27 checks:
  - Two disjoint PRs fold in one tick.
  - `FOLD_MAX_PER_TICK=1` caps it.
  - Two PRs on the same file fold in two ticks. The file has ten lines and
    they edit different ones, so the same-file rule holds them apart and not
    a merge conflict.
  - The revert attribution, end to end, including "no folds while the
    revert is pending".
  - A red base is not attributed to the tick.
  - The trunk-CI jq runs through the real jq.
  - Mutant: no shared-file test.
- Live, read-only (`fold.sh list` from this branch, 2026-09-25 22:26 PDT, against the live PRs):

  ```
  #317 lane/fmv303 @ c21c60ed19: CONFLICTS in docs/testing/nv2a_index.json alone; WOULD REPAIR on the lane branch
  #343 claude/docs-tooling-agentic-coding-u152m1 @ 82d7c22908: CONFLICTS in docs/testing/nv2a_index.json alone; WOULD REPAIR on the lane branch
  #352 lane/xbox-notes @ da08566e9f: WOULD FOLD (score 0)
  #353 lane/turnipfork @ e71f2ca485: WOULD FOLD (score 0)
  #355 lane/xbox-litprime @ 7b09aa6cde: WOULD FOLD (score 0)
  #359 lane/xbox-y16low: WOULD WAIT: 3 folds this tick
  ```

  At that moment the live job had logged `#317 lane/fmv303: CI is NONE ...
  waiting` at 22:06 and 22:15, which is the freeze this fixes. The live
  **acting** tick line (`tick: repaired ...`) appears only after this PR
  folds and the host's fold job runs the new fold.sh.

## Do not repeat

- Don't run an acting `fold.sh` tick from a lane branch against the live
  host to get a tick.log line. The host timer ticks about every 10 minutes
  and shares `$WORK/fold-wt`.
- Don't hand back an attributed PR with `needs-rebase`. After the fold its
  branch is deleted and its PR is closed as merged, so nothing reads that
  label.
- The index must be excluded from the disjointness test. Every hw PR touches
  it, so without that exclusion no two hw PRs could ever share a tick.
- `.status` / `.conclusion` from check-runs: a CANCELLED run from a
  superseded push is not red.
