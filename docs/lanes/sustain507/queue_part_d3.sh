#!/usr/bin/env bash
# Queue Part D.3 of sustain507-fan100.json: Customize 100 at MAX, warm starts
# through the normal gate, Crimson first then GTA SA. Run from the worktree root.
set -u
R=docs/testing/request.sh
P=docs/testing/predictions/sustain507-fan100.json
CRIMSON='Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso'
GTA='54540082-Grand_Theft_Auto_San_Andreas.xiso.iso'

q() { # title route seconds purpose
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.sustain507 --device thor --ref f82e7e87fe \
        --title "$1" --route "$2" --seconds "$3" \
        --env PERF_REGIMEN=max --env FAN_MODE=customize:100 \
        --expect "$P" --purpose "#507 D.3: $4"
}
q "$CRIMSON" crimson-skies 1950 "Crimson Skies B (MAX, fan Customize 100), 1 of 2"
q "$GTA"     gta-sa        2100 "GTA SA B (MAX, fan Customize 100), 2 of 2"
