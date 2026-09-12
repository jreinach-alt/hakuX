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

# --- backlog state, cached so a turn end is not an API round trip every time
now=$(date +%s)
count=""
if [ -f "$CACHE" ]; then
    age=$(( now - $(stat -c %Y "$CACHE" 2>/dev/null || echo 0) ))
    [ "$age" -lt "$CACHE_TTL" ] && count=$(cat "$CACHE" 2>/dev/null)
fi
if [ -z "$count" ]; then
    count=$(timeout 20 gh issue list --repo "$REPO" --state open --limit 100 \
              --json number --jq 'length' 2>/dev/null) || count=""
    case "$count" in
        ''|*[!0-9]*) allow ;;   # fail open: could not establish the state
    esac
    printf '%s' "$count" > "$CACHE"
fi
case "$count" in
    ''|*[!0-9]*) allow ;;
esac
[ "$count" -eq 0 ] && { rm -f "$BLOCKS"; allow; }

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
sweep=$(ls "$D"/queue/z-sweep-*.req 2>/dev/null | wc -l | tr -d ' ')
agentwork=$(( queued - sweep ))
[ "$agentwork" -lt 0 ] && agentwork=0

reason="BACKLOG GATE: $count issues are still open, so this turn must not end \
-- ending it stops every agent waiting on this session.

Device queue: $running running, $agentwork agent request(s) queued, $sweep \
idle-priority sweep request(s) remaining.

Pick up the next piece of work now. In rough order of value:
  1. Fold in any completed agent's diff, build both targets, and dispatch its A/B.
  2. Spawn an implementing agent on an unclaimed issue, on files no live agent \
owns (check the territory table in docs/orchestration.md).
  3. Triage a tracker entry still marked 'unclassified' so the next agent has \
direction: python3 docs/testing/nv2a_index.py, and docs/testing/nv2a_issues.toml.
  4. Close an issue that is measured unmodellable, with the evidence posted.
  5. Re-run docs/testing/collect_sweep.sh to refresh the scoreboard as the \
sweep fills in.

A mid-turn status summary is fine -- just keep working after it. \
(Block $n of $MAX_BLOCKS before the release valve allows a stop.)"

block "$reason"
