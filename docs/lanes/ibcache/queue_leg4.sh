#!/usr/bin/env bash
# lane.ibcache legs 4 and 5b (#507): env A/B pairs on one binary, probe-on arm
# first so the title's first-run shader compiles land on the probe's arm.
# 240 s soaks on routes that reach gameplay by ~105 s end before the Thor's
# thermal pause (+291 s in the GTA pilot).
set -u
here=$(cd "$(dirname "$0")" && pwd)
req="$here/../../testing/request.sh"
R=c8e95ed539
NE="env A/B on one binary, hand-read with title_verdict.py against legs 4 and 5b in docs/lanes/ibcache/NOTES.md"
q() { # route iso name
    bash "$req" --who lane.ibcache --device thor --ref "$R" --title "$2" \
        --route "$1" --seconds 240 --perflog --issue 507 \
        --purpose "#507 lane.ibcache leg 4/5b, arm B: $3 with the inline jump-cache probe ON (default, HAKUX_IBC unset) at $R" \
        --no-expect "$NE"
    bash "$req" --who lane.ibcache --device thor --ref "$R" --title "$2" \
        --route "$1" --seconds 240 --perflog --issue 507 --env HAKUX_IBC=0 \
        --purpose "#507 lane.ibcache leg 4/5b, arm A: $3 with the inline jump-cache probe OFF (HAKUX_IBC=0) at $R" \
        --no-expect "$NE"
}
q crimson-skies "Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso" "Crimson Skies"
q alien-hominid "5A440004-Alien_Hominid.xiso.iso" "Alien Hominid"
