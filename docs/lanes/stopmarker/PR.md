# stopmarker: lane.sh refuses to start or resume a lane the owner stopped

State: ready

Lane: stopmarker            Issue: none (harness defect, dispatched directly)
Base: master @ 66bce0c222
Files: docs/testing/lane.sh, docs/lanes/stopmarker/NOTES.md, docs/lanes/stopmarker/PR.md, docs/lanes/stopmarker/falsify.sh
Prediction: none: no arm (harness script, no pixels)
Needs device: no    Needs NDK: no

When the owner stops a lane, its brief is renamed to
`$WORK/briefs/<name>.md.STOPPED-by-owner-<stamp>`. `lane.sh start` and
`lane.sh resume` now check for that marker. If it exists, they exit **77**
with `REFUSED: lane.<name> was STOPPED BY THE OWNER (marker: <path>)` and name
the file a human renames to lift the stop. `start` also refuses when the
brief argument is itself a marker file. The header comment documents the
convention.

On master, `resume` refused only by accident ("no brief at", exit 3). `start`
on a stopped lane with no worktree launched a unit and copied a fresh brief
over the stop.

| case | master rc / units | this branch |
|---|---|---|
| marker, no worktree, `start` | 1 / **1 launched** | 77 / 0 |
| marker, `resume` (with or without a worktree) | 3 / 0 (generic message) | 77 / 0 |
| marker, `start` with a worktree, or the marker as the brief | 3 or 5 / 0 | 77 / 0 |
| no marker: start, resume, no-brief, no-worktree, another lane's marker | unchanged | identical output and rc |

`docs/lanes/stopmarker/falsify.sh` reproduces the table. The lane.sh selftest
fragments pass: 225 passed, 0 failed. Details are in `NOTES.md`.

Release note (none): harness script only; no emulator change.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
