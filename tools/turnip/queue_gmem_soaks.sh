#!/usr/bin/env bash
# #68 (f): does Turnip's sysmem/GMEM choice move frame time on a reference
# title? Stock T30, one binary, TU_DEBUG as the only variable, interleaved so
# a drift over the queue lands on every arm alike. One request per replicate:
# the soak path runs a title once and refuses --runs.
set -eu
cd "$(dirname "$0")/../.."
REF="${REF:-a7f7c8bda943704323510597f8a6122356d77c6a}"
TITLE="${TITLE:-Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso}"
WHY="survey: TU_DEBUG sysmem/gmem vs autotune on stock T30, frame time; decides whether a T1 GMEM policy is worth writing"
for rep in 1 2; do
    for arm in autotune sysmem gmem; do
        env_args=()
        [ "$arm" = autotune ] || env_args=(--env "TU_DEBUG=$arm")
        docs/testing/request.sh --who turnipfork \
            --purpose "#68 (f) GMEM policy soak: $arm rep $rep" \
            --title "$TITLE" --seconds 240 --ref "$REF" --device nova \
            "${env_args[@]}" --no-expect "$WHY" 2>&1 | grep -E '^queued|refus'
    done
done
