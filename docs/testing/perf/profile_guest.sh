#!/bin/bash
# Profile the emulator during Crimson Skies gameplay with simpleperf.
#
# The critical-path measurement says the guest CPU thread bounds the frame, so
# the question is what that thread is actually doing: executing translated
# guest code, or paying emulator overhead around it. A sampling profile answers
# that without instrumenting anything.
set -u
S=ee317437; PKG=com.jreinach.hakux.debug
ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
W=/home/justin/hakux-work/perf
GAME="${GAME:-/storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso}"
DUR="${1:-20}"
TAG="${2:-perf}"
OUT="${OUT:-$W}"
mkdir -p "$OUT"
# Record the prefs the profile ran under; this script writes none of them.
adb -s $S exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > "$OUT/${TAG}-prefs.xml"
grep -q 'name="validation_layers" value="true"' "$OUT/${TAG}-prefs.xml" \
    && { echo "validation_layers is on in the app prefs; refusing to profile"; exit 1; }

adb -s $S shell am force-stop $PKG; command sleep 2
adb -s $S shell input keyevent KEYCODE_WAKEUP
adb -s $S shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$GAME'" >/dev/null 2>&1
echo "booting"; command sleep ${BOOT_S:-75}
adb -s $S shell 'ps -A -o NAME' | tr -d '\r' | grep -qx "$PKG:xemu" || { echo "not running"; exit 1; }
echo "into gameplay"
bash $W/pad.sh ${MASH:-mash 12 1.5} >/dev/null 2>&1
command sleep ${SETTLE_S:-12}

PID=$(adb -s $S shell "pidof $PKG:xemu" | tr -d '\r' | awk '{print $1}')
echo "profiling pid $PID for ${DUR}s"
# A user build refuses perf_event_open on a bare pid even with perf_harden
# off. --app re-enters the app's own context, which a debuggable package is
# allowed to profile, and cpu-clock is a software event so no hardware counter
# is needed. Output has to land somewhere the app can write.
adb -s $S shell "run-as $PKG rm -f files/perf.data"
adb -s $S shell "simpleperf record --app $PKG -e cpu-clock --call-graph dwarf,8192 --duration $DUR \
  -f 1000 -o /data/local/tmp/perf.data" 2>&1 | tail -4
adb -s $S pull /data/local/tmp/perf.data "$OUT/${TAG}.data" 2>&1 | tail -1
adb -s $S shell am force-stop $PKG
echo "done"
