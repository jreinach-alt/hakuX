# lane.visual404 NOTES

## Status: parked until after 0.5 (#433), no work carried yet

**Why attempt 1 did not finish.** It was stopped on purpose. It opened
draft PR #436 at 13:22 PDT on 2026-09-26 from an unblock request, and that
request had been withdrawn at 13:24. The host then parked #404 until after
the 0.5 release. The owner pointed all dispatch at 0.5, and #404 is not on
its critical path. See #404 comment 2026-09-26T20:23:37Z. The worktree and
brief were kept for after 0.5. The attempt pushed only this NOTES stub, and
no detector code was written.

**Attempt 2 (handback resume, 2026-09-26 ~14:50 PDT).** handback.sh resumed
the lane because the PR was a draft and the unit was not running. It did not
know about the park. I checked the park and it still holds: #433 is open and
#404 carries `blocked:after-0.5`. I did no build work, so the owner stop is
not overridden. I posted a `[lane.visual404] blocked:` comment on #436.

**What unblocks it:** #433 closes (0.5 ships), or the owner or host removes
`blocked:after-0.5` from #404.

## For the next attempt (the brief is unchanged)

- The frames are in `dispatch/results/0-0-y-1790433159-titleplay-p1-*/route-frames/`:
  17 titles, about 38 PNGs each. Galleon's frames are in `titleplay-p1-galleon`.
  Check for MechAssault in the `*-gamecheck-*` results.
- Do not restore `dispatch/parked/titleplay-p1-20260926`, because the owner
  stopped it.
- Nothing has been measured yet, so there is nothing to avoid repeating.
