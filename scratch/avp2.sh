#!/usr/bin/env bash
# AvP: Extinction re-hold (10-05): the title hold selects the squad and scrolls the map (3b1cb99dd3); golden 50a35dcd33ed.
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
OUT=docs/lanes/pathfind/runs/avp-extinction/hold2
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$?"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind AvP Extinction re-hold (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py 56550022 --device nova --budget-min 15 --hold-s 600 --state any \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
