# lane.armsskip — a structural skip must reach the lane

## The defect

`docs/testing/jobs/arms.sh` has two rejection paths. `refused()` (a
`request.sh` refusal) writes a marker under `$WORK/arms/skipped/<sha>` **and**
posts `[job.arms] REFUSED` on the lane's PR. `skip()` — every structural
refusal — writes the marker and says nothing. A cloud lane has no host disk,
so for those the only record is unreachable.

## In progress

Making a structural skip reach the lane's PR (or its issue) exactly once.
</content>
</invoke>
