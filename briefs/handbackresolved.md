# handback.sh: do not resume a lane whose conflict is already resolved; finish the label swap it was waiting for

Lane: handbackresolved            Issue: none (harness defect, dispatched directly)
Base: origin/master
Files: docs/testing/jobs/handback.sh, docs/testing/jobs/selftest.d/99-handback-resolved.sh,
docs/lanes/handbackresolved/**
Needs device: no. Needs NDK: no. Prediction: none. This is harness work: the
proof is the selftest fragment, mutants, and a falsification run against the
old handback.sh.

## The defect, measured 2026-09-25

When fold.sh cannot merge a PR, it sets `needs-rebase`. handback.sh then
resumes the lane with "merge origin/master, resolve, push, then, **once CI is
green on the new head**, swap `needs-rebase` for `fold-ready`".

The lane does the merge and pushes. It cannot wait ten minutes for CI, so it
exits with the swap still to do. The PR still carries `needs-rebase` and no
unit is running, so the next handback tick resumes it again. Each resume spends
one of the lane's four attempts.

- **#234, lane.vshconst.** The second handback, at 13:50Z, reported "asked me
  to fix a merge conflict that no longer exists. PR #234 is waiting on CI, so
  I've stopped." That was a wasted attempt.
- **#237, lane.clrwb91.**
  - 14:18Z: the lane posts that the conflict is resolved and only CI is left.
  - 14:25:34Z: `[job.handback] Not resumed -- lane.clrwb91 has used every
    attempt`. The PR is labelled `blocked:needs-owner`, and the comment tells
    the board to open a decision-needed issue.
  - The head merged cleanly, its merged index checked, and CI went green
    minutes later. Nothing needed the owner. The host cleared it by hand.

## The job

In the `needs-rebase` path, before the liveness check, the cap and the resume,
ask whether the PR's current head still conflicts with `origin/$TIP`. Use
`git merge-tree --write-tree`, which is available on this host, on a fresh
fetch.

- **The head still conflicts:** resume, exactly as today.
- **It merges cleanly and CI on that head is GREEN:** the lane's own last step
  is all that is left. Do it here.
  - `gh-label.sh rm <pr> needs-rebase`, then `add <pr> fold-ready`.
  - Post one comment naming the head, its CI, and the merge base it was
    checked against.
  - No resume, and no attempt spent.
- **It merges cleanly and CI is PENDING:** do nothing this tick. That is
  waiting, not failing. Say so in the log, once per head.
- **It merges cleanly and CI is RED:** keep today's behaviour. A red head that
  already contains the trunk is a live failure, and the lane needs it back.
  Check it against the stale-CI cause (fold.sh `stale_handback`): the reason
  text should say which case it is.

Watch the known traps:
- **gh prints `""` for a pending conclusion**, and jq's `//` does not catch it.
  The row builder already classifies GREEN/RED/PENDING/NONE from
  `statusCheckRollup`, so reuse that and do not write a second classifier.
- **NONE (no runs at all) is NOT green.** A PR with a merge conflict gets zero
  runs (host memory "no CI run means a merge conflict").

## Proof (the "Done when" list reads these)

- **`selftest.d/99-handback-resolved.sh`**, built on `99-handback.sh`'s shims.
  A `needs-rebase` PR whose head:
  - (a) conflicts: resumed, as before.
  - (b) merges cleanly with CI GREEN: relabelled `fold-ready`; `lane.sh` NOT
    called, and the attempt counter unchanged.
  - (c) merges cleanly with CI PENDING: nothing called, nothing labelled.
  - (d) merges cleanly with CI RED: resumed.
  - (e) merges cleanly with CI NONE: not relabelled.

  Assert on the calls the shims record, and on output words, not only on exit
  codes.
- **One mutant per invariant,** each shown to turn its check red:
  - drop the merge-tree test (b resumes);
  - drop the GREEN condition (c relabels);
  - treat NONE as GREEN (e relabels).
- **A falsification run** of the fragment against the real old handback.sh.
  - Do it in a scratch worktree at `origin/master`; never swap the file in
    place, and stage by name.
  - (b) must go red for the reason this brief exists: the old code resumes a
    resolved lane. Count how many reds share that reason.
- `bash docs/testing/jobs/selftest.sh` is all green, with the totals in the PR
  body.

## Do not

- **Touch fold.sh.** lane.foldindex holds it, to regenerate index-only
  conflicts at fold time. The two changes meet only at the labels, and the
  labels are the interface.
- **Change the cap, the attempt counter, or the draft-strand path.**
- **Trigger CI as a self-check.**

## Done when

- The fragment and mutants are green and red as stated.
- The falsification reds are recorded in NOTES.
- The PR carries the lane template with its `Files:` line.
- Preflight passes, and the PR is marked ready.
