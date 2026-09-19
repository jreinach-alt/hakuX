# lane.armlabel — one label, many verdicts

PR #144. `docs/testing/jobs/arms.sh`,
`docs/testing/jobs/selftest.d/94-arms-label-state.sh`. No prediction: this is a
harness script and claims no pixels.

## The defect

`arms.sh` labelled a PR from the verdict in its hand:

```bash
*PASS*) label_add "$pr" verified  && label_rm "$pr" regressed
*FAIL*) label_add "$pr" regressed && label_rm "$pr" verified
```

Unconditional, per verdict. **The label is per-PR and the verdicts are
per-prediction**, so the label reported the most recently judged arm rather than
the state of the PR. On PR #102 that was four verdicts — #89 PASS, #88 FAIL,
#91 FAIL, #91 PASS — and at 2026-09-19T10:03Z the last was judged and flipped
the PR to `verified` with #88's failure live and nothing superseding it.

The direction is the whole problem. `roles/board.md`: a `regressed` PR is not
fold-ready and its lane is resumed with the verdict; a `verified` one proceeds
through audit. So this moved a PR *with a live regression* forward, and it is
structural rather than unlucky: a lane under remediation registers new
predictions **by design**, so every remediation could clear its own regression
label as a side effect of doing what it was told.

## The rule: supersession by issue number

For each issue, the newest registration's verdict counts and the older ones do
not; the PR is `regressed` if any issue's newest verdict is a FAIL. The
alternative considered was supersession by prediction *path* — only a
re-registration of the same file supersedes.

**Why by issue.** By-path has no in-band way for a lane to ever clear a FAIL.
A prediction is bound by the sha256 of its file, so a corrected prediction is a
new registration; in practice it is also a new *name*, because the model
changed and the name describes the model (`issue91-swap-solo-classification` →
`issue91-decline-frame-attribution`). The ARM ERROR path tells lanes in so many
words to "register a fresh prediction". Under by-path none of those supersede
anything, so a PR that once FAILed stays `regressed` until somebody with a
shell on the host deletes a file — and a cloud lane has no host disk at all.
A rule that never clears is not a fix, it is a stuck label; the board would
route around it and we would be back to labels nobody trusts. #102's #91 pair
is genuinely resolved and by-issue says so.

**The case that would make by-path right**, and it is a real one: an issue
whose evidence is deliberately split across several *independent* predictions
that must all hold at once — say #88 with one registration for the same-offset
colour path and another for the offset arithmetic. Those are not successive
models of one claim, they are two claims about one issue, and by-issue lets a
later PASS on one silently supersede an earlier FAIL on the other. If that
shape ever becomes normal here, the grouping key is the thing to change (one
line: `r["key"]`), not the rest of the machinery. It is not normal today:
every registration on file names one model of one issue and replaces its
predecessor.

**What supersedes nothing.** An `ERROR` marker and a `VERDICT: UNJUDGED` are
not verdicts — they set no label and they answer no outstanding FAIL. Missing
that would have been the original defect wearing a different hat: an errored
re-registration clearing a regression it never measured. Both are checked.

**A FAIL is never silently cleared.** Every decision is written to
`$WORK/arms/pairs/<sha>.label.md` as a table of every verdict on the branch and
whether it counts, that table is quoted into the `[job.arms]` comment, and the
comment names which verdict superseded which in prose as well. `arms.sh state
lane/<name>` recomputes the whole thing from disk with no device, no `gh` and
no judging — that is also what makes the decision testable without a scored
result directory.

## What the next lane should not repeat

- **The branch is the PR's identity in this computation**, because `pr_for()`
  resolves an open PR by head branch and a `gh` call per verdict was off the
  table (and would be wrong anyway: the PR is what we are labelling). The known
  limit: if one lane branch carried two PRs over time, a verdict judged under
  the closed one still counts toward the open one. Nothing on file does that,
  and by-issue supersession absorbs the common case, but a lane that starts
  reusing branches should look here first.
- **Cost.** The pair index is one pass over `pairs/` built once per tick, just
  before the judge loop; each decision then reads that file plus the handful of
  `judged/` markers on one branch. Do not put a walk of `judged/*` inside the
  loop over predictions — `bc7ccef95d` took two quadratics out of this file for
  exactly that reason and the tick is 11s.
- **`$ARMS` inside `check ... bash -c '...'` is unset in the child.** Three
  checks in the first draft of the fragment expanded it in the child shell, so
  they ran `bash state lane/selftest`, read an empty script from stdin and
  passed against anything. They were only caught because the *other* checks in
  the same block failed and made me read the block. Negations belong in the
  fragment's own shell.
- **The falsification.** `selftest.sh` run against `origin/master`'s `arms.sh`
  through a symlink tree (`falsify.sh`, not committed — the real path is never
  swapped): **17 of the 19 new checks fail**. That the old code did the actual
  defect, rather than merely failing to start, is carried by the shape of the
  first check: it is a *negation* over `DELETE .../labels/regressed` in the gh
  log straight after the #102 tick, so an `arms.sh` that crashed or wrote
  nothing would leave the log empty and make that check **pass**. It failed, so
  the old script ran the tick and cleared #88's live regression. (Do not try to
  read scenario 1's gh log out of the finished fake host: under the old file
  `arms.sh state` is an unrecognised mode that runs a whole ordinary tick, and
  the later `state` calls overwrite the log.) The two that pass are `a FAIL
  superseded by a later PASS does
  clear regressed` and `the PR is labelled verified`. Nine of the 17 reds are
  one reason — the old file has no `state` mode — so the load-bearing
  falsifiers are the six that drive the judge loop end to end; the `state`
  checks pin the rule's edges (ERROR, UNJUDGED, another branch, an unjudged
  pair), not the defect. The old code clears
  unconditionally, so it gets those right for the wrong reason. They are not
  falsifiers, they are the guard against fixing this into a label that never
  clears — which is the failure mode of the rule I rejected.
- The end-to-end checks drive the judge loop through a **stub `ab_compare.py`**
  reached by a symlink tree, because the real one needs two scored result
  directories with progress-log proof and what is under test is the labelling,
  not the comparison. `arms.sh` derives `$T` from its own `BASH_SOURCE`, which
  is what makes that substitution possible without touching the runner.
- Fragment `94` **clears `$WORK/arms/{pairs,judged}`** and leaves its own four
  fixtures there. Nothing after it reads them today; a fragment that starts to
  must say so in its own header.
