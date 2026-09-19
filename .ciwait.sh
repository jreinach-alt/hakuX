#!/usr/bin/env bash
# Poll PR #147's check rollup until nothing is pending, then print the verdicts.
set -u
R=jreinach-alt/hakuX
for i in $(seq 1 80); do
    pending=$(gh pr view 147 --repo "$R" --json statusCheckRollup \
        --jq '[.statusCheckRollup[] | select(.status != "COMPLETED")] | length' 2>/dev/null)
    [ "${pending:-1}" = 0 ] && break
    sleep 30
done
gh pr view 147 --repo "$R" --json statusCheckRollup \
    --jq '.statusCheckRollup[] | "\(.name // .context)\t\(.status)\t\(.conclusion)"'
