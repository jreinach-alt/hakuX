#!/usr/bin/env bash
# Wait in the foreground (under the Bash tool's 10-minute limit) for the next of
# this lane's Nova requests to finish, then print which are DONE, which are
# running, and what is queued ahead. Reads dispatch/ only.
#
#   wait_nova.sh MAX_SECONDS
set -u
MAX="$1"
D=/home/justin/hakux-work/dispatch
IDS="$(dirname "$0")/../nova_ids.tsv"
want=$(grep -o '17922842[0-9][0-9]-lane.bootstatic1017-[0-9]*' "$IDS" | sort -u)
# The dispatcher may rename a request with a priority prefix ("0-", "1-"), so
# each id is looked up with any prefix.
find_in() { ls -d "$D/$1/"*"$2"* 2>/dev/null | head -n 1; }
count_done() { local n=0 r; for i in $want; do r=$(find_in results "$i"); [ -n "$r" ] && [ -e "$r/DONE" ] && n=$((n + 1)); done; echo "$n"; }
start=$(count_done)
t=0
while [ "$t" -lt "$MAX" ]; do
    [ "$(count_done)" -gt "$start" ] && break
    sleep 20
    t=$((t + 20))
done
echo "waited ${t}s; done $(count_done) of $(echo "$want" | wc -l)"
for i in $want; do
    r=$(find_in results "$i")
    if [ -n "$r" ] && [ -e "$r/DONE" ]; then echo "DONE    $r"
    elif [ -n "$(find_in running "$i")" ]; then echo "RUNNING $i"
    elif [ -n "$(find_in queue "$i")" ]; then echo "QUEUED  $i"
    else echo "?       $i"; fi
done
echo "running: $(ls "$D/running" | grep '\.req$' | tr '\n' ' ')"
echo "queue: $(ls "$D/queue" | grep '\.req$' | tr '\n' ' ')"
