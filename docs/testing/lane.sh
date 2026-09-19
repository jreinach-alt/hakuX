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
#   lane.sh ended <name>            # (called by the unit) mark the fleet row reported
#   lane.sh reconcile               # any fleet row 'running' with no live unit -> reported
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

# THE FLEET REGISTRY, $DISPATCH_DIR/fleet/<lane>.json, IS WRITTEN HERE.
#
# fleet.py -- and through it the board tick's script-first gate -- decides
# what is dispatchable from this registry: an issue owned by a lane whose row
# says `running` is never dispatchable, and a lane whose row never says
# `reported` is never "reported, not folded". The old orchestrator wrote the
# rows; nothing in the job harness did. Measured 2026-09-19: every lane the
# board started at 00:00Z was still `running` at 05:00Z with its unit long
# gone, every unblocked issue on the board sat behind one of them, and the
# board logged "nothing actionable" for six hours with both handhelds idle.
# So the script that starts a lane writes `running`, the unit writes
# `reported` when the session ends, and `reconcile` (run by every board
# tick) closes any row whose unit has died without saying so.
FLEET="${DISPATCH_DIR:-$WORK/dispatch}/fleet"
registry() {   # <name> <state> [issue] [brief] [worktree]
    mkdir -p "$FLEET"
    python3 - "$FLEET/$1.json" "$1" "$2" "${3:-}" "${4:-}" "${5:-}" <<'PY2'
import json, sys, os, datetime
p, lane, state, issue, brief, wt = sys.argv[1:]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
d = json.load(open(p)) if os.path.exists(p) else {}
d.update({"lane": lane, "agent": "hakux-lane-" + lane, "state": state, "waiting_on": d.get("waiting_on", "")})
if issue:
    d["issues"] = sorted(set([str(i) for i in (d.get("issues") or [])] + [str(issue)]))
d.setdefault("issues", [])
if brief and os.path.exists(brief):
    d["asked"] = open(brief).readline().lstrip("# ").strip()[:200]
if wt:
    d["worktree"] = wt
if state == "running":
    d["dispatched_utc"] = now; d.pop("reported_utc", None)
if state == "reported":
    d["reported_utc"] = now
json.dump(d, open(p, "w"), indent=2)
PY2
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
    # local.properties is gitignored and the Android build needs it.
    [ -f "$REPO/android/local.properties" ] && cp "$REPO/android/local.properties" "$wt/android/local.properties"
    log="$WORK/logs/lane/$name.$(date -u +%Y%m%dT%H%M%SZ).json"
    systemd-run --user --unit "hakux-lane-$name" --collect \
        --setenv=HAKUX_ROLE=lane --setenv=HAKUX_BRIEF="$WORK/briefs/$name.md" \
        --setenv=HAKUX_BRANCH="$branch" --setenv=HAKUX_TIP="$TIP" \
        --setenv=DISPATCH_DIR="${DISPATCH_DIR:-$WORK/dispatch}" \
        --setenv=JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}" \
        --working-directory="$wt" \
        bash -c "claude -p \"\$(cat '$WORK/briefs/$name.md')\" --model '$MODEL' --max-turns $TURNS --output-format json --permission-mode acceptEdits --append-system-prompt-file '$JOBS/roles/lane.md' --allowedTools \"\$(cat '$JOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$JOBS/summarise_run.py' '$log' lane-$name '$MODEL' >> '$WORK/logs/lane/index.tsv'; bash '$JOBS/../lane.sh' ended $name; exit \$rc"
    registry "$name" running "$issue" "$brief" "$wt"
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
    log="$WORK/logs/lane/$name.$(date -u +%Y%m%dT%H%M%SZ).json"
    systemd-run --user --unit "hakux-lane-$name" --collect \
        --setenv=HAKUX_ROLE=lane --setenv=HAKUX_BRIEF="$WORK/briefs/$name.md" \
        --setenv=HAKUX_BRANCH="$branch" --setenv=HAKUX_TIP="$TIP" \
        --setenv=DISPATCH_DIR="${DISPATCH_DIR:-$WORK/dispatch}" \
        --setenv=JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}" \
        --working-directory="$wt" \
        bash -c "claude -p \"Resuming lane $name in an existing worktree, attempt $ATTEMPT: read NOTES.md and git log first, say in NOTES.md why the previous attempt did not finish, then continue the brief below.\n\n\$(cat '$WORK/briefs/$name.md')\" --model '$MODEL' --max-turns $TURNS --output-format json --permission-mode acceptEdits --append-system-prompt-file '$JOBS/roles/lane.md' --allowedTools \"\$(cat '$JOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$JOBS/summarise_run.py' '$log' lane-$name '$MODEL' >> '$WORK/logs/lane/index.tsv'; bash '$JOBS/../lane.sh' ended $name; exit \$rc"
    registry "$name" running "" "$WORK/briefs/$name.md" "$wt"
    echo "resumed hakux-lane-$name in $wt; attempt $ATTEMPT on $MODEL; log $log"
    ;;
  rm)
    wt="$WORK/wt/${name:?name}"
    systemctl --user stop "hakux-lane-$name" 2>/dev/null
    git -C "$REPO" worktree remove --force "$wt" && echo "removed $wt"
    ;;
  attempts)
    for f in "$WORK"/attempts/*; do [ -e "$f" ] || { echo "none"; break; }; printf '%-16s %s\n' "$(basename "$f")" "$(cat "$f")"; done
    ;;
  reset)
    rm -f "$WORK/attempts/${name:?name}" && echo "attempts for $name reset"
    ;;
  ended)
    registry "${name:?name}" reported
    echo "fleet: $name reported"
    ;;
  reconcile)
    # Every row that says running while no unit of that name is active is a
    # lane that ended without saying so (a crash, a kill, a wind-down, or a
    # start that predates `ended`). Mark it reported now, so fleet.py shows
    # it as "reported, not folded" and its issues stop reading as owned.
    active=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend --plain 2>/dev/null | awk '{print $1}')
    n=0
    for f in "$FLEET"/*.json; do
        [ -f "$f" ] || continue
        st=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('state',''))" "$f" 2>/dev/null)
        [ "$st" = running ] || continue
        ln=$(basename "$f" .json)
        grep -qx "hakux-lane-$ln.service" <<< "$active" && continue
        registry "$ln" reported
        echo "fleet: $ln was running with no live unit; now reported"
        n=$((n+1))
    done
    echo "reconcile: $n row(s) closed"
    ;;
  list)
    git -C "$REPO" worktree list
    systemctl --user list-units 'hakux-lane-*' --no-legend 2>/dev/null
    ;;
  *) sed -n '3,13p' "$0" ;;
esac
