#!/usr/bin/env bash
# Queue the #303 tier1 A/B: four Thor soaks, interleaved ON, OFF, ON, OFF,
# on one binary. The env is the only independent variable.
set -euo pipefail
cd "$(dirname "$0")/../../.."
T="Spikeout - Battle Street (Europe).iso"
P=docs/testing/predictions/fmv303b-tier1-ab.json
REF=4b96082573
for i in 1 2; do
  docs/testing/request.sh --who fmv303b --purpose "#303 tier1 A/B: ON run $i" \
    --title "$T" --seconds 150 --frames-every 2 --device thor --ref "$REF" \
    --env HAKUX_FMV303_PROBE=1 --expect "$P"
  sleep 2
  docs/testing/request.sh --who fmv303b --purpose "#303 tier1 A/B: OFF run $i" \
    --title "$T" --seconds 150 --frames-every 2 --device thor --ref "$REF" \
    --env HAKUX_FMV303_PROBE=1 --env HAKUX_TIER1_THRESHOLD=0 --expect "$P"
  sleep 2
done
