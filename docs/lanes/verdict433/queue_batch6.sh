#!/usr/bin/env bash
# Batch 6 of lane.verdict433 (#433): three more Nova confirmations, per
# lane.local's 2026-09-30 06:45 PDT addendum ("queue up to 3 more, pick the
# titles with the best evidence of holding 90% at 28.5+ over their full
# window").
#
# The addendum's named examples do not have that evidence on the Nova:
# Nightfire reads 52-65% on every full-window judge (memfast, 09-29),
# Fuzion Frenzy 72-80%, and Spikeout, GoldenEye: Rogue Agent and RalliSport 2
# have no Nova route run that marked gameplay. The three below are the
# titles whose newest Nova route soaks (judged on copies with judge_copy.py,
# see NOTES.md session 8) hold the bar with the widest margin:
#
#   Alien Hominid   4 runs, 100% at 28.5+, median 59.94, min 41-43 fps,
#                   257-260 s each (ibcache c8e95ed539, two with HAKUX_IBC=0)
#   187: Ride or Die 1 run, 100%, median 59.94, min 59.88, 302 s, in the race
#                   (titleroutes, ref 1c0c23fabb, an ancestor of master)
#   Arctic Thunder  4 runs, 100%, median 39-42, min 31.4-34.3, 195-198 s
#                   (tcg424flip 7bcd6e6e2b, both arms)
#
# --seconds is the route's mark time from those runs + 1200 s + 80 s margin
# (batch 4's Baldur's Gate aborted 10 s short of 1200 s on a 60 s margin).
set -u
R=docs/testing/request.sh
REF=${REF:-15f476e77b}

q_nova_default() { # title route seconds why
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
        --title "$1" --route "$2" --seconds "$3" \
        --env PERF_REGIMEN=default --issue 433 \
        --no-expect "Playable confirmation soak (title_verdict.py --require confirmation), not an A/B arm" \
        --purpose "#433 Playable confirmation (batch 6): $4, $2 route, nova, PERF_REGIMEN=default, 1200 s after the mark"
}

q_nova_default '5A440004-Alien_Hominid.xiso.iso' alien-hominid 1390 "Alien Hominid (4 Nova soaks at 100%, median 59.94)"
q_nova_default '55530036-187_Ride_or_Die.xiso.iso' 187-ride-or-die.returning 1360 "187: Ride or Die (Nova soak at 100%, median 59.94)"
q_nova_default '4D570002-Arctic_Thunder.xiso.iso' arctic-thunder 1510 "Arctic Thunder (4 Nova soaks at 100%, min 31.4)"
