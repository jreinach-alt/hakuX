#!/usr/bin/env bash
# Batch 8 of lane.verdict433 (#433): one Nova 600-s confirmation, per
# lane.local's 2026-09-30 12:10 PDT addendum (the Playable confirmation is
# now 600 s of gameplay; judge with title_verdict.py --require screening
# until lane.verdict10min folds) and the 09:55 addendum (30-capped titles
# with clean full windows count).
#
#   Crimson Skies  4 judgeable Nova route soaks since 09-29, 94.1-96.6% at
#                  28.5+, no hang, no audio short, 250-254 s each, 7.1-7.3 W
#                  net. The 94.1% run is ibcache's HAKUX_IBC=0 control
#                  (master's code path); the 96.6% runs are IBC-on builds
#                  not on master. No pass verdict for 4D530021 in the
#                  results (scan.py Crimson). Not a flagged title.
#
# --seconds: the route marks gameplay at ~105 s (wait 75, mash A 12 x 1.5,
# wait 12) + 600 s + 115 s margin.
set -u
R=docs/testing/request.sh
REF=${REF:-5a0a940b8e}

env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
    --title 'Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso' \
    --route crimson-skies --seconds 820 \
    --env PERF_REGIMEN=default --issue 433 \
    --no-expect "Playable confirmation soak (600-s rule, title_verdict.py --require screening), not an A/B arm" \
    --purpose "#433 Playable confirmation (batch 8, 600-s rule of 09-30): Crimson Skies (4 Nova soaks at 94.1-96.6%, 30-capped), crimson-skies route, nova, PERF_REGIMEN=default, 600 s after the mark"
