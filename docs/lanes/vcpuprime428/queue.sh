#!/usr/bin/env bash
# Queue one arm run of the #428 placement A/B: queue.sh A|B LABEL
# (A1 was queued by hand with the same arguments as `queue.sh A A1`.)
set -eu
cd "$(dirname "$0")/../../.."
T="Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso"
ENV=(--env HAKUX_TOPO=200,10)
[ "$1" = B ] && ENV+=(--env HAKUX_PLACE_VCPU=prime)
bash docs/testing/request.sh --who vcpuprime428 --purpose "#428 place $2" \
    --title "$T" --route crimson-skies --seconds 480 --device thor \
    --ref 15d9406b81 "${ENV[@]}" \
    --expect docs/testing/predictions/vcpuprime428-soak.json
