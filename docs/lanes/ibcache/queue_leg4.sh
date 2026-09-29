#!/usr/bin/env bash
# lane.ibcache legs 4 and 5b (#507): env A/B pairs on one binary.
# Usage: queue_leg4.sh <device> <seconds> <order> <route> <iso> <name>
#   order: a string of A/B, one request per letter, in queue order (e.g. BAAB).
# Since 2026-09-29 12:10 PDT fps/J-frame runs go to the Nova (the Thor voided
# 15 of 66 title runs on its thermal pause), so the Thor's 240 s cap is gone.
set -u
here=$(cd "$(dirname "$0")" && pwd)
req="$here/../../testing/request.sh"
R=c8e95ed539
NE="env A/B on one binary, hand-read with title_verdict.py against legs 4 and 5b in docs/lanes/ibcache/NOTES.md"
dev=$1 secs=$2 order=$3 route=$4 iso=$5 name=$6
for (( i=0; i<${#order}; i++ )); do
    case ${order:$i:1} in
    B) bash "$req" --who lane.ibcache --device "$dev" --ref "$R" --title "$iso" \
        --route "$route" --seconds "$secs" --perflog --issue 507 \
        --purpose "#507 lane.ibcache leg 4/5b, arm B: $name with the inline jump-cache probe ON (default, HAKUX_IBC unset) at $R" \
        --no-expect "$NE" ;;
    A) bash "$req" --who lane.ibcache --device "$dev" --ref "$R" --title "$iso" \
        --route "$route" --seconds "$secs" --perflog --issue 507 --env HAKUX_IBC=0 \
        --purpose "#507 lane.ibcache leg 4/5b, arm A: $name with the inline jump-cache probe OFF (HAKUX_IBC=0) at $R" \
        --no-expect "$NE" ;;
    esac
done
