#!/usr/bin/env bash
# Queue #526 render-wait soaks. Usage: queue_rwait.sh pilot|rest|otogi|all  Log: docs/lanes/pacing/.queue_rwait.log (not committed)
set -u
cd /home/justin/hakux-work/wt/pacing
P=docs/testing/predictions/pacing-rwait-soak.json
C="Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso"
O=46530002-Otogi_Myth_of_Demons.xiso.iso
q() { # purpose title route env...
    local purpose="$1" title="$2" route="$3"; shift 3
    local envs=()
    for e in "$@"; do envs+=(--env "$e"); done
    echo "== $purpose"
    env HAKUX_RELEASE_PRIO=1 docs/testing/request.sh --who lane.pacing --purpose "$purpose" \
        --title "$title" --route "$route" --seconds "${SECS:-240}" --device thor --ref f53000f7e4 \
        "${envs[@]}" --expect "${PRED:-$P}"
    echo "rc=$?"
}
case "${1:-}" in
pilot)
    q "#526 render wait A1: yield, Crimson Skies" "$C" crimson-skies HAKUX_RENDER_WAIT=yield PERF_REGIMEN=default
    q "#526 render wait B1: block, Crimson Skies" "$C" crimson-skies PERF_REGIMEN=default
    ;;
rest)
    q "#526 render wait A1: yield, Otogi" "$O" otogi HAKUX_RENDER_WAIT=yield PERF_REGIMEN=default
    q "#526 render wait B1: block, Otogi" "$O" otogi PERF_REGIMEN=default
    q "#526 render wait A2: yield, Crimson Skies" "$C" crimson-skies HAKUX_RENDER_WAIT=yield PERF_REGIMEN=default
    q "#526 render wait B2: block, Crimson Skies" "$C" crimson-skies PERF_REGIMEN=default
    q "#526 render wait A2: yield, Otogi" "$O" otogi HAKUX_RENDER_WAIT=yield PERF_REGIMEN=default
    q "#526 render wait B2: block, Otogi" "$O" otogi PERF_REGIMEN=default
    ;;
otogi)
    # Otogi's route marks gameplay at ~246 s: the 240 s runs were all VOID. A1 B1 B2 A2.
    export SECS=400 PRED=docs/testing/predictions/pacing-rwait-otogi.json
    q "#526 render wait A1: yield, Otogi 400 s" "$O" otogi HAKUX_RENDER_WAIT=yield PERF_REGIMEN=default
    q "#526 render wait B1: block, Otogi 400 s" "$O" otogi PERF_REGIMEN=default
    q "#526 render wait B2: block, Otogi 400 s" "$O" otogi PERF_REGIMEN=default
    q "#526 render wait A2: yield, Otogi 400 s" "$O" otogi HAKUX_RENDER_WAIT=yield PERF_REGIMEN=default
    ;;
all)
    bash "$0" pilot
    bash "$0" rest
    ;;
*) echo "pilot|rest|otogi|all" >&2; exit 2 ;;
esac
