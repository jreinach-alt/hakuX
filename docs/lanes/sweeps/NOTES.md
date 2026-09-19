# lane.sweeps -- two sweeps the harness does not have

Brief: `briefs/sweeps.md` (owner, 2026-09-19). No tracker issue; harness
capability.

Status: in progress. This file is written before the long steps, per the lane
contract, and updated as each class lands.

## What is being built

- `docs/testing/jobs/pr-sweep.sh` -- a script, no model session, on a timer.
- `docs/testing/jobs/issue-sweep.sh` -- mechanical classes plus a handoff to
  the board's tick, which is the harness's existing actor for judgement.
- The units and timers for both, under `docs/testing/systemd/`.
- A selftest fragment per sweep, with a mutant per class.

## Findings so far

Recorded as they are established.
