# lane.cloudtail -- the cloud unit's tail was not guaranteed

Brief: `$WORK/briefs/cloudtail.md`. Harness defect, no tracker issue.
Work in progress; findings are written here as they are established.

## Territory: `docs/testing/jobs/cloud.sh` is held by a LIVE lane

The brief expected `[lane.cloudterritory]` to still hold it and to be stale.
It is not. The board retired that row at wave 126 and **granted
`docs/testing/jobs/cloud.sh` outright to `[lane.turncap]`**, whose PR #171 is
OPEN. So the file is not free, and it is not stale either — it is not mine to
claim and I have not claimed it. Details and the fold-order consequence go on
the PR.
