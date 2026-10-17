#!/bin/sh
# Wait for the result dir of a request id (any prefix) to hold DONE, up to $2 seconds (default 570).
# usage: wait_id.sh <request id> [seconds]
R=/home/justin/hakux-work/dispatch/results
n=${2:-570}
i=0
while [ "$i" -lt "$n" ]; do
    for d in "$R"/*"$1"; do
        if [ -e "$d/DONE" ]; then
            echo "DONE after ${i}s: $d"
            head -c 300 "$d/DONE"
            echo
            exit 0
        fi
    done
    sleep 15
    i=$((i + 15))
done
echo "not done after ${n}s"
ls -d "$R"/*"$1" 2>/dev/null
exit 1
