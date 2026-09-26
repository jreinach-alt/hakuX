#!/bin/bash
# Queue the #427 Crimson soak arms, interleaved A1 B1 A2 B2, on the Thor.
# usage: queue_soaks.sh [A_REF] [B_REF]
set -e
cd "$(dirname "$0")/../../.."
A=${1:-15d9406b81}
B=${2:-6cd1a58b64}
T="Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso"
for arm in A1:$A B1:$B A2:$A B2:$B; do
    bash docs/testing/request.sh --who buildflags427 \
        --purpose "#427 Crimson soak ${arm%%:*}" --title "$T" --device thor \
        --route crimson-skies --seconds 240 --ref "${arm##*:}" \
        --expect docs/testing/predictions/buildflags427-crimson-soak.json
done
