#!/usr/bin/env bash
#
# The board job. Runs from hakux-board.timer every 20 minutes.
#
# SCRIPT FIRST, MODEL SECOND (docs/ORCHESTRATION-DESIGN.md §9.1). fleet.py is
# a script and says, on stderr, exactly what is actionable right now. If it
# says nothing, this tick costs nothing. Only when there is something to act
# on does a bounded claude -p session start, with the FAIL lines as its
# brief and roles/board.md as its contract.
#
# It replaces the long-lived orchestrator session and the Stop hook that
# tried to keep that session alive. Nothing here stays alive; the timer is
# the liveness.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
TIP="${HAKUX_TIP:-master}"
WT="$WORK/board-wt"
mkdir -p "$WORK/logs/board" "$WORK/briefs"
LOG="$WORK/logs/board/tick.log"
say() { echo "$(date -u '+%FT%TZ') $*" | tee -a "$LOG"; }

# A private worktree of the trunk, so this job never reads the owner's checkout.
if [ ! -e "$WT/.git" ]; then
    git -C "$REPO" fetch -q origin "$TIP" && git -C "$REPO" worktree add --quiet --detach "$WT" FETCH_HEAD \
        || { say "cannot create $WT"; exit 1; }
fi
git -C "$WT" fetch -q origin "$TIP" && git -C "$WT" checkout -q --detach FETCH_HEAD
git -C "$WT" fetch -q origin board 2>/dev/null || true

# RUN THE TRUNK'S COPY OF THIS JOB, NOT THE OWNER'S CHECKOUT'S. The unit's
# ExecStart names /home/justin/hakuX, which is whatever branch the owner last
# checked out there; the first evening it was the design branch. Everything
# after this line -- fleet.py, run-claude-job.sh, the role file, the
# allowlist, lane.sh -- comes from $WT, which is origin/master as of this
# tick. The owner's checkout supplies the object store and nothing else.
if [ -z "${HAKUX_BOARD_REEXEC:-}" ] && [ -f "$WT/docs/testing/jobs/board.sh" ]; then
    # SAY SO WHEN THE LAUNCH POINT IS STALE. The unit's ExecStart names the
    # owner's checkout, and on the first evening that checkout sat 8 commits
    # behind master -- so three ticks ran without the turn budget, the lane
    # cap or the allowlist that had already been merged, and nothing said
    # why. The re-exec below fixes it from here on, but the re-exec itself
    # is read from the stale copy, so the first tick after a merge is the
    # one that cannot self-heal. One line beats re-deriving that twice.
    behind=$(git -C "$REPO" rev-list --count HEAD.."origin/$TIP" 2>/dev/null || echo 0)
    [ "${behind:-0}" -gt 0 ] && say "NOTE: $REPO (the unit's ExecStart path) is $behind commit(s) behind origin/$TIP; re-execing the trunk's copy. Run: git -C $REPO checkout $TIP && git -C $REPO pull --ff-only"
    HAKUX_BOARD_REEXEC=1 exec bash "$WT/docs/testing/jobs/board.sh"
fi
JOBS="$WT/docs/testing/jobs"

fails=$(cd "$WT" && timeout 60 python3 docs/testing/fleet.py 2>&1 >/dev/null | grep '^FAIL' || true)

# THE COVERAGE GATE IS THE BOARD'S TOO, AND fleet.py CANNOT SEE IT.
#
# fleet.py reports what the FLEET is doing. preflight's coverage gate reports
# whether the TRACKER agrees with GitHub -- and AGENTS.md's "a lane cannot
# satisfy a gate it is barred from fixing" says five of its six FAIL paths can
# only be cleared by editing nv2a_issues.toml, which only this job may touch.
#
# So a stale row makes every lane's push gate red and no lane can fix it,
# while the only actor who can was never shown it. Measured 2026-09-19: nine
# rows said `open` for issues closed on GitHub -- four of them closed by this
# very job minutes earlier -- and three ticks passed without touching them,
# because they were not on fleet.py's list.
#
# Fails open exactly as check_coverage.py does: no gh, no network, no
# section.
cov=$(cd "$WT" && timeout 60 python3 docs/testing/check_coverage.py 2>&1 | grep -E '^(FAIL|  #)' | head -40 || true)

if [ -z "$fails" ] && [ -z "$cov" ]; then
    say "nothing actionable"
    exit 0
fi
say "actionable:"; printf '%s\n' "$fails" | sed 's/^/  /' | tee -a "$LOG"
[ -n "$cov" ] && { say "coverage gate:"; printf '%s\n' "$cov" | sed 's/^/  /' | tee -a "$LOG"; }

brief="$WORK/briefs/board.$(date -u +%Y%m%dT%H%M%SZ).md"
{
    echo "# board tick"
    echo
    echo "Two gates report below, and BOTH are yours. Push your board edits before any outward action (see your role file)."
    echo
    echo "## fleet.py -- what the fleet is doing"
    echo
    printf '%s\n' "${fails:-none}"
    echo
    echo "## preflight coverage gate -- whether the tracker agrees with GitHub"
    echo
    echo "Every row here makes preflight RED FOR EVERY LANE, and no lane may edit nv2a_issues.toml, so you are the only actor who can clear it. Reconcile each row's status with the issue's real state on GitHub. Clear these FIRST: a lane that cannot push is a lane whose work is stranded."
    echo
    printf '%s\n' "${cov:-none}"
    echo
    echo "Clear fleet items by the rules in your role file, in this order: fold-ready, blocked-on-a-free-file, reported-not-folded, dispatchable-not-dispatched, then the rest. Anything you cannot decide by rule becomes a decision-needed issue. Do not author code. End when both lists are empty or every item has a label, a comment, or an issue."
} > "$brief"
exec bash "$JOBS/run-claude-job.sh" board "$WT" "$brief" "${BOARD_TURNS:-70}"
