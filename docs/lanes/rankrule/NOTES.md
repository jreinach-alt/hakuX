# lane.rankrule -- #569: codify the owner's ranking rule

Docs only. Added "Ranking options: probability times the size of the win,
not cheapness" to `docs/testing/jobs/roles/lane.md` (after "Pilot first") and
`docs/testing/jobs/roles/board.md` (after "What you own"), quoting the owner's
2026-09-28 words as the source. No existing text was moved or reworded.

Both examples were checked against the record before writing:

- `docs/lanes/shaderplan569/NOTES.md` section 7 opens "Order of rank: what a
  player gains ... per unit of work", and P6 (ubershader) is last, "do not
  start before P2 and P3 report".
- The same file, section 2: "Async mode as built does not take the 96% off
  the draw path" (`vkCreateGraphicsPipelines`, doa413c NOTES:195-199), read
  from the code before async413's arm ran.

No device time, no prediction (no arm).

## Status

Preflight PASS (--allow-tracker). Waiting on CI for PR #584; mark ready when green.
