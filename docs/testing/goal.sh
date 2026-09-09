#!/usr/bin/env bash
#
# Record what "fixed" means, and check it on every turn end.
#
#   goal.sh set "Bump map 40/40 on the palette gate" \
#           "docs/testing/palette_gate.py --goldens g --results r Bump_map"
#   goal.sh check      # run the command, report whether the goal is met
#   goal.sh clear
#
# This exists because a coherent explanation kept getting mistaken for a
# finished fix. A change was published as "38 of 40 passing" when the render was
# a solid red square; the metric agreed with it and nobody had looked at the
# images. The habit it guards against is reporting progress as completion.
#
# Wired to the Stop hook, so ending a turn always states the objective status of
# the thing being worked on, in the words written down when the work started —
# not in whatever framing the turn arrived at.
set -u

STATE="${HAKUX_GOAL_FILE:-/tmp/hakux-current-goal}"

case "${1:-check}" in
  set)
    [ $# -ge 3 ] || { echo "usage: goal.sh set <description> <verify-command>"; exit 2; }
    printf '%s\n%s\n' "$2" "$3" > "$STATE"
    echo "goal: $2"
    echo "verify: $3"
    ;;
  clear)
    rm -f "$STATE"; echo "goal cleared"
    ;;
  check)
    [ -f "$STATE" ] || exit 0
    desc=$(sed -n 1p "$STATE")
    cmd=$(sed -n 2p "$STATE")
    echo "── open goal ─────────────────────────────────────────────"
    echo "   $desc"
    out=$(eval "$cmd" 2>&1)
    rc=$?
    # Show the summary line the gate prints, or the tail if it has none.
    summary=$(printf '%s\n' "$out" | grep -E "match the hardware|render only|PASS|FAIL" | tail -3)
    [ -n "$summary" ] && printf '%s\n' "$summary" | sed 's/^/   /'
    if [ "$rc" = 0 ]; then
        echo "   STATUS: met — clear it with goal.sh clear"
    else
        echo "   STATUS: NOT met. Do not report this as fixed."
    fi
    echo "──────────────────────────────────────────────────────────"
    ;;
  *)
    sed -n '3,12p' "$0"
    ;;
esac
exit 0
