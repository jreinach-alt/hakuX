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

echo "== display guard: a foreign overlay on display 0 refuses the soak (#494)"
DG="$T/displayguard"; rm -rf "$DG"; mkdir -p "$DG/bin" "$DG/t"
cat > "$DG/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$DG_FAKE/calls"
case "$*" in
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
