#!/usr/bin/env bash
#
# Start a local lane: a worktree from origin/master, a branch, a brief, and a
# headless Claude Code session that outlives whoever started it.
#
#   lane.sh start <name> <brief.md> [issue-number]
#   lane.sh stop  <name>            # stop the unit; keeps the worktree
#   lane.sh resume <name>           # restart a stopped lane in its own worktree (counts as an attempt)
#   lane.sh attempts | reset <name> # the per-lane attempt counter behind the escalation
#   lane.sh rm    <name>            # remove the worktree once its PR is merged
#   lane.sh list
#   lane.sh fleet-end <name> [rc]   # clear the registry entry (the unit calls this)
#   lane.sh fleet-gc                # drop registry entries whose unit is gone
#
# WHY THE WORKTREE IS MADE HERE AND NOT BY --worktree. Claude Code's own
# worktree base is origin/HEAD, which is right now that master is the trunk,
# but this script fetches first and names the base explicitly so a stale
# mirror or a mid-migration default cannot hand a lane an old tree: 49 lane
# worktrees were measured 4 to 764 commits behind on 2026-09-13. The worktree
# hangs off $REPO's object store; nothing is cloned.
#
# WHY systemd-run. A lane started from an interactive session dies with it.
# A transient user unit does not, is listable, and is stoppable by name.
#
# WHY AN EXPLICIT ALLOWLIST. Nobody answers a prompt in a unit; an unlisted
# tool call in headless mode is refused, and a lane that cannot run git,
# gradle or adb is a lane that reports nothing. jobs/allowed-tools.lane
# names what a lane may run; everything else is still refused.
#
# THE ROLE FILE. jobs/roles/lane.md is appended to every lane's system
# prompt: the PR body template, the prediction rules, and the definition of
# done (mark the PR ready, or the board resumes you). Before it, a lane had
# only its brief, and three lanes ended on finished work left in draft.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"      # the object store only
TIP="${HAKUX_TIP:-master}"
TURNS="${LANE_TURNS:-150}"
JOBS="$(cd "$(dirname "${BASH_SOURCE[0]}")/jobs" && pwd)"   # allowlist, summariser: this tree's
# THE CAP. Every lane is a model session drawing on the account's shared
# five-hour and weekly windows (docs/ORCHESTRATION-DESIGN.md §9.1), and the
# first board tick found eleven dispatchable issues. Nothing else stops a
# tick from starting eleven lanes. $WORK/limits.env overrides the default
# without a commit; the board role file tells the job to stop dispatching
# when this script refuses.
LANE_MAX=2
. "$JOBS/models.env"
[ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
cmd="${1:-}"; name="${2:-}"

# ---------------------------------------------------------------- the registry
#
# $DISPATCH_DIR/fleet/<lane>.json used to be written by the orchestrator, and
# when ORCHESTRATION-DESIGN.md §4 deleted that role nothing took over: the
# files froze, and fleet.py -- the board's only sensor -- went on reporting
# them. On 2026-09-19 it named four running lanes, two of which were not
# running and one of which had been merged, while eight real units went
# unmentioned. See the header of fleet.py.
#
# fleet.py derives the running set from systemd now, so THIS FILE NO LONGER
# CARRIES STATE. It carries only what this script knows first-hand at the
# moment it starts a unit: the brief it handed over, the issue, the attempt,
# the model, the branch and worktree. There is no `state` field to go stale,
# and fleet.py ignores any entry whose unit is not active -- so the worst a
# crashed lane can leave behind is a file that costs disk.
#
# WHAT A MISSING ENTRY COSTS: the `asked` prose and the issue list. A lane
# whose entry is missing still appears in RUNNING, with its issue unlisted --
# so its issue can show up as DISPATCHABLE and the board takes a second look
# at work already in hand. Over-claiming would hide work; this errs the other
# way on purpose.
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
FLEETD="${DISPATCH_DIR:-$WORK/dispatch}/fleet"

fleet_write() {   # <name> <branch> <worktree> <brief> <issue> <attempt> <model>
    mkdir -p "$FLEETD" 2>/dev/null || return 0
    # Built and serialised by json.dump, never by pasting strings into a
    # heredoc: a brief with a quote or a backslash in it would otherwise
    # write a file fleet.py reports as UNREADABLE, and the failure would be
    # invisible until the next board tick.
    python3 - "$FLEETD/$1.json" "$@" <<'PYFLEET' || true
import datetime, json, os, re, sys
path, lane, branch, wt, brief, issue, attempt, model = sys.argv[1:9]
asked = ""
try:
    asked = re.sub(r"\s+", " ", open(brief, encoding="utf-8", errors="replace")
                   .read()).strip()[:400]
except OSError:
    pass
json.dump({"lane": lane, "unit": "hakux-lane-%s.service" % lane,
           "branch": branch, "worktree": wt, "brief": brief,
           "issues": [issue] if issue else [],
           "asked": asked, "attempt": attempt, "model": model,
           "started_utc": datetime.datetime.now(datetime.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ")},
          open(path + ".tmp", "w"), indent=1)
os.replace(path + ".tmp", path)
PYFLEET
}

# ATTEMPTS AND ESCALATION. Every start or resume of a lane is one attempt at
# its issue, counted in $WORK/attempts/<name>. The first LANE_ESCALATE_AFTER
# attempts run on MODEL_LANE; the next one runs on MODEL_LANE_ESCALATED, the
# most capable model, because three failed passes on Opus is the signal that
# the problem needs more reasoning, not more turns. After LANE_MAX_ATTEMPTS
# the script refuses: the board opens a decision-needed issue instead of
# spending a fifth session. `lane.sh attempts <name>` shows the count;
# `lane.sh reset <name>` clears it when the brief itself was the problem.
next_attempt() {   # prints the attempt number this start will be, and the model for it
    local f="$WORK/attempts/$1" n
    mkdir -p "$WORK/attempts"
    n=$(( $(cat "$f" 2>/dev/null || echo 0) + 1 ))
    if [ "$n" -gt "$LANE_MAX_ATTEMPTS" ]; then
        echo "REFUSED: lane $1 has had $(( n - 1 )) attempts (LANE_MAX_ATTEMPTS=$LANE_MAX_ATTEMPTS), the last on $MODEL_LANE_ESCALATED. Open a decision-needed issue; do not start it again." >&2
        return 75
    fi
    if [ "$n" -gt "$LANE_ESCALATE_AFTER" ]; then MODEL="${HAKUX_MODEL:-$MODEL_LANE_ESCALATED}"; else MODEL="${HAKUX_MODEL:-$MODEL_LANE}"; fi
    echo "$n" > "$f"
    ATTEMPT=$n
}

case "$cmd" in
  start)
    brief="${3:?usage: lane.sh start <name> <brief.md> [issue]}"; issue="${4:-}"
    [ -f "$brief" ] || { echo "no such brief: $brief" >&2; exit 2; }
    wt="$WORK/wt/$name"; branch="lane/$name"
    mkdir -p "$WORK/wt" "$WORK/briefs" "$WORK/logs/lane"
    if [ -e "$wt" ]; then echo "worktree exists: $wt (lane.sh rm $name first)" >&2; exit 3; fi
    active=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend 2>/dev/null | wc -l)
    if [ "$active" -ge "$LANE_MAX" ]; then
        echo "REFUSED: $active lane(s) already running and LANE_MAX=$LANE_MAX ($WORK/limits.env). Dispatch nothing more this tick." >&2
        exit 75
    fi
    git -C "$REPO" fetch -q origin "$TIP" || { echo "fetch of origin/$TIP failed" >&2; exit 4; }
    if git -C "$REPO" rev-parse --verify --quiet "refs/remotes/origin/$branch" >/dev/null; then
        # A lane resuming after a wind-down or a crash continues its own branch.
        git -C "$REPO" fetch -q origin "$branch"
        git -C "$REPO" worktree add --quiet "$wt" -B "$branch" "origin/$branch" || exit 5
        echo "resumed $branch from origin"
    else
        git -C "$REPO" worktree add --quiet "$wt" -b "$branch" FETCH_HEAD || exit 5
    fi
    next_attempt "$name" || exit 75
    cp "$brief" "$WORK/briefs/$name.md"
    # `resume` takes no issue argument and the registry entry is gone by then,
    # so the issue has to outlive the unit somewhere. One line beside the brief.
    printf '%s\n' "$issue" > "$WORK/briefs/$name.issue"
    fleet_write "$name" "$branch" "$wt" "$WORK/briefs/$name.md" "$issue" "$ATTEMPT" "$MODEL"
    # local.properties is gitignored and the Android build needs it.
    [ -f "$REPO/android/local.properties" ] && cp "$REPO/android/local.properties" "$wt/android/local.properties"
    log="$WORK/logs/lane/$name.$(date -u +%Y%m%dT%H%M%SZ).json"
    systemd-run --user --unit "hakux-lane-$name" --collect \
        --setenv=HAKUX_ROLE=lane --setenv=HAKUX_BRIEF="$WORK/briefs/$name.md" \
        --setenv=HAKUX_BRANCH="$branch" --setenv=HAKUX_TIP="$TIP" \
        --setenv=DISPATCH_DIR="${DISPATCH_DIR:-$WORK/dispatch}" \
        --setenv=JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}" \
        --working-directory="$wt" \
        bash -c "claude -p \"\$(cat '$WORK/briefs/$name.md')\" --model '$MODEL' --max-turns $TURNS --output-format json --permission-mode acceptEdits --append-system-prompt-file '$JOBS/roles/lane.md' --allowedTools \"\$(cat '$JOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$JOBS/summarise_run.py' '$log' lane-$name '$MODEL' >> '$WORK/logs/lane/index.tsv'; bash '$SELF' fleet-end '$name' \$rc; exit \$rc"
    echo "started hakux-lane-$name in $wt on $branch; attempt $ATTEMPT on $MODEL; log $log"
    [ -n "$issue" ] && echo "issue #$issue -- the lane opens its draft PR; the board job labels it lane:$name"
    ;;
  stop)  systemctl --user stop "hakux-lane-${name:?name}" ;;
  resume)
    # A stopped lane keeps its worktree, its branch and its NOTES.md. Start a
    # fresh session there with the same brief; the SessionStart hook prints
    # the base check and the lane reads its own git log and notes first.
    wt="$WORK/wt/${name:?name}"; branch="lane/$name"
    [ -d "$wt" ] || { echo "no worktree at $wt; use lane.sh start" >&2; exit 3; }
    [ -f "$WORK/briefs/$name.md" ] || { echo "no brief at $WORK/briefs/$name.md" >&2; exit 3; }
    active=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend 2>/dev/null | wc -l)
    if [ "$active" -ge "$LANE_MAX" ]; then
        echo "REFUSED: $active lane(s) already running and LANE_MAX=$LANE_MAX ($WORK/limits.env)." >&2
        exit 75
    fi
    next_attempt "$name" || exit 75
    fleet_write "$name" "$branch" "$wt" "$WORK/briefs/$name.md" \
                "$(cat "$WORK/briefs/$name.issue" 2>/dev/null)" "$ATTEMPT" "$MODEL"
    log="$WORK/logs/lane/$name.$(date -u +%Y%m%dT%H%M%SZ).json"
    systemd-run --user --unit "hakux-lane-$name" --collect \
        --setenv=HAKUX_ROLE=lane --setenv=HAKUX_BRIEF="$WORK/briefs/$name.md" \
        --setenv=HAKUX_BRANCH="$branch" --setenv=HAKUX_TIP="$TIP" \
        --setenv=DISPATCH_DIR="${DISPATCH_DIR:-$WORK/dispatch}" \
        --setenv=JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}" \
        --working-directory="$wt" \
        bash -c "claude -p \"Resuming lane $name in an existing worktree, attempt $ATTEMPT: read NOTES.md and git log first, say in NOTES.md why the previous attempt did not finish, then continue the brief below.\n\n\$(cat '$WORK/briefs/$name.md')\" --model '$MODEL' --max-turns $TURNS --output-format json --permission-mode acceptEdits --append-system-prompt-file '$JOBS/roles/lane.md' --allowedTools \"\$(cat '$JOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$JOBS/summarise_run.py' '$log' lane-$name '$MODEL' >> '$WORK/logs/lane/index.tsv'; bash '$SELF' fleet-end '$name' \$rc; exit \$rc"
    echo "resumed hakux-lane-$name in $wt; attempt $ATTEMPT on $MODEL; log $log"
    ;;
  rm)
    wt="$WORK/wt/${name:?name}"
    systemctl --user stop "hakux-lane-$name" 2>/dev/null
    git -C "$REPO" worktree remove --force "$wt" && echo "removed $wt"
    ;;
  fleet-end)
    # Called by the unit's own command line after summarise_run.py, so the
    # entry describes a lane that exists and nothing else. The final shape
    # goes to history.jsonl -- fleet.py reads only *.json, so it never sees
    # it -- and answers "what was this lane asked, and how did it end?" after
    # the entry is gone. A SIGKILLed unit skips this; that is precisely why
    # fleet.py asks systemd rather than this directory who is running.
    f="$FLEETD/${name:?name}.json"
    [ -f "$f" ] || exit 0
    python3 - "$f" "$FLEETD/history.jsonl" "${3:-}" <<'PYEND' || true
import datetime, json, sys
src, hist, rc = sys.argv[1:4]
try:
    e = json.load(open(src))
except Exception:
    e = {}
e["ended_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
e["rc"] = rc
with open(hist, "a") as fh:
    fh.write(json.dumps(e) + "\n")
PYEND
    rm -f "$f"
    ;;
  fleet-gc)
    # The 38 entries the deleted orchestrator left behind, and anything a
    # killed unit drops. REFUSES if systemd cannot be reached: an empty
    # active set would otherwise read as "nothing is running" and delete the
    # live fleet's entries -- the same mistake, in the other direction.
    units=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend --plain 2>/dev/null) \
        || { echo "REFUSED: systemctl --user did not answer; an empty active set is not an idle fleet." >&2; exit 1; }
    active=" $(echo "$units" | awk '{print $1}' | sed 's/^hakux-lane-//; s/\.service$//' | tr '\n' ' ')"
    n=0
    for f in "$FLEETD"/*.json; do
        [ -f "$f" ] || continue
        l=$(basename "$f" .json)
        case "$active" in *" $l "*) continue ;; esac
        rm -f "$f" && n=$((n+1))
    done
    echo "fleet-gc: removed $n entr(y|ies) with no active unit; kept$active"
    ;;
  attempts)
    for f in "$WORK"/attempts/*; do [ -e "$f" ] || { echo "none"; break; }; printf '%-16s %s\n' "$(basename "$f")" "$(cat "$f")"; done
    ;;
  reset)
    rm -f "$WORK/attempts/${name:?name}" && echo "attempts for $name reset"
    ;;
  list)
    git -C "$REPO" worktree list
    systemctl --user list-units 'hakux-lane-*' --no-legend 2>/dev/null
    ;;
  *) sed -n '3,13p' "$0" ;;
esac
