#!/bin/bash
# Identify a title's frame-rate target without reaching gameplay.
#
# A title that asks for 60 produces some frames under one refresh period even
# when it cannot sustain them; one that asks for 30 sits at exactly two
# periods and its minimum never goes below. So the minimum flip interval over
# a boot-and-idle window names the target, and needs no input sequence.
set -u
S=ee317437; PKG=com.jreinach.hakux.debug
ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
GAME="${1:?usage: fps_target.sh <device iso path> [seconds]}"
SECS="${2:-55}"

adb -s $S shell am force-stop $PKG >/dev/null 2>&1; command sleep 2
adb -s $S shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
adb -s $S logcat -c 2>/dev/null
adb -s $S shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$GAME'" >/dev/null 2>&1
command sleep 70
# a couple of Start presses in case the title sits on a "press start" screen
bash /home/justin/hakux-work/perf/pad.sh press START 80 >/dev/null 2>&1
command sleep "$SECS"
OUT=$(adb -s $S logcat -d -s hakuX-perf 2>/dev/null | grep -oE "G:[0-9.]+\([0-9.]+-[0-9.]+\)")
adb -s $S shell am force-stop $PKG >/dev/null 2>&1
echo "$OUT" | python3 -c "
import sys, re
mins=[]; avgs=[]
for l in sys.stdin:
    m=re.match(r'G:([\d.]+)\(([\d.]+)-([\d.]+)\)', l.strip())
    if m: avgs.append(float(m.group(1))); mins.append(float(m.group(2)))
if not mins:
    print('   no frames presented'); sys.exit()
lo=min(mins)
verdict='targets 60' if lo<=17.5 else ('targets 30' if lo>=26 else 'unclear')
print(f'   samples {len(mins)}  best single frame {lo:.1f} ms  typical {sorted(avgs)[len(avgs)//2]:.1f} ms  -> {verdict}')
"
