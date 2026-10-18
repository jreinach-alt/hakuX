#!/bin/sh
# Wait up to $1 seconds until every listed request id (any result-dir prefix) holds DONE, or until one more
# than were done at the start is done. Prints which are done.  usage: wait_any.sh <seconds> <id> ...
R=/home/justin/hakux-work/dispatch/results
n=$1
shift
count() {
    c=0
    for id in "$@"; do
        for d in "$R"/*"$id"; do
            [ -e "$d/DONE" ] && c=$((c + 1))
        done
    done
    echo "$c"
}
start=$(count "$@")
i=0
while [ "$i" -lt "$n" ]; do
    now=$(count "$@")
    if [ "$now" -gt "$start" ] || [ "$now" -eq "$#" ]; then
        break
    fi
    sleep 15
    i=$((i + 15))
done
echo "after ${i}s:"
for id in "$@"; do
    s=pending
    for d in "$R"/*"$id"; do
        [ -e "$d/DONE" ] && s="DONE $(basename "$d")"
    done
    echo "  $id $s"
done
