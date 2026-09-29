#!/usr/bin/env bash
# Batch 2 of lane.verdict433 (#433): re-run what batch 1 could not finish.
#
# Thor titles (Baldur's Gate DA, KOF MI, Azurik) now run at full fan per the
# owner's 2026-09-29 ~10:00 PDT decision (#433 comment 5894686025):
# PERF_REGIMEN=max, FAN_MODE=customize:100. The bar is unchanged; a thermal
# pause during the run still fails it.
#   - Baldur's Gate DA and KOF MI: lane.local withdrew their batch-1 requests
#     at the defaults (-211577, -211719); this re-queues both at full fan.
#   - Azurik: its batch-1 pilot (1-1790688705-lane.verdict433-3467502) FAILED
#     on heat at the defaults (thermal-pause-F8 at +938 s from a cool 48.6 C
#     start; still paused at the run's end). Re-confirming at full fan per
#     the addendum, since the owner's ruling applies to it too.
#
# Nova titles (WWE Raw 2, 50 Cent) are unchanged (PERF_REGIMEN=default) --
# "Nova confirmations are unchanged" -- and are re-queued only because their
# batch-1 runs did not produce a real reading:
#   - WWE Raw 2 (0-0-x-1-1790693575-lane.verdict433-211620): DONE, but
#     title_verdict.py reads void: "not-foreground: unreadable (ee317437 adb
#     failed (exit 1))" -- a capture glitch, not a low fps reading.
#   - 50 Cent (0-0-x-1-1790693575-lane.verdict433-211666): ERROR "could not
#     set the requested env_vars pref" -- the run never started.
#
# Run from the worktree root. --seconds = the route's `mark gameplay` time in
# its last soak + 1200 s + margin, same figures as queue_batch1.sh (the route
# and its timing did not change).
set -u
R=docs/testing/request.sh
REF=${REF:-3427e75ba1}

q_thor_maxfan() { # title route seconds why
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device thor --ref "$REF" \
        --title "$1" --route "$2" --seconds "$3" \
        --env PERF_REGIMEN=max --env FAN_MODE=customize:100 --issue 433 \
        --no-expect "Playable confirmation soak (title_verdict.py --require confirmation), not an A/B arm" \
        --purpose "#433 Playable confirmation: $4, $2 route, thor, PERF_REGIMEN=max FAN_MODE=customize:100 (full fan, owner 2026-09-29 ~10:00 PDT), 1200 s after the mark"
}

q_nova_default() { # title route seconds why
    env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
        --title "$1" --route "$2" --seconds "$3" \
        --env PERF_REGIMEN=default --issue 433 \
        --no-expect "Playable confirmation soak (title_verdict.py --require confirmation), not an A/B arm" \
        --purpose "#433 Playable confirmation retry: $4, $2 route, nova, PERF_REGIMEN=default, 1200 s after the mark (batch-1 run did not produce a reading)"
}

q_thor_maxfan '5655001A-Baldur_s_Gate_Dark_Alliance.xiso.iso' baldurs-gate-da 1760 "Baldur's Gate: Dark Alliance"
q_thor_maxfan '534E0007-KOF_Maximum_Impact_Maniax.xiso.iso' kof-mi.returning 1500 "KOF: Maximum Impact Maniax"
q_thor_maxfan '4D530007-Azurik_Rise_of_Perathia.xiso.iso' azurik 1480 "Azurik: Rise of Perathia"
q_nova_default '5451000D-WWE_Raw_2.xiso.iso' wwe-raw-2 1550 "WWE Raw 2"
q_nova_default '56550042-50_Cent_Bulletproof.xiso.iso' 50cent 1420 "50 Cent: Bulletproof"
