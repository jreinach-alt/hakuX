# lane.handbacklane

## What changed

`handback.sh`'s `lane_name()` now takes the PR number and has a third resolver.
The first two are the branch strip and the worktree that has the branch checked
out. The third reads the PR body's first `Lane:` line (`lane_from_body`). The
name is taken only if it matches `^[a-z0-9][a-z0-9-]*$` and has `$WORK/wt/<n>`
and `$WORK/briefs/<n>.md`. The body is read once per PR per tick.

A lane resolved from the body has, by construction, no worktree on the PR's
branch: if it had one, the worktree resolver would have found it first. So it
has moved on, and the row is skipped without a label, marker or resume. The
only output is a `list` line: `lane <n> (from the PR body's Lane: line) is live
on <branch>[ (unit running)]`. The resume call site is unchanged (still one).

The dead-end comment ("worktree or brief gone") now says why the body did not
resolve: no `Lane:` line, a line that does not name a lane, or a lane with no
worktree and brief. The rejected text is never echoed into the comment.

## Measured

- Setup plus all 99-handback-* fragments: 297 passed, 0 failed. The new
  `99-handback-lane-line.sh` passes legs (a) moved lane, (b) `Lane: ../x` and
  (c) no line. Its three mutants fail: no body resolver, no skip, no name check.
- Real host, `handback.sh list`: #504 is still parked by `blocked:in-flight`,
  which hostops set. A throwaway copy with #504's park check turned off printed
  `#504 lane/flip474-ts: draft-strand-arm, lane flip474 (from the PR body's
  Lane: line) is live on lane/flip474-sysmem; not stranded`.

## For the next lane

- The full `selftest.sh` takes more than 10 minutes. To check handback only, run
  a scratch copy with the fragment glob narrowed to `99-handback*`; the setup
  before the fragments is shared.
- On the host, `handback.sh list` still writes `say` lines to the tick log on
  the "still running" path. That is existing behaviour and was not changed.
- Once this is folded, hostops can take `blocked:in-flight` off #504: handback
  will skip it anyway.
