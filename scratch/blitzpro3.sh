#!/usr/bin/env bash
# NFL Blitz Pro claim + 600-s hold, run from a clean checkout of committed HEAD (ab8788c38b), so the run's
# tools are a commit (lane.local 10-06 11:00). Output lands in this lane worktree.
set -u
HEADTREE=/home/justin/hakux-work/wt/pathfind-head
OUT=/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs/nfl-blitz-pro/hold3
cd "$HEADTREE" || exit 1
echo "tools at $(git rev-parse --short HEAD) dirty=$(git status --porcelain | wc -l)"
release() { bash docs/testing/jobs/hold.sh release nova lane.pathfind; echo "released rc=$? at $(date +%H:%M:%S)"; }
trap release EXIT
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1200 "pathfind NFL Blitz Pro claim+hold 2 (#433)" || { echo "take timed out"; exit 3; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; exit 3; }
echo "held at $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py NFL_Blitz_Pro --device nova --budget-min 15 --hold-s 600 --state any \
  --goal "The MAIN MENU has tabs (GAME MODES, with L and R arrows): the tabs change with the TRIGGERS, RT:0.3 for the next tab and LT:0.3 for the previous one; R1/L1 and the d-pad do NOT change tabs. FIRST press RT:0.3 until the tab holding OPTIONS (or SETTINGS / GAME OPTIONS) shows, open it, and set QUARTER LENGTH to the LONGEST value offered; then B back, LT:0.3 back to GAME MODES. Only then QUICKPLAY, SELECT TEAMS (A SELECT on each side), LAUNCH GAME with A. Take the defaults elsewhere. Before the snap, a play-call menu or a formation with no menu is not play: A picks the play and snaps the ball. If OPTIONS is not found within 8 looks, go to QUICKPLAY anyway." \
  --out "$OUT"
echo "pathfind rc=$? at $(date +%H:%M:%S)"
