#!/bin/bash
# Queue halo1016-vcpu.json's five arms on the Nova, in order A, F, I, IF, A2.
W=/home/justin/hakux-work/wt/halo1016
REF=d70f782f45
BASE=(--env HAKUX_FRAMETRACE=1 --env HAKUX_PROBE_WAITS=1 --env HAKUX_S2T_CVT=1)
q() {
    local arm=$1; shift
    echo "== $arm"
    TITLE_ROUTES=docs/lanes/halo1016/routes "$W/docs/testing/request.sh" --who halo1016 --device nova \
        --title 'Halo Combat Evolved.iso' --route halo-cinematic --seconds 420 --ref "$REF" --perflog \
        --pull 'frametrace_*' "${BASE[@]}" "$@" --issue 1018 \
        --expect docs/testing/predictions/halo1016-vcpu.json --purpose "halo1016-vcpu arm $arm"
}
q A
q F --env HAKUX_FLDCW_CHAIN=1
q I --env HAKUX_IBC=1
q IF --env HAKUX_FLDCW_CHAIN=1 --env HAKUX_IBC=1
q A2
