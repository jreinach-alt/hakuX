#!/usr/bin/env bash
# Capture a complete, filtered log for one hakuX launch attempt.
#
#   ./hakux-capture.sh esde      # launch the game from ES-DE
#   ./hakux-capture.sh manual    # launch the same game from the hakuX library
#
# Produces a timestamped directory holding the system log for the launch plus
# the app's own rolling logs.  Attach the whole directory, or logcat.log alone.

set -uo pipefail

LABEL="${1:-run}"
: "${ANDROID_SERIAL:=ee317437}"
export ANDROID_SERIAL

PKG="com.rfandango.haku_x"
OUT="hakux-${LABEL}-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

# Start the server explicitly.  The first adb call in a shell has to bring the
# daemon up and fails while that happens, which would look like a missing
# device.
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

# Record what we are actually testing, so a stale install cannot mislead us.
{
  echo "label:   $LABEL"
  echo "serial:  $ANDROID_SERIAL"
  echo "date:    $(date -Is)"
  echo
  adb shell getprop ro.product.model
  adb shell getprop ro.build.version.release
  echo
  adb shell dumpsys package "$PKG" | grep -E "versionName|versionCode|firstInstallTime|lastUpdateTime|flags=" | head
} > "$OUT/env.txt" 2>&1

adb logcat -c 2>/dev/null

# hakuX-nop is deliberately absent: it is a per-interrupt trace that drowns
# everything else.  '*:S' silences every tag not listed.
adb logcat -v threadtime \
  hakuX:V hakuX-crash:V hakuX-xiso:V hakuX-dashboard:V \
  xemu:V nv2a:V SDL:V \
  ActivityTaskManager:V ActivityManager:V WindowManager:V \
  AndroidRuntime:V DEBUG:V libc:V tombstoned:V \
  '*:S' > "$OUT/logcat.log" 2>&1 &
CAP_PID=$!

sleep 1
echo
echo "  Capturing.  Now launch the game via: $LABEL"
echo "  Wait for it to fail (or for the game to come up), then come back here."
echo
read -r -p "  Press ENTER to stop capturing... " _

kill "$CAP_PID" 2>/dev/null
wait "$CAP_PID" 2>/dev/null

# The app keeps its own rotating logs; grab them before anything relaunches.
adb shell run-as "$PKG" cat files/current.log  > "$OUT/app-current.log"  2>/dev/null
adb shell run-as "$PKG" cat files/previous.log > "$OUT/app-previous.log" 2>/dev/null
find "$OUT" -type f -empty -delete

echo
echo "  Done:"
ls -lh "$OUT"
echo
echo "  Attach the files in $OUT/"
