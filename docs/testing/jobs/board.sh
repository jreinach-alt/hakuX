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
. "$SELF/localtime.sh"  # say_time/local_ts: the display zone. Data timestamps below stay `date -u`.
mkdir -p "$WORK/logs/board" "$WORK/briefs" "$WORK/board"
LOG="$WORK/logs/board/tick.log"
# The tick log is read by hand when something jams, so it is display: local.
say() { echo "$(say_time_s) $*" | tee -a "$LOG"; }
# The account's five-hour and weekly windows: window_check / window_defer_line.
# Sourced from beside THIS file, which is the fetched trunk's copy after the
# re-exec below, so the reserve is the trunk's rule and not the owner's
# checkout's.
. "$SELF/window.sh"

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
#
# THE ISSUES COME OUT IN DISPATCH ORDER, NOT gh's. gh lists newest first, and
# the role file used to say "severity bucket, then oldest" over a tracker that
# recorded no size at all -- so a 5k-px edge case and a 1.5 M-px family looked
# the same, and the owner asked (2026-09-25) for the broad ones to go first.
# The host now writes four fields on each tracker row and the board keeps them
# current; this sorts on them, and prints the key on every line so the board
# and a human can see why a row ranks where it does:
#
#   1. game_visible = true                      [game]
#   2. impact_px + impact_onestep_px // 4 > 0, descending  [impact N px]
#      (one-step px count a quarter: they are rounding, not rules)
#   3. a row with no impact fields, oldest first        [no impact estimate]
#   4. a measured zero, oldest first                    [impact 0 px, measured]
#      (host decision 2026-09-25: "measured, nothing recoverable" ranks below
#      an unestimated row, which may be large)
#   5. an issue with no tracker row at all, oldest first [no tracker row]
#
# Ties inside a tier go to the oldest issue. The tracker is read through
# board_files.load, as every other board tool reads it, so this sees
# origin/board and not a fold-lagged copy. If it cannot be read the list is
# still printed -- an unreadable tracker must not read as "no work", which is
# the defect this gate exists to end -- every line says so, and the order is
# oldest first.
board_filter() {   # <issues|prs> <the JSON array gh printed>
    python3 - "$1" "$2" "$SELF/.." <<'PY'
import json, math, sys
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
out = []
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
    out.append((r, (r.get("title") or "").strip() + tail))
if mode != "issues":
    for r, text in out:
        print("#%s %s" % (r.get("number"), text))
    sys.exit(0)

tracker = None
try:
    sys.path.insert(0, sys.argv[3])
    import board_files
    tracker = board_files.load("nv2a_issues.toml").get("issue") or {}
except Exception:
    pass

def num(r):
    try:
        return int(r.get("number"))
    except (TypeError, ValueError):
        return 1 << 62

def rank(r):
    n = num(r)
    if tracker is None:
        return (4, 0, n), "[tracker unreadable]"
    row = tracker.get(str(r.get("number")))
    if not isinstance(row, dict):
        return (4, 0, n), "[no tracker row]"
    # A value is read as a finite real number -- int OR float: the role file
    # asks for size times tractability, a product that a TOML writer emits as
    # 746668.0 -- and used by its integer part. Anything else that is present
    # (a string, nan, inf) is UNREADABLE: it must neither raise (one bad row
    # must not empty the whole list) nor be read as 0, because a measured zero
    # is a tier of its own that dispatches last and says "measured". An
    # unreadable row ranks with the unestimated ones and names the bad field.
    vals, bad = [], []
    for f in ("impact_px", "impact_onestep_px"):
        v = row.get(f)
        if (isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v)):
            vals.append(int(v))
        else:
            vals.append(0)
            if v is not None:
                bad.append("%s=%r" % (f, v))
    px, one = vals
    score = px + one // 4
    size = "impact {:,} px".format(score)
    if one:
        size += " = {:,} structural + {:,} one-step / 4".format(px, one)
    unread = "impact unreadable: " + ", ".join(bad)
    if row.get("game_visible") is True:
        if bad:
            return (0, -score, n), "[game; %s]" % unread
        key = "[game]" if not score else "[game; %s]" % size
        return (0, -score, n), key
    if bad:
        return (2, 0, n), "[%s]" % unread
    if "impact_px" in row or "impact_onestep_px" in row:
        if score <= 0:
            return (3, 0, n), "[impact 0 px, measured]"
        return (1, -score, n), "[%s]" % size
    return (2, 0, n), "[no impact estimate]"

ranked = sorted((rank(r) + (r, text) for r, text in out), key=lambda t: t[0])
for _, key, r, text in ranked:
    print("#%s %s %s" % (r.get("number"), key, text))
PY
}

# FILES RELEASED AT READY (roles/board.md), for the capacity section.
#
# The capacity list above is issues, and the tracker records no files per
# issue, so which issue a free file unblocks is the board's reading. What the
# board could NOT read before is that a file held by a finished lane is free:
# on 2026-09-26 every tick said "every issue needs a file another lane holds"
# while nine hot files sat with lanes waiting only on audit and fold. A row's
# `released = [...]` says so, and this prints each such file with its state:
#   AVAILABLE                       -- start the next lane on it
#   taken by lane.<x>               -- one later lane already has it
# The PR the release came from is `released_at_ready` on the row, if written.
board_released() {   # <dir holding board_files.py>
    python3 - "$1" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
try:
    import board_files
    rows = board_files.load("territory.toml").get("lane") or {}
except Exception as e:
    print("(territory.toml unreadable: %s -- released files unknown)" % e)
    sys.exit(0)
for lane, meta in sorted(rows.items()):
    pr = meta.get("released_at_ready")
    src = "lane.%s%s" % (lane, " (PR #%s ready)" % pr if pr else "")
    for f in meta.get("released") or []:
        taken = [l for l, m in rows.items() if l != lane
                 and f in (m.get("files") or [])
                 and f not in (m.get("released") or [])]
        print("%s  released by %s -- %s"
              % (f, src, "taken by lane." + taken[0] if taken else "AVAILABLE"))
PY
}

# ===================================================================
# THE ISSUE SWEEP'S FINDINGS (jobs/issue-sweep.sh), AS A FIFTH GATE
#
# The sweep decides what is decidable from files -- an open issue with no
# tracker row, a row owned by a lane that no longer exists, an untriaged
# disposition, a row that already says the work is done -- and then stops,
# because the remaining half ("is this blocker still true?") is judgement and
# THIS is the harness's actor for judgement. It is also the only actor
# permitted to write nv2a_issues.toml, so a second model session on a second
# timer would be a second writer of one file reaching the same conclusions
# from a worse vantage point.
#
# WHAT KEEPS IT FROM FIRING FOREVER -- the rule this file states for every
# other trigger, and the reason the key is a CONTENT hash and not a timestamp.
# The sweep runs twice a day and rewrites the same findings while they remain
# true, so a gate that merely asked "does the file exist?" would wake a model
# tick every twenty minutes for as long as one issue stayed untriaged. Keyed
# on the file's sha256, one SET of findings wakes at most one tick; discharge
# any part of it and the next sweep writes a different set, which fires again.
#
# AND IT IS MARKED SEEN ONLY WHEN A TICK ACTUALLY RAN (below, after
# run-claude-job.sh returns 0). Marking here would discharge the findings on a
# tick that died before reading them, and the sweep would never re-offer them:
# the file it writes next would hash the same.
SWEEP_FINDINGS="$WORK/board/issue-sweep.findings"
SWEEP_SEEN="$WORK/board/issue-sweep.seen"
sweep=""; SWEEP_HASH=""
sweep_gate() {
    local h
    [ -s "$SWEEP_FINDINGS" ] || return 0
    h=$(sha256sum "$SWEEP_FINDINGS" 2>/dev/null | cut -d' ' -f1)
    [ -n "$h" ] || return 0            # no sha256sum: no key, so no trigger
    [ "$h" = "$(cat "$SWEEP_SEEN" 2>/dev/null)" ] && return 0
    sweep=$(cat "$SWEEP_FINDINGS")
    SWEEP_HASH="$h"
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
    # THE RESERVE (docs/ORCHESTRATION-DESIGN.md §9.1), and why it lands on
    # `capacity` rather than on the whole tick. Starting a lane or an audit is
    # what spends the account's window; labelling a ready PR, reading the two
    # error gates and rewriting the status page are what keep the fleet
    # legible, and they cost a Sonnet tick at most. So a deferral takes the
    # dispatch trigger away and leaves everything else running -- and it takes
    # it away HERE, in the gate, rather than by telling the model not to
    # dispatch: a tick that wakes every twenty minutes to be told there is
    # work it may not start is the expensive half of the thing being deferred.
    #
    # window_check fails open: an unknown window leaves WINDOW_DEFER=0.
    window_check
    if [ "${WINDOW_DEFER:-0}" = 1 ]; then
        say "$(window_defer_line "lane and audit dispatch")"
    elif [ "${WINDOW_ZONE:-0}" = 1 ]; then
        # In the reserve's own stretch of the week and dispatching anyway,
        # which is the RIGHT answer when nothing has been measured -- but a
        # control that is inert and silent cannot be told from one that works.
        say "NOTE: this is the last fifth of the weekly window, and dispatch is going ahead. $WINDOW_FACTS"
    fi
    if ! command -v gh >/dev/null 2>&1 || ! timeout 30 gh auth status >/dev/null 2>&1; then
        say "NOTE: no usable gh; the capacity and state-label triggers are blind this tick (they fail quiet by design)"
        return
    fi
    if [ "$lanes" -lt "${LANE_MAX:-2}" ] && [ "${WINDOW_DEFER:-0}" != 1 ]; then
        capacity=$(board_filter issues "$(timeout 60 gh issue list --repo "$GH_REPO" \
            --state open --limit 200 --json number,title,labels 2>/dev/null)")
    fi
    unlabelled=$(board_filter prs "$(timeout 60 gh pr list --repo "$GH_REPO" \
        --state open --limit 100 --json number,title,isDraft,labels 2>/dev/null)")
}

# ONE PREDICATE, SHARED. The tick below and `board.sh gate` must agree about
# what "nothing actionable" means, or the gate is tested and the tick is not.
nothing_actionable() { [ -z "$fails$cov$capacity$unlabelled$sweep" ]; }

# `board.sh gate` -- the positive half alone, for the selftest and for a human
# asking "why did that tick not wake?". Exits 0 if it would wake the tick, 1
# if not. It runs before the worktree setup below because it needs no tree.
if [ "${1:-}" = "gate" ]; then
    fails=""; cov=""
    positive_gate
    # A PROBE MARKS NOTHING SEEN. `gate` is what a person runs to ask why a
    # tick did not wake, and the selftest runs it too; if it discharged the
    # sweep's findings they would be gone before any tick read them.
    sweep_gate
    if nothing_actionable; then echo "no positive trigger"; exit 1; fi
    [ -n "$capacity" ] && { echo "capacity: $lanes/$LANE_MAX lanes running, startable issues:"; printf '%s\n' "$capacity"; }
    [ -n "$unlabelled" ] && { echo "ready PRs with no state label:"; printf '%s\n' "$unlabelled"; }
    [ -n "$sweep" ] && { echo "issue-sweep findings not yet seen (sha ${SWEEP_HASH:0:12}):"; printf '%s\n' "$sweep" | grep '^### ' | sed 's/^/  /'; }
    exit 0
fi

# `board.sh released` -- the released-files list the tick brief carries, alone.
if [ "${1:-}" = "released" ]; then board_released "$SELF/.."; exit 0; fi

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
#
# AND IT IS DISPATCH, so the reserve covers it: §9.1 reserves the last fifth
# of the weekly window from "lanes and audits", and an audit session is a lane
# session. A claim made here starts a model session immediately, so the check
# has to be on this side of the call -- cloud.sh has no idea whose timer it is
# on. An audit already running is left alone; only the claim is deferred.
window_check
if [ "${WINDOW_DEFER:-0}" = 1 ]; then
    say "$(window_defer_line "the audit outlet's next claim")"
else
    bash "$JOBS/cloud.sh" >/dev/null 2>&1 || say "audit outlet (cloud.sh) exited $?"
fi

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
# And the issue sweep's handoff, if it has written a set this job has not read.
sweep_gate

if nothing_actionable; then
    # "no startable issue" would be a lie while the reserve holds -- the
    # capacity trigger was taken away, not found empty -- and this line is
    # what the status page shows.
    if [ "${WINDOW_DEFER:-0}" = 1 ]; then
        say "nothing actionable ($lanes/${LANE_MAX:-2} lanes, no unlabelled ready PR) AND dispatch is deferred until $WINDOW_UNTIL -- capacity was not consulted"
    else
        say "nothing actionable ($lanes/${LANE_MAX:-2} lanes, no startable issue, no unlabelled ready PR)"
    fi
    bash "$JOBS/status.sh" >/dev/null 2>&1
    exit 0
fi
say "actionable:"
[ -n "$fails" ] && printf '%s\n' "$fails" | sed 's/^/  /' | tee -a "$LOG"
[ -n "$cov" ] && { say "coverage gate:"; printf '%s\n' "$cov" | sed 's/^/  /' | tee -a "$LOG"; }
[ -n "$capacity" ] && { say "capacity: $lanes/${LANE_MAX:-2} lanes running and $(printf '%s\n' "$capacity" | wc -l | tr -d ' ') startable issue(s):"; printf '%s\n' "$capacity" | sed 's/^/  /' | tee -a "$LOG"; }
[ -n "$unlabelled" ] && { say "ready PRs with no state label:"; printf '%s\n' "$unlabelled" | sed 's/^/  /' | tee -a "$LOG"; }
[ -n "$sweep" ] && { say "issue sweep (sha ${SWEEP_HASH:0:12}):"; printf '%s\n' "$sweep" | grep '^### ' | sed 's/^/  /' | tee -a "$LOG"; }

# UTC in the FILENAME: data. These sort, and `ls` ordering is how a stack of
# them is read back; a local-time name would jumble across the fall-back.
brief="$WORK/briefs/board.$(date -u +%Y%m%dT%H%M%SZ).md"
{
    echo "# board tick"
    echo
    echo "Five gates report below, and ALL are yours. Push your board edits before any outward action (see your role file)."
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
    [ "${WINDOW_DEFER:-0}" = 1 ] && { echo "**START NO LANE AND CLAIM NO AUDIT THIS TICK.** $WINDOW_WHY. Dispatch resumes at $WINDOW_UNTIL and the list below is deliberately empty; do not go looking for startable issues yourself. Everything else in this brief is still yours: labels, the coverage gate, comments, briefs. This is a budget decision, not a failure -- do not open a decision-needed issue about it. ($WINDOW_FACTS)"; echo; }
    echo "$lanes of ${LANE_MAX:-2} lanes are running. Every issue below is open, carries no \`lane:\` label, no \`claimed:cloud\`, and none of \`blocked:*\`, \`decision-needed\`, \`upstream\`, \`unmodellable\`, \`xbox-hardware\`, \`harness-status\` -- so a lane could be started on it. They are NOT all \`dispatchable\`; deciding that is your job (files free, no blocker), and only you may apply the label. Dispatch UP TO THREE this tick (roles/board.md), in the order listed (it is sorted by expected improvement: game-visible, then recoverable px, and each line shows its key), each on files that are free with no blocker, and label \`cloud\` the ones that need no device so the hourly cloud session takes the overflow. If \`lane.sh\` prints REFUSED you are at the cap: stop, do not retry."
    echo
    printf '%s\n' "${capacity:-none}"
    echo
    echo "### files released at ready -- free for the rule above"
    echo
    echo "Each file below is held by a lane whose PR is ready (out of draft, CI green, unit gone), and its row lists it in \`released\`. An AVAILABLE one counts as free: start the next lane on it, and its brief names the ready PR on that file and says to merge master (or that PR's branch, if it has not folded) and re-run its arm before marking its own PR ready (roles/board.md, release at ready). A file taken by a later lane is not free again."
    echo
    released=$(board_released "$WT/docs/testing")
    printf '%s\n' "${released:-none}"
    echo
    echo "## ready PRs with no state label -- the pipeline is stalled on you"
    echo
    echo "Each PR below is out of draft and carries none of \`needs-audit-1\`, \`needs-audit-2\`, \`needs-remediation\`, \`fold-ready\`, \`folded\`, \`needs-rebase\`. You are the only actor that sets the first label, so each of these is a finished lane whose work goes nowhere until you do. Per your role file: a diff touching nothing under hw/, target/, accel/, android/ needs no audit -- check CI green on its head and set \`fold-ready\` with a comment; anything else gets \`needs-audit-1\`. Set it with \`bash docs/testing/jobs/gh-label.sh add <n> <label>\`; the label flags of \`gh pr edit\` exit 1 on this host and apply nothing, which is why that helper exists."
    echo
    printf '%s\n' "${unlabelled:-none}"
    echo
    echo "## issue sweep -- backlog states that no other actor reaches"
    echo
    echo "From \`docs/testing/jobs/issue-sweep.sh\`, which decides what is decidable from files and stops there. It repairs nothing, because \`nv2a_issues.toml\` has exactly one writer and it is you. Each section below says what it costs and what the decision is; the judgement half -- is this blocker still true, can this \`decision-needed\` be settled -- is why it was handed to a tick and not to a second script. You are seeing this set ONCE: it is keyed on its own sha256 and marked read when this tick returns, so leaving an item undone means it will not wake another tick until the sweep's findings change. Act on it here, or say in the row or on the issue why it stays."
    echo
    printf '%s\n' "${sweep:-none}"
    echo
    echo "Clear fleet items by the rules in your role file, in this order: fold-ready, blocked-on-a-free-file, reported-not-folded, dispatchable-not-dispatched, then the rest. Anything you cannot decide by rule becomes a decision-needed issue. Do not author code. End when every list above is empty or every item on it has a label, a comment, an issue, or (for up to three capacity items) a running lane."
} > "$brief"
bash "$JOBS/run-claude-job.sh" board "$WT" "$brief" "${BOARD_TURNS:-70}"; rc=$?
# MARKED SEEN ONLY NOW, AND ONLY ON A TICK THAT RAN. The sweep rewrites the
# same findings for as long as they hold, so without this key one untriaged
# row would wake a model tick every twenty minutes; and marking it before the
# session -- or after a session that failed to start -- would discharge a set
# nobody read, which the sweep cannot re-offer because its next file hashes
# the same.
if [ -n "$SWEEP_HASH" ] && [ "$rc" = 0 ]; then
    printf '%s\n' "$SWEEP_HASH" > "$SWEEP_SEEN"
    say "issue-sweep findings ${SWEEP_HASH:0:12} handed to this tick and marked read"
elif [ -n "$SWEEP_HASH" ]; then
    say "issue-sweep findings ${SWEEP_HASH:0:12} were in this tick's brief but it exited $rc; leaving them unread for the next tick"
fi
# The roll-up after every tick, model or not: the status comment is how the
# owner sees this job at all (jobs/status.sh).
bash "$JOBS/status.sh" >/dev/null 2>&1
exit $rc
