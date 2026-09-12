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

# Every adb call gets a deadline. Without one this script finished a run,
# extracted its results, and then sat for seven hours wedged in the exit trap
# because adb stopped answering -- the work was done and the job still looked
# alive. A device that goes unresponsive must not be able to hold a slot.
a() { timeout "${ADB_TIMEOUT:-120}" adb -s "$SERIAL" "$@"; }

# Optional logcat capture, off unless CAPTURE_LOG names a file.
#
# It has to STREAM, not dump at the end. The core's own fprintf(stderr) never
# reaches logcat on Android, so anything we want to see from pgraph is routed
# through __android_log_print -- and the interesting lines are the startup set,
# emitted in the first second. A run can take the full 1800s plus a ~1.5GB
# pull, and the ring has long since turned over by then: a closing `logcat -d`
# reliably returns everything except the lines we came for. That eviction is
# already on record in galleon-flashing-deck.md.
#
# So the reader starts BEFORE `am start` and is killed by PID in release().
# Killing by PID matters: a pattern kill here would match this script's own
# command line.
CAPTURE_LOG="${CAPTURE_LOG:-}"
LOGCAT_SPEC="${LOGCAT_SPEC:-hakuX-unhandled:W hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-pages:I hakuX:W VALIDATION:W ValidationLayer:W vulkan:W VulkanLoader:W *:S}"
LOGCAT_PID=""

release() {
    [ -n "$LOGCAT_PID" ] && kill "$LOGCAT_PID" 2>/dev/null
    a shell am force-stop "$PKG" >/dev/null 2>&1
    a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    rm -f "$LEASE"
}
trap release EXIT INT TERM

mkdir -p "$(dirname "$HDD")"
a push "$ISO" "$DEVISO" >/dev/null 2>&1 || { echo "push failed"; exit 1; }
a shell am force-stop "$PKG" >/dev/null 2>&1
a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1

if [ -n "$CAPTURE_LOG" ]; then
    a logcat -c >/dev/null 2>&1
    # Unwrapped by design: `a` imposes a 120s deadline, and this outlives the run.
    # shellcheck disable=SC2086
    adb -s "$SERIAL" logcat -v time $LOGCAT_SPEC >"$CAPTURE_LOG" 2>/dev/null &
    LOGCAT_PID=$!
fi

a shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$DEVISO'" >/dev/null 2>&1

# Wait for the guest in two stages, because the obvious single loop is wrong
# in both directions.
#
# It watched for the process to *disappear* from the first second, with one ps
# call deciding. But `am start` returns before the :xemu process exists, so an
# early poll sees nothing and concludes the run is over; and any transient adb
# failure returns no output at all, which reads the same way. That cost a
# 1,300-test group: the loop declared the emulator gone after eleven seconds
# while it was mid-test-32, the harness force-stopped a healthy run, and
# twenty-two of the twenty-three suites on the disc never ran. The evidence was
# a progress log that simply stopped, which looks exactly like a guest crash.
#
# So: wait for it to appear, then require several consecutive misses before
# believing it has gone.
alive() { a shell 'ps -A -o NAME' | tr -d '\r' | grep -qx "$PKG:xemu"; }

s=0
appeared=0
while [ "$s" -lt "${APPEAR_TIMEOUT:-90}" ]; do
    sleep 1; s=$((s+1))
    touch "$LEASE"
    if alive; then appeared=1; break; fi
done
if [ "$appeared" = 0 ]; then
    echo "the emulator never started: no $PKG:xemu within ${APPEAR_TIMEOUT:-90}s"
    exit 1
fi

misses=0
while [ "$s" -lt "$TIMEOUT" ]; do
    sleep 1; s=$((s+1))
    touch "$LEASE"          # hold off the Stop hook while we legitimately run
    if alive; then misses=0; continue; fi
    misses=$((misses+1))
    [ "$misses" -ge "${MISSES_TO_EXIT:-3}" ] && break
done
TIMED_OUT=0
if [ "$s" -ge "$TIMEOUT" ]; then
    # Extract anyway. A run that overruns has usually written most of its
    # captures, and the progress log names the test it stopped on -- which is
    # the single most useful thing you can have about a hang. Exiting here
    # threw all of that away and left "0 files", which reads as "the guest
    # wrote nothing" when it means "we never looked". Two hangs were
    # misdiagnosed that way before this was fixed.
    echo "TIMEOUT after ${s}s — the guest never exited; extracting anyway"
    TIMED_OUT=1
    a shell am force-stop "$PKG" >/dev/null 2>&1
    sleep 2
else
    echo "ran ${s}s"
fi

# The image is ~1.5GB; allow generously for it but never indefinitely.
ADB_TIMEOUT="${PULL_TIMEOUT:-600}" \
    a pull /storage/emulated/0/Android/data/"$PKG"/files/x1box/hdd.img "$HDD" \
    >/dev/null 2>&1 || { echo "pull failed or timed out"; exit 1; }
# A pull can exit 0 and still leave nothing behind -- two runs sharing this one
# fixed path is enough to do it, and the only symptom was a FileNotFoundError
# from the extractor thirty lines further down, which reads as "the extractor is
# broken". Check for the file instead of trusting the exit status.
[ -s "$HDD" ] || { echo "pull reported success but $HDD is missing or empty"; exit 1; }
rm -rf "$RESULTS"
python3 "$HERE/extract_results.py" "$HDD" -d "$GUEST_DIR" -o "$RESULTS" | tail -1
# The image is the whole point of the fixed path: take it back off the disk
# before the next run needs the room.
rm -f "$HDD"
echo "results: $RESULTS ($(ls "$RESULTS" 2>/dev/null | wc -l) files)"
if [ "$TIMED_OUT" = 1 ]; then
    echo "  ^ PARTIAL: the guest did not exit. The tail of"
    echo "    $RESULTS/pgraph_progress_log.txt names the test it stopped on."
    exit 1
fi
