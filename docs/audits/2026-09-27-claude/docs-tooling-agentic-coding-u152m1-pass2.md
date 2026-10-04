# Audit pass 2: PR #480, lane.remote, #461 memo retirement (M1)

Head verified: `8c02ea77`. That is pass 1's head `a53261f9` plus only the pass-1
audit file. CI is green on it (build, build, check), and the PR is mergeable.

**Verdict: clean.** Pass 1 found no HIGH or MEDIUM. Both of the items it left
for pass 2 hold, so the PR goes to `fold-ready`.

## The pass-1 items, checked

1. **`b_ref` is still the code under review.** `git diff 8f9c74f0 8c02ea77 -- hw/`
   is empty, and nothing after `8f9c74f0` touches `hw/`:
   `7dd4b495`, `fa04ca20`, `a53261f9` and `8c02ea77` are tooling, prediction,
   NOTES and audit commits. Both predictions stay bound to the code they
   describe, so neither needs re-registering.
2. **The correctness arm has not reported yet.** There is no `[job.arms]`
   verdict for `remote-461-memo-texture.json` on the PR. The only `[job.arms]`
   comment is the expected SKIPPED for `remote-461-memo-perf-crimson.json`,
   a title soak that is read by hand, as the PR body says. Pass 1 made the
   `txt_A8R8G8B8_ADD` band check conditional on the arm having reported, so
   it does not block. The fold does not wait on it either: `fold.sh` blocks
   only on `regressed`, and the arms job judges the prediction whether it
   runs on the lane ref or on master. If that arm comes back FAILED, the
   `regressed` label is the gate that catches it.

## LOWs

- **LOW-1** (`diag_download_surface()` sets no dirty bit): unchanged. Pass 1
  said no remedy was needed, and the gap was already there before this PR.
- **LOW-2** (`tex461_read.py` on a 29 February stamp read in the next year):
  unchanged. It can only happen with a logcat spanning more than six months,
  so no remedy is needed.

Nothing is left for this PR.
