#!/bin/bash
# Hold the device lease while a *person* is driving the emulator.
#
# The Stop hook force-stops the emulator at the end of every agent turn unless
# the lease has been touched within LEASE_TTL. That is correct for an idle
# agent -- the handheld does not charge over the adb cable -- but it also means
# that every time the agent replies to someone who is mid-session, their game
# dies. Sitting through an unskippable two-minute intro only to lose it to a
# hook is a bad trade.
#
# So renew the lease on their behalf, for a bounded time. Bounded matters: if
# this is forgotten, protection returns on its own rather than leaving the
# emulator draining the battery overnight.
#
#   hold_device.sh [minutes]        default 30
#   hold_device.sh release          drop the lease now
set -u
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"

if [ "${1:-}" = release ]; then
    rm -f "$LEASE"
    echo "device lease released; the Stop hook will force-stop as usual"
    exit 0
fi

MINS="${1:-30}"
END=$(( $(date +%s) + MINS * 60 ))
echo "holding the device lease for ${MINS} minutes (renewing every 60s)"
while [ "$(date +%s)" -lt "$END" ]; do
    touch "$LEASE"
    sleep 60
done
rm -f "$LEASE"
echo "device lease expired after ${MINS} minutes; protection resumed"
