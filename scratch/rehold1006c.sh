#!/usr/bin/env bash
# 10-06 owner order (validity rule): Armageddon is held again under the new hold (extension to a valid verdict, ladder past the
# step cap). It runs after the five-title queue (rehold1006.sh, pid in rehold1006.pid) so the Nova order is kept.
set -u
cd /home/justin/hakux-work/wt/pathfind || exit 1


GATE=scratch/rehold1006_gate.py
trap 'bash docs/testing/jobs/hold.sh release nova lane.pathfind >/dev/null 2>&1' EXIT
out=docs/lanes/pathfind/runs/rehold2b-4D570034
mkdir -p "$out"
python3 "$GATE" ready "$(date +%s)" || { echo "GATE REFUSED before Armageddon retry: Nova not clean"; exit 1; }
bash docs/testing/jobs/hold.sh wait nova lane.pathfind 1500 "pathfind Armageddon retry, validity rule (#433)" || { echo "take timed out"; exit 1; }
bash docs/testing/jobs/hold.sh wait-idle nova 900 || { echo "not idle"; bash docs/testing/jobs/hold.sh release nova lane.pathfind; exit 1; }
echo "=== 4D570034 retry start $(date +%H:%M:%S)"
python3 docs/testing/titles/pathfind.py 4D570034 --device nova --budget-min 15 --hold-s 600 --state any --out "$out" > "$out/run.log" 2>&1
echo "=== 4D570034 retry rc=$? end $(date +%H:%M:%S)"
bash docs/testing/jobs/hold.sh release nova lane.pathfind
echo "ARMAGEDDON RETRY DONE $(date +%H:%M:%S)"
