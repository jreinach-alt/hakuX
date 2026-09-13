#!/usr/bin/env bash
#
# The device table. Sourced by the dispatcher; runnable on its own to check.
#
#   . devices.sh && device_env <serial>     # exports SERIAL, DEVICE_*, LEASE
#   devices.sh list                         # what is attached and known
#
# There are two handhelds and they are NOT interchangeable until proven so.
# Both are kalama (Snapdragon 8 Gen 2, Adreno 740) on the same Turnip build,
# which is why sharing a queue is plausible at all -- but "plausible" is not
# "measured", and a scoreboard column that silently mixes two devices is the
# same failure as one that silently mixes two binaries. That cost a day when
# the binary was the variable; see the hw-commits-behind column.
#
# So every result records the serial it came from, and the pairing is verified
# by running one identical disc on both and diffing the captures. Until that
# passes, treat them as two lanes, not one pool.
#
# Paths differ per device and there is no discovering them: the SD card UUID
# is per-card and the library layout is whatever the owner chose.
set -u

device_env() {
    case "${1:?device_env needs a serial}" in
    ee317437)   # Retroid Pocket Nova
        export SERIAL=ee317437
        export DEVICE_LABEL="nova"
        export DEVICE_ISO_ROOT="/storage/E6C6-D7AA/Games/XBox"
        ;;
    bdc158a5)   # AYN Thor
        export SERIAL=bdc158a5
        export DEVICE_LABEL="thor"
        export DEVICE_ISO_ROOT="/storage/388C-68F7/ROMS/xbox"
        ;;
    *)  echo "unknown device $1 -- add it to devices.sh rather than guessing" >&2
        return 2 ;;
    esac
    export PKG="${PKG:-com.jreinach.hakux.debug}"
    # Per-device lease. One lease file for two devices would have each
    # dispatcher think the other's run was its own.
    export HAKUX_DEVICE_LEASE="/tmp/hakux-device-lease.$DEVICE_LABEL"
    return 0
}

device_default() {
    # Resolve a serial when the caller gave none -- and REFUSE when the answer
    # is ambiguous.
    #
    # Every script here used to say `adb devices | awk 'NR==2{print $1}'`,
    # which means "whichever device adb happens to list first". With one
    # handheld that is unambiguous. With two it is a coin flip decided by
    # lexical order, and bdc158a5 (Thor) sorts before ee317437 (Nova) -- so
    # the day a second device was attached, every one of those scripts
    # silently changed which handheld it drives, with no error and no log
    # line. A run against the wrong device does not fail; it produces a
    # perfectly clean result from somewhere else.
    #
    # So: one device, use it. More than one, demand SERIAL. Guessing is the
    # one thing not on offer.
    local attached
    attached=$(adb devices | tr -d '\r' | awk 'NR>1 && $2=="device"{print $1}')
    local n; n=$(printf '%s\n' "$attached" | grep -c .)
    if [ "$n" -eq 1 ]; then
        printf '%s' "$attached"; return 0
    fi
    if [ "$n" -eq 0 ]; then
        echo "no device attached" >&2; return 2
    fi
    {
        echo "$n devices attached and SERIAL is not set; refusing to guess:"
        printf '%s\n' "$attached" | sed 's/^/  /'
        echo "re-run with SERIAL=<serial>, or see devices.sh list"
    } >&2
    return 2
}

device_list() {
    # tr -d '\r' is load-bearing: adb prints CRLF, so without it $2 is
    # "device\r", nothing ever matches, and the list comes back empty rather
    # than wrong -- which reads as "no devices attached". sweep_queue.sh has
    # always stripped it; this did not, and silently listed nothing.
    adb devices | tr -d '\r' | awk 'NR>1 && $2=="device"{print $1}' | while read -r s; do
        if device_env "$s" 2>/dev/null; then
            printf '%-12s %-6s %s\n' "$s" "$DEVICE_LABEL" "$DEVICE_ISO_ROOT"
        else
            printf '%-12s %-6s (not in the table)\n' "$s" "?"
        fi
    done
}

[ "${BASH_SOURCE[0]}" = "$0" ] && { [ "${1:-list}" = list ] && device_list; }
