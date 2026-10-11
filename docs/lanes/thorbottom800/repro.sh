#!/bin/bash
# Launch a title on one Thor display for a few seconds, screenshot that
# display, keep the SDL/hakuX sizing lines from logcat, then stop the app.
#   repro.sh <pkg> <display id> <out prefix> [seconds]
# Thor: display 0 = top (1920x1080, dead), display 4 = bottom (1240x1080).
set -u
S=bdc158a5
PKG=$1
DISP=$2
OUT=$3
SECS=${4:-25}
ISO=/storage/388C-68F7/ROMS/xbox/4D530005-Amped_Freestyle_Snowboarding.xiso.iso
a() { adb -s "$S" "$@"; }

# Physical ids, read 2026-10-04 from dumpsys SurfaceFlinger --displays.
case $DISP in
  0) phys=4630946441858561667 ;;
  4) phys=4630946482288158084 ;;
esac

a shell am force-stop "$PKG"
a shell input keyevent KEYCODE_WAKEUP
sleep 1
a logcat -b all -c
a shell "am start --display $DISP -a android.intent.action.VIEW -n $PKG/com.rfandango.haku_x.LauncherActivity --es rom_path '$ISO'"
sleep "$SECS"
a shell "screencap -d $phys -p /sdcard/tb800.png"
a pull /sdcard/tb800.png "$OUT.png" >/dev/null
a shell 'dumpsys activity activities' | grep -E 'ResumedActivity|displayId=' > "$OUT.activities.txt"
a shell "dumpsys window windows" | grep -E 'Window #|mFrame=|mDisplayId|mSurface|Requested w=|mDisplayFrames|containing=|frame=' > "$OUT.windows.txt"
a logcat -d -b main -s SDL:V hakuX:V hakuX-lane:V hakuX-stderr:V > "$OUT.logcat.txt"
a shell am force-stop "$PKG"
echo "done $OUT"
