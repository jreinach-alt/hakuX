# lane.boardgate

## The defect

`docs/testing/jobs/board.sh`'s gate has two inputs and both are error reports:
`fleet.py`'s `FAIL` lines (a lane stuck, reported-not-folded, waiting) and
`check_coverage.py` (the tracker disagreeing with GitHub). Neither can say
*"there is capacity and there is work"*, so a **healthy** board dispatches
nothing — and the board job is the only actor permitted to label an issue
`dispatchable` or call `lane.sh start` (design §4). Six consecutive ticks
(03:25–05:10Z) logged `nothing actionable` with 29 issues open, 0 lanes
running against `LANE_MAX=4`, and both handhelds attached and idle.

## What I built

(in progress — see the PR body)
