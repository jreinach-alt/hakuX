#!/bin/bash
# lane.blinx2input: run several nav.py steps in one call, e.g.
#   nav.sh "press A" "wait 1.5" "press R3" "shot r3"
# Each argument is one nav.py command line. Stops at the first failure.
here=$(cd "$(dirname "$0")" && pwd)
nav="$here/../../testing/titles/nav.py"
export NAV_DIR="${NAV_DIR:-scratch/nav}" SERIAL="${SERIAL:-ee317437}"
for step in "$@"; do
    # shellcheck disable=SC2086
    python3 "$nav" $step || exit 1
done
