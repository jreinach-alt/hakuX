#!/usr/bin/env bash
# Strike Force Bowling hold5 (10-05): the name entry at a game end gets the title's own sequence, DOWN x4 then A (claim step 9).
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
OUT=docs/lanes/pathfind/runs/strike-force-bowling/hold5
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$?"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind Strike Force Bowling hold5 (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py Strike_Force_Bowling --device nova --budget-min 15 --hold-s 600 --state any \
  --goal "Set the game length (frames or games) to the LONGEST value offered and the speed to the slowest if offered; choose one human player (controller 1); take the defaults elsewhere. At a name entry, the default name is accepted with DOWN, DOWN, DOWN, DOWN, then A (Done is the last row of the panel). Then start a game and bowl; at a game over, look for a rematch or play-again entry before walking back to the title." \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
