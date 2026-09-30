#!/usr/bin/env bash
# Batch 7 of lane.verdict433 (#433): one Thor cold-start confirmation, per
# lane.local's 2026-09-30 10:20 PDT addendum ("the Thor takes cold-start
# confirmations of light titles again").
#
# A full-sweep of every judgeable Thor route soak since 2026-09-26 (session
# 10, sweep.py against device=thor) found exactly one title meeting the
# addendum's bar -- light, 30-fps-capped, best evidence under about 4.5 W
# net, holding 28.5+ -- that does not already have a Playable verdict:
# Otogi: Myth of Demons (46530002, Thor-only per listing-nova.txt/
# listing-thor.txt). Four independent short screening runs (lane.pacing,
# lane.slowtier2 x2, lane.energymap507, all pre-09-30) read 88.1-95.5% at
# 28.5+ (mean ~90.7%), net_w 4.0-5.1 W -- consistent with "light" and
# marginally at the bar, not comfortably above it. No hang or crash in any
# of the four. Every other Thor-only title with real evidence (Crimson
# Skies, Bruce Lee, Crash Twinsanity, Burnout, 25 to Life) reads well under
# 90% or is inconsistent run to run; none queued.
#
# Alien Hominid already carries a live PASS Playable Thor confirmation
# (1-1790515369-lanelocal-1183547, lane.local, 2026-09-27, fps_ok=1.0,
# gameplay=1273.6s) found in this same sweep -- not this lane's work, noted
# in NOTES, nothing to queue for it here.
#
# --seconds: the route's `mark gameplay` lands at 256-263 s into the run
# across three independent requests (energymap507 -1790650474, slowtier2
# -1790609660, pacing -1790637578: request `seconds` minus each run's
# recorded gameplay_s). Using 265 s + 1200 s confirmation + 80 s margin.
#
# Run from the worktree root.
set -u
R=docs/testing/request.sh
REF=${REF:-b536bac125}

env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device thor --hard-pin --ref "$REF" \
    --title '46530002-Otogi_Myth_of_Demons.xiso.iso' --route otogi --seconds 1545 \
    --env PERF_REGIMEN=default --issue 433 \
    --no-expect "Playable confirmation soak (title_verdict.py --require confirmation), not an A/B arm" \
    --purpose "#433 Playable confirmation: Otogi: Myth of Demons, otogi route, thor cold-start (lane.local's thor_coldconfirm.sh, 2026-09-30 10:20 PDT addendum), PERF_REGIMEN=default, 1200 s after the mark"
