# The board dispatches by expected improvement: game-visible first, then the most recoverable pixels

Lane: boardprio            Issue: none (harness change; owner's request 2026-09-25)
Base: origin/master
Files: docs/testing/jobs/board.sh, docs/testing/jobs/roles/board.md,
docs/testing/jobs/selftest.d/97-board-priority.sh, docs/lanes/boardprio/**
Needs device: no. Needs NDK: no. Prediction: none. The proof is the selftest fragment, mutants,
and a falsification run against the old board.sh.

## The owner's ask

"Can we also establish a prioritization for these based on expected improvements so these broader
more impactful issues get dispatched ahead of the smaller edge cases?"

## What happens today

- `board.sh`'s `board_filter issues` prints the startable issues **in the order `gh issue list`
  returns them** (newest first).
- `roles/board.md` tells the board to take "the most valuable `dispatchable` issues whose files are
  free, severity bucket first, then oldest".
- Nothing in the tracker records an issue's expected improvement, so a 5k-px edge case and a
  1.5 M-px family look the same.

## The data: the host writes it and you read it

`nv2a_issues.toml` rows on `origin/board` carry these new fields. The host is populating them now,
and the board keeps them current when it triages:

| field | type | meaning |
|---|---|---|
| `impact_px` | int | expected recoverable **structural** px (the size multiplied by how tractable the next step is), not the whole residual |
| `impact_onestep_px` | int | expected recoverable **one-step** px, from a named mechanism |
| `impact_basis` | string | where the numbers come from (run id, or estimate plus reason) |
| `game_visible` | bool | the defect is seen in a commercial game (a crash or a visible glitch) |

## The job

1. **Sort the startable list** in `board_filter issues` using the tracker, loaded through
   `board_files.load("nv2a_issues.toml")` exactly as the other board tools do:
   - **first**, `game_visible = true` rows;
   - **then** by `impact_px + impact_onestep_px // 4` descending (one-step px count a quarter: they
     are rounding, not rules);
   - **then** rows with no impact fields, oldest issue number first.

   Print each line with its key, for example
   `#266 [impact 1,493,336 px] W buffering: ...  [labels]` or `#301 [game] Galleon: ...`, so the
   board and a human see why it ranks where it does. An issue with no tracker row sorts last and
   says so.
2. **The role file** replaces "severity bucket first, then oldest" with: take startable issues **in
   the order listed**; the list is sorted by expected improvement. Also say that the board keeps
   `impact_*` and `game_visible` current when it files or triages an issue, with an
   `impact_basis`. Keep every other rule in that paragraph.
3. **Do not change** what is startable (the SKIP labels and prefixes), the cap, the audit outlet, or
   the window reserve.

## Proof

- **`selftest.d/97-board-priority.sh`**, using a fixture tracker and a fixture `gh` JSON. At least
  five issues:
  - a game-visible issue with no px;
  - a large-structural issue;
  - a one-step-only issue whose quarter weight puts it below the structural one;
  - a small-structural issue;
  - an issue with no fields.

  Assert the printed order and the printed keys. Put the correct answer for any tie-break in the
  middle of three candidates.
- **Mutants, each red:**
  - sort ascending;
  - ignore `game_visible`;
  - weight one-step equal to structural;
  - drop the tracker join, so the order falls back to gh's.
- **A falsification run** against the real old board.sh, in a scratch worktree at
  `origin/master`. Never swap the file in place, and stage by name. It must be red because the
  order is gh's, not for an import or path error.
- `bash docs/testing/jobs/selftest.sh`: all green, with the totals in the PR body.

## Do not

- **Touch `fleet.py` or `check_coverage.py`.** They are lane.toolsmith's. If `fleet.py`'s
  DISPATCHABLE list should share the order, say so in NOTES and the PR body.
- **Edit the board files.** The host owns the data fields.
- **Trigger CI as a self-check.**

## Done when

The fragment and mutants are green and red as stated, the falsification reds are in NOTES, and the
PR has the lane template, preflight passes, and it is marked ready. It touches the board's
dispatch path, so expect `needs-audit-1`.
