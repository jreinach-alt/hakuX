#!/usr/bin/env bash
#
# Launch a title (or a pgraph test disc) and report whether it renders or hangs.
#
#   docs/testing/boot-test.sh <label> [iso-path-on-device]
#
# Environment:
#   SERIAL  adb device serial            (default: first attached device)
#   PKG     package to launch            (default: com.jreinach.hakux.debug)
#   OUTDIR  where screenshots/logs land  (default: ./boot-test-out)
#
# Why this exists rather than "just launch it": several device-level details
# silently invalidate a run and make a healthy build look broken. They are
# handled here so a result means what it says. See AGENTS.md.
set -u

LABEL="${1:-boot}"
ISO="${2:-}"
SERIAL="${SERIAL:-$(adb devices | awk 'NR==2{print $1}')}"
PKG="${PKG:-com.jreinach.hakux.debug}"
ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
OUTDIR="${OUTDIR:-./boot-test-out}"
mkdir -p "$OUTDIR"

a() { adb -s "$SERIAL" "$@"; }

a shell am force-stop "$PKG" >/dev/null 2>&1
# A sleeping screen minimises the app about two seconds after launch. The run
# then looks like a crash and is not one.
a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
a logcat -b all -c >/dev/null 2>&1
sleep 1

if [ -n "$ISO" ]; then
    # The device-side shell re-parses adb arguments, and title filenames
    # routinely contain spaces and parentheses. Quote for that shell too.
    a shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$ISO'" >/dev/null 2>&1
else
    a shell "am start -n $ACT" >/dev/null 2>&1
fi

sleep 25
a exec-out screencap -p > "$OUTDIR/boot_$LABEL.png" 2>/dev/null
a logcat -b all -d > "$OUTDIR/boot_$LABEL.log" 2>/dev/null

# pidof does not match "<pkg>:xemu" on every device; ps does.
ALIVE=$(a shell 'ps -A -o NAME' | tr -d '\r' | grep -cx "$PKG:xemu")
NOFB=$(grep -ac "refresh no nv2a fb" "$OUTDIR/boot_$LABEL.log")
CRASH=$(grep -ac "Caught signal" "$OUTDIR/boot_$LABEL.log")
FATAL=$(grep -a "hakuX-stderr" "$OUTDIR/boot_$LABEL.log" |
        grep -aiE "assertion|unimplemented|out of range" | tail -1)

echo "[$LABEL] alive=$ALIVE crashes=$CRASH no-framebuffer-frames=$NOFB"
[ -n "$FATAL" ] && echo "[$LABEL] ${FATAL#*hakuX-stderr: }"

if [ "$CRASH" -gt 0 ]; then
    echo "[$LABEL] RESULT: CRASHED"; exit 1
elif [ "$ALIVE" != "1" ]; then
    echo "[$LABEL] RESULT: EXITED"; exit 2
elif [ "$NOFB" -ge 5 ]; then
    # Running, but the display has no nv2a framebuffer to show — it is
    # presenting an uninitialised surface, which looks like video static.
    echo "[$LABEL] RESULT: HUNG (no framebuffer)"; exit 3
fi
echo "[$LABEL] RESULT: RENDERING"
