# lane.nightlytrunk -- the nightly built the owner's checkout, not the trunk

Brief only, no tracker issue. `nightly-2026-09-20` and `nightly-2026-09-21`
were both built from `20e4708d50` (evening of 09-19) because
`hakux-nightly.service` ExecStarted out of `/home/justin/hakuX` and
`nightly_build.sh` asked that checkout what it was. `origin/master` was 152
commits ahead; both releases said "No commits in the last day".

Work in progress -- see the PR body.
