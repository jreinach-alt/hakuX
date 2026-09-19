# lane.foldci — a stopped fold that never reaches the PR

Issue: none (harness defect, dispatched directly). Files: `docs/testing/jobs/fold.sh`,
`docs/testing/jobs/selftest.sh`, this file. Prediction: none — harness script, no
pixels claimed.

## Why this took three attempts (the fix itself took one)

Attempt 1 built and proved the fix. Attempts 2 and 3 were both **lost races on
`selftest.sh`**, and nothing about the fix changed in either.

Attempt 2 merged `origin/master` at `bdeab36f75` (2026-09-18 23:18 -0700) and
pushed. That merge was correct when it was made. PR #131 (`lane/notespath`)
folded as `1f7572a34c` **after** it, appending its own block to the same place in
`selftest.sh`, and the fold job hit the conflict at 07:07:30Z and handed #127
back as `needs-rebase`. So attempt 2 did not fail to do the merge; it did the
merge against a `master` that moved again before the fold job reached it.

The lesson is not "merge harder": with six lanes appending to one file, a merge
is only valid for as long as the queue in front of you takes. What made this
cheap to redo is that both blocks are *appends* — the resolution is "keep both,
delete the three markers", not a content decision. Attempt 3 did exactly that
again, plus the one thing attempt 2 could not have known about:

**`NOTES.md` moved.** #131 retired root `NOTES.md` (`roles/lane.md` item 3 now
says `docs/lanes/<lane>/NOTES.md`), and `master` has no root copy at all. Leaving
this file at the root would have landed the very file #131's fold removed, so it
is now at `docs/lanes/foldci/NOTES.md`. `fold.sh`'s new `resolve-notes` path
would have rescued it, but only by reacting to a conflict this lane can simply
not create. If you are resumed on an old branch, check where your notes are
supposed to live before you push.

## What was wrong

`fold.sh` mapped a head with zero checks to `NONE` and waited on it forever. The
`say` line went to `$WORK/logs/fold/tick.log` on the owner's host, which no lane
and no cloud session can read. PR #102 sat a full day in exactly that state. Only
`RED` ever produced a comment.

## What I changed

One function, `ci_report <pr> <head> <state>`, replaces the inline RED-only block.
It comments for `RED`, `NONE` and a stuck `PENDING`, and nothing else about the
fold path moved: `NONE` still `continue`s before the worktree is ever created, so
it is still a gate, just not a silent one.

Three decisions worth knowing before the next lane touches this:

**The marker is a ledger, not a boolean.** The brief said to reuse
`$F/failed/$pr-$head-ci`, and the obvious reading — `[ ! -f "$m" ]` as the whole
dedup — moves the silence one state over instead of closing it: a head seen first
as `NONE` would then never get its `RED` comment when the run finally appears and
fails. The file now holds one line per state already reported, and the dedup is
`grep -qxF "$ci"`. A head therefore gets at most two comments in its life
(`NONE`-or-`PENDING`, then `RED`), which is not the per-tick noise the brief
rules out.

**An empty marker means RED.** The pre-09-18 job `touch`ed the file and only ever
did so for `RED`, so an empty one found on disk is normalised to `RED` on first
read. Without that, the upgrade tick would re-comment on every head that was
already reported red. There is a selftest for it.

**`PENDING` needs an age, not a tick count.** Ticks are 30 minutes and the Android
build is long, so a run in flight is routinely `PENDING` across two ticks —
commenting on the second sighting would have put a comment on nearly every
fold-ready PR. First sighting records `PENDING-seen <epoch>` in the ledger and
says nothing; a comment happens only once that is `PENDING_STUCK_SECS` old
(default 7200 = 4 ticks). The env var exists so the selftest can force it to 0.

The `NONE` comment names `[skip ci]` in the head commit as the cause, rules out
the path-filter theory explicitly (`android.yml` and `desktop.yml` trigger on
`pull_request:` with no `paths:`), gives the empty-commit unblock, and warns that
GitHub matches the marker anywhere in the message including the body — so the
commit you push to explain the problem must not quote it.

## What the next lane should not repeat

- **`fold.sh list` posts comments.** It always has: the `[ "$mode" = list ]` echo
  on the non-green path does not `continue`, so it falls through to the comment.
  I kept that parity rather than fix it, because "RED behaviour is unchanged" was
  an explicit constraint and changing it in this lane would have changed RED. It
  is a real defect in a read-only subcommand and it is now three states wide
  instead of one. Worth its own lane; the ledger keeps it to one comment per
  state regardless of how often someone runs `list`.
- **The GREEN path is still untested.** I did not add a fold-for-real case: it
  would `git worktree add` inside the selftest's temp dir against the real repo
  and push to `$TIP`. The new tests assert the negative instead — that `NONE`
  never creates `$WORK/fold-wt` — which is what "still a gate" actually means
  here.

## selftest.sh: it is slow, and it was slow before this lane

`selftest.sh` takes minutes on this worktree, not the "seconds" the brief
promises, and `arms.sh list` alone accounts for most of it — 131 files in
`docs/testing/predictions/` and a git walk per file. I confirmed this is not mine
by restoring both files from `origin/master` and running: master's copy stops at
the same line (`a second run does not queue it again`) with the same 90s timeout.
Budget ~5 minutes, do not assume it has hung, and do not pipe it to `tail` — the
pipe buffers and you see nothing until it ends.

## My new checks fail against the code they replace

Verified by `git show origin/master:docs/testing/jobs/fold.sh` over the working
copy, running the block, and restoring. 12 pass on the new `fold.sh`; against
master's, 7 of the 12 fail — the five `NONE` reporting checks and both stuck-
`PENDING` checks.

The other five pass both ways, and it is worth being clear about why, because a
check that cannot fail has measured nothing:

- `RED is unchanged` and `a run still in flight is not commented on` are the
  two constraints the brief says must not move. Passing on both files is the
  result, not a gap.
- `NONE still does not fold` guards the gate. It cannot fail on master because
  master does not fold a `NONE` either; it exists so that a future lane that
  "fixes" the waiting by letting `NONE` through trips it.
- `a RED that follows a NONE` and `an EMPTY marker … still means RED` pass on
  master for the same reason: master writes no marker for `NONE` and only ever
  wrote empty ones. They are falsifiers for the two ways *this* change could
  have gone wrong, so I built those two mutants and ran them:

      marker used as a boolean (`[ -f "$m" ] && return`)   -> 3 fail, incl. "a RED that follows a NONE"
      normalisation line deleted                            -> 1 fail: "an EMPTY marker … still means RED"

  Each mutant trips exactly the check written for it.

**The mutants earned their keep — one of my checks could not fail.** The
empty-marker check was written `bash -c '! grep -q "CI is red" "$FC/..."'`. `$FC`
is not exported, so inside that child shell the path was `/comments.log`, grep
failed on a missing file, the `!` made it succeed, and the check passed against
anything. It is now a function (`unsaid`), which `check` runs in the current
shell where `$FC` is set. Anyone adding a *negative* check to this file should
do the same: in `selftest.sh` only `HERE`, `HAKUX_WORK`, `DISPATCH_DIR`,
`GOLDENS`, `GH_REPO` and `SELFTEST_GH_LOG` are exported, and a `bash -c` negative
over any other variable is green by construction.
