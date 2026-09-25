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
  3. a tracker row with no impact fields: `[no impact estimate]`
  4. no tracker row: `[no tracker row]`

  Oldest issue first inside each tier and inside any score tie. What is
  startable (SKIP, SKIP_PREFIX), the cap, the audit outlet and the window
  reserve are unchanged; the PR half of `board_filter` is unchanged.
- If the tracker cannot be read, every line says `[tracker unreadable]` and
  the order is oldest first. It must never print nothing: an empty capacity
  list reads as "no work", which is the defect the positive gate exists to end.
  A non-integer impact value counts as 0 for the same reason (one bad row must
  not empty the list).
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

## For the owner / the next lane

- **A measured zero sorts above an unknown.** Following the brief literally, a
  row with `impact_px = 0, impact_onestep_px = 0` (#31, #38, #50 today) is in
  tier 2 at score 0, above every row with no fields. If "measured, nothing
  recoverable" should rank below "not yet estimated", that is a one-line
  change to `rank()` (return tier 2 for score 0), and the fragment would need
  a row for it.
- **`fleet.py`'s DISPATCHABLE list does not share this order.** It is
  lane.toolsmith's file and was not touched. If it should, the sort is
  `rank()` in board.sh's `board_filter`; lifting it into a small module both
  could import (beside `board_files.py`) is cleaner than a second copy.
- Do not test this against the real `docs/testing/nv2a_issues.toml`:
  board_files prefers origin/board, so a fixture has to be read through a
  copy of board_files.py whose directory holds it (what the fragment does).
