# lane.handbackresolved

Brief: when `handback.sh` finds a `needs-rebase` PR, stop resuming a lane
whose conflict it has already resolved, and do the `needs-rebase` ->
`fold-ready` swap the lane was waiting to do.

## The defect

`resume_rebase` tells the lane to merge, push, and then, once CI is green,
swap `needs-rebase` for `fold-ready`. A lane cannot wait ten minutes, so it
exits with the swap still to do. The next tick sees `needs-rebase`, a new
head and no unit running, and resumes the lane again. That cost #234 an
attempt, and it labelled #237 `blocked:needs-owner` while its head was clean
and CI was about to go green (2026-09-25).

## What changed (`docs/testing/jobs/handback.sh`)

In the label path, straight after the stale-label skip (so before the lane
name, the marker, the liveness check, the cap and the resume), a
`needs-rebase` row gets `merge_state`:

- It fetches `origin/$TIP` into its tracking ref, once per tick, in
  `$HAKUX_REPO_DIR`. If this object store does not have the row's head, it
  fetches the branch too.
- Then it runs `git merge-tree --write-tree --no-messages <tip> <head>`:
  - exit 0 is CLEAN;
  - exit 1 is CONFLICT;
  - anything else, a failed fetch or a missing object is UNKNOWN.

Only CLEAN changes anything. CONFLICT and UNKNOWN fall through to exactly the
old path.

If the head is CLEAN, `head_ci` reads `headRefOid` and the CI state with a
single `gh pr view`.

| CI on the clean head | action |
|---|---|
| GREEN | `label_rm needs-rebase`, then `label_add fold-ready`. One comment names the head, `master` at the tip sha and GREEN. No resume, no attempt, brief untouched. |
| PENDING | Nothing. It is logged once per head (`done/pending-<pr>-<head>`). No marker, no label, no comment. |
| RED | Resume as before. The comment and brief say which case applies: the stale-CI cause (cause file `action=resume_stale_ci`), a head that already contains the tip (a live failure), or a conflict that no longer reproduces. |
| NONE | Resume as before, and say there is no CI run, which is not green. Never relabelled. |
| head moved | `headRefOid` != the row's head. Nothing this tick. |

There is one classifier. The jq that turns the rollup into
GREEN/RED/PENDING/NONE is now `CI_STATE_JQ`, a jq `def ci_state`. The draft
pickup (`stranded_drafts`) and `head_ci` both prefix it. `""` (a running
check) still reads PENDING, and an empty rollup reads NONE.

I did not touch fold.sh, the cap, the attempt counter or the draft-strand
path.

`99-handback-draft.sh` needed two small edits, so it is on the PR's `Files:`
line:

- Its query round-trip now expands `$CI_STATE_JQ`.
- Its verb check now allows `gh pr view`, which is a read.

## Proof

`selftest.d/99-handback-resolved.sh` sets up a real bare origin and a real
clone. It builds a trunk commit, a conflicting head, a clean head and a clean
head that has merged the trunk, and points `HAKUX_REPO_DIR` at the clone. It
covers:

- cases (a) to (e) from the brief;
- the stale-CI and live-failure variants of (d);
- a head that moves between the pickup and the CI read;
- `head_ci`'s jq run through the real jq.

`bash docs/testing/jobs/selftest.sh` on ead5e3a6fe: **1248 passed, 0 failed**.

### Mutants and falsification

Each run was a full selftest in a scratch worktree, using
`docs/lanes/handbackresolved/mutants.sh HEAD <scratch> <case>...`.

| run | total | reds in this fragment | red on the invariant |
|---|---|---|---|
| no-merge-tree (`MERGE_STATE=UNKNOWN`) | 1227 / 21 failed | 21 | (b) `lane.sh is NOT called` goes red: b resumes |
| no-green (relabel any clean head) | 1233 / 15 failed | 15 | (c) `is not relabelled` goes red: c relabels |
| none-is-green (`GREEN\|NONE)`) | 1245 / 3 failed | 3 | (e) `not relabelled` goes red: e relabels |
| **old handback.sh** (origin/master @ f25ceaf66e) | 1221 / 27 failed | 26 | (b) resumes a resolved lane |

The 27 reds against the old handback.sh break down like this:

- **15 are the reason this brief exists: the old code resumes a lane whose
  head merges cleanly.**
  - (b) 9: it resumes, calls lane.sh, bumps the attempt counter, appends to
    the brief and never relabels.
  - (c) 5: it resumes a PENDING head.
  - 1: it resumes on a head that moved.
- 6 are reason text the old code cannot produce, on resumes it does
  correctly: 4 in (d), 1 in (e) and 1 for the moved head.
- 5 are `head_ci` / `CI_STATE_JQ` checks on functions the old code does not
  have.
- 1 is outside the fragment: the draft fragment's verb check expects the new
  `gh pr view`.

## For the next lane

- In the selftest, `HAKUX_REPO_DIR` is the real checkout. The other handback
  fragments (99-handback, 99-handback-draft) use fake shas, so `merge_state`
  reads UNKNOWN for them after one real `git fetch origin master` in that
  checkout, and they take the old path unchanged. That fetch is the only
  side effect.
- Do not move the check below the marker check. A head resumed once could
  become clean and green later (for example if the trunk reverts the
  conflicting commit), and it should still be relabelled.
