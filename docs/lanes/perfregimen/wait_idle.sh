#!/usr/bin/env bash
# wait_idle.sh <label> [max seconds]: wait until no dispatcher request runs on
# <label>. Exit 0 when idle, 1 on timeout.
D="${DISPATCH_DIR:-$HOME/hakux-work/dispatch}"
end=$(( $(date +%s) + ${2:-540} ))
while [ "$(date +%s)" -lt "$end" ]; do
    busy=""
    for f in "$D"/running/*.owner; do
        [ -f "$f" ] && [ "$(cat "$f")" = "$1" ] && busy="$(basename "$f" .owner)"
    done
    echo "$(date +%H:%M:%S) $1 ${busy:-IDLE}"
    [ -z "$busy" ] && exit 0
    sleep 30
done
exit 1
