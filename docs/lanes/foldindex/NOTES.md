# lane.foldindex: fold.sh regenerates an index-only conflict over pinned trees

Brief: `briefs/foldindex.md` (harness defect, no issue). Base: master @ 84a67b9cf8.

## What changed

`docs/testing/jobs/fold.sh`

- `resolve_index_only <wt>` sits beside `resolve_root_notes`. It resolves only
  when the unmerged set is exactly `docs/testing/nv2a_index.json`, both
  stage-2 and stage-3 copies name the same `provenance.tests_commit`, and both
  pins can be set up. Then it stages master's side (`--ours`: the fold
  worktree is detached at `origin/$TIP`). Anything else returns 1 and the PR
  is handed back exactly as before, with the same label, cause file and
  comment. When the index was the whole conflict but a gate refused it, the
  tick log gets one extra line saying why.
- The merge commit carries a second paragraph. It says the index conflicted
  and master's copy was taken, and it names the two pinned commits the gate
  below checks and rebuilds over.
- `regen_index <wt> <pr>` replaces the inline index gate, and both clean
  merges and resolved ones use it. It runs over detached worktrees at
  `$WORK/fold-pins/{nxdk_pgraph_tests,pbkitplusplus}`. They are created from
  the host checkouts (`TESTS`/`SUPPORT`, still `find_repo`), sit at exactly
  the index's `tests_commit` and the workflow's `PBKIT_SHA`, and are
  refreshed in place when a pin moves. A commit that is not present locally
  is never fetched. After a build the result must `check`, and it must have
  at least as many suites as `HEAD^1`'s and `HEAD^2`'s index.
- Failures:
  - resolved conflict, and the rebuild fails, does not check, or loses a
    suite: `failed/<pr>-<head>`, the existing index-failure comment plus the
    reason, and a hand-back (`needs-rebase` plus a cause file naming the
    index).
  - clean merge, rebuild fails: same as before, `failed/` and the "Needs a
    person" comment.
  - clean merge, pins unavailable or no index in the tree: the gate is
    skipped with a note, which is what a host without the sources always
    did.
- New modes: `resolve-index <wt>` and `regen-index <wt> [pr]`. They print the
  refusal reason on stderr.
- The conflict hand-back block became `hand_back()`, so both paths write the
  same label and cause file. Its text is unchanged.

`selftest.d/90-fold-index.sh` is new and holds 31 checks:

- (a) to (d) from the brief;
- the pinned-path check: the stub `nv2a_index.py` records its args and the
  `HEAD` of each tree, and the pin is the middle commit of three;
- a moved pin is refreshed in place;
- a rebuild that loses a suite is refused and commits nothing;
- three real `fold.sh` ticks against a bare origin: pins unavailable means an
  ordinary hand-back; a lost suite means a hand-back with the reason; an
  index-only conflict folds, with the regenerate commit on top of a merge
  that holds master's copy;
- the three mutants, built inside the fragment by `sed` on a copy of the
  jobs dir. Each one first checks that its `sed` changed the file.

`selftest.d/99-handback.sh` (added to `Files:`; the brief did not name it).
It had a static check, "fold.sh still resolves no conflict itself", that
failed on `checkout --ours`. Spelling the resolution as `git show :2:` would
have dodged the grep, but that games the guard, so I narrowed the guard
instead. The rule is now: no merge strategy, exactly one `checkout
--ours|--theirs` line, it is `checkout --ours -- "$INDEX"`, and `INDEX` is the
generated index. The cause-path check (`handback/cause/$pr-$head`) had been
passing only because `stale_handback` matched it, so `hand_back()` now uses
named locals and matches it by itself.

## Measured

- `bash docs/testing/jobs/selftest.sh`: **1212 passed, 0 failed**. Run
  standalone, the new fragment gives 31 passed, 0 failed.
- Mutants, each red on its own check:
  - `onepath` (delete the exactly-one-path test): (b) red. The index got
    staged, leaving only `UU src.c`.
  - `samepin` (the `tests_commit` comparison becomes `true`): (d) red. The
    mismatched sides resolved cleanly.
  - `livetree` (`--tests "$TESTS"` in place of the pin): the pinned-path
    check is red. The stub recorded `tests=<live checkout>@<commit 3>`.
- **Falsification run.** New fragment, old `fold.sh`, from a scratch worktree
  at `origin/master` 84a67b9cf8. The fragment was sourced from this branch
  with `HERE` pointing at the old jobs dir, so nothing was copied or staged.
  Result: 5 ok, 14 FAIL. There were no import or path errors. The old script
  has no `resolve-index` mode, so it ran an ordinary no-op tick (status.sh
  via shims) and exited 0.
  - **5 reds: the index-only conflict is left unmerged (handed back).** (a),
    the pinned-path check, the moved pin, the suite-loss refusal and its
    message. The last three die at `git commit` with "you have unmerged
    files" on the index.
  - 3 reds: (b), (c), (d). They go red only because the old script exits 0
    where a refusal exits non-zero. The tree itself is untouched, which is
    what those checks assert about the state.
  - 3 reds: the new refusal reasons (c ×2, d ×1) do not exist in the old log.
  - 3 reds: the mutants' "the sed applied" checks, because the lines they
    mutate do not exist in old code.
  - The end-to-end ticks were added after this run and were not part of it.

## For the next lane

- `nv2a_index.py build` has its own gates (`tests_provenance_gate`,
  `suite_removal_gate`) against the index next to the script, which is the
  staged master copy. Over the pins, both pass by construction. The suite
  check in fold.sh also covers the branch's side, which those gates cannot
  see.
- Nothing in `handback.sh`, `nv2a_index.py` or the workflow needed to change.
- On the host, the first resolved fold creates `~/nxdk_pgraph_tests/.git/worktrees/`
  and `~/pbkitplusplus/.git/worktrees/` entries for the pins. Those entries
  are expected.
- Do not make this general. Another generated file needs its own pins and
  its own brief.
