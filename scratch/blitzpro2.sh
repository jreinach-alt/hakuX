#!/usr/bin/env bash
# NFL Blitz Pro claim + 600-s hold, run from a clean checkout of committed HEAD (8d7af64998), so the run's
# tools are a commit (lane.local 10-06 11:00). Output lands in this lane worktree.
set -u
HEADTREE=/home/justin/hakux-work/wt/pathfind-head
OUT=/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs/nfl-blitz-pro/hold2
cd "$HEADTREE" || exit 1
echo "tools at $(git rev-parse --short HEAD) dirty=$(git status --porcelain | wc -l)"
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$? at $(date +%H:%M:%S)"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1200 "pathfind NFL Blitz Pro claim+hold (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py NFL_Blitz_Pro --device nova --budget-min 15 --hold-s 600 --state any \
  --goal "FIRST open OPTIONS on the main menu (below QUICKPLAY), then PLAY OPTIONS, and set QUARTER LENGTH to the LONGEST value offered (5 minutes in NFL Blitz 2002); then B back to the main menu. Only then QUICKPLAY: team select (A FORWARD), and A to kick off. Take the defaults elsewhere. Before the snap, a formation with no menu is not play: A snaps the ball." \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
