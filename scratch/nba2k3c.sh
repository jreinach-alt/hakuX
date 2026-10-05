#!/usr/bin/env bash
# NBA 2K3, first run to a held 600-s verdict (Visual Concepts 2K family; sibling of NBA 2K2: the longest quarter, a human team).
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
OUT=docs/lanes/pathfind/runs/nba-2k3/hold3
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$?"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind NBA 2K3 held run (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py NBA_2K3 --device nova --budget-min 15 --hold-s 600 --state any \
  --goal "Set the quarter length to the LONGEST value offered and the game clock to the slowest or real-time setting if offered (options or game settings, before the game starts); take the defaults elsewhere. On TEAM SELECT: press RIGHT exactly ONCE. Controller 1 (the top controller) moves one notch into the side column next to the HOME team and a 'User Name' plate appears above it: that is assigned (it never moves under the logo). Then press START at once; no more LEFT/RIGHT. Then start the game and play." \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
