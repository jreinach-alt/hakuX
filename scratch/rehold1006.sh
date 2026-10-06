#!/usr/bin/env bash
# lane.local 06:35 10-06: re-hold five titles on master, each to a verdict before the next.
# Full pathfind per title (claim, then a 600-s hold), --state any (the golden if one exists).
# The Nova is taken per title (hold.sh) and released on every exit path (trap).
# The gate (rehold1006_gate.py) stops the queue if the Nova is not on master's build with no env.
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
GATE=scratch/rehold1006_gate.py
TITLES="4D570034 4D570029 4D57000C NBA_2K3.xiso.iso 4541038A"
REL=0
trap 'bash docs/testing/jobs/hold.sh release nova lane.pathfind >/dev/null 2>&1' EXIT
for t in $TITLES; do
    now=$(date +%H%M)
    if [ "$now" -ge 2200 ]; then echo "DEADLINE: not starting $t at $(date +%H:%M)"; break; fi
    slug=$(echo "$t" | sed 's/\.xiso\.iso$//; s/\.iso$//')
    out=docs/lanes/pathfind/runs/rehold-$slug
    mkdir -p "$out"
    python3 "$GATE" ready "$REL" || { echo "GATE REFUSED before $t at $(date +%H:%M:%S): Nova not clean"; exit 1; }
    bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind re-hold $t (#433)" || { echo "take timed out: $t"; continue; }
    bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle: $t"; bash docs/testing/jobs/hold.sh release nova lane.pathfind; REL=$(date +%s); continue; }
    echo "=== $t start $(date +%H:%M:%S)"
    python3 docs/testing/titles/pathfind.py "$t" --device nova --budget-min 15 --hold-s 600 --state any --out "$out" > "$out/run.log" 2>&1
    echo "=== $t rc=$? end $(date +%H:%M:%S)"
    bash docs/testing/jobs/hold.sh release nova lane.pathfind
    REL=$(date +%s)
done
echo "REHOLD LOOP DONE $(date +%H:%M:%S)"
