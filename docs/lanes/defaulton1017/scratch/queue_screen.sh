#!/bin/bash
# Queue defaulton1017-screen.json's rows on the Nova, by name: queue_screen.sh HON HNI ...
# Each row as the prediction's "rows" block spells it. Prints each request id.
W=/home/justin/hakux-work/wt/defaulton1017
REF=ed2b1d3333
EXP=docs/testing/predictions/defaulton1017-screen.json
INSTR=(--env HAKUX_FRAMETRACE=1 --env HAKUX_PROBE_WAITS=1 --env HAKUX_REPORT_TRACE=1)
cd "$W" || exit 1
halo() {
    local row=$1; shift
    TITLE_ROUTES=docs/lanes/halo1016/routes "$W/docs/testing/request.sh" --who defaulton1017 --device nova \
        --title 'Halo Combat Evolved.iso' --route halo-cinematic --seconds 420 --ref "$REF" --perflog \
        --pull 'frametrace_*' "${INSTR[@]}" "$@" --issue 1018 --expect "$EXP" \
        --purpose "defaulton1017 row $row (Halo, #1018 default-on screen)"
}
title() {
    local row=$1 iso=$2 dir=$3 route=$4 secs=$5
    shift 5
    local r=()
    [ -n "$route" ] && r=(--route "$route")
    # HAKUX_IBC=0: HIBC missed in the pilot, so IBC stays off by default (NOTES, 05:25); this is the
    # shipped configuration on ed2b1d3333's binary.
    TITLE_ROUTES="$dir" "$W/docs/testing/request.sh" --who defaulton1017 --device nova \
        --title "$iso" "${r[@]}" --seconds "$secs" --ref "$REF" --perflog --env HAKUX_IBC=0 "$@" --issue 1018 \
        --expect "$EXP" --purpose "defaulton1017 row $row (#1018 default-on screen)"
}
for row in "$@"; do
    echo "== $row"
    case "$row" in
        HON) halo HON ;;
        HNI) halo HNI --env HAKUX_IBC=0 ;;
        HOFF) halo HOFF --env HAKUX_S2T_CVT=0 --env HAKUX_REPORT_EARLY=0 --env HAKUX_FLDCW_CHAIN=0 --env HAKUX_IBC=0 ;;
        MKSM) title MKSM 4D570029-Mortal_Kombat_Shaolin_Monks.xiso.iso docs/lanes/fps1015/routes fps1015-mksm 330 ;;
        # conditional (NOTES, "Conditional rows"): MKSM logged FLDCW precision flips, so the chain's exit ran
        MKC) title MKC 4D570029-Mortal_Kombat_Shaolin_Monks.xiso.iso docs/lanes/fps1015/routes fps1015-mksm 330 \
            --env HAKUX_FLDCW_CHAIN=0 ;;
        TS) title TS 4D530035-Top_Spin.xiso.iso docs/lanes/fps1015/routes fps1015-topspin 450 ;;
        RS) title RS 4D53000F-RalliSport_Challenge.xiso.iso docs/lanes/accuracy804 rallisport-804g 240 ;;
        SHR) title SHR 56550015-The_Simpsons_Hit_Run.xiso.iso docs/testing/titles/routes simpsons-hit-run 300 ;;
        CLR) title CLR 'Conker Live & Reloaded.iso' docs/testing/titles/routes '' 300 ;;
        # conditional: CLR flipped precision on 99.5% of its FLDCW calls, and kept no frames to compare
        CLF) title CLF 'Conker Live & Reloaded.iso' docs/testing/titles/routes '' 300 --frames-every 5 ;;
        CLC) title CLC 'Conker Live & Reloaded.iso' docs/testing/titles/routes '' 300 --frames-every 5 \
            --env HAKUX_FLDCW_CHAIN=0 ;;
        AMP) title AMP 'Amped 2 (USA).xiso.iso' docs/testing/titles/routes amped2 578 ;;
        TSC1|TSC2)
            "$W/docs/testing/request.sh" --who defaulton1017 --device nova --suites Texture_shadow_comparator \
                --ref f5a67ba52c --issue 1018 --expect docs/testing/predictions/defaulton1017-tsc.json \
                --purpose "defaulton1017 $row: fps1015's pixel item, Texture_shadow_comparator on arm A, no env (#1018, #986)" ;;
        *) echo "unknown row $row"; exit 2 ;;
    esac
done
