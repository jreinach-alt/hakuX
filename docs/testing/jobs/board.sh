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
if [ -z "$fails" ]; then
    say "nothing actionable"
    exit 0
fi
say "actionable:"; printf '%s\n' "$fails" | sed 's/^/  /' | tee -a "$LOG"

brief="$WORK/briefs/board.$(date -u +%Y%m%dT%H%M%SZ).md"
{
    echo "# board tick"
    echo
    echo "fleet.py reports these actionable states. Clear each one by the rules in your role file, in this order: fold-ready, blocked-on-a-free-file, reported-not-folded, dispatchable-not-dispatched, then the rest. Anything you cannot decide by rule becomes a decision-needed issue. Do not author code. End when the list is empty or every item has a label, a comment, or an issue."
    echo
    printf '%s\n' "$fails"
} > "$brief"
exec bash "$JOBS/run-claude-job.sh" board "$WT" "$brief" "${BOARD_TURNS:-70}"
