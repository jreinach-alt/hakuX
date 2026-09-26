# lane.boardprio: the board dispatches by expected improvement

Owner, 2026-09-25: "establish a prioritization for these based on expected
improvements so these broader more impactful issues get dispatched ahead of
the smaller edge cases".

## What changed

- `docs/testing/jobs/board.sh`, `board_filter issues`: joins gh's startable
  list to the tracker through `board_files.load("nv2a_issues.toml")` (so it
  reads `origin/board`, as every other board tool does) and sorts it:
  1. `game_visible = true`: `[game]`, or `[game; impact N px]` when it also has px
  2. `impact_px + impact_onestep_px // 4` descending: `[impact N px]`, with the
     breakdown `= S structural + O one-step / 4` when one-step px count
  3. a tracker row with no impact fields: `[no impact estimate]`, and, ranked
     with it, a row whose impact value is present but not a finite number:
     `[impact unreadable: impact_px='big']`
  4. a measured zero (fields present, score <= 0): `[impact 0 px, measured]`
     -- below the unestimated rows (host decision 2026-09-25)
  5. no tracker row: `[no tracker row]`

  Oldest issue first inside each tier and inside any score tie. What is
  startable (SKIP, SKIP_PREFIX), the cap, the audit outlet and the window
  reserve are unchanged; the PR half of `board_filter` is unchanged.
- If the tracker cannot be read, every line says `[tracker unreadable]` and
  the order is oldest first. It must never print nothing: an empty capacity
  list reads as "no work", which is the defect the positive gate exists to end.
  An impact value is read as any finite int or float (a size-times-
  tractability product comes out as a float) by its integer part; anything
  else is shown as unreadable rather than raising (one bad row must not empty
  the list) and rather than read as a measured zero (audit pass 1, M1).
- The tick brief's capacity paragraph and `roles/board.md` now say "in the
  order listed" instead of "severity bucket, then oldest", and the role file
  says the board keeps `impact_px`, `impact_onestep_px`, `game_visible` and
  `impact_basis` current when it files or triages.

## Proof

`selftest.d/97-board-priority.sh`: fixture tracker + fixture gh JSON, twelve
issues, run through `board.sh gate` from a copy of the jobs layout under `$T`
(board_files reads beside itself, so the fixture tracker needs its own
`board_files.py`; `HAKUX_BOARD_REF=""` makes it read the working-tree copy).
Both ties (a 50,000-px tie and a no-estimate tie) put the right answer in the
middle of three in gh's order. 8 checks, all green.

Mutants (`mutants.sh`, each edits a copy of board.sh in a scratch dir):

| mutant | result | order it produced |
|---|---|---|
| ascending | red, 1 fail | #301 #305 #270 #310 #320 #303 #302 ... |
| ignore game_visible | red, 2 fails | #302 #303 ... #290 #301 #304 #300 |
| one-step weighted 1:1 | red, 2 fails | #301 #303 #302 ... |
| drop the tracker join (gh order) | red, 1 fail | #310 #270 #320 #305 #304 ... |
| tie in gh order (no number in key) | red, 1 fail | ... #310 #270 #320 ... #304 #280 #290 |
| tie newest first | red, 1 fail | ... #320 #310 #270 ... #304 #290 #280 |

Falsification: the fragment run (`run-fragment.sh <jobs-dir>`) against the
real board.sh in a scratch worktree at origin/master d92ae5d7f3: **7 of 8
red**, order `#310 #270 #320 #305 #304 #280 #290 #303 #302 #301 #300`, which
is exactly gh's order. The eighth check (a lane-held issue stays out) is green
there too, so the run reached the filter: red because of the order, not an
import or path error.

Against the real tracker (`real-tracker.sh`, origin/board 2026-09-25):
`#77 [game]`, `#266 [impact 1,493,336 px]`, `#10 [impact 365,820 px = 0 +
1,463,282 / 4]`, `#224 [221,046]`, `#13 [4,734]`, `#31 [impact 0 px]`,
`#4 [no impact estimate]`, `#99999 [no tracker row]`.

## Attempt 2 (2026-09-25)

**Why attempt 1 did not finish:** the work, the mutants and the falsification
were done and committed, but the session ended with PR #270 still a draft
whose body said "Work in progress", with an open question (measured zero vs
unknown) in NOTES. A draft is skipped by board.sh, fleet.py and fold.sh, so
nothing downstream could see it. Do not end on a draft again.

**Host decision (owner-delegated): a measured zero ranks BELOW an unknown.**
Tiers are now: game-visible; score > 0 descending; no estimate; measured
zero (`[impact 0 px, measured]`: fields present, score 0); no tracker row.
Fixture gained #296/#306/#312 (measured zeros, tie winner #296 in the
middle); fragment is 9 checks, all green. New mutant `zero-above-unknown`
(tier 1 at score 0, the attempt-1 behaviour): red. All seven mutants red.

Falsification re-run against origin/master d709a8d1fa (after merging it):
**8 of 9 red**, order `#310 #270 #320 #305 #304 #280 #290 #312 #296 #306
#303 #302 #301 #300` = gh's order exactly; the lane-held check stays green,
so the run reached the filter.

`roles/board.md` also now says the host holds the owner's delegation for
`decision-needed` / `regression-accepted` calls: the board routes them with
a `[board]` comment and keeps dispatching, never idling on the owner.

## Attempt 3 (2026-09-25)

**Why attempt 2 did not finish:** the decision and role-file line were
committed and pushed (ee5e290acd, CI green), but the session ended before the
PR body was replaced with the lane template and before `gh pr ready 270`:
`.pr-body.md` was written but never PATCHed onto the PR. Same failure as
attempt 1, one step later. No code changed in attempt 3: master (63 commits
ahead) merges cleanly and touches none of this lane's files, so it was not
merged in (that would only re-run CI on an identical diff). Preflight passes
on ee5e290acd; the body was set via REST PATCH and read back, then marked
ready.

## Resume after audit (2026-09-25, handback: stale base)

**Why the previous session did not finish:** it did finish -- #270 was
marked ready and audited twice (be2355b412) -- but attempt 3 chose not to
merge master, reasoning an identical diff needed no fresh CI. The fold job
then refused be2355b412 because its only red (selftest) ran before
master's head, and GitHub never re-runs a PR's checks on a base move.
Lesson: when master has moved, merge it; "no conflicts, none of my files"
is not the fold's test, a CI verdict newer than trunk is.

This resume: fast-forwarded to the audit commits, merged origin/master
(130 commits, clean, no lane file touched), preflight passes on
ec022efb83, pushed. No code changed.

## For the owner / the next lane

- Real tracker today: #31, #38, #50 are measured zeros and now sort below
  every unestimated row.
- **`fleet.py`'s DISPATCHABLE list does not share this order.** It is
  lane.toolsmith's file and was not touched. If it should, the sort is
  `rank()` in board.sh's `board_filter`; lifting it into a small module both
  could import (beside `board_files.py`) is cleaner than a second copy.
- Do not test this against the real `docs/testing/nv2a_issues.toml`:
  board_files prefers origin/board, so a fixture has to be read through a
  copy of board_files.py whose directory holds it (what the fragment does).

## Attempt 5 (2026-09-26, handback: CI red after a master merge)

**Why attempt 4 did not finish:** it merged origin/master (196e007b06) and
started two selftest runs with `run_in_background`, then its turn ended. A
headless session exits at the end of a turn, so no completion notice came
back and the merge was never pushed. Lesson: in a headless lane, wait on
long work in the foreground; the full jobs selftest runs longer than one
10-minute tool call here, so detach it into a log and wait on the log's
exit line in successive foreground calls.

The red on efc8fb9391 was three checks in `86-nightly-notes.sh` (the
previous-nightly tag range), not this lane's code: the fixture named
"yesterday" by the runner's clock, and a UTC runner between 00:00Z and
07:00Z is a day ahead of the script's Los Angeles day. Master fixed it in
241e720324 ("name the fixture's yesterday by the script's clock"), so this
lane edits nothing there; merging master (ff14a4580c) brings the fix in.
The selftest was re-run under `TZ=UTC` on the merged tree to confirm.

## Attempt 6 (2026-09-26): release files at PR-ready

**Why attempt 5 did not finish:** it did. Attempt 5 pushed the merge,
CI went green, and #270 folded at 2026-09-26T04:30:55Z (a97c049f2e). The
branch was pruned after the fold. This resume carries a new addendum
(the owner said "Yes, brief it"): release a lane's files when its PR is ready,
not when it folds. It is new work on a new PR, branched from master at
8552e1ff89 (a fast-forward: the old branch had no commits master lacked).
