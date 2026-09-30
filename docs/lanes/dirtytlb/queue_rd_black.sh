#!/bin/bash
# Queue dirtytlb-rd-black.json's Black pair (#548): B first, then A, both on
# the Thor. Logs each request id to docs/lanes/dirtytlb/queue.log.
# Two requests of 760 s: 28.3 min by request.sh's estimate, under the pilot
# gate's 30, so the pair is its own pilot.
# Usage: queue_rd_black.sh A_REF B_REF
set -u
cd "$(dirname "$0")/../../.."
A=$1; B=$2
P=docs/testing/predictions/dirtytlb-rd-black.json
LOG=docs/lanes/dirtytlb/queue.log
BLACK='45410083-Black.xiso.iso'
q() {  # ref arm
    echo "== rd-black $2 thor $1" >> "$LOG"
    bash docs/testing/request.sh --who lane.dirtytlb --issue 548 \
        --purpose "#548 fix arm $2 on thor, Black: walk only the live MMU modes" \
        --title "$BLACK" --route black.returning --seconds 760 --perflog \
        --device thor --ref "$1" --expect "$P" >> "$LOG" 2>&1
    echo "rc=$?" >> "$LOG"
}
q "$B" B
q "$A" A
