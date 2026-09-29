#!/usr/bin/env bash
# Batch 1 of lane.verdict433 (#433): 20-min Playable confirmations at the
# device's defaults (PERF_REGIMEN=default, the #433 ruling of 2026-09-27), on
# the handheld and route each title's best route soak ran on. Queue it only
# after the pilot (Azurik, 1-1790688705-lane.verdict433-3467502) is reviewed
# and $DISPATCH_DIR/pilots/lane.verdict433.ok is written. Run from the
# worktree root. --seconds = the route's `mark gameplay` time in its last soak
# + 1200 s + about 60 s of margin.
set -u
R=docs/testing/request.sh
REF=${REF:-83b030fa27}
q() { # device title route seconds why
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device "$1" --ref "$REF" \
        --title "$2" --route "$3" --seconds "$4" --env PERF_REGIMEN=default --issue 433 \
        --no-expect "Playable confirmation soak (title_verdict.py --require confirmation), not an A/B arm" \
        --purpose "#433 Playable confirmation: $5, $3 route, $1, PERF_REGIMEN=default, 1200 s after the mark"
}
q thor '5655001A-Baldur_s_Gate_Dark_Alliance.xiso.iso' baldurs-gate-da 1760 "Baldur's Gate: Dark Alliance"
q nova '5451000D-WWE_Raw_2.xiso.iso' wwe-raw-2 1550 "WWE Raw 2"
q nova '56550042-50_Cent_Bulletproof.xiso.iso' 50cent 1420 "50 Cent: Bulletproof"
q thor '534E0007-KOF_Maximum_Impact_Maniax.xiso.iso' kof-mi.returning 1500 "KOF: Maximum Impact Maniax"
