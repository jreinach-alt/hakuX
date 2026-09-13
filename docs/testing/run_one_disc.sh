#!/usr/bin/env bash
#
# Run one disc to completion and leave the results in the guest's disk image.
#
#   run_one_disc.sh <iso> [timeout-seconds]
#
# run_disc.sh pulls the 1.5GB image and extracts after every run, which is
# right when you want one suite's results now and wrong when you are about to
# run twenty more: twenty-three pulls is half an hour of the night spent moving
# the same image. This runs the disc and stops there, so a caller can run a
# whole group and pull once. It is the same split sweep_queue.sh uses for the
# solo arm.
#
# The two-stage wait is not a detail. `am start` returns before the :xemu
# process exists, and a transient adb failure returns no output at all -- both
# look identical to "the run finished" if a single ps call decides. That
# mistake force-stopped a healthy 1,300-test group after eleven seconds and
# left a progress log that simply stopped, which reads as a guest crash.
set -u

ISO="${1:?usage: run_one_disc.sh <iso> [timeout-s]}"
TIMEOUT="${2:-900}"

SERIAL="${SERIAL:-$(adb devices | tr -d '\r' | awk 'NR>1 && $2=="device"{print $1; exit}')}"
PKG="${PKG:-com.jreinach.hakux.debug}"
ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
DEVISO="${DEVISO:-/storage/E6C6-D7AA/Games/XBox/fast.iso}"
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"

a() { timeout "${ADB_TIMEOUT:-120}" adb -s "$SERIAL" "$@"; }
alive() { a shell 'ps -A -o NAME' | tr -d '\r' | grep -qx "$PKG:xemu"; }

# The caller owns the device for the whole group, so this does not put the
# panel out or drop the lease on the way out -- only stop the emulator, so the
# next disc starts from a clean process.
trap 'a shell am force-stop "$PKG" >/dev/null 2>&1' EXIT INT TERM

a push "$ISO" "$DEVISO" >/dev/null 2>&1 || { echo "push failed"; exit 1; }
a shell am force-stop "$PKG" >/dev/null 2>&1
a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
a shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$DEVISO'" \
    >/dev/null 2>&1

s=0
appeared=0
while [ "$s" -lt "${APPEAR_TIMEOUT:-90}" ]; do
    sleep 1; s=$((s+1)); touch "$LEASE"
    if alive; then appeared=1; break; fi
done
if [ "$appeared" = 0 ]; then
    echo "the emulator never started: no $PKG:xemu within ${APPEAR_TIMEOUT:-90}s"
    exit 1
fi

misses=0
while [ "$s" -lt "$TIMEOUT" ]; do
    sleep 1; s=$((s+1)); touch "$LEASE"
    if alive; then misses=0; continue; fi
    misses=$((misses+1))
    [ "$misses" -ge "${MISSES_TO_EXIT:-3}" ] && break
done

if [ "$s" -ge "$TIMEOUT" ]; then
    echo "TIMEOUT after ${s}s; the guest never exited"
    exit 2
fi
echo "ran ${s}s"
