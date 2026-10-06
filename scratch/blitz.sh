#!/usr/bin/env bash
# NFL Blitz 2002, first run to a held 600-s verdict (sports rule 10-05: the claim sets the longest period).
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
OUT=docs/lanes/pathfind/runs/nfl-blitz-2002/hold2
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$?"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1200 "pathfind NFL Blitz 2002 held run (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py NFL_Blitz_2002 --device nova --budget-min 15 --hold-s 600 --state any \
  --goal "FIRST open OPTIONS on the main menu (below QUICKPLAY) and find the quarter or game length: set the LONGEST value offered, and the game clock to the slowest or real-time setting if offered; then B back to the main menu. Only then QUICKPLAY: team select (A FORWARD), and A to kick off. Take the defaults elsewhere. Before the snap, a formation with no menu is not play: A snaps the ball." \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
