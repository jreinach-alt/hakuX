#!/usr/bin/env bash
#
# The board job. Runs from hakux-board.timer every 20 minutes.
#
# SCRIPT FIRST, MODEL SECOND (docs/ORCHESTRATION-DESIGN.md §9.1). Four cheap
# script gates decide whether this tick costs anything: fleet.py and
# check_coverage.py say what is BROKEN, and the positive gate below says when
# there is capacity and work, or a ready PR this job owes a label. If all four
# are silent, this tick costs nothing. Only when one speaks does a bounded
# claude -p session start, with their output as its brief and roles/board.md as
# its contract.
#
# `board.sh gate` runs the positive half alone and prints what it found, which
# is the answer to "there is obviously work, why did that tick not wake?".
#
# It replaces the long-lived orchestrator session and the Stop hook that
# tried to keep that session alive. Nothing here stays alive; the timer is
# the liveness.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
TIP="${HAKUX_TIP:-master}"
WT="$WORK/board-wt"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$WORK/logs/board" "$WORK/briefs"
LOG="$WORK/logs/board/tick.log"
say() { echo "$(date -u '+%FT%TZ') $*" | tee -a "$LOG"; }

# ===================================================================
# THE POSITIVE GATE
#
# The two gates further down are ERROR REPORTS, and a healthy board dispatches
# nothing. fleet.py prints FAIL when a lane is stuck, reported-but-not-folded
# or waiting; check_coverage.py prints when the tracker disagrees with GitHub.
# Neither can ever say "there is capacity and there is work".
#
# Measured 2026-09-20: six consecutive ticks (03:25, 03:46, 04:07, 04:28,
# 04:49, 05:10Z) logged `nothing actionable` with 29 issues open, 0 labelled
# dispatchable, 0 lanes running against LANE_MAX=4, and both handhelds
# attached and idle. It feeds itself -- no lane runs, so no lane commits a
# prediction, so the arms job has nothing to queue, so the devices idle -- and
# idleness is not a FAIL any gate reports. This job is the only actor
# permitted to label an issue `dispatchable` or call `lane.sh start`
# (docs/ORCHESTRATION-DESIGN.md §4), so nothing else could break the loop.
#
# script-first, model-second (§9.1) is right and is not the problem. The
# problem was that the script half only knew how to detect breakage. So: two
# POSITIVE triggers, gh calls and arithmetic, no model turn.
#
#   capacity   lanes_running < LANE_MAX and at least one open issue is
#              startable. `dispatchable` is deliberately NOT required: only
#              this job may apply it, so requiring it would make the trigger
#              as circular as the gate it sits beside.
#   labels     a PR that is ready (not a draft) and carries no state label.
#              #101 went ready at 04:36Z and #102 at 04:38Z; the 04:49Z tick
#              logged `nothing actionable` and both labels had to be set by
#              hand. This job is the only actor that sets `needs-audit-1`, or
#              `fold-ready` on a doc-only diff.
#
# WHAT KEEPS IT FROM FIRING FOREVER. A gate that always fires is this defect
# with its sign flipped: a model tick every twenty minutes for the rest of the
# account's window. Each trigger is discharged by an action this job can take
# in one tick and that GitHub then remembers. `capacity` goes quiet when
# LANE_MAX lanes are running -- lane.sh REFUSES past the cap and nothing here
# raises or bypasses it -- or when every remaining open issue carries a
# `lane:`, `blocked:*` or `decision-needed` label. `labels` goes quiet as soon
# as the state label is on the PR; `needs-rebase` counts as a state label for
# exactly this reason, because the LANE owns that fix and a PR waiting on its
# lane must not wake the board every twenty minutes.
#
# It fails QUIET, not loud: no gh, no network, no trigger. A gh outage that
# woke a model tick every twenty minutes would be worse than the idleness it
# was written to end.
# ===================================================================
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"

# The filter is the interesting half, so it runs here on gh's raw --json and
# not inside a --jq the selftest's gh shim could never evaluate.
#
# The JSON arrives as ARGV, not on stdin: `python3 - <<PY` already spends stdin
# on the script, so a piped array would be read as source and the filter would
# silently return nothing -- which reads exactly like "no work", the defect this
# file is about.
board_filter() {   # <issues|prs> <the JSON array gh printed>
    python3 - "$1" "$2" <<'PY'
import json, sys
mode = sys.argv[1]
# An issue no lane may be started on. Everything else open is startable.
SKIP = {"claimed:cloud", "decision-needed", "upstream", "unmodellable",
        "xbox-hardware", "harness-status"}
SKIP_PREFIX = ("lane:", "blocked:")
# The pipeline's states. A ready PR with none of these is waiting on the board.
# `verified`/`regressed` are the arms job's verdicts, not states: a verified PR
# with no audit label still needs needs-audit-1.
STATE = {"needs-audit-1", "needs-audit-2", "needs-remediation",
         "fold-ready", "folded", "needs-rebase"}
try:
    rows = json.loads(sys.argv[2] or "[]") or []
except Exception:
    sys.exit(0)
for r in rows:
    names = [l.get("name", "") for l in (r.get("labels") or [])]
    if mode == "issues":
        if any(n in SKIP or n.startswith(SKIP_PREFIX) for n in names):
            continue
    else:
        if r.get("isDraft"):
            continue
        if any(n in STATE for n in names):
            continue
    tail = "  [" + ",".join(names) + "]" if names else ""
    print("#%s %s%s" % (r.get("number"), (r.get("title") or "").strip(), tail))
PY
}

capacity=""; unlabelled=""; lanes=0
positive_gate() {
    # The cap, read and never raised. lane.sh's default is 2 and
    # $WORK/limits.env overrides it without a commit (it is 4 on the host).
    LANE_MAX=2
    [ -f "$SELF/models.env" ] && . "$SELF/models.env"
    [ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
    lanes=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend 2>/dev/null | wc -l)
    lanes=${lanes//[^0-9]/}; lanes=${lanes:-0}
    if ! command -v gh >/dev/null 2>&1 || ! timeout 30 gh auth status >/dev/null 2>&1; then
        say "NOTE: no usable gh; the capacity and state-label triggers are blind this tick (they fail quiet by design)"
        return
    fi
    if [ "$lanes" -lt "${LANE_MAX:-2}" ]; then
        capacity=$(board_filter issues "$(timeout 60 gh issue list --repo "$GH_REPO" \
            --state open --limit 200 --json number,title,labels 2>/dev/null)")
    fi
    unlabelled=$(board_filter prs "$(timeout 60 gh pr list --repo "$GH_REPO" \
        --state open --limit 100 --json number,title,isDraft,labels 2>/dev/null)")
}

# ONE PREDICATE, SHARED. The tick below and `board.sh gate` must agree about
# what "nothing actionable" means, or the gate is tested and the tick is not.
nothing_actionable() { [ -z "$fails$cov$capacity$unlabelled" ]; }

# `board.sh gate` -- the positive half alone, for the selftest and for a human
# asking "why did that tick not wake?". Exits 0 if it would wake the tick, 1
# if not. It runs before the worktree setup below because it needs no tree.
if [ "${1:-}" = "gate" ]; then
    fails=""; cov=""
    positive_gate
    if nothing_actionable; then echo "no positive trigger"; exit 1; fi
    [ -n "$capacity" ] && { echo "capacity: $lanes/$LANE_MAX lanes running, startable issues:"; printf '%s\n' "$capacity"; }
    [ -n "$unlabelled" ] && { echo "ready PRs with no state label:"; printf '%s\n' "$unlabelled"; }
    exit 0
fi

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

# THE AUDIT OUTLET IS DISPATCH, AND DISPATCH IS SCRIPT-FIRST.
#
# A PR labelled needs-audit-1, needs-audit-2 or needs-remediation is a unit of
# work whose brief is already written (jobs/roles/cloud.md). Nothing about
# starting it needs a model: the label IS the decision. It used to hang off
# hakux-cloud.timer, which the owner disabled on 2026-09-19, and off a rule in
# roles/board.md that could only run on a tick -- and a tick only starts when
# one of the two gates below says FAIL. Neither gate counts an unremediated
# audit, so pass 1 on #102 posted 2 MEDIUM findings, labelled it
# needs-remediation, and nothing ever picked it up.
#
# So it runs here, on the board's timer, and BEFORE the early exit below:
# a quiet fleet is exactly when the outlet has a window to spend.
# cloud.sh claims at most one unit per tick and refuses at LANE_MAX -- the same
# number and the same hakux-lane-* count as lane.sh, because an audit session
# IS a lane session.
bash "$JOBS/cloud.sh" >/dev/null 2>&1 || say "audit outlet (cloud.sh) exited $?"

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

# The positive half: is there capacity and work, and is there a ready PR this
# job owes a label? See THE POSITIVE GATE at the top of this file.
positive_gate

if nothing_actionable; then
    say "nothing actionable ($lanes/${LANE_MAX:-2} lanes, no startable issue, no unlabelled ready PR)"
    bash "$JOBS/status.sh" >/dev/null 2>&1
    exit 0
fi
say "actionable:"
[ -n "$fails" ] && printf '%s\n' "$fails" | sed 's/^/  /' | tee -a "$LOG"
[ -n "$cov" ] && { say "coverage gate:"; printf '%s\n' "$cov" | sed 's/^/  /' | tee -a "$LOG"; }
[ -n "$capacity" ] && { say "capacity: $lanes/${LANE_MAX:-2} lanes running and $(printf '%s\n' "$capacity" | wc -l | tr -d ' ') startable issue(s):"; printf '%s\n' "$capacity" | sed 's/^/  /' | tee -a "$LOG"; }
[ -n "$unlabelled" ] && { say "ready PRs with no state label:"; printf '%s\n' "$unlabelled" | sed 's/^/  /' | tee -a "$LOG"; }

brief="$WORK/briefs/board.$(date -u +%Y%m%dT%H%M%SZ).md"
{
    echo "# board tick"
    echo
    echo "Four gates report below, and ALL are yours. Push your board edits before any outward action (see your role file)."
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
    echo "## capacity -- there is room under LANE_MAX and there is startable work"
    echo
    echo "$lanes of ${LANE_MAX:-2} lanes are running. Every issue below is open, carries no \`lane:\` label, no \`claimed:cloud\`, and none of \`blocked:*\`, \`decision-needed\`, \`upstream\`, \`unmodellable\`, \`xbox-hardware\`, \`harness-status\` -- so a lane could be started on it. They are NOT all \`dispatchable\`; deciding that is your job (files free, no blocker), and only you may apply the label. Dispatch AT MOST ONE this tick, by your role file's order (severity bucket, then oldest), and label \`cloud\` the ones that need no device so the hourly cloud session takes the overflow. If \`lane.sh\` prints REFUSED you are at the cap: stop, do not retry."
    echo
    printf '%s\n' "${capacity:-none}"
    echo
    echo "## ready PRs with no state label -- the pipeline is stalled on you"
    echo
    echo "Each PR below is out of draft and carries none of \`needs-audit-1\`, \`needs-audit-2\`, \`needs-remediation\`, \`fold-ready\`, \`folded\`, \`needs-rebase\`. You are the only actor that sets the first label, so each of these is a finished lane whose work goes nowhere until you do. Per your role file: a diff touching nothing under hw/, target/, accel/, android/ needs no audit -- check CI green on its head and set \`fold-ready\` with a comment; anything else gets \`needs-audit-1\`. Set it with \`bash docs/testing/jobs/gh-label.sh add <n> <label>\`; the label flags of \`gh pr edit\` exit 1 on this host and apply nothing, which is why that helper exists."
    echo
    printf '%s\n' "${unlabelled:-none}"
    echo
    echo "Clear fleet items by the rules in your role file, in this order: fold-ready, blocked-on-a-free-file, reported-not-folded, dispatchable-not-dispatched, then the rest. Anything you cannot decide by rule becomes a decision-needed issue. Do not author code. End when every list above is empty or every item on it has a label, a comment, an issue, or (for at most one capacity item) a running lane."
} > "$brief"
bash "$JOBS/run-claude-job.sh" board "$WT" "$brief" "${BOARD_TURNS:-70}"; rc=$?
# The roll-up after every tick, model or not: the status comment is how the
# owner sees this job at all (jobs/status.sh).
bash "$JOBS/status.sh" >/dev/null 2>&1
exit $rc
