#!/usr/bin/env bash
#
# The one way every scheduled job starts a model session.
#
#   run-claude-job.sh <job> <worktree> <brief.md> [max-turns]
#
# Bounded twice -- --max-turns and a wall-clock timeout -- so a job that loops
# is capped and a job that hangs is killed and re-run on the next tick. Its
# JSON output is the audit trail; summarise_run.py keeps a one-line index so
# nobody reads transcripts to learn what a job did.
#
# THE TOOL ALLOWLIST IS EXPLICIT, because nobody is at the keyboard: in
# headless mode a tool call that is not pre-approved is refused, not
# prompted, and the first version of this passed no allowlist at all, which
# would have left the board session unable to run git or gh and logged a
# run that did nothing. allowed-tools.job names what a job may run; a lane
# gets the wider allowed-tools.lane from lane.sh. Anything outside the list
# is still refused, which is the point.
#
# EXIT 75 ON A USAGE-WINDOW LIMIT. The account's five-hour and weekly windows
# are shared by every session, local and cloud. A limit is not a failure to
# retry into: 75 is EX_TEMPFAIL, the unit's RestartSec grows, and the next
# tick after the reset succeeds (docs/ORCHESTRATION-DESIGN.md §9.1).
set -u
job=${1:?job}; wt=${2:?worktree}; brief=${3:?brief}; turns=${4:-40}
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
log="$WORK/logs/$job/$(date -u +%Y%m%dT%H%M%SZ).json"
mkdir -p "$(dirname "$log")"
cd "$wt" || exit 2
br=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
git fetch -q origin && [ -n "$br" ] && git merge -q --ff-only "origin/$br" 2>/dev/null
HAKUX_ROLE="$job" HAKUX_BRIEF="$brief" \
timeout "${JOB_TIMEOUT:-50m}" claude -p "$(cat "$brief")" \
    --max-turns "$turns" \
    --output-format json \
    --permission-mode acceptEdits \
    --allowedTools "$(cat "$REPO/docs/testing/jobs/allowed-tools.job")" \
    --append-system-prompt-file "$REPO/docs/testing/jobs/roles/$job.md" \
    > "$log" 2>&1
rc=$?
python3 "$REPO/docs/testing/jobs/summarise_run.py" "$log" "$job" >> "$WORK/logs/$job/index.tsv"
grep -qiE '"is_error": *true.*(rate.?limit|usage limit)' "$log" && exit 75
exit $rc
