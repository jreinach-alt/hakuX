# lane.handbackwaiter

Brief: when handback.sh skips a lane as PARKED (`blocked:*` on its PR or its
lane's issue) while that lane still has dispatch requests in flight, arm the
host waiter instead of a bare `continue`. Until now each case (shaderfb569,
litcompile569, memfast, ibcache, gpl569 #594, verdict433 #610) needed hostops
to notice harness_health's `parked-nowaker` and start
`hakux-waiter-<lane>` by hand.

## What changed

`docs/testing/jobs/handback.sh`: new `park_waiter`, called from the PARKED
branch just before its `continue`. The parking decision itself
(`parked_label`, `PARKED_LANES`, `ISSUE_NOT_PARKING`) is untouched.

`park_waiter` arms `systemd-run --user --unit=hakux-waiter-<lane> bash
$WORK/host-tools/resume_when_runs_finish.sh <lane> <lane> 14` only when all
of these hold, each read fresh every tick:

| gate | why |
|---|---|
| `lane_requests_of` finds a request queued/running | the resume path's own reader; nothing in flight means nothing to wait for, and the plain `continue` stands |
| `hakux-lane-<lane>` is not active | its session is still deciding what it waits for; next tick decides |
| `hakux-waiter-<lane>.service` is not active | idempotence: handback ticks every few minutes |
| a `queue/` or `running/` name matches `[-.]<lane>-` | the waiter's OWN pattern. `lane_requests_of` also attributes by a request's `lane` field and arm pair shas; if the waiter's filename glob cannot see the request, it would call `lane.sh resume` at once with the run still out. Not armed; said once |
| `$WORK/attempts/<lane>` < `LANE_MAX_ATTEMPTS` | `lane.sh resume` refuses at the cap (harness_health's `capped-waiter`). Not armed; the cap is named on the PR once |

`LANE_MAX_ATTEMPTS` is read the way `lane.sh` reads it: `models.env`, then
`$WORK/limits.env` over it. Before `systemd-run`, `reset-failed` on the unit:
a waiter that timed out exits 1 and stays loaded as `failed`, holding the
name. `list` mode arms nothing and prints the decision (`WOULD ARM`,
`already armed`, `NOT ARMING ... (reason)`). A run-mode arm posts one PR
comment and one tick-log line; a PR-less (idle-no-pr) row gets the log line
only, as every other no-PR action does.

`selftest.d/99-handback.sh` and `99-handback-draft.sh` each held the
invariant "no non-comment `systemd-run` in handback.sh" (meaning: handback
starts no lane session itself). The brief requires one `systemd-run`, so both
checks now allow exactly one, which must be the waiter call on a
`hakux-waiter-$name` unit. The waiter, not handback, calls `lane.sh`. Those
two fragments were not in the brief's file list; they are on the PR's
`Files:` line.

## Proof

`selftest.d/99-handback-waiter.sh`, fixture pattern of 99-handback-parked.sh
(shimmed gh/systemctl/systemd-run; the systemd-run shim adds the unit to the
active set so `is-active` reads it armed afterwards). CI has no user systemd
manager, and a real transient unit would run the host's waiter against the
fixture, so "assert via `systemctl --user is-active`" is done against the
shim, not real systemd. Legs: (a) parked PR label + queued request -> one
waiter with the exact argv, one comment, lane not resumed, list says WOULD
ARM and arms nothing; (b) immediate re-run -> still one arm, one unit, one
comment, list "already armed"; (c) parked via the issue -> armed; (d)
nothing in flight -> nothing; (e) at the cap -> not armed, cap named once;
(e') one under -> armed; (f) request attributed by `lane` field under an id
the glob cannot see -> not armed, said once; (g) lane session running -> not
yet; (h) unparked lane -> no waiter, existing wait path; (i) neighbour
lane's request -> not ours. Mutants: `noarm`, `noidem`, `nocap`,
`nopattern`, each red.

    env SELFTEST_ONLY=99-handback-waiter bash docs/testing/jobs/selftest.sh
    selftest: 29 passed, 0 failed, PARTIAL: 1 of 110 fragments

With the `park_waiter` call reverted out of the PARKED branch by hand:

    FAIL (a) a parked draft with a queued request gets hakux-waiter-<lane>
    FAIL (a)   running the host's waiter on the lane, for 14 h
    FAIL (a)   and the unit is then active
    FAIL (a)   list names the decision
    FAIL (a)   one PR comment says so
    FAIL (b) ... (four legs)  FAIL (c) ...  FAIL (e)/(e')/(f) messages
    FAIL mutant anchor 'noarm' no longer matches handback.sh
    selftest: 11 passed, 18 failed

Every handback fragment plus 99-limits-env together:
`348 passed, 0 failed, PARTIAL: 12 of 110 fragments`.

Live, `bash docs/testing/jobs/handback.sh list` from this worktree on the
host, 2026-09-29 08:14 PDT:

    #610 lane/verdict433: draft-strand-quiet, skipped: parked by issue #433 blocked:tracking (a blocked:* label has its own actor)
    #610 lane/verdict433: parked with queue/1-1790693574-lane.verdict433-211577 in flight; waiter hakux-waiter-verdict433 already armed

That is the waiter hostops started by hand at ~07:5x; the job reads it and
would not re-arm. #436, #439 and #535 are parked with nothing in flight and
print no waiter line. #594 (gpl569) produced no row this tick.

## For the next lane

- The waiter's resume (`lane.sh resume` from resume_when_runs_finish.sh)
  spends an attempt; handback's own strand resumes refund theirs. A parked
  lane woken by its waiter is waiting, not failing, so the same refund
  arguably belongs there. That is in the host script, not this repo.
- The waiter's glob and `lane_requests_of` still disagree for requests
  attributed only by `lane` field or pair sha. This job refuses to arm in
  that case rather than guess; widening the host script's pattern would
  close it.
- harness_health's `parked-nowaker` and `capped-waiter` are untouched and
  remain the safety net.
