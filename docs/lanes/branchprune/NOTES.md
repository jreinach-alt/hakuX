# lane.branchprune — nothing deletes a lane branch, and two jobs walk them all

## Why attempt 1 did not finish

It finished the work and did not say so. Every part of the brief was built,
the self-test was green, and CI went green on `f567c9cf18` — and the session
ended with **PR #137 still a draft**, because it ended *waiting* for that CI
rather than returning to mark the PR ready once it passed.

A draft is invisible to every actor here: `board.sh` skips drafts, `fleet.py`'s
READY-NOT-FOLDED does not count them, `fold.sh` folds only non-drafts, and
`handback.sh` never looks at them. So the cost of not typing `gh pr ready 137`
was not a delay, it was a PR that would have sat there until a person noticed —
and a whole resumed session to type one command. From outside, silence and
unfinished look identical.

What attempt 2 did: merged the 120 commits `master` had moved (one real
conflict in `fold.sh`, resolved by keeping both additions — see below), moved
the checks out of `selftest.sh` into `selftest.d/97-fold-branch-prune.sh` now
that the split had landed, re-ran the gate, and marked the PR ready. No part of
attempt 1's design was redone.

**The rule this lane pays for:** mark ready when the work is green and current,
not after the last possible re-merge. A ready PR that needs one more merge is a
visible task; a draft that needs nothing is not a task at all.

## The merge attempt 2 had to resolve

`master` moved 120 commits under this branch (through `415dcc6997`). One
conflict, both sides pure additions to `fold.sh`:

| side | added |
| --- | --- |
| this lane | `prune_branch()`, the `prune` sweep, the `prune-branch` hidden mode |
| `origin/master` (`lane/foldci`) | `preflight_board_only()`, `preflight-verdict`, `board_gate_report()` |

Kept both, mine first, and the same in the usage header. The fold-path call
site — `prune_branch "$WT" "$branch" HEAD`, after the push to `$TIP` — merged
cleanly and is still below that push (`fold.sh:449` push, `fold.sh:464` prune),
which is the line-order check in the fragment.

## The measurement, and it moved while the lane ran

| when | lane refs | fully merged into `origin/master` |
| --- | --- | --- |
| brief, 07:15Z | 25 | 8 |
| start of this lane | 25 | 8 |
| end of this lane | 26 | **12** |

The brief's numbers reproduced exactly, and then four more folded during the
session (`lane/armpin`, `lane/blit84`, `lane/fleetreg`, `lane/foldci`). The
dead-ref backlog grew 50% in one evening. That is the premise of the lane
measured twice rather than asserted.

The twelve, with the sha each would be restored from
(`git push origin <sha>:refs/heads/lane/<n>`):

| branch | tip | local head | worktree holding it |
| --- | --- | --- | --- |
| `lane/armpin` | `ed9b3902f8` | yes | `$WORK/wt/armpin` |
| `lane/armsperf` | `630258bad7` | yes | `$WORK/wt/armsperf` |
| `lane/blit84` | `a5b572a64b` | yes | `$WORK/wt/blit84` |
| `lane/cloudwt` | `fc547df32e` | yes | `$WORK/wt/cloudwt` |
| `lane/fleetreg` | `ccd3615ebc` | yes | `$WORK/wt/fleetreg` |
| `lane/foldci` | `40212487f0` | yes | `$WORK/wt/foldci` |
| `lane/jobsfix` | `5aa5354111` | yes | `$WORK/wt/jobsfix` |
| `lane/jobslabel` | `ecbc46f416` | yes | `$WORK/wt/jobslabel` |
| `lane/notespath` | `1eee0f08da` | yes | `$WORK/wt/notespath` |
| `lane/swizzle87` | `dffcb619bd` | yes | `$WORK/wt/swizzle87` |
| `lane/tier81fix` | `b2532b9fe4` | yes | `$WORK/wt/tier81fix` |
| `lane/toolsmith` | `baa5b32698` | yes | `$WORK/wt/toolsmith` |

## Two things the brief framed in a way that would have produced a no-op

**1. The worktree is not the edge case, it is the only case.** 12 of 12
already-merged branches still have a local head held by a lane worktree.
`lane.sh rm` is what removes those and it does not run on a fold. A design
whose delete was `git branch -d` would have deleted **nothing at all**, on
every branch, forever, and the tick cost would not have moved.

**2. The ref that costs a tick anything is not the one you reach for.**
`arms.sh:76` builds `tips` from `refs/remotes/origin/lane/*`, and its fetch at
`arms.sh:71` is `+refs/heads/lane/*:refs/remotes/origin/lane/*` — **no
`--prune`**. So deleting the branch on `origin` alone leaves the
remote-tracking ref in `$REPO` standing and `collect()` walks it every tick for
the life of the repository. The remote delete is the visible half; dropping the
tracking ref is the half that buys the time back.

Three refs, three different things:

| ref | who reads it | what `prune_branch` does |
| --- | --- | --- |
| `origin`'s `lane/<n>` | `gh`, a lane's push | deleted |
| `refs/remotes/origin/lane/<n>` | **`arms.sh` `collect()`**, the board | deleted — **this is the cost** |
| `refs/heads/lane/<n>` | nothing walks it | `branch -d`, which git refuses while a worktree holds it. Refusal logged, ref kept, never `-D` |

## Does this un-arm a registered prediction? Measured: no

`arms.sh`'s `live_ancestor()` (line 176) asks whether a `b_ref` is an ancestor
of `refs/remotes/origin/master` **or of any lane tip**. A prediction is
un-armed by the delete only if that answer flips yes → no.

Over every prediction blob reachable from every lane ref (139 unique blobs, 152
distinct `a_ref`/`b_ref` values, 149 resolvable):

```
live-ancestor BEFORE the delete: 96/149
live-ancestor AFTER  the delete: 96/149
UN-ARMED BY THE DELETE (yes -> no): 0
merged refs whose commits are NOT all on origin/master: 0
```

**I got this wrong once first, and the way I got it wrong is the lesson.** My
first script asked "is this ref an ancestor of master or of a *surviving* lane
ref" and reported **804 would un-arm**. That number is real and it is not about
my change: it is what `arms.sh` answers *today*, before any deletion — those
shas name commits on the `wt/*` development branches, which `live_ancestor()`
never consults. I had measured one arm and called it a difference. The
differential is 0 because a commit reachable from a fully-merged ref is
reachable from `master` by construction; the point of running it was that the
construction should not have to be trusted.

(53 of 149 registered ref values are not live ancestors of anything
`live_ancestor()` looks at, today, independent of this change. That is a real
finding about the registrations and belongs to someone else's lane.)

## What was built

`docs/testing/jobs/fold.sh`:

- `prune_branch <dir> <branch> <proof>` — the three-ref delete above. Guarded
  on the name (`lane/?*` **and** `git check-ref-format`) and on ancestry.
- called from the fold path as `prune_branch "$WT" "$branch" HEAD`, placed
  **after** `push origin HEAD:$TIP` succeeds. A branch deleted on a fold that
  failed to push is work destroyed.
- the ancestry proof is `HEAD` — the commit the push just put on the trunk —
  not `origin/$TIP`, which is one fetch stale inside `$WORK/fold-wt`; and the
  sha judged is what `ls-remote` says origin holds **now**, not what the fold
  fetched, because a lane that pushed after the merge's fetch has commits the
  fold never saw and deleting that ref would destroy them.
- `fold.sh prune` — the sweep over every lane ref, **a dry run by default**;
  `fold.sh prune --apply` does it.
- `fold.sh prune-branch <dir> <branch> <proof>` — the hidden-mode trick
  `resolve-notes` established, so the checks can drive it against a scratch
  remote with no fake `gh`.

`docs/testing/jobs/selftest.d/97-fold-branch-prune.sh` — **`selftest.sh` itself
is untouched, byte-identical to master.** The block was written against the old
single-file `selftest.sh`, and `lane.selftestsplit` landed the `selftest.d/`
split mid-session; the merge kept my block appended, which works but re-creates
exactly the collision that lane removed. Moving it to a fragment of its own was
the point of their work, so I did that and my diff no longer touches any file
another lane is likely to be in.

## Did I run the sweep? No — deliberately, and the board should

`fold.sh prune --apply` is ready and the dry run is in the PR body. Two reasons
a lane should not fire it on its own initiative:

1. The code has not been reviewed or folded. Running a not-yet-audited deletion
   script against twelve real refs on the shared remote is exactly the shape of
   an outward-facing, hard-to-reverse action that is the board's call.
2. It is reversible only because the shas are written down above, which is why
   they are.

After #137 folds: `bash docs/testing/jobs/fold.sh prune` for the list, then
`--apply`. The thirteenth branch it finds will be `lane/branchprune` itself,
which is correct — the fold path would have deleted it anyway.

## How the checks were verified, and the one that was inert

The gate is that a new check FAILS against the code it replaces.

| run | result |
| --- | --- |
| attempt 1: merged tree, this branch | **162 passed, 0 failed** |
| attempt 1: same suite, `origin/master`'s `fold.sh` | **139 passed, 23 failed** |
| attempt 2, after merging `415dcc6997`: this branch | **351 passed, 0 failed** |
| attempt 2: same suite, `origin/master`'s `fold.sh` | **328 passed, 23 failed** |

Re-run after the merge because the suite itself had more than doubled (162 →
351 checks as nine harness lanes folded) and `fold.sh` had gained
`lane/foldci`'s `preflight-verdict` block. The same 23 fail and no others:
351 − 23 = 328, so nothing outside this lane's fragment moved either way.

**The 23 are not one reason**, which is the thing worth checking about a red
column — they are the dry run (3), the apply (3), the name guard (3 refused
branches × 2 assertions each), the ancestry guard (2), the worktree legs (4),
the idempotence leg (1), the unreachable-origin legs (2), and the line-order
legs (2). A single missing function would have produced 23 reds too; what
says the checks discriminate is that they fail in eight independent groups.

The falsification ran in a **separate detached worktree** with `fold.sh`
checked out from `origin/master` — never by editing the real path, so the
working tree could not be left holding the old code.

The 23 are every behavioural check of the new code. The checks that *pass*
against the old file are must-not-move legs, and an inert control is not a
measurement, so each got a mutant that should move it:

| mutant | what tripped |
| --- | --- |
| drop the `is-ancestor` check | `lane/live` is deleted → 3 checks |
| drop the `lane/?*` name guard | `board` is deleted → 4 checks |
| `branch -d` → `branch -D` | only the source grep (see below) |
| `branch -d` → `update-ref -d` | the 4 worktree legs |
| `rc -eq 2` → `rc -ne 0` | the unreachable-origin leg |
| move the prune above the push | the line-order check |

**Two of those found real gaps rather than confirming me.**

*`branch -D` does not force past a worktree.* git's worktree check is not part
of `-d`'s merge check — `-D` refuses a worktree-held branch too. So the
behavioural leg ("the local head the worktree holds is KEPT") does not
discriminate `-d` from `-D`; only `grep -nE "branch +-D"` does. The mutant that
genuinely forces past a worktree is `update-ref -d refs/heads/<n>`, which has no
worktree check at all and leaves the lane worktree on a dangling HEAD. That is
the mutant that proves those legs live.

*The idempotence checks were inert as first written.* `ls-remote --exit-code`
says 2 for "no matching ref" and 128 for a fatal, and my first pair of checks
passed against a mutant that lumped them together — because the fixture only
ever produced the absent-ref case. A `-ne 0` there drops a tracking ref still
bound to a live branch, on a bad network, for every lane at once. The fix is a
fixture with `origin` pointed at a path that does not exist.

## What the next lane should not repeat

- Do not measure this by counting `refs/heads/lane/*`. Nothing walks those.
  Count `refs/remotes/origin/lane/*` in `$REPO` — what `arms.sh:76` enumerates.
- Do not "simplify" `branch -d` into `update-ref -d` on the grounds that the
  ancestry was already proved. It is not the merge check that `-d` is there
  for; it is the worktree check.
- Do not assume `origin/$TIP` is current inside `$WORK/fold-wt`. It is not.
- Before reporting that a change breaks N things, check whether N is a
  before/after difference or just the "after" column. Mine was the latter, and
  804 is a convincing-looking number.
- `docs/ORCHESTRATION-DESIGN.md` §8.1 still describes the fold without the
  delete. Outside this lane's files; a doc lane should add the line.
