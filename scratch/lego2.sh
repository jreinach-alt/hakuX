#!/usr/bin/env bash
# LEGO Star Wars re-hold (10-05): the hold look no longer answers START to the hub join prompt; golden 5251f98730d1, recorded path.
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
OUT=docs/lanes/pathfind/runs/lego-star-wars/hold2
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$?"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind LEGO Star Wars re-hold (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py 4553001D --device nova --budget-min 15 --hold-s 600 --state any \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
