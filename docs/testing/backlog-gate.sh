#!/usr/bin/env bash
#
# Stop hook: refuse to end a turn while the issue backlog is non-empty.
#
# This session is an orchestrator and is meant to run until the backlog is
# cleared. Ending a turn stops every agent waiting on it, so an idle turn end
# is not a pause -- it halts the whole fleet. A mid-turn status summary is
# fine; stopping with work outstanding is not.
#
# Wired as a Stop hook. Blocks by printing {"decision":"block","reason":...},
# which Claude Code surfaces back into the turn.
#
# Two deliberate safety properties, because a hook that can trap a session is
# more dangerous than one that lets it stop too early:
#
#   FAIL OPEN. Any failure to establish the backlog state -- no `gh`, no
#   network, an API error -- allows the stop. A network blip must not make the
#   session unstoppable.
#
#   RELEASE VALVE. After MAX_BLOCKS consecutive blocks inside WINDOW seconds it
#   allows the stop and says why. Without it, a genuinely blocked session (every
#   remaining issue waiting on a human, or a device that has gone away) would
#   spin. The user can always interrupt, but they should not have to.
#
#   IT CANNOT TAKE EFFECT IN THE SESSION THAT EDITS IT. settings.json is read
#   at SESSION START, so a gate reworked mid-session is loaded by the next
#   session and not this one. That is measured, not assumed: settings.json was
#   last edited 2026-09-12 21:46:58 and this gate's invocation log stops at
#   21:43:40 the same day -- three minutes earlier -- while the orchestrator
#   session claiming the role dates to 16:08 that morning. So it has fired
#   ZERO times in the session that has most needed it, and the discipline it
#   encodes has been manual for six days. Say that out loud when reworking it;
#   the failure mode is reporting a fixed hook and then ending turns anyway.
#
#   ORCHESTRATOR ONLY. A Stop hook in .claude/settings.json fires for EVERY
#   session in this project, and only the orchestrator is supposed to run until
#   the backlog is clear. Without this check the hook gated an unrelated
#   session -- one opened to add a second device -- through six blocks before
#   it could end a turn, which is the opposite of useful. So the orchestrator
#   claims the role by session id:
#
#       backlog-gate.sh claim          # from the orchestrator session
#       backlog-gate.sh release
#
#   and the hook blocks only when the incoming session_id matches the claim.
#   Any other session is allowed immediately. No claim file means no
#   orchestrator, so nothing is gated.
set -u

STATE_DIR="${HAKUX_GATE_STATE:-/tmp/hakux-backlog-gate}"
CACHE="$STATE_DIR/issues.count"
BLOCKS="$STATE_DIR/blocks"
CACHE_TTL=120
MAX_BLOCKS=6
WINDOW=1800
REPO="jreinach-alt/hakuX"
CLAIM="$STATE_DIR/orchestrator"

mkdir -p "$STATE_DIR"

case "${1:-}" in
  claim)
    # The session id is the basename of this project's most recently written
    # transcript. Taking it from there rather than asking the caller means the
    # orchestrator cannot claim the role on another session's behalf by typo.
    sid=$(ls -t "$HOME/.claude/projects/-home-justin-hakuX"/*.jsonl 2>/dev/null \
          | head -1 | xargs -r basename | sed 's/\.jsonl$//')
    [ -n "$sid" ] || { echo "could not determine the session id" >&2; exit 1; }
    printf '%s\n' "$sid" > "$CLAIM"
    echo "orchestrator claimed by $sid"
    exit 0
    ;;
  release)
    rm -f "$CLAIM" "$BLOCKS"; echo "orchestrator released"; exit 0
    ;;
  status)
    if [ -f "$CLAIM" ]; then echo "orchestrator: $(cat "$CLAIM")";
    else echo "orchestrator: unclaimed -- the gate is inert for every session"; fi
    exit 0
    ;;
esac

# Unconditional audit line, first thing, before any logic can exit early.
# Added because the hook silently failed to fire and I could not tell whether
# Claude Code was not invoking it or it was invoking it and ignoring the
# result. Those need different fixes, and the state files could not
# distinguish them: an early `allow` writes nothing.
printf '%s pid=%s ppid=%s args=%s\n' "$(date '+%F %T')" "$$" "$PPID" "$*" \
    >> "$STATE_DIR/invocations.log" 2>/dev/null || true

# The hook's stdin carries the session JSON; we only need stop_hook_active.
payload=$(cat 2>/dev/null || true)
active=$(printf '%s' "$payload" | python3 -c "
import json,sys
try: print('1' if json.load(sys.stdin).get('stop_hook_active') else '0')
except Exception: print('0')" 2>/dev/null || echo 0)

sid=$(printf '%s' "$payload" | python3 -c "
import json,sys
try: print(json.load(sys.stdin).get('session_id') or '')
except Exception: print('')" 2>/dev/null || echo '')

allow() {
    printf '%s allowed\n' "$(date '+%F %T')" \
        >> "$STATE_DIR/invocations.log" 2>/dev/null || true
    exit 0
}

block() {
    printf '%s BLOCKED n=%s\n' "$(date '+%F %T')" "${n:-?}" \
        >> "$STATE_DIR/invocations.log" 2>/dev/null || true
    python3 -c "
import json,sys
print(json.dumps({'decision':'block','reason':sys.argv[1]}))" "$1"
    exit 0
}

# --- is this the orchestrator? if not, this hook has no business here
if [ ! -f "$CLAIM" ]; then
    printf '%s allowed (no orchestrator claimed)\n' "$(date '+%F %T')" \
        >> "$STATE_DIR/invocations.log" 2>/dev/null || true
    exit 0
fi
claimed=$(cat "$CLAIM" 2>/dev/null || echo '')
if [ -z "$sid" ] || [ "$sid" != "$claimed" ]; then
    printf '%s allowed (session %s is not the orchestrator %s)\n' \
        "$(date '+%F %T')" "${sid:-unknown}" "$claimed" \
        >> "$STATE_DIR/invocations.log" 2>/dev/null || true
    exit 0
fi

# --- WHAT THIS GATES ON, REWORKED 2026-09-18, AND WHY THE OLD SIGNAL WAS WRONG
#
# It used to gate on the raw count of OPEN ISSUES. That is the wrong signal and
# it got worse as the board got better. Thirty-two issues are open and most of
# them are open for reasons no amount of turn-taking fixes: a measured pixel
# floor where exactness would make the score WORSE (#52's adverse cell), a
# defect whose fix needs goldens re-shot on silicon nobody has (#53), a
# capability gap (#77), an upstream question (#41, #46, #49). Gating on that
# count means the gate is either always blocking -- and then the release valve
# fires every time, which trains everyone to ignore it -- or it is telling the
# session to churn on issues that cannot move.
#
# THE RIGHT SIGNAL IS WORK THAT IS ACTIONABLE *BY THIS SESSION, RIGHT NOW*, and
# fleet.py already computes exactly that and exits non-zero on it:
#
#   REPORTED, NOT FOLDED            a lane finished and its claim still reads
#                                   as coverage
#   WAITING ON THE ORCHESTRATOR     a lane is blocked on this session
#   DISPATCHABLE NOW, NOT DISPATCHED an issue nothing holds and nothing blocks
#   LANE CLAIMED WITH NO RUNNING AGENT / RUNNING WITH NO TERRITORY ROW
#   BLOCKER NEVER RECORDED AS TESTED
#
# Every one of those is a thing only this session can clear, and every one of
# them was sitting non-empty at some point today while the session ended a turn
# anyway. That is the failure this gate is for -- not "issues exist".
#
# The old open-issue count is still fetched, but only to put a number in the
# reason. It no longer decides anything.
now=$(date +%s)
count=""
if [ -f "$CACHE" ]; then
    age=$(( now - $(stat -c %Y "$CACHE" 2>/dev/null || echo 0) ))
    [ "$age" -lt "$CACHE_TTL" ] && count=$(cat "$CACHE" 2>/dev/null)
fi
if [ -z "$count" ]; then
    count=$(timeout 20 gh issue list --repo "$REPO" --state open --limit 100 \
              --json number --jq 'length' 2>/dev/null) || count="?"
    printf '%s' "$count" > "$CACHE"
fi

# FAIL OPEN on the deciding signal, for the same reason as everything else
# here: if fleet.py cannot run, the state is unknown, and an unknown state must
# not make the session unstoppable.
FLEET="${CLAUDE_PROJECT_DIR:-/home/justin/hakuX}/docs/testing/fleet.py"
[ -f "$FLEET" ] || allow
# NOTE THE 2>&1, AND DO NOT "TIDY" IT AWAY. fleet.py writes its FAIL lines to
# STDERR and its inventory to stdout. The first version of this rework captured
# stdout only, found zero FAILs, and allowed the stop -- a gate that failed
# open on a board with three live FAILs, which is precisely the failure it was
# written to prevent. Caught by dry-running it rather than by trusting it.
# AND NOTE THERE IS NO `|| fleet_out=""` HERE, WHICH IS THE SECOND BUG THIS
# REWORK SHIPPED AND CAUGHT. fleet.py EXITS NON-ZERO BY DESIGN when it finds
# actionable work -- that non-zero IS the signal. A `||` clause therefore fired
# on exactly the runs that mattered and blanked the output it had just
# captured, so the gate allowed the stop whenever there was something to do and
# blocked only when there was nothing. Inverted, silently, and it looked
# defensive.
#
# So: capture unconditionally, ignore the status, and decide on the CONTENT.
# Emptiness is the fail-open condition, checked on the next line.
fleet_out=$(cd "${CLAUDE_PROJECT_DIR:-/home/justin/hakuX}" 2>/dev/null; \
            timeout 30 python3 "$FLEET" 2>&1)
[ -n "$fleet_out" ] || allow

# The actionable lines are exactly fleet.py's own FAIL lines.
actionable=$(printf '%s\n' "$fleet_out" | grep -c '^FAIL' || true)
case "$actionable" in ''|*[!0-9]*) allow ;; esac
[ "$actionable" -eq 0 ] && { rm -f "$BLOCKS"; allow; }
fleet_fails=$(printf '%s\n' "$fleet_out" | grep '^FAIL' | sed 's/^/  /')

# --- release valve
prev_n=0; prev_t=0
if [ -f "$BLOCKS" ]; then
    prev_n=$(sed -n 1p "$BLOCKS" 2>/dev/null || echo 0)
    prev_t=$(sed -n 2p "$BLOCKS" 2>/dev/null || echo 0)
fi
case "$prev_n" in ''|*[!0-9]*) prev_n=0 ;; esac
case "$prev_t" in ''|*[!0-9]*) prev_t=0 ;; esac
if [ $(( now - prev_t )) -gt "$WINDOW" ]; then prev_n=0; fi
n=$(( prev_n + 1 ))
printf '%s\n%s\n' "$n" "$now" > "$BLOCKS"

if [ "$n" -gt "$MAX_BLOCKS" ]; then
    rm -f "$BLOCKS"
    exit 0
fi

# --- what is in flight, so the reason is actionable rather than a nag
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
queued=$(ls "$D"/queue/*.req 2>/dev/null | wc -l | tr -d ' ')
running=$(ls "$D"/running/*.req 2>/dev/null | wc -l | tr -d ' ')
sweep=$(ls "$D"/queue/z-*.req 2>/dev/null | wc -l | tr -d ' ')
agentwork=$(( queued - sweep ))
[ "$agentwork" -lt 0 ] && agentwork=0

reason="BACKLOG GATE: $actionable thing(s) on this board are actionable BY THIS \
SESSION RIGHT NOW, so this turn must not end -- ending it stops every agent \
waiting on it.

$fleet_fails

Those are fleet.py's own FAIL lines: a lane that reported and has not been \
folded, a lane blocked on you, or an issue nothing holds and nothing blocks. \
Each is something only this session can clear. ($count issues are open in \
total, which is NOT what this gate measures -- most of those are floors, \
capability gaps or upstream questions that no amount of turn-taking moves.)

Device queue: $running running, $agentwork agent request(s) queued, $sweep \
idle-priority sweep request(s) remaining.

Pick up the next piece of work now. In rough order of value:
  1. Fold a reported lane's work -- lane.fold owns the mechanics; you decide
     WHAT folds and record what it means. A lane that reported and sits
     unfolded has a claim asserting coverage that no longer exists.
  2. Answer a lane that is blocked on you. Check every waiting_on in
     \$DISPATCH_DIR/fleet/*.json, and remember that 'told to ask' is not a
     handoff: if a file is in [free] and a lane needs it, GRANT IT rather than
     waiting to be asked. That deadlock cost 77 commits several hours.
  3. Dispatch an issue nothing holds and nothing blocks. Write the territory
     row BEFORE the agent starts, in a pushed commit.
  4. Read \$HAKUX_SWEEP_DIR/unread.md -- the hourly comment sweep. A lane
     reporting into an issue nobody reads is the cheapest way to lose finished
     work; that went unread for a week once.
  5. Re-queue an arm that ab_compare REFUSED (MIN_RUNS, device drop): the
     prediction is still bound, so it costs device time and no re-derivation.

A mid-turn status summary is fine -- just keep working after it. \
(Block $n of $MAX_BLOCKS before the release valve allows a stop.)"

block "$reason"
