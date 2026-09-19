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
# tick after the reset succeeds (docs/ORCHESTRATION-DESIGN.md §9.1). The test
# itself moved to jobs/window.sh, which lane.sh now shares -- a lane meeting
# a closed window used to read as a lane that failed at its work.
set -u
job=${1:?job}; wt=${2:?worktree}; brief=${3:?brief}; turns=${4:-40}
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
# Role files, the allowlist and the summariser are taken from beside THIS
# script, which board.sh runs out of the fetched trunk worktree -- never
# from the owner's checkout, whose branch is nobody's business here.
JOBS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Model by role (jobs/models.env, overridden by $WORK/limits.env): the board
# tick and triage are bookkeeping and run on the bookkeeping model; an audit
# reads code for defects and runs on the audit model.
. "$JOBS/models.env"
. "$JOBS/window.sh"          # window_limit_hit / window_note_limit
[ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
case "$job" in
    audit*) MODEL="${HAKUX_MODEL:-$MODEL_AUDIT}" ;;
    *)      MODEL="${HAKUX_MODEL:-$MODEL_BOOKKEEPING}" ;;
esac
log="$WORK/logs/$job/$(date -u +%Y%m%dT%H%M%SZ).json"
mkdir -p "$(dirname "$log")"
cd "$wt" || exit 2
br=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
git fetch -q origin && [ -n "$br" ] && git merge -q --ff-only "origin/$br" 2>/dev/null
HAKUX_ROLE="$job" HAKUX_BRIEF="$brief" \
timeout "${JOB_TIMEOUT:-50m}" claude -p "$(cat "$brief")" \
    --model "$MODEL" \
    --max-turns "$turns" \
    --output-format json \
    --permission-mode acceptEdits \
    --allowedTools "$(cat "$JOBS/allowed-tools.job")" \
    --append-system-prompt-file "$JOBS/roles/$job.md" \
    > "$log" 2>&1
rc=$?
python3 "$JOBS/summarise_run.py" "$log" "$job" "$MODEL" >> "$WORK/logs/$job/index.tsv"
if window_limit_hit "$log"; then
    # Recorded, not just returned: the hit is the fleet's only first-hand
    # evidence that the account's window closed, and board.sh's reserve reads
    # the record. Saying it here too, because a unit that merely goes orange
    # with a 75 looks exactly like a unit that is broken.
    window_note_limit "$job" "$log"
    echo "$(date -u '+%FT%TZ') $job STOPPED ON THE ACCOUNT'S USAGE WINDOW, not on its work: exit 75 (EX_TEMPFAIL), the unit's RestartSec grows, the next tick after the reset continues. Recorded in \$WORK/window/limits.tsv; the board defers dispatch while it is fresh." \
        | tee -a "$WORK/logs/$job/tick.log"
    exit 75
fi

# A TURN-CAP CUT IS NOT A FAILURE, AND MUST NOT BE REPORTED AS ONE.
#
# claude -p returns is_error with subtype error_max_turns when it reaches
# --max-turns. The work done up to that point is real and durable -- the
# board's third tick posted five comments and closed an issue, then hit the
# cap, and systemd showed nothing but `failed (Result: exit-code)`. A red
# unit for a job that did its work teaches the reader to ignore the unit.
#
# So: say it plainly in the log, and exit 0. The next tick re-derives state
# from the board and continues; that is the whole point of a stateless job.
# What it must NOT do is hide: the line below is unconditional and
# summarise_run.py records MAXTURNS in the index rather than ERR.
if grep -q '"subtype": *"error_max_turns"' "$log" 2>/dev/null; then
    echo "$(date -u '+%FT%TZ') $job HIT THE TURN CAP (--max-turns $turns) after doing work; the next tick continues. Raise ${job^^}_TURNS in \$WORK/limits.env if this repeats." \
        | tee -a "$WORK/logs/$job/tick.log"
    exit 0
fi
exit $rc
