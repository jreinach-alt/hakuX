#!/bin/bash
# wait_results.sh <timeout_s> <id>...
# Polls $DISPATCH_DIR/{queue,running,results} every 20 s until every id has a
# results/<id>/DONE, or the timeout passes. Prints one line per state change.
# Exit 0 all done, 3 timeout. Run in the foreground in chunks under 10 min.
D=${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}
timeout=$1
shift
end=$(( $(date +%s) + timeout ))
declare -A said
while :; do
    left=0
    for id in "$@"; do
        if [ -e "$D/results/$id/DONE" ]; then s=done
        elif [ -e "$D/running/$id.req" ]; then s=running
        elif [ -e "$D/queue/$id.req" ]; then s=queued
        else s=absent
        fi
        [ "$s" = done ] || left=$((left + 1))
        if [ "${said[$id]}" != "$s" ]; then
            echo "$(date -u +%H:%M:%S) $id $s"
            said[$id]=$s
        fi
    done
    [ "$left" -eq 0 ] && exit 0
    [ "$(date +%s)" -ge "$end" ] && { echo "$(date -u +%H:%M:%S) timeout, $left not done; running: $(ls "$D/running" | grep '\.req$' | tr '\n' ' ')"; exit 3; }
    sleep 20
done
