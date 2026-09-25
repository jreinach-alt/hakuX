# fold.sh: resolve a conflict in the generated nv2a index by regenerating it, not by handing it back

Lane: foldindex            Issue: none (harness defect, dispatched directly)
Base: origin/master
Files: docs/testing/jobs/fold.sh, docs/testing/jobs/selftest.d/90-fold-index.sh,
docs/lanes/foldindex/**
Needs device: no. Needs NDK: no. Prediction: none. This is harness work: the
proof is the selftest fragment plus a falsification run against the old
fold.sh.

## The defect, measured this morning (2026-09-25, `$WORK/logs/fold/tick.log`)

Every PR that changes a line under `hw/` also regenerates
`docs/testing/nv2a_index.json`, which the `nv2a-index` CI job requires. The
index records a line number for every register site. So whenever fold.sh folds
one such PR, every other open hw PR now conflicts with master in that file.
fold.sh resolves nothing except a root `NOTES.md`, so each of those PRs goes to
`needs-rebase`, and `handback.sh` spends a lane session on it.

- 06:40: #234 CONFLICT in `docs/testing/nv2a_index.json`, then #235, same file.
- 06:50: #237, same file.
- 07:10: lane.clrwb91 resumed for it (attempt 3). lane.vshconst was resumed
  twice for #234 and lane.shadeflat224 once for #235.

Each resolution is mechanical, and handback.sh's own text says so: "a generated
file is regenerated, not hand-merged". The next fold (#235) will do it again to
#234 and #237.

## The job

fold.sh already regenerates the index after a CLEAN merge that leaves it stale
(the `# The index: regenerate if the merge moved it` block after the merge).
What it lacks is the step before that: accepting a merge whose ONLY conflict is
that file.

1. **`resolve_index_only`**, beside `resolve_root_notes` and shaped like it.
   - It applies only when the unmerged set is exactly
     `docs/testing/nv2a_index.json`. Any other unmerged path means a hand-back,
     exactly as today.
   - It stages master's side (the fold worktree is detached at `origin/$TIP`,
     so that is `--ours`). The existing regenerate step below then rebuilds it
     over the merged tree. Commit the merge with a second `-m` paragraph that
     says the index conflicted, master's copy was taken, and it was regenerated
     below. It must not read as a clean fold.
   - Give it a `resolve-index` mode, like `resolve-notes`, so the fragment can
     drive it without a GitHub round-trip.
2. **Regenerate over the PINNED trees, not the host's live checkouts.** Today
   `TESTS`/`SUPPORT` are `find_repo` results: whatever `~/nxdk_pgraph_tests`
   and `~/pbkitplusplus` hold. CI regenerates nothing. It checks the index
   against nxdk_pgraph_tests at the index's own `provenance.tests_commit`, and
   pbkitplusplus at `PBKIT_SHA` in `.github/workflows/nv2a-index.yml`. A fold
   that regenerates from a checkout at any other commit can:
   - silently drop a suite while fixing line numbers (it has happened; see the
     host memory "index regeneration needs a dated tests tree");
   - or turn master's own CI red after the fold.

   So resolve both commits the way CI does. Use detached worktrees of the host
   checkouts at exactly those commits, kept under `$WORK/fold-pins/`, and
   refresh them when a pin moves.
   - If either commit is not present locally, hand the PR back as today and say
     why in the log. Do not fetch a different commit and carry on.
   - If master's index and the branch's index name different `tests_commit`s,
     hand it back: that is a decision, not a regeneration.
   - The host's `~/nxdk_pgraph_tests` currently shows a modified
     `third_party/nxdk` submodule pointer and two untracked build directories.
     A pinned worktree makes that irrelevant, which is the point.
3. **Refuse loudly rather than fold a wrong index.**
   - If the regeneration fails, or the result does not `check`, or it has fewer
     suites than either parent's index, write `failed/`, comment as the current
     index-failure path does, and hand back.
   - A merge that regenerates cleanly continues to the existing local gates and
     the push, unchanged.
4. **The comment and label behaviour for every other conflict stays exactly as
   it is.** That is `needs-rebase`, the cause file for handback.sh, and the
   existing comment text.

## Proof (the "Done when" list reads these)

- **`selftest.d/90-fold-index.sh`**, with its own git fixtures and no shared
  state, modelled on `90-fold-notes.sh`:
  - (a) An index-only conflict resolves, and the staged file is master's copy.
  - (b) An index conflict plus one source file is refused, with nothing staged
    or changed.
  - (c) With the pins unavailable, it is refused.
  - (d) With `tests_commit` differing between the two sides, it is refused.

  For the regeneration itself, stub `nv2a_index.py` with a script that records
  its `--tests`/`--support` arguments. Then assert the pinned paths were passed,
  not the `find_repo` ones. Put the correct answer in the MIDDLE of three
  candidates, so first-wins and last-wins mutants both fail. Do not use grep on
  prose to decide a check: anchor on the call.
- **One mutant per new invariant**, each shown to turn its check red:
  - delete the exactly-one-path test;
  - drop the pin comparison;
  - pass `$TESTS` instead of the pinned path.
- **A falsification run** of the new fragment against the real old fold.sh.
  - Do it in a scratch worktree at `origin/master`, never by swapping the file
    in place. Stage by name, because `git add -A` there sweeps up the whole
    old-code tree.
  - It must be red for the reason the fragment exists (the index-only conflict
    is handed back), not for an import or path error. Count how many of the
    reds share that one reason.
- `bash docs/testing/jobs/selftest.sh`: every fragment green, with the totals in
  the PR body.

## Do not

- **Touch `handback.sh`, `nv2a_index.py` or the CI workflow.** If you think one
  of them needs changing, say so in NOTES and in the PR body.
- **Resolve any other generated file the same way.** One file, named, with its
  pins. Anything more general is a separate brief.
- **Trigger CI as a self-check, or open the PR before the selftest is green.**
  Pushes to the branch are free; the PR's runs are not.

## Done when

- The fragment and mutants above are green and red as stated.
- The falsification run's reds are recorded in NOTES.
- The PR carries the lane template with its `Files:` line.
- Preflight passes, and the PR is marked ready.
