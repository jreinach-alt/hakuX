# lane.cloudlaneguard

Lane: cloudlaneguard
Issue: none (harness defect, dispatched directly by hostops)
Base: origin/master
Files:
- docs/testing/jobs/cloud.sh
- docs/testing/jobs/selftest.d/99-cloud-lane-branch.sh
- docs/lanes/cloudlaneguard/NOTES.md

## Why (evidence)

`cloud.sh`'s claim guard (`held_why` / `unit_busy`) refuses a PR only when another `hakux-lane-cloud-*-<num>` unit is running. It never asks whether **the PR's own lane session** (a non-cloud `hakux-lane-<x>` unit whose worktree `$WORK/wt/<x>` has the PR's head branch checked out) is still running.

On 2026-09-27, PR #523 (`lane/thermal507-power`) went through two cloud sessions while `hakux-lane-thermal507.service` was active (it started at 17:45 PDT and got a new addendum at 18:37 PDT):
- audit1, claimed at 01:24Z;
- remediate, claimed at 01:34Z.

Two sessions committed to that one branch within minutes:
- `fe5940a6e2` "remediate #523's audit pass 1";
- `20502ec594`, a master merge.

A rejected push is the only thing standing between them and a clobber. An audit of a branch its lane is still changing also audits a moving target.

The interim mitigation lives on the host: `host-tools/audit_outlet.sh` now calls `host-tools/lane_on_branch.sh <head>` and stops before claiming. The repo's `cloud.sh` still claims such a PR when anything else runs it.

## Build

1. In `cloud.sh`, add a check to `held_why`, for every kind except `issue`: read the PR's `headRefName` (by number, REST). If any active or activating `hakux-lane-*` unit that is not `cloud-*` has `$WORK/wt/<x>` checked out on that branch, print why and return 0 (held).
   - Fail closed if the head cannot be read, like the label read.
   - `cloud.sh list` must show "skip <kind> #<n>: its lane hakux-lane-<x> is still running on <branch>".
2. A selftest fragment, `selftest.d/99-cloud-lane-branch.sh`, with a stub `systemctl` and a fake `$WORK/wt/<x>` git worktree. It must show three cases:
   - held when the lane unit is active on the head branch;
   - claimable when that unit is inactive;
   - claimable when the unit is active on a different branch.

## Proof

- The fragment passes.
- It FAILS with the new `held_why` lines reverted: say so in NOTES with the output.
- Run `cloud.sh list` on the real host and paste its output in NOTES.

## Do not

- Do not touch `host-tools/*` (not in the repo).
- Do not change the claim order or the cap.
- Harness only: nothing under hw/ target/ accel/ android/ tcg/.
- Open a draft PR, and mark it ready when CI is green.
