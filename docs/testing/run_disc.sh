#!/usr/bin/env bash
#
# Run one test disc on the device and extract its results.
#
#   run_disc.sh <iso> <guest-dir> <results-dir> [timeout-seconds]
#
# e.g. run_disc.sh iso-blank3.iso blank3 ./res_blank3
#
# This exists because the same fifteen lines were being retyped for every
# measurement, and two of the details are not obvious:
#
#   * The hard disk image is ~1.5GB and it is pulled after every run. Pulling
#     each one to a *new* filename grew the WSL ext4.vhdx by 12GB in an
#     afternoon, filled the host's C: drive, and killed the VM mid-session --
#     a dynamically expanding VHDX never returns deleted blocks to the host.
#     So: one fixed path, reused, deleted as soon as the results are out.
#
#   * Stopping the emulator is only half of releasing the device. ES-DE is the
#     home app here and its window carries FLAG_KEEP_SCREEN_ON, so the moment
#     the emulator exits the display is pinned on and the 30s timeout never
#     fires -- the handheld then sits at -107mA instead of charging.
#     KEYCODE_SLEEP overrides the flag where the timeout cannot.
set -u

ISO="${1:?usage: run_disc.sh <iso> <guest-dir> <results-dir> [timeout-s]}"
GUEST_DIR="${2:?}"
RESULTS="${3:?}"
TIMEOUT="${4:-900}"

SERIAL="${SERIAL:-$(adb devices | awk 'NR==2{print $1}')}"
PKG="${PKG:-com.jreinach.hakux.debug}"
ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
DEVISO="${DEVISO:-/storage/E6C6-D7AA/Games/XBox/fast.iso}"
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"
HDD="${HAKUX_HDD_SCRATCH:-$HOME/hakux-work/hdd.img}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

a() { adb -s "$SERIAL" "$@"; }
release() {
    a shell am force-stop "$PKG" >/dev/null 2>&1
    a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    rm -f "$LEASE"
}
trap release EXIT INT TERM

mkdir -p "$(dirname "$HDD")"
a push "$ISO" "$DEVISO" >/dev/null 2>&1 || { echo "push failed"; exit 1; }
a shell am force-stop "$PKG" >/dev/null 2>&1
a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
a shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$DEVISO'" >/dev/null 2>&1

s=0
while [ "$s" -lt "$TIMEOUT" ]; do
    sleep 1; s=$((s+1))
    touch "$LEASE"          # hold off the Stop hook while we legitimately run
    a shell 'ps -A -o NAME' | tr -d '\r' | grep -qx "$PKG:xemu" || break
done
if [ "$s" -ge "$TIMEOUT" ]; then
    echo "TIMEOUT after ${s}s — the guest never exited"
    exit 1
fi
echo "ran ${s}s"

a pull /storage/emulated/0/Android/data/"$PKG"/files/x1box/hdd.img "$HDD" >/dev/null 2>&1 \
    || { echo "pull failed"; exit 1; }
rm -rf "$RESULTS"
python3 "$HERE/extract_results.py" "$HDD" -d "$GUEST_DIR" -o "$RESULTS" | tail -1
# The image is the whole point of the fixed path: take it back off the disk
# before the next run needs the room.
rm -f "$HDD"
echo "results: $RESULTS ($(ls "$RESULTS" 2>/dev/null | wc -l) files)"
