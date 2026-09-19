# lane.branchprune — nothing deletes a lane branch, and two jobs walk them all

## The measurement, reproduced on this branch (2026-09-19)

```
total lane refs: 25, fully merged into origin/master: 8
```

The brief's numbers reproduce exactly. The eight:

| branch | tip | local head | worktree holding it |
| --- | --- | --- | --- |
| `lane/armsperf` | `630258bad7` | yes | `$WORK/wt/armsperf` |
| `lane/cloudwt` | `fc547df32e` | yes | `$WORK/wt/cloudwt` |
| `lane/jobsfix` | `5aa5354111` | yes | `$WORK/wt/jobsfix` |
| `lane/jobslabel` | `ecbc46f416` | yes | `$WORK/wt/jobslabel` |
| `lane/notespath` | `1eee0f08da` | yes | `$WORK/wt/notespath` |
| `lane/swizzle87` | `dffcb619bd` | yes | `$WORK/wt/swizzle87` |
| `lane/tier81fix` | `b2532b9fe4` | yes | `$WORK/wt/tier81fix` |
| `lane/toolsmith` | `baa5b32698` | yes | `$WORK/wt/toolsmith` |

## The thing the brief got slightly wrong, and it changes the design

**8 of 8 still have a local branch held by a lane worktree.** The brief framed
the worktree as a case to *handle*; it is the only case there is. `lane.sh rm`
is what removes those worktrees and it is not run on a fold, so a design whose
delete was `git branch -d` would have deleted *nothing at all*, on every one of
the eight, forever.

**And the ref that costs a tick anything is not the one you would reach for.**
`arms.sh:76` builds its `tips` list from `refs/remotes/origin/lane/*`, and its
fetch at line 71 uses `+refs/heads/lane/*:refs/remotes/origin/lane/*` — a
refspec with **no `--prune`**. So deleting the branch on `origin` alone leaves
the remote-tracking ref in `$REPO` standing, and `collect()` goes on walking it
every tick for the life of the repository. The remote delete is the visible
half; dropping the tracking ref is the half that actually buys back the time.

Three refs, and they are three different things:

| ref | who reads it | what `prune_branch` does |
| --- | --- | --- |
| `origin`'s `lane/<n>` | `gh`, a lane's push | deleted |
| `refs/remotes/origin/lane/<n>` | **`arms.sh` `collect()`**, the board | deleted — **this is the cost** |
| `refs/heads/lane/<n>` | nothing walks it | `branch -d`, which git refuses while a worktree holds it. Refusal logged, ref kept, never `-D` |

## Why this cannot un-arm a prediction

The arms job's `live_ancestor()` (`arms.sh:176`) asks whether a `b_ref` is an
ancestor of `refs/remotes/origin/master` **or of any lane tip**. A fold is
`--no-ff`, so every commit keeps its sha; if the branch is fully merged, every
commit on it is on the trunk, and the `origin/master` leg of that test carries
the ref on its own after the lane tip is gone.

That is the argument. The check is that the argument is *tested, not assumed*:
`prune_branch` refuses unless `merge-base --is-ancestor` passes, and it asks
against the commit the fold **just pushed** rather than `origin/$TIP`, which is
one fetch stale inside the fold worktree — and against what `ls-remote` says
origin holds **now**, not what the fold fetched, because a lane that pushed
after the merge's fetch has commits the fold never saw and deleting that ref
would destroy them.

Measured rather than argued: every `a_ref`/`b_ref` in every prediction file
reachable from the eight branches was resolved and re-tested against
`origin/master` alone. See `.refcheck` result in the PR body.

## What was built

`docs/testing/jobs/fold.sh`:

- `prune_branch <dir> <branch> <proof>` — the three-ref delete above, guarded
  on the name (`lane/?*` plus `git check-ref-format`) and on ancestry.
- called from the fold path as `prune_branch "$WT" "$branch" HEAD`, placed
  **after** the `push origin HEAD:$TIP` succeeds. A branch deleted on a fold
  that failed to push is work destroyed.
- `fold.sh prune` — the one-time sweep over every lane ref, **a dry run by
  default**; `fold.sh prune --apply` does it. Deleting refs on a shared remote
  should take saying so.
- `fold.sh prune-branch <dir> <branch> <proof>` — the same hidden-mode trick
  `resolve-notes` uses, so the self-test can drive it against a scratch remote
  with no fake `gh`.

## Did I run the sweep?

**No — deliberately, and the board should.** `fold.sh prune --apply` is ready
and the dry run is in the PR body. Two reasons for not firing it from the lane:

1. The code has not been reviewed or folded yet. Running a not-yet-audited
   deletion script against eight real refs on the shared remote is the exact
   shape of an outward-facing, hard-to-reverse action a lane should not take on
   its own initiative.
2. It is reversible only if someone wrote the shas down first — which is why
   they are in the table at the top of this file. `git push origin
   <sha>:refs/heads/lane/<n>` restores any of them exactly.

Once #137 folds: `bash docs/testing/jobs/fold.sh prune` to see the list, then
`--apply`. Note the *ninth* branch it will find by then is `lane/branchprune`
itself, which is correct — the fold path would have deleted it anyway.

## How the self-test checks were verified, and where they are inert

The gate is that a new check FAILS against the code it replaces. Run against
`origin/master`'s `fold.sh` with this branch's `selftest.sh`: **77 passed, 20
failed**. The 20 are every behavioural check of the new code.

The checks that *pass* against the old file are the must-not-move legs, and an
inert control is not a measurement, so each got a mutant:

| mutant | check that tripped |
| --- | --- |
| drop the `is-ancestor` check | `lane/live` is deleted → 3 checks fail |
| drop the `lane/?*` name guard | `board` is deleted → 4 checks fail |
| `branch -d` → `branch -D` | only the source-grep check fails (see below) |
| move the prune above the push | the line-order check fails |
| `branch -d` → `update-ref -d` | the worktree legs fail (see below) |

**The `-D` mutant is the interesting one.** `git branch -D` *also* refuses a
branch a worktree holds — the worktree check is not part of `-d`'s merge check.
So the behavioural leg ("the local head the worktree holds is KEPT") does **not**
discriminate `-d` from `-D`; only the `grep -nE "branch +-D"` source check does.
The mutant that genuinely forces past a worktree is `update-ref -d
refs/heads/<n>`, which has no worktree check at all and would leave the lane
worktree on a dangling HEAD. That is mutant 5, and it is what proves the
worktree legs are live.

Next lane: do not "simplify" `branch -d` into `update-ref -d` because the
ancestry was already proved. It is not the merge check that `-d` is there for —
it is the worktree check.

## What the next lane should not repeat

- Do not measure this problem by counting `refs/heads/lane/*`. Nothing walks
  those. Count `refs/remotes/origin/lane/*` in `$REPO`, which is what
  `arms.sh:76` enumerates.
- Do not assume a fold leaves `origin/$TIP` current in `$WORK/fold-wt`. It does
  not; the fold pushes `HEAD:$TIP` and only re-fetches into `$REPO`. Use `HEAD`
  as the proof commit there.
- `docs/ORCHESTRATION-DESIGN.md` §8.1 still describes the fold without
  mentioning the delete. It is outside this lane's files; a doc lane should add
  a line.
