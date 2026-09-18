#!/usr/bin/env bash
#
# Start a local lane: a worktree from origin/master, a branch, a brief, and a
# headless Claude Code session that outlives whoever started it.
#
#   lane.sh start <name> <brief.md> [issue-number]
#   lane.sh stop  <name>            # stop the unit; keeps the worktree
#   lane.sh rm    <name>            # remove the worktree once its PR is merged
#   lane.sh list
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
[ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
cmd="${1:-}"; name="${2:-}"

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
        bash -c "claude -p \"\$(cat '$WORK/briefs/$name.md')\" --max-turns $TURNS --output-format json --permission-mode acceptEdits --allowedTools \"\$(cat '$JOBS/allowed-tools.lane')\" > '$log' 2>&1; rc=\$?; python3 '$JOBS/summarise_run.py' '$log' lane-$name >> '$WORK/logs/lane/index.tsv'; exit \$rc"
    echo "started hakux-lane-$name in $wt on $branch; log $log"
    [ -n "$issue" ] && echo "issue #$issue -- the lane opens its draft PR; the board job labels it lane:$name"
    ;;
  stop)  systemctl --user stop "hakux-lane-${name:?name}" ;;
  rm)
    wt="$WORK/wt/${name:?name}"
    systemctl --user stop "hakux-lane-$name" 2>/dev/null
    git -C "$REPO" worktree remove --force "$wt" && echo "removed $wt"
    ;;
  list)
    git -C "$REPO" worktree list
    systemctl --user list-units 'hakux-lane-*' --no-legend 2>/dev/null
    ;;
  *) sed -n '3,9p' "$0" ;;
esac
