#!/usr/bin/env bash
# Unscreened sweep titles (owner order, 10-05 09:15 addendum), one 600-s held run each, first-run claim with the hold after.
# The Nova is taken and released per title (hold.sh); no new title starts at or after 22:40 PDT (the 23:00 stop).
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
TITLES="4D570029 4D570034 4D57000C 4156002B 45410389 4541007B 54540008 4541003E 56550039 5655002F 4541038A 5343000E 54510109 4B4E002F 4D4A0008 5443000E"
for id in $TITLES; do
    now=$(date +%H%M)
    if [ "$now" -ge 2240 ]; then echo "DEADLINE: not starting $id at $(date +%H:%M)"; break; fi
    out=docs/lanes/pathfind/runs/sweep-$id
    mkdir -p "$out"
    bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind sweep $id (#433)" || { echo "take timed out: $id"; continue; }
    bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle: $id"; bash docs/testing/jobs/hold.sh release nova lane.pathfind; continue; }
    echo "=== $id start $(date +%H:%M:%S)"
    python3 docs/testing/titles/pathfind.py "$id" --device nova --budget-min 15 --hold-s 600 --state any --out "$out" > "$out/run.log" 2>&1
    echo "=== $id rc=$? end $(date +%H:%M:%S)"
    bash docs/testing/jobs/hold.sh release nova lane.pathfind
done
echo "SWEEP LOOP DONE $(date +%H:%M:%S)"
