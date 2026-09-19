# lane.armsskip — a structural skip must reach the lane

## The defect

`docs/testing/jobs/arms.sh` had two rejection paths and only one of them spoke.

- `refused()` — a `request.sh` refusal — wrote `$WORK/arms/skipped/<sha>` **and**
  posted `[job.arms] REFUSED` on the lane's PR.
- `skip()` — every structural refusal (no `a_ref`/`b_ref`, `a_ref == b_ref`, a
  ref that does not resolve, a `b_ref` that is not a live ancestor, a soak, no
  suite with goldens) — wrote the marker and said nothing at all.

Measured on PR #115: a cloud session registered
`undersized-pitch-swizzle-layout.json` with English prose where the `a_ref`
belonged ("4129a349e6 with xemu.toml [display] renderer = OpenGL"). The job
refused it at 04:29:32Z on 2026-09-19 and has refused it every 30 minutes
since. Nothing on the PR mentions it. The lane believes it has an arm running.
A cloud lane has no host disk, so for it the marker does not exist at all.

## What was built

`skip()` now records **and** tells; `mark()` is the record-only half that
`refused()` uses, because `refused()` posts its own, richer comment with
request.sh's stderr in it and must not get a second one.

The comment is `[job.arms] SKIPPED: ...` carrying the marker's own reason
verbatim, posted on the lane's PR via the existing `pr_for()`, falling back to
the issue via the existing `post()` for a master or host-registered prediction.

## The one design decision worth arguing about

The obvious implementation is "the marker's existence is the record that it has
been said" — which is what `refused()` does. **That would have exempted exactly
the two markers this was written for**, both of them written by a version that
told nobody, one of them #115's. This file has already made that mistake once:
`already_ran`'s retry was keyed on an `arms=` stamp introduced by the same
commit as the retry, so the single refusal it existed to clear took the `else`
and was skipped forever (see the comment block at `already_ran`).

So the marker holds the reason and a separate `told=` line holds the
announcement, and an unstamped structural marker is announced on the next tick.
`tell_skip()` is therefore also called on the `already_ran` path.

**What bounds that backlog** is not the 131 predictions on disk and not the 38
behind the watermark — history is counted and `continue`d before any `skip()`
runs and leaves no marker. The backlog is exactly the files under
`$WORK/arms/skipped`, i.e. everything `skip()` and `refused()` have ever
written. On the day this shipped there were two:

```
3236c83efc10  master:docs/testing/predictions/tier81fix-timetofull.json: no suite with goldens in its keys or disc
d8522a7e87f7  lane/cloud-109:docs/testing/predictions/undersized-pitch-swizzle-layout.json: a_ref 4129a349e6 with xemu.toml [display] renderer = OpenGL does not resolve
```

The first goes to its issue, the second to PR #115. That is the whole first
tick's traffic.

`told=nowhere` is written when there is no open PR and no `issue` field, so a
permanently unpostable marker does not log a failure every 30 minutes. A
genuine post failure is *not* stamped, so it is retried on the next tick.

## The check, and that it fails against the code it replaces

Five new checks in `selftest.sh` under
`== arms.sh: a STRUCTURAL skip reaches the lane too, exactly once`, using PR
#115's exact registration shape. Against `origin/master:arms.sh` (restored into
the tree, new selftest kept) the five that pin the new behaviour fail; against
this branch all pass. See the PR body for the two runs.

Three of the checks are must-not-move and pass both ways, which is the point of
them:

- a `request.sh` refusal is not *also* told as a structural skip;
- a second tick does not tell the same marker again;
- a **broken** prediction behind the watermark is neither marked nor
  announced. Its `a_ref` is prose too, so it would skip structurally if the
  watermark did not fence it first — that is the 38-comments-in-one-tick guard.

## What the next lane should not repeat

- `selftest.sh` is not "seconds" on this host any more: each `arms.sh` tick
  re-runs `collect()`, which `git cat-file`s every prediction on master and on
  every live `lane/*` branch, plus a network fetch. The whole file takes minutes
  and my four extra ticks are a small part of that. If it needs to be fast,
  cache `collect()` per tick rather than trimming checks.
- Do not edit a job script while `selftest.sh` is running against it. Bash reads
  a script lazily by byte offset and each tick re-execs it; an edit mid-run
  invalidates the run (and can corrupt an in-flight tick). I did this once and
  had to restart.
- `status.sh` prints a skipped marker with `cat`; the appended `told=` line
  joins the preceding line as a lazy markdown continuation, so it reads as one
  row. Nothing to fix there, but do not be surprised by it.

## Why attempt 1 did not finish (and the trap it left behind)

It ran out of turns in the middle of the falsification step, and the way that
step is written is a hazard worth naming.

The brief's recipe is `git show origin/master:<file> > <file>`, run, restore.
Attempt 1 did that — it copied its finished `arms.sh` aside to `.arms.sh.mine`,
overwrote `arms.sh` with master's, started the ~4-minute `selftest.sh`, and the
session ended there. **`git status` then showed `arms.sh` as unmodified**, so
the branch looked like a lane that had written a test and no fix. The entire
implementation was sitting in an untracked dotfile that nothing would have
looked at.

The falsification step destroys your work for the duration of the run, and the
window is minutes, not seconds, because `selftest.sh` runs `arms.sh` eight
times and each tick walks every prediction on master and on every live `lane/*`
branch. Commit before you falsify, and falsify with `git stash`-free mechanics:
`git show origin/master:<f> > <f>; run; git checkout -- <f>` after the commit
exists, so the restore is a checkout and not a copy you have to remember.

Attempt 2 recovered `.arms.sh.mine`, confirmed it differed from `HEAD`'s
`arms.sh` only by the intended change, committed it, and only then merged
`origin/master`.

## The merge with master (attempt 2)

`arms.sh` auto-merged: `bc7ccef95d` removed two quadratics from `collect()` and
`live_ancestor()` and touched no line this lane changed. `selftest.sh`
conflicted with `1f7572a34c`'s `fold.sh` NOTES.md block, as predicted — both
sides append immediately before the final summary `echo`. Both blocks are kept,
master's first, ours last; they share only the fixture harness and neither
reads the other's state. `NOTES.md` moved from the branch root to
`docs/lanes/armsskip/NOTES.md`, which is the path `1f7572a34c` established and
the reason that conflict existed at all.

## Measured, both ways, on the merged tree

```
ours                     selftest: 76 passed, 0 failed
origin/master's arms.sh  selftest: 70 passed, 6 failed   (exit 1)
```

The six that fail against the old file are the announcement itself: *posted as
a comment*, *says SKIPPED not REFUSED*, *carries the marker's reason*, *records
`told=`*, and both halves of *a marker written before `told=` existed is
announced, and stamped*.

The other five pass both ways **on purpose**, and it is worth being explicit
about why rather than mistaking them for dead weight:

| check | what it pins |
| --- | --- |
| the prose `a_ref` is recorded as a structural skip | the marker still gets written; telling must not replace recording |
| a second tick does not tell it again | trivially true on the old file, which never tells at all — it only has teeth on ours |
| a `request.sh` refusal is not also told as a structural skip | `refused()` keeps its single richer comment |
| a broken prediction behind the watermark is not skipped | the 38-comments-in-one-tick guard |
| and nothing is posted for it | same, from the posting side |

So one of them (*a second tick*) is a genuine tautology against the old file
and is only a test of the new one; the rest are must-not-move guards. Neither
kind discharges the "your check must fail against the code you replaced"
requirement on its own — the six above are what does.

## Why attempt 2 did not finish, which is not what the resume assumed

Attempt 2 finished the brief's checklist. It merged, ran the gate green, pushed,
marked the PR ready at 07:35:38Z and labelled it `harness` and `fold-ready` by
07:38:49Z — the timeline says so. It did not stop in draft, and turns were not
what stopped it.

What it did not do is diagnose why the PR would not fold. `fold.sh` said, twice,
that **no CI run exists** on the head, and both that comment and the 08:07Z
resume read the missing run as a `[skip ci]` marker — which is what `fold.sh`'s
own comment names as "the usual cause". So the response was an empty
`ci: build this head` commit, which produced no run either. That is the real
reason a third attempt was needed, and the cause was never the commit message.

## The finding: a PR that conflicts with master gets no CI run at all

GitHub builds a `pull_request` event against the *merge* of head and base. When
that merge conflicts, there is no merge commit to build, so **no workflow run is
created** — not a failed one, not a skipped one, none. `fold.sh` then reads
`NONE` and correctly refuses to fold, and its advice sends the lane after a
`[skip ci]` marker that is not there.

Every head of this branch, correlated against the master tip of its own moment:

| head | merges with then-master | runs created |
| --- | --- | --- |
| `0e591da552` (NOTES only, PR opened 05:56Z) | clean (`a1691ae68e`) | Android + Desktop build |
| `997e28b235` (the fix + the selftest block) | **conflict** (`1f7572a34c`) | none |
| `d8db6092cf` (`ci: build this head`, empty) | **conflict** (`ae3712aae1`) | none |
| `584b8fdcfd` (this one, after the merge below) | clean (`912f58a1c1`) | **Android + Desktop + jobs selftest, at 08:12:39Z, seconds after the push** |

That last row is the test, not a restatement: the hypothesis said a
conflict-free head would produce runs with no other change, and it did — three
of them, including `jobs selftest`, which had never run on this branch because
the only earlier head that *could* run touched nothing under
`docs/testing/jobs/`. Nothing was done to the commit messages.

Reproduce it without pushing anything:
`git merge-tree --write-tree --name-only <head> <master>` exits 1 on exactly
the heads that got no run, and 0 on the two that did. The conflict was always
`selftest.sh` — every harness lane appended to the same spot, which is the
collision `#136`'s split was folded to end.

So the diagnosis order for "no CI run" is: **check mergeability first**, and
only then the commit message. An empty commit cannot fix a conflict, and
pushing one hides the cause behind a new head. This is worth saying in
`fold.sh`'s comment, which is not this lane's file — it is in a PR comment on
#123 for whoever owns `fold.sh` next.

## Attempt 3: the merge, and the block moved into a fragment

`#136` folded as `f53f3f66c2` between attempt 2's push and this attempt:
`selftest.sh` now keeps only the fixtures, shims and tally and sources
`selftest.d/NN-*.sh` in sorted order. The merge of `origin/master` (37 commits)
auto-resolved — master's side deleted every inline block and ours was the only
one left standing — so the whole of this lane's section survived in
`selftest.sh`, where it no longer belonged.

Moved verbatim to `docs/testing/jobs/selftest.d/92-arms-skip-told.sh`, with only
a fragment header added. `selftest.sh` is byte-identical to `origin/master`
again (`git diff origin/master -- docs/testing/jobs/selftest.sh` is empty),
which is the check that the move was a move.

**92** is the number because the fragment is not self-contained: it reads
`$sha2`, the `request.sh` refusal that `40-arms-refusal.sh` leaves standing, to
assert that a refusal does not also get a structural-skip comment. It must
therefore run after 40, and after 50, which clears markers and drives the whole
queue itself. Nothing after it reads anything it leaves.
