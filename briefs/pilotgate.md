# Pilot gate: no device batch over 30 minutes without a reviewed pilot

Lane: pilotgate            Issue: none (harness defect)
Base: origin/master
Files: docs/testing/request.sh, docs/testing/jobs/roles/lane.md, AGENTS.md, docs/testing/jobs/selftest.d/99-pilot-gate.sh, docs/lanes/pilotgate/**
       (request.sh is LENT from lane.toolsmith; any other writer of dispatch/queue/*.req you find: ask for it on a board request)
Needs device: no.

## Why (the owner, 2026-09-26)

"We need some safeguards established that make bad long-running device decisions durable. If
something is going to hold the device for more than, say, 30 minutes, we need to test the first few
minutes to confirm our approach is valid before dispatching the remainder of the work."

What prompted it: titleplay's pass 1 (#397) queued 29 soaks of 420 s at head-of-queue priority. They
held the only live handheld for hours while the Nova charged, and the generic START/A route reached
clean gameplay in 7 of 15 titles. Nobody looked at the first two runs' frames before the other 27 ran.
The host has parked the batch, and a host-side health check (`[device-budget]` in
host-tools/harness_health.py) now finds such batches after the fact. This lane makes the enqueue
path refuse them in the first place.

## The rule

A requester's device time is the sum over its queued and running requests of `seconds` + 90 s of
setup, times `runs`. A suite run with no `seconds` counts 180 s. This is the same estimate the health
check uses; keep the two identical and say where each one lives.

- If adding a request would take the requester over 30 min, the enqueue is REFUSED unless
  `dispatch/pilots/<requester>.ok` exists and is less than 24 h old.
- The refusal names the rule, the estimate and the way out: queue a pilot of at most two requests,
  review what it produced against the batch's purpose, record the verdict in
  `dispatch/pilots/<requester>.ok` (result ids, what the output showed, date), then queue the rest.
- The first 30 min always goes through; that IS the pilot.

## The job

1. `docs/testing/request.sh`: implement the guard before the request file is written. Grep every
   writer of `$DISPATCH_DIR/queue/` (arms.sh, the sweep queuer, anything else) and route each through
   the same guard, or list on this lane's PR why a writer is exempt.
2. `docs/testing/jobs/roles/lane.md` and AGENTS.md ("Working with a device"): state the rule where
   lanes read it, with the titleplay example in one sentence.
3. A selftest with a fixture queue:
   - a requester over budget is refused;
   - with a fresh `.ok` it is accepted;
   - with a stale `.ok` it is refused;
   - under budget it is accepted.
   Name the world in which each leg fails.

## Definition of done

The PR is ready (not draft), with its selftest green and the rule text in both documents. Everything
touches only harness scripts and docs; no device time is needed.

## Do not

- Change the 30-minute threshold. It is the owner's. The 24 h validity and the 90 s / 180 s estimates
  are the host's choices: change them only with a reason on the PR.
- Hold a device, touch adb, or queue device work.
