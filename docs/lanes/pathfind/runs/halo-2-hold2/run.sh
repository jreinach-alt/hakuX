#!/usr/bin/env bash
# held run: take the Nova, wait for idle, run pathfind, release on every exit path
# Halo 2 (4D530064), golden 0a4742f1e45d, the build's default HAKUX_GPL 3, a moving shooter hold (10-03)
cd /home/justin/hakux-work/wt/pathfind || exit 1
TAG=pathfind:halo2
OUT=docs/lanes/pathfind/runs/halo-2-hold2
bash docs/testing/jobs/hold.sh take nova $TAG "pathfind Halo 2 held run 600 s (moving shooter hold)"
rc=$?
if [ $rc -ne 0 ]; then echo "HOLD_TAKE_FAILED=$rc"; exit 1; fi
trap 'bash docs/testing/jobs/hold.sh release nova $TAG; echo HOLD_RELEASED=$?' EXIT
bash docs/testing/jobs/hold.sh wait-idle nova 900
rc=$?
if [ $rc -ne 0 ]; then echo "WAIT_IDLE_FAILED=$rc"; exit 1; fi
python3 docs/testing/titles/pathfind.py 4D530064 --device nova --budget-min 15 --hold-s 600 --state any --out $OUT
echo PATHFIND_EXIT=$?
