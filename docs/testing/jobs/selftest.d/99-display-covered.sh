# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The display guard (#494): devices.sh display_clear, soak_title.sh's refusal
# and black-frame guard, and title_verdict.py's `void`. Driven against a fake
# adb that serves a `dumpsys power` and a `dumpsys window windows` from files.
#
# THE LEGS, and the world in which each one fails:
#   covered    the 2026-09-27 block: AYN's assistant, primaryScreenTopLayout,
#              ty=BOOT_PROGRESS, fillxfill, on display 0. Fails if the check
#              reads that as clear, or names the wrong window.
#   clear      hakuX in front, the owner's emulator (a full-screen APPLICATION
#              window, not an overlay type) behind it, a status bar, and a
#              systemui overlay. Fails if any non-overlay type, or systemui,
#              counts as a cover: the mutant with the type check removed.
#   hidden     the same overlay at mViewVisibility=0x8. Fails if an invisible
#              window counts.
#   display 1  the same overlay on the Thor's second screen. Fails if the
#              display is not checked.
#   asleep     mWakefulness=Asleep. Fails if only the window list is read.
#   unknown    adb answers nothing. Fails if silence reads as clear or as
#              covered (the second would void every run on a vsock drop).
#   soak       covered: exit 4, `display-covered:` in run.log, no `am start`,
#              no MAX, no KEYCODE_SLEEP over the owner's screen. clear: the
#              title starts. Fails if the refusal comes after `am start`.
#   verdict    a refused run, and a run with perf lines whose route frames
#              are all under 12 KB, are void with every fps field null; the
#              same run with one real frame is judged. Fails if a void run
#              carries a frame rate.
#
# THE FOREGROUND LEGS (hakux_in_front, and the soak's route guard):
#   (a) lime   Lime3DS is the top resumed activity. Fails if a route may
#              start, or its input reach that app.
#   (b) focus  hakuX is display 0's top activity, but input focus is display
#              4's SecondaryDisplayLauncher (mTopFocusedDisplayId=4), the
#              12:10 PDT Thor. Fails if only the top activity is read: the
#              focus mutant turns it green, and the leg red.
#       flat   the same with no per-display blocks: one global mCurrentFocus.
#       null   hakuX on top, mCurrentFocus=null. Fails if no focus is ours.
#   (c) ours   both hakuX, focus on display 0: the route plays.
#       silent adb answers nothing: unknown, never in front.
#   soak (a) and (b): exit 5, `ROUTE ABORTED: not foreground (<pkg>)`, one
#              `am start --display 0` remedy, and not one sendevent.
#   soak (c):  the route starts and sends input; nothing is aborted.
#   mid-route: in front for the first reads, then Lime3DS: the route is
#              stopped before its second press, the hold ends early, exit 5.
#              Fails if the watcher is gone (the watcher mutant).
#   verdict:   a not-foreground run is void.

echo "== display guard: a foreign overlay on display 0 refuses the soak (#494)"
DG="$T/displayguard"; rm -rf "$DG"; mkdir -p "$DG/bin" "$DG/t"
cat > "$DG/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$DG_FAKE/calls"
case "$*" in
    # hakux_in_front's one call. The Nth read serves fg.N when there is one,
    # else fg: a fixture can change what is in front partway through a route.
    *topResumedActivity*)
        n=$(( $(cat "$DG_FAKE/fgn" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$DG_FAKE/fgn"
        if [ -f "$DG_FAKE/fg.$n" ]; then cat "$DG_FAKE/fg.$n"; else cat "$DG_FAKE/fg" 2>/dev/null; fi ;;
    *"dumpsys power"*)            cat "$DG_FAKE/power" 2>/dev/null ;;
    *"dumpsys window windows"*)   cat "$DG_FAKE/windows" 2>/dev/null ;;
    *"settings get system performance_mode"*) echo "0 4" ;;
    *"am start"*)                 touch "$DG_FAKE/started" ;;
    *"ps -A -o NAME"*)
        printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$DG/bin/adb"

# One window block in `dumpsys window windows` form. <n> <name> <pkg> <type>
# <display> <visibility> [<attrs>]
dg_win() {
    printf '  Window #%s Window{%x u0 %s}:\r\n' "$1" "$((0x1a2b3c + $1))" "$2"
    printf '    mDisplayId=%s rootTaskId=1 mSession=Session{5d1e 1234:u0a10123} mClient=android.os.BinderProxy@9f0\r\n' "$5"
    printf '    mOwnerUid=10123 showForAllUsers=true package=%s appop=SYSTEM_ALERT_WINDOW\r\n' "$3"
    printf '    mAttrs={(0,0)(%s) sim={adjust=pan} ty=%s fmt=TRANSLUCENT\r\n' "${7:-fillxfill}" "$4"
    printf '      fl=NOT_FOCUSABLE LAYOUT_IN_SCREEN HARDWARE_ACCELERATED}\r\n'
    printf '    Requested w=1920 h=1080 mLayoutSeq=412\r\n'
    printf '    mViewVisibility=%s mHaveFrame=true mObscured=false\r\n' "$6"
    printf '    mHasSurface=true isReadyForDisplay()=true mWindowRemovalAllowed=false\r\n'
}
dg_head() { printf 'WINDOW MANAGER WINDOWS (dumpsys window windows)\r\n'; }
dg_tail() { printf '\r\n  mGlobalConfiguration={1.0 ?mcc?mnc [en_US] ldltr sw1080dp}\r\n  mCurrentFocus=Window{1a2b3e u0 com.jreinach.hakux.debug/com.rfandango.haku_x.EmulationActivity}\r\n'; }
dg_common() {   # the windows every fixture has: status bar, hakuX, the owner's app
    dg_win 1 StatusBar com.android.systemui STATUS_BAR 0 0x0 fillxwrap
    dg_win 2 com.jreinach.hakux.debug/com.rfandango.haku_x.EmulationActivity com.jreinach.hakux.debug BASE_APPLICATION 0 0x0
    dg_win 3 io.github.lime3ds.android/org.citra.citra_emu.activities.EmulationActivity io.github.lime3ds.android BASE_APPLICATION 0 0x0
    dg_win 4 ScreenDecorOverlay com.android.systemui SYSTEM_OVERLAY 0 0x0
}
{ dg_head; dg_win 0 primaryScreenTopLayout com.odin.dualscreen.assistant BOOT_PROGRESS 0 0x0; dg_common; dg_tail; } > "$DG/w.covered"
{ dg_head; dg_common; dg_tail; } > "$DG/w.clear"
{ dg_head; dg_win 0 primaryScreenTopLayout com.odin.dualscreen.assistant BOOT_PROGRESS 0 0x8; dg_common; dg_tail; } > "$DG/w.hidden"
{ dg_head; dg_win 0 primaryScreenTopLayout com.odin.dualscreen.assistant BOOT_PROGRESS 1 0x0; dg_common; dg_tail; } > "$DG/w.display1"
printf '  mWakefulness=Awake\r\n  mWakefulnessChanging=false\r\n' > "$DG/p.awake"
printf '  mWakefulness=Asleep\r\n  mWakefulnessChanging=false\r\n' > "$DG/p.asleep"
: > "$DG/p.empty"; : > "$DG/w.empty"

dg_check() {   # <devices.sh> <power fixture> <windows fixture> -> "rc|line"
    local out rc
    cp "$DG/p.$2" "$DG/power"; cp "$DG/w.$3" "$DG/windows"
    out=$(PATH="$DG/bin:$PATH" DG_FAKE="$DG" DISPLAY_WAKE_S=0 ADB_RETRY_SLEEP=0 \
        bash -c '. "$1" >/dev/null 2>&1; display_clear ee317437' _ "$1" 2>/dev/null); rc=$?
    printf '%s|%s\n' "$rc" "$out"
}
dg_legs() {    # <devices.sh> -> one "FAIL <why>" per unmet leg
    local d="$1" r
    r=$(dg_check "$d" awake covered)
    case "$r" in "1|display-covered: "*"primaryScreenTopLayout (com.odin.dualscreen.assistant, BOOT_PROGRESS)"*) ;;
        *) echo "FAIL covered: [$r]" ;; esac
    r=$(dg_check "$d" awake clear)
    case "$r" in "0|display-clear: ee317437 Awake, no foreign overlay on display 0 (4 windows read)") ;;
        *) echo "FAIL clear: [$r]" ;; esac
    r=$(dg_check "$d" awake hidden)
    case "$r" in "0|display-clear: "*"(5 windows read)") ;; *) echo "FAIL hidden: [$r]" ;; esac
    r=$(dg_check "$d" awake display1)
    case "$r" in "0|display-clear: "*"(5 windows read)") ;; *) echo "FAIL display 1: [$r]" ;; esac
    r=$(dg_check "$d" asleep clear)
    case "$r" in "1|display-covered: ee317437 reads mWakefulness=Asleep after KEYCODE_WAKEUP, not Awake") ;;
        *) echo "FAIL asleep: [$r]" ;; esac
    r=$(dg_check "$d" empty clear)
    case "$r" in "2|display-unknown: no mWakefulness line"*) ;; *) echo "FAIL unknown power: [$r]" ;; esac
    r=$(dg_check "$d" awake empty)
    case "$r" in "2|display-unknown: dumpsys window windows"*"listed no window") ;; *) echo "FAIL unknown windows: [$r]" ;; esac
}
out=$(dg_legs "$TESTING/devices.sh")
[ -z "$out" ] && ok "display_clear: covered, clear, hidden, display 1, asleep and unknown each read as they should" \
    || bad "display_clear: $(printf '%s; ' "$out")"

echo "== display guard mutant: drop the overlay-type condition"
if python3 - "$TESTING/devices.sh" "$DG/t/devices.sh" <<'PY'
import sys
s = open(sys.argv[1]).read()
old = "d0 && fill && surf && vis && ty"
if old not in s:
    sys.exit(3)
open(sys.argv[2], "w").write(s.replace(old, "d0 && fill && surf && vis", 1))
PY
then
    out=$(dg_legs "$DG/t/devices.sh")
    case "$out" in *"FAIL clear: [1|display-covered: "*io.github.lime3ds.android*) ok "type mutant: the owner's app window reads as a cover, and the clear leg turns red" ;;
        *) bad "type mutant: the legs did not catch it: [$out]" ;; esac
else
    bad "type mutant: its anchor is gone from devices.sh -- update the mutant"
fi

echo "== display guard: soak_title.sh refuses before am start, and runs when clear"
dg_soak() {    # <windows fixture> [route file] -> rc; run.log in $DG/run/run.log
    local rc
    rm -rf "$DG/run"; mkdir -p "$DG/run"; : > "$DG/calls"; rm -f "$DG/started"
    cp "$DG/p.awake" "$DG/power"; cp "$DG/w.$1" "$DG/windows"
    PATH="$DG/bin:$PATH" DG_FAKE="$DG" SERIAL=ee317437 DISPLAY_WAKE_S=0 \
        HAKUX_DEVICE_LEASE="$DG/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 \
        PERF_RESULT="$DG/run/perf_regimen.json" ROUTE_FILE="${2:-}" \
        timeout 60 bash "$TESTING/soak_title.sh" /fake/iso.iso 1 > "$DG/run/run.log" 2>&1; rc=$?
    echo "$rc"
}
rc=$(dg_soak covered)
if [ "$rc" = 4 ] && grep -q '^display-covered: .*primaryScreenTopLayout' "$DG/run/run.log" \
        && [ ! -f "$DG/started" ] && ! grep -q 'performance_mode 2' "$DG/calls" \
        && ! grep -q KEYCODE_SLEEP "$DG/calls"; then
    ok "covered: exit 4, display-covered in run.log, no am start, no MAX, no sleep over the owner's screen"
else
    bad "covered: rc=$rc started=$([ -f "$DG/started" ] && echo yes || echo no) run.log: $(tr '\n' '|' < "$DG/run/run.log" | tail -c 400)"
fi
cp -r "$DG/run" "$DG/refused"
rc=$(dg_soak clear)
if [ "$rc" = 0 ] && grep -q '^display-clear: ' "$DG/run/run.log" && [ -f "$DG/started" ] \
        && ! grep -q '^display-black' "$DG/run/run.log"; then
    ok "clear: the title started and the soak ran to its deadline"
else
    bad "clear: rc=$rc run.log: $(tr '\n' '|' < "$DG/run/run.log" | tail -c 400)"
fi
# The black-frame guard: an empty route is not played, but its frame dir is
# still read. 10,899 B is the 09-27 frame; one 40 KB frame clears the guard.
mkdir -p "$DG/rt/route-frames"; : > "$DG/rt/route.txt"
for i in 1 2 3; do head -c 10899 /dev/zero > "$DG/rt/route-frames/11060$i-mark.png"; done
dg_soak clear "$DG/rt/route.txt" >/dev/null
grep -q '^display-black: all 3 route frames under 12288 B (largest 10899 B)' "$DG/run/run.log" \
    && ok "black-frame guard: three 10,899 B frames log display-black" \
    || bad "black-frame guard: no display-black line: $(tr '\n' '|' < "$DG/run/run.log" | tail -c 400)"
head -c 40000 /dev/zero > "$DG/rt/route-frames/110604-gameplay.png"
dg_soak clear "$DG/rt/route.txt" >/dev/null
! grep -q '^display-black' "$DG/run/run.log" \
    && ok "black-frame guard: one real-sized frame and the run is not black" \
    || bad "black-frame guard: a 40 KB frame still logged display-black"

echo "== display guard: title_verdict.py voids a covered or black run"
dg_verdict() {   # <rdir> -> "void|fps_ok_share|fps_window_median|fps_windows|pass|failing"
    python3 "$TESTING/title_verdict.py" "$1" --targets /dev/null >/dev/null 2>&1 || { echo "exit $?"; return; }
    python3 -c 'import json,sys; v=json.load(open(sys.argv[1]+"/verdict.json"))
print("|".join(str(v.get(k)) for k in ("void","fps_ok_share","fps_window_median","fps_windows","pass","failing")))' "$1"
}
r=$(dg_verdict "$DG/refused")
case "$r" in "display-covered: "*"primaryScreenTopLayout"*"|None|None|0|False|void: display-covered: "*) ok "refused run: void, no frame rate, first failure names display-covered" ;;
    *) bad "refused run verdict: [$r]" ;; esac
# A played run: 40 perf lines at 60 flips per second after `mark gameplay`.
PV="$DG/played"; rm -rf "$PV"; mkdir -p "$PV/route-frames"
python3 - "$PV/logcat.txt" <<'PY'
import sys
out = ["09-27 11:10:00.000 I/hakuX-route( 100): soak start",
       "09-27 11:10:05.000 I/hakuX-route( 100): mark gameplay"]
for i in range(40):
    out.append("09-27 11:10:%02d.000 I/hakuX-perf( 200): gfps=60 G:16.7(16.0-17.0)" % (6 + i))
out.append("09-27 11:10:50.000 I/hakuX-route( 100): soak end")
open(sys.argv[1], "w").write("\n".join(out) + "\n")
PY
printf 'held iso.iso for 45s\nadb_failures=0\n' > "$PV/run.log"
echo '{"title": "iso.iso"}' > "$PV/request.json"
for i in 1 2 3; do head -c 10899 /dev/zero > "$PV/route-frames/11100$i-mark.png"; done
r=$(dg_verdict "$PV")
case "$r" in "display-black: all 3 route frames under 12288 B|None|None|0|False|void: display-black: "*) ok "black frames, old run.log: void from the frames themselves, no frame rate" ;;
    *) bad "black frames verdict: [$r]" ;; esac
printf 'display-black: all 3 route frames under 12288 B (largest 10899 B) -- x\n' >> "$PV/run.log"
head -c 40000 /dev/zero > "$PV/route-frames/111004-gameplay.png"
r=$(dg_verdict "$PV")
case "$r" in "display-black: all 3 route frames"*"|None|None|0|False|void: "*) ok "display-black in run.log voids the run even with a later frame on disk" ;;
    *) bad "run.log display-black verdict: [$r]" ;; esac
sed -i '/^display-black/d' "$PV/run.log"
r=$(dg_verdict "$PV")
case "$r" in "None|1.0|60.0|39|"*) ok "control: the same run with a real frame is judged, 39 windows at 60 fps" ;;
    *) bad "control verdict: [$r]" ;; esac

echo "== foreground guard: route input only while hakuX holds display 0 and focus (#494)"
HX=com.jreinach.hakux.debug/com.rfandango.haku_x.EmulationActivity
LIME=io.github.lime3ds.android/org.citra.citra_emu.activities.EmulationActivity
L3=com.android.launcher3/com.android.launcher3.secondarydisplay.SecondaryDisplayLauncher
# What the device prints for hakux_in_front's call: <top> <top-focused display>
# <display 0 focus> <display 4 focus>. `-` for a line that is not there.
fg_fix() {
    [ "$1" = - ] || printf '  topResumedActivity=ActivityRecord{8c1f2a u0 %s t41}\r\n' "$1"
    printf 'WINDOW MANAGER DISPLAY CONTENTS (dumpsys window displays)\r\n'
    printf '  Display: mDisplayId=0 rootTasks=4\r\n'
    [ "$3" = - ] || printf '    mCurrentFocus=Window{51d0e7 u0 %s}\r\n' "$3"
    printf '  Display: mDisplayId=4 rootTasks=1\r\n'
    [ "$4" = - ] || printf '    mCurrentFocus=Window{a0e4c2 u0 %s}\r\n' "$4"
    printf 'WINDOW MANAGER WINDOWS (dumpsys window windows)\r\n'
    [ "$2" = - ] || printf '  mTopFocusedDisplayId=%s\r\n' "$2"
}
fg_fix "$LIME" 0 "$LIME" "$L3" > "$DG/f.lime"
fg_fix "$HX" 4 "$HX" "$L3" > "$DG/f.focus"
printf '  topResumedActivity=ActivityRecord{8c1f2a u0 %s t41}\r\n  mCurrentFocus=Window{a0e4c2 u0 %s}\r\n' "$HX" "$L3" > "$DG/f.flat"
printf '  topResumedActivity=ActivityRecord{8c1f2a u0 %s t41}\r\n  mCurrentFocus=null\r\n  mTopFocusedDisplayId=0\r\n' "$HX" > "$DG/f.null"
fg_fix "$HX" 0 "$HX" "$L3" > "$DG/f.ours"
: > "$DG/f.silent"

fg_check() {   # <devices.sh> <fixture> -> "rc|line"
    local out rc
    rm -f "${DG:?}/fgn" "$DG"/fg.[0-9]*; cp "$DG/f.$2" "$DG/fg"
    out=$(PATH="$DG/bin:$PATH" DG_FAKE="$DG" ADB_RETRY_SLEEP=0 \
        bash -c '. "$1" >/dev/null 2>&1; hakux_in_front ee317437' _ "$1" 2>/dev/null); rc=$?
    printf '%s|%s\n' "$rc" "$out"
}
fg_legs() {    # <devices.sh> -> one "FAIL <why>" per unmet leg
    local d="$1" r
    r=$(fg_check "$d" lime)
    case "$r" in "1|not-foreground: io.github.lime3ds.android (the top resumed activity on ee317437, not hakuX)") ;;
        *) echo "FAIL (a) lime: [$r]" ;; esac
    r=$(fg_check "$d" focus)
    case "$r" in "1|not-foreground: com.android.launcher3 (input focus is on display 4 of ee317437, not display 0)") ;;
        *) echo "FAIL (b) focus: [$r]" ;; esac
    r=$(fg_check "$d" flat)
    case "$r" in "1|not-foreground: com.android.launcher3 (holds input focus on ee317437; hakuX is only the top activity)") ;;
        *) echo "FAIL flat: [$r]" ;; esac
    r=$(fg_check "$d" null)
    case "$r" in "1|not-foreground: null (holds input focus"*) ;; *) echo "FAIL null: [$r]" ;; esac
    r=$(fg_check "$d" ours)
    case "$r" in "0|in-front: ee317437 top=com.jreinach.hakux.debug focus=com.jreinach.hakux.debug display=0") ;;
        *) echo "FAIL (c) ours: [$r]" ;; esac
    r=$(fg_check "$d" silent)
    case "$r" in "2|foreground-unknown: ee317437 answered top=(none) focus=(none)") ;;
        *) echo "FAIL silent: [$r]" ;; esac
}
out=$(fg_legs "$TESTING/devices.sh")
[ -z "$out" ] && ok "hakux_in_front: Lime3DS on top, focus on display 4, a flat focus, null focus, hakuX, and silence each read as they should" \
    || bad "hakux_in_front: $(printf '%s; ' "$out")"

echo "== foreground guard mutant: read the top activity only, not the focus"
if python3 - "$TESTING/devices.sh" "$DG/t/devices.sh" <<'PY'
import sys
s = open(sys.argv[1]).read()
olds = ['if (tfd != "" && tfd != "0") {', 'if (!ours(focus)) {']
if any(s.count(o) != 1 for o in olds):
    sys.exit(3)
for o in olds:
    s = s.replace(o, "if (0) {", 1)
open(sys.argv[2], "w").write(s)
PY
then
    out=$(fg_legs "$DG/t/devices.sh")
    case "$out" in *"FAIL (b) focus: [0|in-front: "*) ok "focus mutant: display 4's launcher with focus reads as in front, and leg (b) turns red" ;;
        *) bad "focus mutant: the legs did not catch it: [$out]" ;; esac
else
    bad "focus mutant: its anchors are gone from devices.sh -- update the mutant"
fi

echo "== foreground guard: soak_title.sh plays the route only while hakuX is in front"
printf 'press A\nwait 2\npress B\nwait 30\n' > "$DG/fg.route"
fg_soak() {    # <soak_title.sh> <hold s> <fixture> [<fixture for read 1> ...] -> rc; run.log in $DG/run
    local s="$1" hold="$2" f="$3" i=1 rc; shift 3
    rm -rf "${DG:?}/run"; mkdir -p "$DG/run"; : > "$DG/calls"; rm -f "$DG/started" "$DG/fgn" "$DG"/fg.[0-9]*
    cp "$DG/p.awake" "$DG/power"; cp "$DG/w.clear" "$DG/windows"; cp "$DG/f.$f" "$DG/fg"
    for f in "$@"; do cp "$DG/f.$f" "$DG/fg.$i"; i=$((i+1)); done
    PATH="$DG/bin:$PATH" DG_FAKE="$DG" SERIAL=ee317437 DISPLAY_WAKE_S=0 ADB_RETRY_SLEEP=0 \
        HAKUX_DEVICE_LEASE="$DG/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 HAKUX_WORK="$DG" \
        PAD_DEV=/dev/input/event7 FG_POLL_S=0.2 FG_WAIT_S=1 FG_REMEDY_S=1 \
        PERF_RESULT="$DG/run/perf_regimen.json" ROUTE_FILE="$DG/fg.route" ROUTE_FRAMES="$DG/run/rf" \
        timeout 60 bash "$s" /fake/iso.iso "$hold" > "$DG/run/run.log" 2>&1; rc=$?
    echo "$rc"
}
fg_refused() {   # <label> <pkg> <rc>: the pre-route abort, asserted on the words
    local why=""
    [ "$3" = 5 ] || why="$why rc=$3"
    grep -qxF "ROUTE ABORTED: not foreground ($2)" "$DG/run/run.log" || why="$why no-ABORTED-line"
    grep -q "^not-foreground: $2 " "$DG/run/run.log" || why="$why no-not-foreground-line"
    [ "$(grep -c 'am start --display 0' "$DG/calls")" = 1 ] || why="$why remedy-count=$(grep -c 'am start --display 0' "$DG/calls")"
    ! grep -q sendevent "$DG/calls" || why="$why INPUT-SENT"
    ! grep -q '^ROUTE started' "$DG/run/run.log" || why="$why route-started"
    grep -q '^soak aborted: not-foreground before' "$DG/run/run.log" || why="$why no-soak-aborted"
    [ -z "$why" ] && ok "$1: exit 5, ROUTE ABORTED ($2), one --display 0 remedy, no input sent" \
        || bad "$1:$why | $(tr '\n' '|' < "$DG/run/run.log" | tail -c 500)"
}
rc=$(fg_soak "$TESTING/soak_title.sh" 5 lime); fg_refused "soak (a) Lime3DS on top" io.github.lime3ds.android "$rc"
rm -rf "${DG:?}/fgrefused"; cp -r "$DG/run" "$DG/fgrefused"
rc=$(fg_soak "$TESTING/soak_title.sh" 5 focus); fg_refused "soak (b) focus on display 4" com.android.launcher3 "$rc"
rc=$(fg_soak "$TESTING/soak_title.sh" 2 ours)
if [ "$rc" = 0 ] && grep -q '^in-front: ee317437' "$DG/run/run.log" && grep -q '^ROUTE started' "$DG/run/run.log" \
        && grep -q 'sendevent /dev/input/event7 1 304 1' "$DG/calls" && ! grep -q 'ROUTE ABORTED\|^not-foreground' "$DG/run/run.log" \
        && ! grep -q 'am start --display 0' "$DG/calls"; then
    ok "soak (c) hakuX in front: the route starts, presses A, and nothing is aborted"
else
    bad "soak (c): rc=$rc $(tr '\n' '|' < "$DG/run/run.log" | tail -c 500)"
fi
fg_midroute() {   # <soak_title.sh> -> "" or the reasons it failed
    local rc t0 dt why=""
    t0=$(date +%s)
    rc=$(fg_soak "$1" 8 lime ours ours); dt=$(( $(date +%s) - t0 ))
    [ "$rc" = 5 ] || why="$why rc=$rc"
    grep -qxF "ROUTE ABORTED: not foreground (io.github.lime3ds.android)" "$DG/run/run.log" || why="$why no-ABORTED-line"
    grep -q 'sendevent /dev/input/event7 1 304 1' "$DG/calls" || why="$why A-not-pressed"
    ! grep -q 'sendevent /dev/input/event7 1 305 1' "$DG/calls" || why="$why B-PRESSED"
    grep -q '^soak aborted: not-foreground after' "$DG/run/run.log" || why="$why hold-not-ended"
    [ "$dt" -lt 6 ] || why="$why took-${dt}s"
    echo "$why"
}
why=$(fg_midroute "$TESTING/soak_title.sh")
[ -z "$why" ] && ok "mid-route: Lime3DS comes to the front, the route stops before its second press, the hold ends, exit 5" \
    || bad "mid-route:$why | $(tr '\n' '|' < "$DG/run/run.log" | tail -c 500)"

echo "== foreground guard mutant: no watcher while the route plays"
if python3 - "$TESTING" "$DG/t" <<'PY'
import os, shutil, sys
src, dst = sys.argv[1], sys.argv[2]
for d in ("titles", "perf"):
    shutil.rmtree(os.path.join(dst, d), ignore_errors=True)
    shutil.copytree(os.path.join(src, d), os.path.join(dst, d))
shutil.copy(os.path.join(src, "devices.sh"), os.path.join(dst, "devices.sh"))
s = open(os.path.join(src, "soak_title.sh")).read()
old = "    fg_watch &\n"
if s.count(old) != 1:
    sys.exit(3)
open(os.path.join(dst, "soak_title.sh"), "w").write(s.replace(old, "    : &\n", 1))
PY
then
    why=$(fg_midroute "$DG/t/soak_title.sh")
    case "$why" in *B-PRESSED*) ok "watcher mutant: the route presses B into Lime3DS, and the mid-route leg turns red" ;;
        *) bad "watcher mutant: the mid-route leg did not catch it: [$why]" ;; esac
else
    bad "watcher mutant: its anchor is gone from soak_title.sh -- update the mutant"
fi

r=$(dg_verdict "$DG/fgrefused")
case "$r" in "not-foreground: io.github.lime3ds.android "*"|None|None|0|False|void: not-foreground: "*) ok "verdict: a not-foreground run is void, with no frame rate" ;;
    *) bad "not-foreground verdict: [$r]" ;; esac
