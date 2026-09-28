# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The USB dialog: soak_title.sh's foreground wait sends ONE KEYCODE_BACK when
# display 0's focused window is a bare window of a vendor settings package
# (com.rp.settings, com.odin.settings), and nothing to anything else. Driven
# against a fake adb that serves `dumpsys input` from a file and, when the
# fixture says BACK closes the dialog, swaps in hakuX on the first BACK. A
# BACK with no dialog up reaches hakuX and toggles its pause menu, served as
# the PauseMenuOverlay line of `dumpsys activity top`.
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
#   (d) race     someone else closes the dialog between our read and our
#                BACK (the host timer, a person), so our BACK reaches hakuX
#                and opens its pause menu: the pause read sees the overlay
#                shown, ONE more BACK resumes it, and the route plays
#                unpaused. Fails if the route starts with hakuX paused (the
#                pause-check mutant).
#   (e) stuck    as (d), but the resume BACK leaves the menu shown: exit 5,
#                no route input.
#   (f) blind    the dialog closes, and `dumpsys activity top` shows no
#                PauseMenuOverlay line: exit 5, no route input. Fails if an
#                unreadable pause state is taken as "not paused".
#   Every leg: never keyevent 96.

echo "== usb dialog: the foreground wait dismisses a vendor settings dialog with one BACK"
UD="$T/usbdialog"; rm -rf "$UD"; mkdir -p "$UD/bin" "$UD/t"
cat > "$UD/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$UD_FAKE/calls"
case "$*" in
    *"dumpsys input"*)
        if [ -f "$UD_FAKE/dialog" ]; then
            cat "$UD_FAKE/f.cover"
            # usb_dialog's raw re-read (no device-side grep): another actor
            # closes the dialog right after it, before our BACK lands.
            case "$*" in *"dumpsys input |"*) ;; *) [ -f "$UD_FAKE/othercloses" ] && rm -f "$UD_FAKE/dialog" ;; esac
        else cat "$UD_FAKE/f.ours"; fi ;;
    *"dumpsys activity top"*)
        [ -f "$UD_FAKE/blind" ] && exit 0
        v=G; [ -f "$UD_FAKE/paused" ] && v=V
        printf '  View Hierarchy:\r\n    com.rfandango.haku_x.PauseMenuOverlay{7f3a21 %s.E...... ........ 0,0-1920,1080}\r\n' "$v" ;;
    *"dumpsys power"*)            printf '  mWakefulness=Awake\r\n  mWakefulnessChanging=false\r\n' ;;
    *"dumpsys window windows"*)   cat "$UD_FAKE/windows" ;;
    *"settings get system performance_mode"*) echo "0 4" ;;
    *"keyevent KEYCODE_BACK"*)
        if [ -f "$UD_FAKE/dialog" ]; then [ -f "$UD_FAKE/backclears" ] && rm -f "$UD_FAKE/dialog"
        elif [ -f "$UD_FAKE/paused" ]; then [ -f "$UD_FAKE/stuckpause" ] || rm -f "$UD_FAKE/paused"
        else touch "$UD_FAKE/paused"; fi ;;
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

ud_soak() {    # <soak_title.sh> <cover window name> <backclears 0|1> [fake flags...] -> rc; run.log in $UD/run
    local rc f
    rm -rf "${UD:?}/run"; mkdir -p "$UD/run"; : > "$UD/calls"
    rm -f "$UD/backclears" "$UD/othercloses" "$UD/paused" "$UD/stuckpause" "$UD/blind"
    ud_fix "$2" > "$UD/f.cover"; touch "$UD/dialog"
    [ "$3" = 1 ] && touch "$UD/backclears"
    for f in "${@:4}"; do touch "$UD/$f"; done
    PATH="$UD/bin:$PATH" UD_FAKE="$UD" SERIAL=ee317437 DISPLAY_WAKE_S=0 ADB_RETRY_SLEEP=0 \
        HAKUX_DEVICE_LEASE="$UD/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 HAKUX_WORK="$UD" \
        PAD_DEV=/dev/input/event7 FG_POLL_S=0.2 FG_WAIT_S=1 FG_REMEDY_S=1 \
        PERF_RESULT="$UD/run/perf_regimen.json" ROUTE_FILE="$UD/route" ROUTE_FRAMES="$UD/run/rf" \
        timeout 60 bash "$1" /fake/iso.iso 2 > "$UD/run/run.log" 2>&1; rc=$?
    echo "$rc"
}
ud_backs() { grep -c 'keyevent KEYCODE_BACK' "$UD/calls"; }
ud_played() {  # <soak_title.sh> [backs wanted] [fake flags...] -> "" or why leg (a)/(d) failed
    local rc why=""
    rc=$(ud_soak "$1" "bebf6bb com.rp.settings" 1 "${@:3}")
    [ "$rc" = 0 ] || why="$why rc=$rc"
    [ "$(ud_backs)" = "${2:-1}" ] || why="$why backs=$(ud_backs)"
    [ ! -f "$UD/paused" ] || why="$why PAUSED"
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
why=$(ud_played "$TESTING/soak_title.sh" 2 othercloses)
grep -qxF 'FOREGROUND: hakuX resumed' "$UD/run/run.log" || why="$why no-resumed-line"
[ -z "$why" ] && ! grep -q 'keyevent 96' "$UD/calls" \
    && ok "(d) another actor closes the dialog first: our BACK pauses hakuX, one more BACK resumes it, the route plays unpaused" \
    || bad "(d) race:$why | $(tr '\n' '|' < "$UD/run/run.log" | tail -c 500)"
ud_paused_abort() {  # <label> <rc> <backs wanted>
    local why=""
    [ "$2" = 5 ] || why="$why rc=$2"
    [ "$(ud_backs)" = "$3" ] || why="$why backs=$(ud_backs)"
    ! grep -q sendevent "$UD/calls" || why="$why INPUT-SENT"
    grep -qxF 'ROUTE ABORTED: not foreground (hakuX-paused)' "$UD/run/run.log" || why="$why no-paused-abort"
    [ -z "$why" ] && ok "$1: exit 5, $3 BACK, no route input" \
        || bad "$1:$why | $(tr '\n' '|' < "$UD/run/run.log" | tail -c 500)"
}
rc=$(ud_soak "$TESTING/soak_title.sh" "bebf6bb com.rp.settings" 1 othercloses stuckpause)
ud_paused_abort "(e) the pause menu survives the resume BACK" "$rc" 2
rc=$(ud_soak "$TESTING/soak_title.sh" "bebf6bb com.rp.settings" 1 blind)
ud_paused_abort "(f) no PauseMenuOverlay line after the BACK" "$rc" 1

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

echo "== usb dialog mutant: skip the pause check"
if python3 - "$TESTING" "$UD/t" <<'PY'
import os, shutil, sys
src, dst = sys.argv[1], sys.argv[2]
for d in ("titles", "perf"):
    shutil.rmtree(os.path.join(dst, d), ignore_errors=True)
    shutil.copytree(os.path.join(src, d), os.path.join(dst, d))
shutil.copy(os.path.join(src, "devices.sh"), os.path.join(dst, "devices.sh"))
s = open(os.path.join(src, "soak_title.sh")).read()
old = "            fg_unpaused && return 0\n"
if s.count(old) != 1:
    sys.exit(3)
open(os.path.join(dst, "soak_title.sh"), "w").write(s.replace(old, "            return 0\n", 1))
PY
then
    why=$(ud_played "$UD/t/soak_title.sh" 2 othercloses)
    case "$why" in *"backs=1"*"PAUSED"*) ok "pause-check mutant: the route plays with hakuX paused, and leg (d) turns red" ;;
        *) bad "pause-check mutant: leg (d) did not catch it: [$why]" ;; esac
else
    bad "pause-check mutant: its anchor is gone from soak_title.sh -- update the mutant"
fi
