# lane.boardtreeheal: land the session's board worktree, or stop, before it is edited

Issue: none (harness defect, dispatched directly -- see memory
dispatch-harness-fixes-dont-file-issues; put `Issue: none (harness defect,
dispatched directly)` on your PR body).

Base: origin/master at 44dc2188ff4aca5a8e47466e53093ad3217b0e31.

## What is broken

`docs/testing/jobs/board.sh` fixed this exact bug for `$WT` in PR #619
(fold ~2026-09-29T18:40Z, see the retired.boardwt-checkout-selfheal row in
territory.toml): a dirty or stale `$WT` used to make every downstream tool
read wrong data, silently. The fix added `refresh_wt()`, called on `$WT`
every tick: fetch origin/$TIP, stash any dirt reversibly (never
reset/clean), checkout FETCH_HEAD, verify HEAD==FETCH_HEAD or abort loudly.

It was never extended to `$BT` ("$WT/.boardtree", the session's board-branch
worktree, created around board.sh:490-500). Read that block: `$BT` is
created ONCE if missing (`git worktree add ... "$BT" board`) and then never
touched again by board.sh -- no fetch, no dirty check, no fast-forward. A
board tick session edits files in `$BT` and is expected to commit+push them
to `origin/board`, but nothing stops a tick from starting on a `$BT` that is
behind `origin/board` or that still holds another tick's uncommitted work.

This is not hypothetical: this tick (2026-09-29T21:xx) found `$BT` five
commits behind `origin/board`, carrying a staged diff that duplicated part
of PR #619's own board.sh patch (36 lines) plus a new
`selftest.d/99-board-wt-refresh.sh`, and an unstaged diff spanning 47 files
(arms.sh, fleet.py, affinity.py, several selftest.d fragments, a dozen
prediction jsons, nv2a_index.json...) that reverted those files to an older
state than HEAD. `git stash list` in that worktree already held four prior
auto-stashes tagged the same way going back to 2026-09-21 -- this has
happened repeatedly and nothing has fixed the underlying gap. The
boardwt-checkout-selfheal PR's own retirement note flagged this as an open
follow-up: "whatever writes uncommitted files into board-wt ... is still
unidentified."

Likely mechanism (confirm, don't assume): a board.sh edit was drafted
directly inside `$BT` in an earlier tick session (application/harness code
has no business being edited on the `board` branch at all -- see memory
lanes-must-not-edit-board-files, which is usually stated the other
direction), the session ended (turn cap) before it was committed, and no
later tick ever refreshed `$BT` to notice.

## What to build

Extend `docs/testing/jobs/board.sh` so `$BT` gets the same treatment `$WT`
gets, every tick, before anything in the tick can read or edit it:

- A function (reuse `refresh_wt`'s shape, or generalize it to take the
  target ref -- your call, whichever is the smaller diff) that, for `$BT`:
  fetches `origin/board`, and if `$BT` is dirty, stashes it reversibly with a
  descriptive tag (never `reset --hard`/`clean -f` -- the whole point is a
  human can later `git stash list` and find what a broken tick wrote). Then
  fast-forwards `$BT`'s local `board` branch to `origin/board` (`git merge
  --ff-only`, since `$BT` stays on branch `board`, unlike `$WT` which is
  detached) or, if that is not a clean fast-forward (local commits diverge
  from origin/board -- should not happen in normal operation since the
  session pushes every tick, but handle it), abort the tick loudly rather
  than guess.
- Call it right after the existing `$BT` creation block (around line 490),
  before the `install_board_hook` loop that follows it.
- A `board.sh refresh-bt <worktree>` subcommand mirroring `refresh-wt`, for
  the selftest.

## Falsifier

Write `selftest.d/99-board-wt-refresh.sh`'s sibling (or extend it -- read it
first, it already covers `refresh_wt`) with cases for `refresh_bt`/whatever
you name it:
1. Clean `$BT` at an old commit of `board` -> ends at `origin/board`'s tip,
   nothing stashed.
2. Dirty `$BT` (uncommitted edit to a tracked file) -> tick proceeds, the
   dirt is stashed (verify via `git stash list`, not just exit code), `$BT`
   ends at `origin/board`'s tip, dirty content is recoverable from the
   stash.
3. `$BT` with a local commit not on `origin/board` (simulate divergence) ->
   function aborts (non-zero, no data loss), does not force-push or rewrite
   history.
A mutant that reverts your fast-forward call back to a no-op (the old
create-once-never-refresh behavior) must fail the dirty/stale case (2) --
match the existing 99-board-wt-refresh.sh's mutant-testing pattern (its
current mutant kills 12/19).

## Done when

- `refresh_bt` (or your chosen name) lands in board.sh, called every tick
  right after `$BT` is created/verified, before install_board_hook.
- The new/extended selftest passes on your branch and its mutant fails the
  cases above.
- PR body says `Issue: none (harness defect, dispatched directly)` and
  states the base sha above.
- Do not touch `refresh_wt` or `$WT`'s handling -- PR #619 already covers
  that; this brief is `$BT` only. If you can cleanly share code between the
  two, fine, but don't change `$WT`'s observed behavior.
