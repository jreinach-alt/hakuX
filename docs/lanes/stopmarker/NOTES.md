# lane.stopmarker: lane.sh refuses a lane the owner stopped

## The defect

On 2026-10-02 the owner stopped lane.titleroutes2 at 06:36 PDT. A hostops
tick resumed it at 06:37, because no file said the stop was deliberate.
At 08:25 lane.local began renaming the brief to
`$WORK/briefs/<name>.md.STOPPED-by-owner-<stamp>`. `lane.sh` then refused
the stopped lane only by accident:

- `resume` refused with `no brief at ...` (exit 3). That message reads like
  a lost file someone should restore.
- `start` did not refuse at all once the worktree was gone. It copied a
  fresh brief over `$WORK/briefs/<name>.md` and launched a unit. That
  silently lifted the stop. The falsifier below shows it on master.

## The change (docs/testing/lane.sh only)

- `refuse_if_owner_stopped <lane> [brief-arg]` refuses when either of these
  exists: `$WORK/briefs/<lane>.md.STOPPED-by-owner-*`, or a brief argument
  whose name contains `.STOPPED-by-owner-`. It prints
  `REFUSED: lane.<name> was STOPPED BY THE OWNER (marker: <path>) ...` with
  the path to rename back, then exits **77**. No other lane.sh refusal uses
  77 (the others are 1, 2, 3, 4, 5, 75, 76), so a caller can tell "do not
  retry" apart from "broken".
- `start` calls it right after `refuse_if_remote`, before any worktree,
  fetch or attempt.
- `resume` calls it right after `refuse_if_remote`, before the worktree and
  brief checks. A stopped lane whose worktree is gone therefore gets the
  owner-stop message, not "use lane.sh start".
- The header comment documents the convention in three lines.

## Falsifier (`falsify.sh`, run 2026-10-02)

`bash docs/lanes/stopmarker/falsify.sh [old-ref]` runs each case against
`<old-ref>:docs/testing/lane.sh` and the working tree's copy. It uses a
scratch `HAKUX_WORK`, a scratch git repo, and stubbed `systemd-run` and
`systemctl`. `units=` counts `systemd-run` calls. Old ref: 66bce0c222.

| case | old rc / units | new rc / units |
|---|---|---|
| marker, worktree, `resume` | 3 / 0 ("no brief at") | **77 / 0** |
| marker, no worktree, `start` | 1 / **1 (launched)** | **77 / 0** |
| marker, worktree, `start` | 3 / 0 ("worktree exists") | **77 / 0** |
| marker passed as the brief argument, `start` | 5 / 0 (a leftover-branch artefact of the row above) | **77 / 0** |
| marker, no worktree, `resume` | 3 / 0 ("no worktree") | **77 / 0** |
| no marker: `start` | 1 / 1 | 1 / 1 (same output) |
| no marker: `resume` | 0 / 1 | 0 / 1 (same output) |
| no marker, no brief: `resume` | 3 / 0 | 3 / 0 (same output) |
| no marker, no worktree: `resume` | 3 / 0 | 3 / 0 (same output) |
| `alphabet.md.STOPPED-*` present, `resume alpha` | 0 / 1 | 0 / 1 (same output) |

`start` exits 1 on success on both old and new. That comes from the trailing
`[ -n "$issue" ] && echo`: the last command is false when no issue is given.
It predates this change, and this lane leaves it alone.

Selftest: `SELFTEST_ONLY="98-lane-shape 96-fleet-registry 99-limits-env
88-window-budget 99-lane-model-file 99-handback-waiter"` gave 225 passed,
0 failed.

## For the next lane

- No selftest fragment was added, because the brief limits this lane to
  `lane.sh`. `falsify.sh` holds the cases. To make the check permanent, add
  a fragment in `98-lane-shape.sh` next to the remote-lane guard; its
  `lane_ls` helper already provides the stubs.
- `harness_health.py` already understands the marker (host-tools). Nothing
  here touches lane.titleroutes2's stop.
