#!/usr/bin/env bash
# Capture one hakuX launch attempt into a timestamped directory.
#
#   ./tools/hakux-capture.sh esde          # launch from ES-DE
#   ./tools/hakux-capture.sh manual        # launch from the hakuX library
#   ./tools/hakux-capture.sh esde 60       # capture for 60s instead of 45
#
# Capturing runs for a fixed number of seconds with a visible countdown, so
# there is nothing to press and nothing that can exit early.  Start it, then
# launch the game while the countdown runs.

set -uo pipefail

LABEL="${1:-run}"
SECS="${2:-45}"
: "${ANDROID_SERIAL:=ee317437}"
export ANDROID_SERIAL

PKG="com.rfandango.haku_x"
OUT="hakux-${LABEL}-$(date +%Y%m%d-%H%M%S)"

# The first adb call in a shell has to start the daemon and fails while that
# happens, which would look like a missing device.
adb start-server >/dev/null 2>&1

# This handset is often attached twice, over USB and over wireless TLS, so
# match the serial exactly rather than assuming a single transport.
ready=0
for _ in 1 2 3 4 5 6; do
  if adb devices | awk -v s="$ANDROID_SERIAL" '$1 == s && $2 == "device" { ok = 1 } END { exit !ok }'; then
    ready=1
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  echo "No device ready for serial '$ANDROID_SERIAL'. Devices seen:" >&2
  adb devices -l >&2
  echo >&2
  echo "If the serial is listed but shows 'offline' or 'unauthorized', accept the" >&2
  echo "USB debugging prompt on the handheld, or run: adb disconnect" >&2
  exit 1
fi

mkdir -p "$OUT"

# Record what is actually installed, so a stale build cannot mislead us.
{
  echo "label:  $LABEL"
  echo "serial: $ANDROID_SERIAL"
  echo "date:   $(date -Is)"
  echo
  adb shell getprop ro.product.model
  adb shell getprop ro.build.version.release
  echo
  adb shell dumpsys package "$PKG" | grep -E "versionName|versionCode|lastUpdateTime" | head
} > "$OUT/env.txt" 2>&1

adb logcat -c 2>/dev/null

# hakuX-nop is deliberately absent: it is a per-interrupt trace that drowns
# everything else.  '*:S' silences every tag not listed.
adb logcat -v threadtime \
  hakuX:V hakuX-crash:V hakuX-xiso:V hakuX-dashboard:V \
  xemu:V nv2a:V SDL:V \
  ActivityTaskManager:V ActivityManager:V WindowManager:V \
  AndroidRuntime:V DEBUG:V libc:V tombstoned:V \
  '*:S' </dev/null > "$OUT/logcat.log" 2>&1 &
CAP_PID=$!
trap 'kill "$CAP_PID" 2>/dev/null' EXIT INT TERM

echo
echo "  Capturing for ${SECS}s into $OUT/"
echo "  >>> LAUNCH THE GAME NOW ($LABEL) <<<"
echo
for ((i = SECS; i > 0; i--)); do
  printf "\r  %3ds remaining ... " "$i"
  sleep 1
done
printf "\r                                   \r"

kill "$CAP_PID" 2>/dev/null
wait "$CAP_PID" 2>/dev/null
trap - EXIT INT TERM

# The app keeps its own rotating logs; grab them before anything relaunches.
adb shell run-as "$PKG" cat files/current.log  > "$OUT/app-current.log"  2>/dev/null
adb shell run-as "$PKG" cat files/previous.log > "$OUT/app-previous.log" 2>/dev/null
find "$OUT" -type f -empty -delete

lines=$(wc -l < "$OUT/logcat.log" 2>/dev/null || echo 0)
hakux=$(grep -c "hakuX" "$OUT/logcat.log" 2>/dev/null || echo 0)

echo "  Captured $lines lines, $hakux mentioning hakuX."
if [ "$hakux" -lt 5 ]; then
  echo
  echo "  WARNING: almost nothing from hakuX was captured.  The launch probably"
  echo "  happened outside the capture window - rerun and launch as soon as the"
  echo "  countdown starts, or allow more time:  $0 $LABEL 90"
fi
echo
ls -lh "$OUT"
echo
echo "  Attach the files in $OUT/"
