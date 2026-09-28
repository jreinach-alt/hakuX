# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The USB dialog: soak_title.sh's foreground wait sends ONE KEYCODE_BACK when
# display 0's focused window is a bare window of a vendor settings package
# (com.rp.settings, com.odin.settings), and nothing to anything else. Driven
# against a fake adb that serves `dumpsys input` from a file and, when the
# fixture says BACK closes the dialog, swaps in hakuX on the first BACK.
#
# THE LEGS, and the world in which each one fails:
#   (a) dialog   the 2026-09-27 22:30 PDT Nova: `bebf6bb com.rp.settings`
#                over hakuX; BACK closes it. The route starts, exactly one
#                BACK, the dismissed line, no am start remedy. Fails if no
#                BACK is sent (the mutant), or more than one.
#   (a') stuck   the Thor's dialog, and BACK does not close it: one BACK, not
#                a stream, then the remedy and the abort as before.
#   (b) activity an ACTIVITY of com.odin.settings (`pkg/cls`) holds focus: no
#                BACK, exit 5. Fails if the check reads the owner and not the
#                window's `/`.
#   (c) other    a bare window of another package: no BACK, exit 5. Fails if
#                any bare window gets a BACK.
#   Every leg: never keyevent 96.

echo "== usb dialog: the foreground wait dismisses a vendor settings dialog with one BACK"
UD="$T/usbdialog"; rm -rf "$UD"; mkdir -p "$UD/bin" "$UD/t"
cat > "$UD/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$UD_FAKE/calls"
case "$*" in
    *"dumpsys input"*)
        if [ -f "$UD_FAKE/dialog" ]; then cat "$UD_FAKE/f.cover"; else cat "$UD_FAKE/f.ours"; fi ;;
    *"dumpsys power"*)            printf '  mWakefulness=Awake\r\n  mWakefulnessChanging=false\r\n' ;;
    *"dumpsys window windows"*)   cat "$UD_FAKE/windows" ;;
    *"settings get system performance_mode"*) echo "0 4" ;;
    *"keyevent KEYCODE_BACK"*)    [ -f "$UD_FAKE/backclears" ] && rm -f "$UD_FAKE/dialog" ;;
    *"ps -A -o NAME"*)            printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *) exit 0 ;;
esac
exit 0
EOF
chmod +x "$UD/bin/adb"
HX=com.jreinach.hakux.debug/com.rfandango.haku_x.EmulationActivity
{
    printf 'WINDOW MANAGER WINDOWS (dumpsys window windows)\r\n'
    printf '  Window #1 Window{1a2b3d u0 %s}:\r\n' "$HX"
    printf '    mDisplayId=0 rootTaskId=1 mSession=Session{5d1e 1234:u0a10123} mClient=android.os.BinderProxy@9f0\r\n'
    printf '    mOwnerUid=10123 showForAllUsers=false package=com.jreinach.hakux.debug appop=NONE\r\n'
    printf '    mAttrs={(0,0)(fillxfill) sim={adjust=pan} ty=BASE_APPLICATION fmt=TRANSLUCENT\r\n'
    printf '      fl=LAYOUT_IN_SCREEN HARDWARE_ACCELERATED}\r\n'
    printf '    mViewVisibility=0x0 mHaveFrame=true mObscured=false\r\n'
    printf '    mHasSurface=true isReadyForDisplay()=true mWindowRemovalAllowed=false\r\n'
    printf '\r\n  mCurrentFocus=Window{1a2b3d u0 %s}\r\n' "$HX"
} > "$UD/windows"
# `dumpsys input`, FocusedDisplayId 0, hakuX the focused application on
# display 0, and <window> its focused window. An ANR block follows, with the
# USB dialog in it, so a read past the live block would see a dialog in (a)'s
# control too.
ud_fix() {
    printf 'Input Dispatcher State:\r\n  FocusedDisplayId: 0\r\n  FocusedApplications:\r\n'
    printf "    displayId=0, name='ActivityRecord{8c1f2a u0 %s t41}', dispatchingTimeout=5000ms\r\n" "$HX"
    printf "  FocusedWindows:\r\n    displayId=0, name='%s'\r\n" "$1"
    printf 'Input Dispatcher State at time of last ANR:\r\n  ANR:\r\n    Time: 2026-09-27 11:06:41\r\n'
    printf "  FocusedDisplayId: 0\r\n  FocusedWindows:\r\n    displayId=0, name='bebf6bb com.rp.settings'\r\n"
}
ud_fix "51d0e7 $HX" > "$UD/f.ours"
printf 'press A\nwait 30\n' > "$UD/route"

ud_soak() {    # <soak_title.sh> <cover window name> <backclears 0|1> -> rc; run.log in $UD/run
    local rc
    rm -rf "${UD:?}/run"; mkdir -p "$UD/run"; : > "$UD/calls"; rm -f "$UD/backclears"
    ud_fix "$2" > "$UD/f.cover"; touch "$UD/dialog"
    [ "$3" = 1 ] && touch "$UD/backclears"
    PATH="$UD/bin:$PATH" UD_FAKE="$UD" SERIAL=ee317437 DISPLAY_WAKE_S=0 ADB_RETRY_SLEEP=0 \
        HAKUX_DEVICE_LEASE="$UD/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 HAKUX_WORK="$UD" \
        PAD_DEV=/dev/input/event7 FG_POLL_S=0.2 FG_WAIT_S=1 FG_REMEDY_S=1 \
        PERF_RESULT="$UD/run/perf_regimen.json" ROUTE_FILE="$UD/route" ROUTE_FRAMES="$UD/run/rf" \
        timeout 60 bash "$1" /fake/iso.iso 2 > "$UD/run/run.log" 2>&1; rc=$?
    echo "$rc"
}
ud_backs() { grep -c 'keyevent KEYCODE_BACK' "$UD/calls"; }
ud_played() {  # <soak_title.sh> -> "" or why leg (a) failed
    local rc why=""
    rc=$(ud_soak "$1" "bebf6bb com.rp.settings" 1)
    [ "$rc" = 0 ] || why="$why rc=$rc"
    [ "$(ud_backs)" = 1 ] || why="$why backs=$(ud_backs)"
    grep -qxF 'FOREGROUND: dismissed com.rp.settings dialog (KEYCODE_BACK)' "$UD/run/run.log" || why="$why no-dismissed-line"
    grep -q '^ROUTE started' "$UD/run/run.log" || why="$why route-not-started"
    grep -q 'sendevent /dev/input/event7 1 304 1' "$UD/calls" || why="$why A-not-pressed"
    ! grep -q 'am start --display 0' "$UD/calls" || why="$why remedy-issued"
    ! grep -q 'ROUTE ABORTED\|^not-foreground' "$UD/run/run.log" || why="$why aborted"
    echo "$why"
}
ud_refused() { # <label> <rc> <backs wanted>
    local why=""
    [ "$2" = 5 ] || why="$why rc=$2"
    [ "$(ud_backs)" = "$3" ] || why="$why backs=$(ud_backs)"
    [ "$(grep -c 'am start --display 0' "$UD/calls")" = 1 ] || why="$why remedy-count=$(grep -c 'am start --display 0' "$UD/calls")"
    ! grep -q sendevent "$UD/calls" || why="$why INPUT-SENT"
    ! grep -q 'keyevent 96' "$UD/calls" || why="$why KEYCODE-96"
    grep -q '^soak aborted: not-foreground before' "$UD/run/run.log" || why="$why no-soak-aborted"
    [ -z "$why" ] && ok "$1: exit 5, $3 BACK, one am start remedy, no route input" \
        || bad "$1:$why | $(tr '\n' '|' < "$UD/run/run.log" | tail -c 500)"
}

why=$(ud_played "$TESTING/soak_title.sh")
[ -z "$why" ] && ! grep -q 'keyevent 96' "$UD/calls" \
    && ok "(a) the Nova's com.rp.settings dialog: one BACK, the dismissed line, the route plays, no remedy" \
    || bad "(a) dialog:$why | $(tr '\n' '|' < "$UD/run/run.log" | tail -c 500)"
rc=$(ud_soak "$TESTING/soak_title.sh" "4e5f60 com.odin.settings" 0)
ud_refused "(a') the Thor's dialog survives BACK" "$rc" 1
rc=$(ud_soak "$TESTING/soak_title.sh" "51d0e7 com.odin.settings/com.odin.settings.UsbModeChooserActivity" 1)
ud_refused "(b) an activity of com.odin.settings" "$rc" 0
rc=$(ud_soak "$TESTING/soak_title.sh" "9a8b7c com.example.overlay" 1)
ud_refused "(c) another package's bare window" "$rc" 0

echo "== usb dialog mutant: drop the BACK"
if python3 - "$TESTING" "$UD/t" <<'PY'
import os, shutil, sys
src, dst = sys.argv[1], sys.argv[2]
for d in ("titles", "perf"):
    shutil.rmtree(os.path.join(dst, d), ignore_errors=True)
    shutil.copytree(os.path.join(src, d), os.path.join(dst, d))
shutil.copy(os.path.join(src, "devices.sh"), os.path.join(dst, "devices.sh"))
s = open(os.path.join(src, "soak_title.sh")).read()
old = "            a shell input keyevent KEYCODE_BACK >/dev/null 2>&1\n"
if s.count(old) != 1:
    sys.exit(3)
open(os.path.join(dst, "soak_title.sh"), "w").write(s.replace(old, "", 1))
PY
then
    why=$(ud_played "$UD/t/soak_title.sh")
    case "$why" in *"rc=5"*"backs=0"*) ok "BACK mutant: the dialog stays, the soak aborts, and leg (a) turns red" ;;
        *) bad "BACK mutant: leg (a) did not catch it: [$why]" ;; esac
else
    bad "BACK mutant: its anchor is gone from soak_title.sh -- update the mutant"
fi
