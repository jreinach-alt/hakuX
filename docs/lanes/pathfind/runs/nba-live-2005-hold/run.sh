#!/usr/bin/env bash
# held run: take the Nova, wait for idle, run pathfind, release on every exit path
cd /home/justin/hakux-work/wt/pathfind || exit 1
TAG=pathfind:nba2005
OUT=docs/lanes/pathfind/runs/nba-live-2005-hold
bash docs/testing/jobs/hold.sh take nova $TAG "pathfind NBA Live 2005 held run 600 s"
rc=$?
if [ $rc -ne 0 ]; then echo "HOLD_TAKE_FAILED=$rc"; exit 1; fi
trap 'bash docs/testing/jobs/hold.sh release nova $TAG; echo HOLD_RELEASED=$?' EXIT
bash docs/testing/jobs/hold.sh wait-idle nova 900
rc=$?
if [ $rc -ne 0 ]; then echo "WAIT_IDLE_FAILED=$rc"; exit 1; fi
python3 docs/testing/titles/pathfind.py 45410050 --device nova --budget-min 15 --hold-s 600 --state first-run \
  --goal "Settings: set the quarter length to the LONGEST option (12 minutes if offered) so one quarter covers the 600 s hold; take the defaults elsewhere; then start an Exhibition (or Quick Play) game" \
  --out $OUT
echo PATHFIND_EXIT=$?
