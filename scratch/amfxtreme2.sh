#!/usr/bin/env bash
# AMF Xtreme Bowling, first run (sibling of AMF Bowling 2004) to a held 600-s verdict (lead of the bowling family; the sports period rule applies:
# the longest game length offered, so one game outlasts the hold).
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
OUT=docs/lanes/pathfind/runs/amf-xtreme-bowling/hold2
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$?"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind AMF Xtreme Bowling held run (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py AMF_Xtreme_Bowling --device nova --budget-min 15 --hold-s 600 --state any \
  --goal "Sibling of AMF Bowling 2004, whose route was: skip logos with START/A, title START, main menu Start New Game (A), then the setup screen: controller 1 Human as Player 1, game length the LONGEST offered (10 frames), then Next/A to start. Choose PIN CHALLENGE (Easy) or a full 10-frame game, NOT Practice (Practice ends after a few throws and drops to the menus). Set the game length to the LONGEST value offered; one human player (controller 1); defaults elsewhere. In the game, push the stick UP, then a throw is HOLD A (about 3 s), not a tap; keep playing through each frame's result and score screens. A high-score NAME ENTRY: move the cursor to Done/End and press A, do not type letters with A." \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
