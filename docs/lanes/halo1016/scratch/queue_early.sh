#!/bin/bash
# Queue halo1016-early.json's six arms on the Nova: E, B, EIF, S, then the picture arms EV, BV.
W=/home/justin/hakux-work/wt/halo1016
REF=08fd920b5c
BASE=(--env HAKUX_FRAMETRACE=1 --env HAKUX_PROBE_WAITS=1 --env HAKUX_S2T_CVT=1 --env HAKUX_REPORT_TRACE=1)
q() {
    local arm=$1; shift
    echo "== $arm"
    TITLE_ROUTES=docs/lanes/halo1016/routes "$W/docs/testing/request.sh" --who halo1016 --device nova \
        --title 'Halo Combat Evolved.iso' --route halo-cinematic --seconds 420 --ref "$REF" --perflog \
        --pull 'frametrace_*' "${BASE[@]}" "$@" --issue 1018 \
        --expect docs/testing/predictions/halo1016-early.json --purpose "halo1016-early arm $arm"
}
q E --env HAKUX_REPORT_EARLY=1
q B
q EIF --env HAKUX_REPORT_EARLY=1 --env HAKUX_FLDCW_CHAIN=1 --env HAKUX_IBC=1
q S --env HAKUX_REPORT_SUBMIT=2000
q EV --env HAKUX_REPORT_EARLY=1 --frames-every 20
q BV --frames-every 20
