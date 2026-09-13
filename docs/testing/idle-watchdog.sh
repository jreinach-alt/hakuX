#!/usr/bin/env bash
#
# Wake the orchestrator when it goes idle with the backlog still open.
#
#   idle-watchdog.sh <session-id>      # run under the Monitor tool
#
# Why this exists, and why it is not the Stop hook
# ------------------------------------------------
#
# `backlog-gate.sh` is a Stop hook and is correct: claimed by session id, fails
# open, tested on all four paths. It has never once run in the orchestrator
# session. Proof: its first action is an unconditional append to
# invocations.log, and that file does not exist after three turn ends.
#
# The reason is that `.claude/settings.json` is read when a session STARTS. The
# hook was registered mid-session, so it is live for every session opened
# afterwards -- it gated an unrelated session through six blocks -- and dead for
# the session that registered it. Editing the script cannot fix that; only a
# restart can.
#
# So this is the in-session equivalent. It watches the orchestrator's own
# transcript: when nothing has been appended for IDLE_AFTER seconds and issues
# are still open, it prints one line. Under the Monitor tool a printed line
# becomes a notification, which re-invokes the session -- the same effect the
# hook's `block` would have had, by a route that does not depend on settings
# having been loaded.
#
# Design constraints that matter
# ------------------------------
#
# ONE EVENT PER IDLE PERIOD. It latches after firing and only re-arms once the
# transcript is touched again. A monitor that emits repeatedly gets throttled
# and then stopped by the harness, which would leave the session unwatched
# precisely when it had gone quiet.
#
# FAIL QUIET, NOT LOUD. If `gh` is unreachable it does not fire. A network blip
# should not produce a nag, and an un-actionable nag trains the reader to
# ignore the actionable ones.
#
# IT EXITS WHEN THE BACKLOG IS CLEAR. That is the terminating condition for the
# whole exercise, so the watchdog should not outlive it.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SID="${1:?usage: idle-watchdog.sh <session-id>}"
# Overridable so the latching behaviour can be tested without relocating HOME,
# which hides gh's credentials and makes the fail-quiet path swallow the test.
TRANSCRIPT="${WATCHDOG_TRANSCRIPT:-$HOME/.claude/projects/-home-justin-hakuX/$SID.jsonl}"
REPO="jreinach-alt/hakuX"
DISPATCH="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"

IDLE_AFTER=${IDLE_AFTER:-75}     # seconds of transcript silence before firing
POLL=${POLL:-20}
ISSUE_TTL=${ISSUE_TTL:-300}      # how long an issue count is reused

last_count=""
last_count_at=0
armed=1                          # 1 = will fire when idle; 0 = already fired
last_mtime=0

issue_count() {
    local now; now=$(date +%s)
    if [ -n "$last_count" ] && [ $(( now - last_count_at )) -lt "$ISSUE_TTL" ]; then
        printf '%s' "$last_count"; return 0
    fi
    local c
    c=$(timeout 20 gh issue list --repo "$REPO" --state open --limit 100 \
          --json number --jq 'length' 2>/dev/null) || c=""
    case "$c" in ''|*[!0-9]*) printf ''; return 1 ;; esac
    last_count="$c"; last_count_at="$now"
    printf '%s' "$c"
}

while :; do
    sleep "$POLL"

    [ -f "$TRANSCRIPT" ] || continue

    mtime=$(stat -c %Y "$TRANSCRIPT" 2>/dev/null || echo 0)
    now=$(date +%s)
    idle=$(( now - mtime ))

    # Re-arm as soon as the session speaks again.
    if [ "$mtime" != "$last_mtime" ]; then
        last_mtime="$mtime"
        armed=1
        continue
    fi

    [ "$armed" = 1 ] || continue
    [ "$idle" -ge "$IDLE_AFTER" ] || continue

    count=$(issue_count) || continue      # fail quiet
    [ -n "$count" ] || continue
    if [ "$count" -eq 0 ]; then
        echo "BACKLOG CLEAR: 0 issues open. The watchdog is exiting; nothing left to nag about."
        exit 0
    fi

    queued=$(ls "$DISPATCH"/queue/*.req 2>/dev/null | wc -l | tr -d ' ')
    running=$(ls "$DISPATCH"/running/*.req 2>/dev/null | wc -l | tr -d ' ')
    sweep=$(ls "$DISPATCH"/queue/z-*.req 2>/dev/null | wc -l | tr -d ' ')
    agentwork=$(( queued - sweep )); [ "$agentwork" -lt 0 ] && agentwork=0

    # NAME THE SPECIFIC GAP, not the generic list. The old message printed the
    # same five suggestions every time, which is a nag: it tells the reader
    # nothing they did not know and trains them to skim it. Worse, on
    # 2026-09-13 the orchestrator twice asserted a state of the board that the
    # board did not support -- once saying every issue had a lane or a blocker
    # when #53 had neither, once saying the remaining work was all blocked when
    # two items were neither blocked nor claimed. Both were caught by reading
    # the machine-readable state instead of the summary.
    #
    # check_coverage.py already reads exactly that state and already fails open
    # without gh, so ask it rather than re-deriving. Its output replaces the
    # suggestion list when it has something specific to say.
    cov=$(cd "$HERE/../.." 2>/dev/null && timeout 45 python3 \
              docs/testing/check_coverage.py 2>&1 | head -6)
    case "$cov" in
        FAIL*)  hint="COVERAGE GAP -- $(printf '%s' "$cov" | sed -n 2p | sed 's/^ *//'). Give it a lane in territory.toml or write blocked_on on its tracker entry." ;;
        *"NOT CHECKED"*) hint="coverage unchecked (no gh). Pick up: fold a finished lane's diff and dispatch its A/B; claim an issue whose files territory.toml lists free; or refresh the scoreboard with collect_sweep.sh." ;;
        *)      hint="$(printf '%s' "$cov" | sed -n 1p). Nothing is uncovered, so the next move is a FINISHED lane to fold, a free file in territory.toml to claim, or collect_sweep.sh." ;;
    esac

    armed=0
    echo "IDLE ${idle}s with ${count} issues open -- ${running} device run(s) in flight, ${agentwork} agent request(s) queued, ${sweep} sweep request(s) left. ${hint}"
done
