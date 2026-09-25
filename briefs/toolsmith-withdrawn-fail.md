# arms.sh: a FAIL whose registered code is gone from the branch is `withdrawn`, not `regressed`

Lane: toolsmith (standing)            Issue: none (harness defect; decision #257 option 3)
Base: origin/master (PR #249, defects 0-10 of the dispatch-hardening brief, is folded as 93e356b9fd)
Files: docs/testing/jobs/arms.sh, one new `docs/testing/jobs/selftest.d/NN-arms-withdrawn.sh`
(two digits; the runner sorts `[0-9][0-9]-*.sh` by full name), docs/lanes/dispatch-hardening/NOTES.md
Needs device: no. Needs NDK: no. Prediction: none. This is harness work; the proof is the
fragment, the mutants and a falsification run against the old arms.sh.

## The defect (defect 11 of `briefs/toolsmith-dispatch-hardening.md`)

`arms.sh` recomputes a PR's `regressed` label from the newest verdict on disk.

A lane whose arm **refutes** its candidate reverts the code, which is the
correct outcome. That leaves a docs-only branch. A docs-only head builds
master's binary, so no arm can ever supersede the FAIL, and the PR stays
`regressed` forever.

- It happened on PR #252 (#224 family B). The only exits were an owner override
  that "records an acceptance that is not one" (#257, option 1) or re-landing
  the docs from a fresh branch with no prediction (option 2). The host did the
  second, as PR #259.
- #246 (#223) had the same shape, but it registered nothing, so it escaped.

## The job

A FAIL verdict is **withdrawn** when the branch head no longer touches any
file that the arm's b_ref changed against its a_ref.

1. Compute the arm's code files: `git diff --name-only <a_ref> <b_ref>`,
   restricted to paths outside `docs/`.
2. Compare them with `git diff --name-only origin/<tip>...<head>` for the PR.
3. If none of the arm's code files is still in the PR's diff, the verdict is
   withdrawn:
   - it does not make the PR `regressed`;
   - `arms.sh state` prints `withdrawn <prediction>`, so the record stays
     visible;
   - the verdict comment is untouched.

A PASS is never withdrawn by this rule. A FAIL whose code is still partly in
the diff stays `regressed`: a partial revert is not a withdrawal.

## Proof

- **The fragment,** with git fixtures, no shared state, and output words
  asserted, not only exit codes:
  - (a) a refuted-then-fully-reverted branch reads `withdrawn`, not
    `regressed`;
  - (b) a partly-reverted branch stays `regressed`;
  - (c) a branch whose FAIL code is intact stays `regressed`;
  - (d) a PASS on a branch with no code change stays whatever it was.

  Three candidate diffs where one must be chosen, so the right one sits in the
  middle.
- **Mutants, each red:**
  - drop the `docs/` restriction, so NOTES keep a FAIL alive;
  - treat any overlap as withdrawal, so (b) goes wrong.
- **A falsification run** against the real old arms.sh in a scratch worktree
  at `origin/master`. Never swap the file in place, and stage by name. (a) must
  be red for the reason this brief exists: the old code says `regressed`.
- **One real check:** run `arms.sh state lane/shadetie224` on the host. #252's
  branch still exists on origin, closed unmerged, and it must read `withdrawn`.
- `bash docs/testing/jobs/selftest.sh`: all green, with the totals in the PR
  body.

## Done when

- The fragment, mutants and falsification behave as stated.
- NOTES record it under "Defect 11".
- The PR carries the lane template with its `Files:` line.
- Preflight passes, and the PR is marked ready. It touches the verdict path, so
  it gets `needs-audit-1`, like #249.
