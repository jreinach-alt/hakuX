# lane.boardtreeheal -- land $BT on origin/board every tick, or stop (harness defect)

Issue: none (harness defect, dispatched directly). Base: origin/master @
44dc2188ff4aca5a8e47466e53093ad3217b0e31. Files touched:
`docs/testing/jobs/board.sh`, `docs/testing/jobs/selftest.d/99-board-wt-refresh.sh`.

## What was wrong

PR #619's `refresh_wt()` fixed a dirty-or-stale `$WT` (board.sh's private
mirror of `origin/$TIP`): fetch, stash any dirt reversibly, checkout
`FETCH_HEAD`, verify, or abort. It only ever touched `$WT`. `$BT`
(`$WT/.boardtree`, the session's `board`-branch worktree) was created once
if missing and never refreshed again -- no fetch, no dirty check, no
fast-forward, for the whole life of `$WT` (which the "$WT is NOT removed
between ticks" comment in `98-window-budget.sh`'s fixture confirms can span
many ticks). The brief's tick found `$BT` five commits behind
`origin/board`, carrying a staged diff duplicating part of #619's own patch
and an unstaged diff reverting 47 files -- a board-editing session had
apparently drafted work directly in `$BT` (which is wrong on its own terms:
lanes-must-not-edit-board-files, mirrored here for the board's own worktree)
and the session ended before committing it, and nothing since had refreshed
`$BT` to notice or recover it.

## What changed

Added `refresh_bt()` in `board.sh`, same shape as `refresh_wt()`: fetch
`origin board`, stash any dirt (`git stash push -u`, never
`reset --hard`/`clean -f`) tagged `board.sh: auto-cleared dirty <path>`,
then `git merge --ff-only FETCH_HEAD` (not a checkout+detach like
`refresh_wt` -- `$BT` stays ON branch `board`, so the fast-forward is a
merge). If the merge fails (a true divergence: `$BT` and `origin/board` each
hold a commit the other lacks) the tick aborts loudly rather than guess how
to reconcile it. `board.sh refresh-bt <worktree>` mirrors `refresh-wt` for
the selftest. The call site sits right after `$BT` is created/verified
(board.sh:~555, `[ -e "$BT/.git" ] && { refresh_bt "$BT" || exit 1; }`),
before `install_board_hook` -- so nothing in the tick can read or edit `$BT`
before it is known to be at `origin/board`'s tip.

One thing this does NOT attempt: reconciling true divergence automatically.
If a future tick sees `$BT` diverged (its own unpushed commit plus a
separate push from elsewhere landing on `origin/board`), the tick just stops
and says so -- the same posture `refresh_wt` takes on an unresolvable base.
That should not happen in normal operation (the session pushes every tick),
and guessing how to merge two board-branch histories is worse than a human
looking at it once.

## Falsifier

Extended `selftest.d/99-board-wt-refresh.sh` (did not split into a sibling
file -- it already covered `refresh_wt` end to end with the same fixture
shape, and $BT is literally nested inside $BW/wt built for the refresh_wt
cases, so reusing that fixture was the smaller diff) with:

- clean `$BT`, `origin/board` moved on -> lands at the new tip, no stash
  (checked as **no change** in `git stash list`'s count, not a count of
  zero -- `refs/stash` is repo-wide, shared with every worktree of the same
  repository, and the refresh-wt cases above already stashed into it);
- dirty `$BT` (modified tracked path + untracked path), `origin/board`
  moved on -> lands at the new tip, dirt stashed and recoverable
  (`git stash show`, not just exit code);
- `$BT` and `origin/board` truly diverged (each holds a commit the other
  lacks) -> aborts (rc 1), local commit intact, `origin/board` untouched.
  First attempt at this case used a `$BT` merely AHEAD of an unmoved
  `origin/board` -- that is not divergence, `merge --ff-only` treats an
  ancestor as already-up-to-date and succeeds, so the case caught nothing
  until `origin/board` was also given a commit `$BT` lacks;
- a fetch failure also aborts (rc 1), same as `refresh_wt`;
- a mutant reverting the `merge --ff-only` line to `true` (the old
  create-once-never-refresh shape) fails the dirty/stale case: with the
  fast-forward gone, `$BT` never reaches the new tip after the stash.
  Verified this mutant is actually caught (`SELFTEST_ONLY` run below), not
  just asserted to be.

Ran `SELFTEST_ONLY="99-board-wt-refresh.sh" bash selftest.sh`: 40/40 pass,
including the mutant catch. Also ran the other board.sh-touching fragments
that could plausibly reach the new code path
(`88-window-budget.sh 97-board-gate.sh 97-board-priority.sh
97-board-release.sh 97-board-push-gate.sh`): 136/136 pass. Checked every
other fragment referencing `board.sh` for a bare (no-subcommand) invocation
that would reach `$BT`'s block -- `gate`/`released`/`refresh-wt`/
`refresh-bt`/`install-hook` all exit before it, and `88-window-budget.sh`'s
one full-tick run never gives its sandboxed `origin` a `board` branch, so
`$BT` is never created there and `refresh_bt` is never called (confirmed by
the guard `[ -e "$BT/.git" ]`) -- unaffected by this change either way. Did
not run the full ~114-fragment suite (memory: CI minutes are finite, never
run the whole suite as a self-check; this file's CI job runs it in full).

## Next lane

`refresh_wt` and `refresh_bt` are two copies of a five-line shape (fetch,
dirt-check, stash, land, verify) that differ only in how they land (checkout
--detach vs. merge --ff-only) and what "landed" means to verify. If a third
worktree ever needs this treatment, factor the common shape out; two copies
was the smaller diff for two call sites and the brief said not to touch
`refresh_wt`'s observed behavior, so I left it alone rather than refactor it
into something a divergent third caller might silently break.
