# lane.boardwt-checkout-selfheal

Harness defect, dispatched directly (no issue).

## The defect

`board.sh` refreshed its private trunk tree `$WORK/board-wt` with
`git fetch && git checkout --detach FETCH_HEAD` and read neither exit code. A
dirty tree makes that checkout refuse, so every tick ran on whatever the tree
held. On 2026-09-29 it held 39 uncommitted paths matching the tree of an old
WIP commit (fc7bb08d2a, not on master). The stale `fleet.py` in that tree
predated #611's `battery_gated` bucket and reported nova's battery-gated
pgraph runs as a queue-stall FAIL. The repository's stash list shows a board
tick hit the same thing on 09-28 and stashed it by hand.

## The change

`refresh_wt` in `docs/testing/jobs/board.sh`:

- fetch `origin/$TIP`, or ABORT the tick;
- `git status --porcelain` excluding `.boardtree` (the session's nested board
  worktree, untracked in `$WT` by design; the real `board-wt` on 2026-09-29
  showed nothing else untracked, and ignored build/pycache paths are not
  reported by `--porcelain` nor stashed by `-u`);
- if dirty, say a NOTE (count, first three paths, stash message) and
  `git stash push -u -m "board.sh: auto-cleared dirty <wt> at <UTC>"`, never
  reset or clean;
- checkout `--detach FETCH_HEAD` and verify `HEAD == FETCH_HEAD`, or ABORT
  (exit 1).

`board.sh refresh-wt <tree>` runs the refresh alone, for the selftest.

## Measured

`selftest.d/99-board-wt-refresh.sh`: 19/19 pass. A mutant with the dirty
branch disabled (the old behaviour, now at least loud) fails 12 of 19: the
tree stays dirty and off the tip.

## For the next lane

The stash only removes the symptom. Whatever writes uncommitted files into
`board-wt` is still unknown. If the NOTE shows up in
`logs/board/tick.log`, the stash it names shows which files were written; find
the writer from those. The stash is shared by every worktree of the repository
(`refs/stash`), so look for the entry by its message and never pop it by index.
