# lane.ciskip

Two harness defects, each of which cost several PRs on 2026-09-18/19.

1. Lanes keep writing the retired skip-ci marker into commit messages. GitHub
   then creates no workflow run at all, `statusCheckRollup` is empty, `fold.sh`
   reads `NONE` and the PR waits forever. `AGENTS.md` retired the marker; the
   role files a lane is actually started with never mentioned it.
2. `fold.sh` records a preflight failure as `$F/failed/$pr-$head` and skips that
   head forever, but preflight's `coverage` and `territory` gates are about the
   **board**, not about the PR. #123, #124 and #130 were each marked permanently
   failed on an innocent head when the board opened #138.

(in progress)
