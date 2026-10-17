#!/bin/sh
# Wait for a dispatch result's DONE file, up to $2 seconds (default 570).
# usage: wait_done.sh <request id> [seconds]
d=/home/justin/hakux-work/dispatch/results/$1
n=${2:-570}
i=0
while [ "$i" -lt "$n" ]; do
    if [ -e "$d/DONE" ]; then
        echo "DONE after ${i}s: $(cat "$d/DONE" 2>/dev/null | head -c 300)"
        exit 0
    fi
    sleep 10
    i=$((i + 10))
done
echo "not done after ${n}s"
exit 1
