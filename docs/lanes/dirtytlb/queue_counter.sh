#!/bin/bash
# Queue dirtytlb-counter.json's soaks (#548): per title B first, then A, one
# handheld per title. Logs each request id to docs/lanes/dirtytlb/queue.log.
set -u
cd "$(dirname "$0")/../../.."
A=9d777502fa; B=111c7fea74
P=docs/testing/predictions/dirtytlb-counter.json
LOG=docs/lanes/dirtytlb/queue.log
CRIMSON='Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso'
BLINX='4D530013-Blinx_The_Time_Sweeper.xiso.iso'
q() {  # title route device ref arm
    echo "== $5 $3 $4" >> "$LOG"
    bash docs/testing/request.sh --who lane.dirtytlb --issue 548 \
        --purpose "#548 [rdc] counter arm $5 on $3" \
        --title "$1" --route "$2" --seconds 240 --perflog --device "$3" \
        --ref "$4" --expect "$P" >> "$LOG" 2>&1
    echo "rc=$?" >> "$LOG"
}
q "$CRIMSON" crimson-skies thor "$B" B
q "$CRIMSON" crimson-skies thor "$A" A
q "$BLINX" survey nova "$B" B
q "$BLINX" survey nova "$A" A
