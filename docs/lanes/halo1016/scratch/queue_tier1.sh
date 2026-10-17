#!/bin/bash
# Queue halo1016-tier1.json's two arms on the Nova, T then FIT, after the vcpu arms.
W=/home/justin/hakux-work/wt/halo1016
REF=d70f782f45
BASE=(--env HAKUX_FRAMETRACE=1 --env HAKUX_PROBE_WAITS=1 --env HAKUX_S2T_CVT=1 --env HAKUX_TIER1_THRESHOLD=0)
q() {
    local arm=$1; shift
    echo "== $arm"
    TITLE_ROUTES=docs/lanes/halo1016/routes "$W/docs/testing/request.sh" --who halo1016 --device nova \
        --title 'Halo Combat Evolved.iso' --route halo-cinematic --seconds 420 --ref "$REF" --perflog \
        --pull 'frametrace_*' "${BASE[@]}" "$@" --issue 1018 \
        --expect docs/testing/predictions/halo1016-tier1.json --purpose "halo1016-tier1 arm $arm"
}
q T
q FIT --env HAKUX_FLDCW_CHAIN=1 --env HAKUX_IBC=1
