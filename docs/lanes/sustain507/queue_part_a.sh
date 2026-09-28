#!/usr/bin/env bash
# Queue Part A of sustain507-regimen.json in its registered order, then #424's
# third Thor pair (tbflip424-blinx2.json). Run from the worktree root.
set -u
R=docs/testing/request.sh
P=docs/testing/predictions/sustain507-regimen.json
CRIMSON='Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso'
GTA='54540082-Grand_Theft_Auto_San_Andreas.xiso.iso'
MA2='4D53006B-MechAssault_2_Lone_Wolf.xiso.iso'
BLINX='4D530013-Blinx_The_Time_Sweeper.xiso.iso'

q() { # title route seconds regimen purpose
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.sustain507 --device thor --ref f82e7e87fe \
        --title "$1" --route "$2" --seconds "$3" --env "PERF_REGIMEN=$4" \
        --expect "$P" --purpose "#507 Part A: $5"
}
q "$CRIMSON" crimson-skies 1950 max     "Crimson Skies A (max), pair 1 of 3, order A then B"
q "$CRIMSON" crimson-skies 1950 default "Crimson Skies B (default), pair 1 of 3"
q "$GTA"     gta-sa        2100 default "GTA SA B (default), pair 2 of 3, order B then A"
q "$GTA"     gta-sa        2100 max     "GTA SA A (max), pair 2 of 3"
q "$MA2"     mechassault-2 2100 max     "MechAssault 2 A (max), pair 3 of 3, order A then B"
q "$MA2"     mechassault-2 2100 default "MechAssault 2 B (default), pair 3 of 3"

env HAKUX_RELEASE_PRIO=1 "$R" --who lane.sustain507 --device thor --ref 00c2840810 \
    --title "$BLINX" --route survey --seconds 540 \
    --expect docs/testing/predictions/tbflip424-blinx2.json \
    --purpose "#424 tbflip424-blinx2 Thor r3 A (no env), MAX as registered"
env HAKUX_RELEASE_PRIO=1 "$R" --who lane.sustain507 --device thor --ref 00c2840810 \
    --title "$BLINX" --route survey --seconds 540 --env HAKUX_TCG424_RANGE=1 \
    --expect docs/testing/predictions/tbflip424-blinx2.json \
    --purpose "#424 tbflip424-blinx2 Thor r3 B (HAKUX_TCG424_RANGE=1), MAX as registered"
