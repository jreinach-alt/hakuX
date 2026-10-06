#!/usr/bin/env bash
# Strike Force Bowling re-hold (name entry identified 10-05: END is left of A on the letter wheel, then Done).
# The bowling family sibling of AMF Bowling 2004: the bowl loop and the frame-scorecard budget are the verified ones.
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1
OUT=docs/lanes/pathfind/runs/strike-force-bowling/hold4
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$?"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind Strike Force Bowling re-hold (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py Strike_Force_Bowling --device nova --budget-min 15 --hold-s 600 --state any \
  --goal "Set the game length (frames or games) to the LONGEST value offered and the speed to the slowest if offered; choose one human player (controller 1); take the defaults elsewhere. At a name entry, the letters are on a wheel: D-pad moves the ring, A selects the letter under it. END and DEL sit just LEFT of A on the wheel; move the ring onto END, press A, then DOWN to Done in the panel and A. START does nothing on this screen. Then start a game and bowl; at a game over, look for a rematch or play-again entry before walking back to the title." \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
