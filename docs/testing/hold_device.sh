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

PIDFILE="$LEASE.holder"

if [ "${1:-}" = release ]; then
    # Deleting the lease file is not enough: a renewer still looping will
    # recreate it within the minute and the Stop hook stays suppressed, which
    # is how the emulator ends up running all night on a handheld that does
    # not charge over the cable. Stop the renewer first.
    if [ -f "$PIDFILE" ]; then
        holder=$(cat "$PIDFILE" 2>/dev/null || echo)
        if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
            kill "$holder" 2>/dev/null
            # Verify rather than announce. This printed success while the
            # renewer carried on, which is the failure that makes a released
            # lease silently keep the Stop hook suppressed.
            gone=0
            for _ in 1 2 3 4 5 6 7 8 9 10; do
                kill -0 "$holder" 2>/dev/null || { gone=1; break; }
                sleep 0.5
            done
            if [ "$gone" = 1 ]; then
                echo "stopped the renewer (pid $holder)"
            else
                kill -9 "$holder" 2>/dev/null
                sleep 0.5
                if kill -0 "$holder" 2>/dev/null; then
                    echo "WARNING: renewer $holder is still alive; the lease may" >&2
                    echo "         come back and the Stop hook stay suppressed." >&2
                else
                    echo "renewer $holder ignored TERM; killed it"
                fi
            fi
        fi
        rm -f "$PIDFILE"
    fi
    rm -f "$LEASE"
    echo "device lease released; the Stop hook will force-stop as usual"
    exit 0
fi

MINS="${1:-30}"
END=$(( $(date +%s) + MINS * 60 ))
echo $$ > "$PIDFILE"
# Two traps, not one. A TERM handler that only cleans up does NOT stop the
# loop: the handler runs, the cleanup deletes the lease, and the next
# iteration touches it again -- so `release` prints that it stopped the
# renewer, the files vanish, and sixty seconds later the lease is back. Worse,
# bash defers the trap until the foreground `sleep` returns, so the whole
# thing happens a minute after the operator was told it was done. Measured and
# reproduced by the device-setup session; only kill -9 ended it.
#
# EXIT does the cleanup; INT/TERM exit and let EXIT run.
trap 'rm -f "$LEASE" "$PIDFILE"' EXIT
trap 'exit 0' INT TERM
echo "holding the device lease for ${MINS} minutes (renewing every 60s)"
while [ "$(date +%s)" -lt "$END" ]; do
    touch "$LEASE"
    # Backgrounded so a TERM is handled the moment it arrives rather than up
    # to a minute later. `wait` returns immediately when a trap fires.
    sleep 60 & wait $! 2>/dev/null || true
done
rm -f "$LEASE" "$PIDFILE"
echo "device lease expired after ${MINS} minutes; protection resumed"
