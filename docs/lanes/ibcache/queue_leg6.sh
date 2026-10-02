#!/usr/bin/env bash
# lane.ibcache leg 6 (#507): the probe with the idle halt ON in both arms.
# Usage: queue_leg6.sh <ref> <order>   e.g. queue_leg6.sh 1b752de638 BAAB
# B = HAKUX_IBC=1, A = probe off (HAKUX_IBC unset, the default since the
# default-off commit); both arms HAKUX_IDLE_HALT=1. Forza, driven route,
# Nova, 420 s. The route is copied into titles/routes/ only to queue
# (request.json carries its text) and removed after.
set -u
here=$(cd "$(dirname "$0")" && pwd)
top=$(cd "$here/../../.." && pwd)
req="$top/docs/testing/request.sh"
rt="$top/docs/testing/titles/routes/ibcache-forza-drive.route"
R=$1 order=$2
NE="env A/B on one binary, both arms with the idle halt on, hand-read against leg 6 in docs/lanes/ibcache/NOTES.md"
cp "$here/forza-drive.route" "$rt"
for (( i=0; i<${#order}; i++ )); do
    case ${order:$i:1} in
    B) bash "$req" --who lane.ibcache --device nova --ref "$R" \
        --title 4D53006E-Forza_Motorsport.xiso.iso --route ibcache-forza-drive \
        --seconds 420 --perflog --issue 507 --env HAKUX_IDLE_HALT=1 --env HAKUX_IBC=1 \
        --purpose "#507 lane.ibcache leg 6, arm B: Forza (driven) with the idle halt ON and the inline jump-cache probe ON (HAKUX_IBC=1) at $R" \
        --no-expect "$NE" ;;
    A) bash "$req" --who lane.ibcache --device nova --ref "$R" \
        --title 4D53006E-Forza_Motorsport.xiso.iso --route ibcache-forza-drive \
        --seconds 420 --perflog --issue 507 --env HAKUX_IDLE_HALT=1 \
        --purpose "#507 lane.ibcache leg 6, arm A: Forza (driven) with the idle halt ON and the probe OFF (default) at $R" \
        --no-expect "$NE" ;;
    esac
done
rm -f "$rt"
