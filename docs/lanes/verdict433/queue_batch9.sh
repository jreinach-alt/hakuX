#!/usr/bin/env bash
# Batch 9 of lane.verdict433 (#433): re-queue of batch 8's Crimson Skies
# confirmation, which batch 8's own request (`-750238`) never actually ran --
# it was withdrawn by lane.local at 14:37 PDT citing the 14:40 PDT Galleon
# block, but the withdrawn request's title field reads "Crimson Skies - High
# Road to Revenge...", not Galleon (41540004 is nowhere in it). The only
# plausible trigger is the route's own comment text, which mentions
# "Galleon-era perf runs" as flavour text about a historical crash fix --
# a false positive on prose, not on the title. See NOTES session 14 for the
# withdrawn .req/.why read. Crimson Skies (4D530021) is not on
# host-tools/blocked-titles.txt and is not blocked.
#
# Same form as queue_batch8.sh, now on lane.verdict10min's folded
# confirmation_s=600 default (native in title_verdict.py as of this merge,
# so this reads with plain `--require confirmation`, no --require screening
# workaround).
set -u
R=docs/testing/request.sh
REF=${REF:-05695acc7c}

env HAKUX_RELEASE_PRIO=1 "$R" --who lane.verdict433 --device nova --ref "$REF" \
    --title 'Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso' \
    --route crimson-skies --seconds 820 \
    --env PERF_REGIMEN=default --issue 433 \
    --no-expect "Playable confirmation soak (600-s confirmation_s default), not an A/B arm" \
    --purpose "#433 Playable confirmation (batch 9, re-queue of batch 8 after its false-positive Galleon withdrawal): Crimson Skies (4 Nova soaks at 94.1-96.6%, 30-capped), crimson-skies route, nova, PERF_REGIMEN=default, 600 s after the mark"
