#!/bin/bash
# Queue halo1016-reports.json's two arms on the Nova, RT then RC, after the tier-1 arms.
W=/home/justin/hakux-work/wt/halo1016
REF=7da5534b6b
BASE=(--env HAKUX_FRAMETRACE=1 --env HAKUX_PROBE_WAITS=1 --env HAKUX_S2T_CVT=1 --env HAKUX_REPORT_TRACE=1)
q() {
    local arm=$1; shift
    echo "== $arm"
    TITLE_ROUTES=docs/lanes/halo1016/routes "$W/docs/testing/request.sh" --who halo1016 --device nova \
        --title 'Halo Combat Evolved.iso' --route halo-cinematic --seconds 420 --ref "$REF" --perflog \
        --pull 'frametrace_*' "${BASE[@]}" "$@" --issue 1018 \
        --expect docs/testing/predictions/halo1016-reports.json --purpose "halo1016-reports arm $arm"
}
q RT
q RC --env HAKUX_REPORT_CATCHUP=1
