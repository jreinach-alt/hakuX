#!/usr/bin/env bash
# Queue Part C of sustain507-levers.json in its registered order: the Thor's
# Blinx pair ON then OFF, the Nova's AUF pair OFF then ON, all at the device
# defaults. Each run is scored only from a cold start (xo <= 50 C, battery
# zone <= 36 C), which the queue cannot ask for: see the prediction's `runs`.
# Run from the worktree root.
set -u
R=docs/testing/request.sh
P=docs/testing/predictions/sustain507-levers.json
REF=9d777502fa
BLINX='4D530013-Blinx_The_Time_Sweeper.xiso.iso'
AUF='4541000D-007_Agent_Under_Fire.xiso.iso'

q() { # device title purpose env...
    local dev="$1" title="$2" purpose="$3"; shift 3
    local envs=()
    for e in "$@"; do envs+=(--env "$e"); done
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.sustain507 --device "$dev" --ref "$REF" \
        --title "$title" --route survey --seconds 2160 "${envs[@]}" \
        --expect "$P" --purpose "#507 Part C: $purpose; needs a COLD start (xo <= 50 C, battery <= 36 C)"
}
q thor "$BLINX" "Thor Blinx halt ON, first of the pair" PERF_REGIMEN=default HAKUX_IDLE_HALT=1
q thor "$BLINX" "Thor Blinx halt OFF, second of the pair" PERF_REGIMEN=default
q nova "$AUF"   "Nova AUF halt OFF, first of the pair" PERF_REGIMEN=default
q nova "$AUF"   "Nova AUF halt ON, second of the pair" PERF_REGIMEN=default HAKUX_IDLE_HALT=1
