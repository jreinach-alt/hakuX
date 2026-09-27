#!/usr/bin/env bash
# ab_run.sh --dry-run against a 0.5-labelled issue and an unlabelled one:
# prints the request.sh lines it would queue, with HAKUX_RELEASE_PRIO=1 in
# front of the labelled one's. Queues nothing, registers nothing.
#   bash docs/lanes/relprio432/abrun_dry.sh <labelled-issue> <unlabelled-issue> [fix-ref]
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
FIX="${3:-$(git -C "$ROOT" rev-parse --short origin/master)}"
for n in "$1" "$2"; do
    echo "=== #$n labels: $(gh api "repos/jreinach-alt/hakuX/issues/$n" --jq '.labels[].name' | tr '\n' ' ')"
    bash "$ROOT/docs/testing/ab_run.sh" --dry-run --who relprio-dry --fix "$FIX" --issue "$n" \
        --suites "Blend surface" --no-expect 2>&1 | grep -E 'priority|request.sh|could not'
done
