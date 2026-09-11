#!/bin/bash
# One Crimson Skies perf sample. Same input sequence every time, so runs are
# comparable: boot, press A through the intro and the first tutorial prompts,
# settle, then measure with the sticks centred so the plane flies level.
#
#   run_perf.sh <surface_scale> <tag> [measure_s]
set -u
S=ee317437; PKG=com.jreinach.hakux.debug
ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
W=/home/justin/hakux-work/perf
GAME='/storage/E6C6-D7AA/Games/XBox/Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso'

SCALE="${1:?usage: run_perf.sh <surface_scale> <tag> [measure_s]}"
TAG="${2:?}"
MEASURE="${3:-45}"
BOOT=${BOOT_S:-75}
SETTLE=${SETTLE_S:-12}

adb -s $S shell am force-stop $PKG
command sleep 2

# surface_scale lives in the app's prefs, which a debuggable build lets us
# write directly. Read-modify-write so nothing else in the file is lost.
adb -s $S exec-out run-as $PKG cat shared_prefs/x1box_prefs.xml > $W/prefs-cur.xml
python3 - "$SCALE" <<'PY'
import re, sys
p = "/home/justin/hakux-work/perf/prefs-cur.xml"
s = open(p).read()
scale = int(sys.argv[1])
s = re.sub(r'\s*<int name="surface_scale".*?/>\n', '\n', s)
s = s.replace('</map>', f'    <int name="surface_scale" value="{scale}" />\n</map>')
open("/home/justin/hakux-work/perf/prefs-new.xml", "w").write(s)
PY
adb -s $S push -q $W/prefs-new.xml /data/local/tmp/p.xml >/dev/null 2>&1 \
    || adb -s $S push $W/prefs-new.xml /data/local/tmp/p.xml >/dev/null
adb -s $S shell "run-as $PKG cp /data/local/tmp/p.xml shared_prefs/x1box_prefs.xml"
adb -s $S shell rm -f /data/local/tmp/p.xml

adb -s $S shell input keyevent KEYCODE_WAKEUP
adb -s $S logcat -c
adb -s $S shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$GAME'" >/dev/null 2>&1

echo "[$TAG] booting (${BOOT}s)"; command sleep $BOOT
adb -s $S shell 'ps -A -o NAME' | tr -d '\r' | grep -qx "$PKG:xemu" \
    || { echo "[$TAG] emulator not running, aborting"; exit 1; }

echo "[$TAG] advancing through intro"
bash $W/pad.sh mash 12 1.5 >/dev/null 2>&1
command sleep $SETTLE

adb -s $S exec-out screencap -p > $W/${TAG}-start.png 2>/dev/null
echo "[$TAG] measuring ${MEASURE}s"
adb -s $S logcat -c
bash $W/loadsample.sh "$MEASURE" 2 "$W/${TAG}-load.txt" &
LOADPID=$!
command sleep $MEASURE
wait $LOADPID 2>/dev/null
adb -s $S logcat -d -s hakuX-perf hakuX-phase xemu-gpu xemu-work hakuX-cpu > $W/${TAG}.log 2>/dev/null
adb -s $S exec-out screencap -p > $W/${TAG}-end.png 2>/dev/null
adb -s $S shell am force-stop $PKG

echo "[$TAG] scale=$SCALE  $(grep -c 'hakuX-perf' $W/${TAG}.log) perf lines"
grep "hakuX-perf" $W/${TAG}.log | tail -3
