#!/bin/bash
# Queue dirtytlb-rd.json's Crimson pair (#548): B first, then A, both on the
# Thor. Logs each request id to docs/lanes/dirtytlb/queue.log.
# Usage: queue_rd.sh A_REF B_REF
set -u
cd "$(dirname "$0")/../../.."
A=$1; B=$2
P=docs/testing/predictions/dirtytlb-rd.json
LOG=docs/lanes/dirtytlb/queue.log
CRIMSON='Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso'
q() {  # ref arm
    echo "== rd $2 thor $1" >> "$LOG"
    bash docs/testing/request.sh --who lane.dirtytlb --issue 548 \
        --purpose "#548 fix arm $2 on thor: walk only the live MMU modes" \
        --title "$CRIMSON" --route crimson-skies --seconds 240 --perflog \
        --device thor --ref "$1" --expect "$P" >> "$LOG" 2>&1
    echo "rc=$?" >> "$LOG"
}
q "$B" B
q "$A" A
