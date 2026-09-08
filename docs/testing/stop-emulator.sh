#!/usr/bin/env bash
#
# Force-stop the emulator on every attached device.
#
# Wire this to a Stop hook (see .claude/settings.json) so that an agent's turn
# can never end with the emulator holding the GPU. A left-running emulator
# stops the handheld trickle-charging, so an abandoned run flattens the battery
# rather than merely wasting it — and issue #20 means a finished run does not
# exit by itself, so this happens on the *success* path too, not just on
# crashes.
#
# Per-script `trap ... EXIT` handlers are not enough on their own: they only
# cover their own script, and say nothing about a turn ending while a
# background campaign holds the device.
#
# Exits 0 unconditionally. It must never fail a turn.
#
# A long-running batch that legitimately owns the device can hold a lease by
# touching $HAKUX_DEVICE_LEASE (default /tmp/hakux-device-lease) at least once
# every LEASE_TTL seconds. The lease is deliberately short-lived: if the batch
# dies, protection resumes on its own rather than staying disabled forever.

LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"
LEASE_TTL="${HAKUX_LEASE_TTL:-90}"
PKGS="com.jreinach.hakux.debug com.jreinach.hakux"

command -v adb >/dev/null 2>&1 || exit 0

if [ -f "$LEASE" ]; then
    now=$(date +%s)
    then_=$(stat -c %Y "$LEASE" 2>/dev/null || echo 0)
    age=$((now - then_))
    if [ "$age" -lt "$LEASE_TTL" ]; then
        echo "hakuX: device lease renewed ${age}s ago — leaving the emulator running."
        echo "hakuX: if that is wrong, rm $LEASE"
        exit 0
    fi
fi

# Match ANY process belonging to the package, not just "<pkg>:xemu".  The
# launcher activity runs as bare "<pkg>" and the emulator child may not have
# spawned yet (or may have exited leaving the activity up); either way the app
# is on screen holding the display.  Checking only the :xemu child missed
# exactly that case in testing.
stopped=""
# `adb devices` emits CRLF, so without stripping CR the state field is
# "device\r", never matches, and this loop silently iterates over nothing --
# the hook then exits 0 having done nothing, which is indistinguishable from
# success.  This bit once; keep the tr.
for serial in $(adb devices 2>/dev/null | tr -d '\r' |
                awk 'NR>1 && $2=="device" {print $1}'); do
    procs=$(adb -s "$serial" shell 'ps -A -o NAME' 2>/dev/null | tr -d '\r')
    for pkg in $PKGS; do
        if printf '%s\n' "$procs" | grep -qE "^${pkg}(:.*)?$"; then
            adb -s "$serial" shell am force-stop "$pkg" >/dev/null 2>&1
            stopped="$stopped $serial/$pkg"
        fi
    done
done

[ -n "$stopped" ] && echo "hakuX: force-stopped the emulator on:$stopped"
exit 0
