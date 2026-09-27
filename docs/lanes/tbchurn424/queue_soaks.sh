#!/usr/bin/env bash
# Queue #424's soaks, interleaved A/B on the Thor. Arg 1: first index to
# queue (the Crimson A r1 went out by hand as 1790454893-lane.tbchurn424-3968865).
set -u
cd "$(dirname "$0")/../../.."
C="Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso"
X="4D530013-Blinx_The_Time_Sweeper.xiso.iso"
P=docs/testing/predictions/tbchurn424-soak.json
A=7e6a4ac88a
B=1d1251aa4b
q() {
    bash docs/testing/request.sh --who lane.tbchurn424 --purpose "$1" \
        --title "$2" --route "$3" --seconds 300 --device thor --ref "$4" \
        --expect "$P" 2>&1 | grep '^queued'
}
q "#424 B crimson route r1" "$C" crimson-skies $B
q "#424 A crimson route r2" "$C" crimson-skies $A
q "#424 B crimson route r2" "$C" crimson-skies $B
q "#424 A crimson route r3" "$C" crimson-skies $A
q "#424 B crimson route r3" "$C" crimson-skies $B
q "#424 A blinx survey r1" "$X" survey $A
q "#424 B blinx survey r1" "$X" survey $B
q "#424 A blinx survey r2" "$X" survey $A
q "#424 B blinx survey r2" "$X" survey $B
