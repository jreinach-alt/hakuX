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
# Stopping the emulator is only half of it. On this device ES-DE
# (org.es_de.frontend) is the *home* app, and its main window carries
# FLAG_KEEP_SCREEN_ON, so force-stopping the emulator hands the foreground back
# to a window that pins the display on for good. Measured on a Retroid Pocket
# Nova: asleep and idle draws +122uA (charging), the same device sitting on
# ES-DE with the screen lit draws -107mA, and the screen-off timeout never
# fires because the flag suppresses it. So put the device back to sleep
# explicitly. KEYCODE_SLEEP overrides FLAG_KEEP_SCREEN_ON where the timeout
# cannot -- verified: Awake -> Asleep, display suspend blocker released,
# current_now back to 0.
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

#
# There are two kinds of lease. The shared file below covers every device and
# is what hold_device.sh and the older single-device scripts touch. The
# dispatcher instead holds one lease PER DEVICE (devices.sh names it), so that
# two dispatchers do not each mistake the other's run for their own. This hook
# runs without that environment, so it has to look the per-device lease up
# itself: checking only the shared file meant that once nothing touched it,
# every turn end in any session force-stopped both handhelds mid-run.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"
LEASE_TTL="${HAKUX_LEASE_TTL:-90}"
PKGS="com.jreinach.hakux.debug com.jreinach.hakux.debug2 com.jreinach.hakux"

command -v adb >/dev/null 2>&1 || exit 0

lease_age() {   # seconds since the file was touched, or nothing if absent
    [ -f "$1" ] || return 1
    echo $(( $(date +%s) - $(stat -c %Y "$1" 2>/dev/null || echo 0) ))
}

if age=$(lease_age "$LEASE") && [ "$age" -lt "$LEASE_TTL" ]; then
    echo "hakuX: device lease renewed ${age}s ago — leaving the emulator running."
    echo "hakuX: if that is wrong, rm $LEASE"
    exit 0
fi

# The per-device lease path for a serial, from the device table. A subshell,
# because device_env exports into whatever sources it. Sourcing devices.sh
# returns non-zero (its last line is a false test), so do not chain on it.
device_lease() {
    ( . "$HERE/devices.sh" >/dev/null 2>&1
      device_env "$1" >/dev/null 2>&1 && printf '%s' "$HAKUX_DEVICE_LEASE" )
}

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
    # Leave a device alone -- emulator and screen both -- while its own lease
    # is fresh. Putting the panel to sleep mid-run minimises the app.
    dlease=$(device_lease "$serial")
    if [ -n "$dlease" ] && age=$(lease_age "$dlease") && [ "$age" -lt "$LEASE_TTL" ]; then
        echo "hakuX: $serial lease ($dlease) renewed ${age}s ago — leaving it running."
        continue
    fi
    procs=$(adb -s "$serial" shell 'ps -A -o NAME' 2>/dev/null | tr -d '\r')
    for pkg in $PKGS; do
        if printf '%s\n' "$procs" | grep -qE "^${pkg}(:.*)?$"; then
            adb -s "$serial" shell am force-stop "$pkg" >/dev/null 2>&1
            stopped="$stopped $serial/$pkg"
        fi
    done
    # Whether or not we stopped anything, do not leave the screen lit: the
    # emulator may already have exited on its own straight back onto ES-DE.
    adb -s "$serial" shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
done

[ -n "$stopped" ] && echo "hakuX: force-stopped the emulator on:$stopped"
exit 0
