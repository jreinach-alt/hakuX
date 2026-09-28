#!/bin/bash
# Requeue dirtytlb-counter.json's Crimson B soak (#548): the first one,
# 1-1790606269-lane.dirtytlb-479803, aborted not-foreground (both Thor
# displays OFF at start) before the route's first input. V: re-queued once.
set -u
cd "$(dirname "$0")/../../.."
LOG=docs/lanes/dirtytlb/queue.log
echo "== B thor 9d33d2dac2 (requeue of 479803: not-foreground, displays OFF)" >> "$LOG"
bash docs/testing/request.sh --who lane.dirtytlb --issue 548 \
    --purpose "#548 [rdc] counter arm B on thor (requeue of 479803)" \
    --title 'Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso' \
    --route crimson-skies --seconds 240 --perflog --device thor \
    --ref 9d33d2dac2 --expect docs/testing/predictions/dirtytlb-counter.json >> "$LOG" 2>&1
echo "rc=$?" >> "$LOG"
