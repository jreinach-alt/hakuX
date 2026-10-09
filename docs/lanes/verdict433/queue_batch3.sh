#!/usr/bin/env bash
# Batch 3 of lane.verdict433 (#433): Nova confirmations for the three
# titles that only ran on the Thor, now that lane.xbox has copied them to
# the Nova (hardware/titlepush/listing-nova.txt, listed 2026-09-29T20:34Z;
# lane.local's 14:15 PDT addendum).
#
# All three had FULL-FAN THOR confirmations withdrawn by lane.local's 12:00
# PDT addendum ("heat-sensitive runs move off the Thor" -- 16/66 Thor title
# runs hit the thermal pause in the preceding 30 h). Azurik's own Thor pilot
# at the defaults (1-1790688705-lane.verdict433-3467502) FAILED on heat
# (thermal-pause-F8 at +938 s). These three re-queue on the Nova instead, at
# the Nova's normal (unchanged) confirmation regimen -- Nova had 0/85
# thermal pauses in the same window.
#
# Same routes as the Thor requests (baldurs-gate-da, kof-mi.returning,
# azurik) -- per the addendum, "the Thor routes may transfer, but check the
# first run's frames" once each lands, since route timings were calibrated
# on the Thor's boot/menu latency, not the Nova's.
#
# --seconds unchanged from queue_batch2.sh: each route's `mark gameplay`
# time in its last soak + 1200 s + margin.
set -u
R=docs/testing/request.sh
REF=${REF:-246fce4e23}

q_nova_default() { # title route seconds why
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
        --title "$1" --route "$2" --seconds "$3" \
        --env PERF_REGIMEN=default --issue 433 \
        --no-expect "Playable confirmation soak (title_verdict.py --require confirmation), not an A/B arm" \
        --purpose "#433 Playable confirmation: $4, $2 route, nova (moved off the Thor per lane.local's 2026-09-29 12:00 PDT heat addendum), PERF_REGIMEN=default, 1200 s after the mark"
}

q_nova_default '5655001A-Baldur_s_Gate_Dark_Alliance.xiso.iso' baldurs-gate-da 1760 "Baldur's Gate: Dark Alliance"
q_nova_default '534E0007-KOF_Maximum_Impact_Maniax.xiso.iso' kof-mi.returning 1500 "KOF: Maximum Impact Maniax"
q_nova_default '4D530007-Azurik_Rise_of_Perathia.xiso.iso' azurik 1480 "Azurik: Rise of Perathia"
