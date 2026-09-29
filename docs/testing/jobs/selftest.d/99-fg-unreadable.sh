# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# An unreadable foreground read is not an unknown one (#592). hakux_in_front
# (devices.sh) returns 3, `foreground-unreadable:`, when adb hung, failed or
# answered nothing, and 2, `foreground-unknown:`, only when the device
# answered without a FocusedDisplayId or a focused window. soak_title.sh's
# route watcher aborts on two unknowns in a row but allows FG_UNREADABLE_MAX
# unreadable reads in a row. Driven against a fake adb that serves read N of
# `dumpsys input` from fg.N (else fg), where a file saying HANG sleeps past
# the timeout and FAIL exits 1.
#
# THE LEGS, and the world in which each one fails:
#   (a) hung    the read hangs past ADB_QUICK_TIMEOUT: exit 3, `adb hung`.
#               Fails on master, which reads the empty stdout as exit 2
#               `answered no FocusedDisplayId`. Also: adb exits 1 twice
#               (`adb failed`), and adb answers nothing (`answered nothing`).
#   (b) nofield the device answers sections but no FocusedDisplayId: exit 2,
#               as before. Fails if every non-answer is folded into 3.
#   (c) watch   in front, then unreadable x3, then in front: the route plays
#               its second press and nothing is aborted. Fails on master,
#               which aborts at the second hung read (the 09-28 Nova).
#   (d) unknown in front, then unknown x2: aborted before the second press.
#       bound   in front, then unreadable x FG_UNREADABLE_MAX (3 here):
#               aborted, `not-foreground: unreadable`. Fails if unreadable is
#               never bounded, or is taken as in front.
#   (e) lime    in front, then Lime3DS once: aborted at once.
#   (f) wait    unreadable before the first input: no input is sent, one
#               am start remedy, exit 5 with `not-foreground: unreadable`.

echo "== foreground reads: unreadable (adb hung or failed) is not unknown (#592)"
FU="$T/fgunreadable"; rm -rf "$FU"; mkdir -p "$FU/bin"
cat > "$FU/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$FU_FAKE/calls"
case "$*" in
    *"dumpsys input"*)
        n=$(( $(cat "$FU_FAKE/fgn" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$FU_FAKE/fgn"
        f="$FU_FAKE/fg"; [ -f "$FU_FAKE/fg.$n" ] && f="$FU_FAKE/fg.$n"
        case "$(head -1 "$f" 2>/dev/null)" in
            HANG) exec sleep 30 ;;
            FAIL) echo "error: closed" >&2; exit 1 ;;
        esac
        cat "$f" 2>/dev/null ;;
    *"dumpsys power"*)  printf '  mWakefulness=Awake\r\n' ;;
    *"dumpsys window windows"*)
        printf '  Window #0 Window{1a2b u0 StatusBar}:\r\n    mDisplayId=0 rootTaskId=1\r\n' ;;
    *"settings get system performance_mode"*) echo "0 4" ;;
    *"ps -A -o NAME"*)  printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$FU/bin/adb"

FU_HX=com.jreinach.hakux.debug/com.rfandango.haku_x.EmulationActivity
FU_LIME=io.github.lime3ds.android/org.citra.citra_emu.activities.EmulationActivity
fu_fix() {   # <display 0 application and window>
    printf '  FocusedDisplayId: 0\r\n  FocusedApplications:\r\n'
    printf "    displayId=0, name='ActivityRecord{8c1f2a u0 %s t41}', dispatchingTimeout=5000ms\r\n" "$1"
    printf "  FocusedWindows:\r\n    displayId=0, name='51d0e7 %s'\r\n" "$1"
}
fu_fix "$FU_HX" > "$FU/f.ours"
fu_fix "$FU_LIME" > "$FU/f.lime"
printf '  DispatchEnabled: true\r\n  FocusedApplications:\r\n  FocusedWindows:\r\n' > "$FU/f.nofield"
echo HANG > "$FU/f.hang"; echo FAIL > "$FU/f.fail"; : > "$FU/f.empty"

fu_check() {   # <devices.sh> <fixture> -> "rc|line"
    local out rc
    rm -f "${FU:?}/fgn" "$FU"/fg.[0-9]*; cp "$FU/f.$2" "$FU/fg"
    out=$(PATH="$FU/bin:$PATH" FU_FAKE="$FU" ADB_RETRY_SLEEP=0 ADB_QUICK_TIMEOUT=1 \
        bash -c '. "$1" >/dev/null 2>&1; hakux_in_front ee317437' _ "$1" 2>/dev/null); rc=$?
    printf '%s|%s\n' "$rc" "$out"
}
r=$(fu_check "$TESTING/devices.sh" hang)
[ "$r" = "3|foreground-unreadable: ee317437 adb hung (no answer in 1s)" ] \
    && ok "(a) hung read: exit 3, foreground-unreadable, adb hung" || bad "(a) hung read: [$r]"
r=$(fu_check "$TESTING/devices.sh" fail)
[ "$r" = "3|foreground-unreadable: ee317437 adb failed (exit 1)" ] \
    && ok "(a) failed read: exit 3, foreground-unreadable, adb failed" || bad "(a) failed read: [$r]"
r=$(fu_check "$TESTING/devices.sh" empty)
[ "$r" = "3|foreground-unreadable: ee317437 adb answered nothing" ] \
    && ok "(a) empty read: exit 3, foreground-unreadable, answered nothing" || bad "(a) empty read: [$r]"
r=$(fu_check "$TESTING/devices.sh" nofield)
[ "$r" = "2|foreground-unknown: ee317437 answered no FocusedDisplayId" ] \
    && ok "(b) an answer without FocusedDisplayId: exit 2, foreground-unknown, as before" || bad "(b) no field: [$r]"

echo "== foreground watch: unreadable reads are bounded apart from unknowns (#592)"
printf 'press A\nwait 3\npress B\nwait 30\n' > "$FU/route"
fu_soak() {   # <hold s> <default fixture> [<fixture for read 1> ...] -> rc; run.log in $FU/run
    local hold="$1" f="$2" i=1 rc; shift 2
    rm -rf "${FU:?}/run"; mkdir -p "$FU/run"; : > "$FU/calls"; rm -f "$FU/fgn" "$FU"/fg.[0-9]*
    cp "$FU/f.$f" "$FU/fg"
    for f in "$@"; do cp "$FU/f.$f" "$FU/fg.$i"; i=$((i+1)); done
    PATH="$FU/bin:$PATH" FU_FAKE="$FU" SERIAL=ee317437 DISPLAY_WAKE_S=0 ADB_RETRY_SLEEP=0 \
        ADB_QUICK_TIMEOUT=1 HAKUX_DEVICE_LEASE="$FU/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 \
        HAKUX_WORK="$FU" PAD_DEV=/dev/input/event7 FG_POLL_S=0.2 FG_WAIT_S=1 FG_REMEDY_S=1 \
        FG_UNREADABLE_MAX="${FU_MAX:-5}" \
        PERF_RESULT="$FU/run/perf_regimen.json" ROUTE_FILE="$FU/route" ROUTE_FRAMES="$FU/run/rf" \
        timeout 90 bash "$TESTING/soak_title.sh" /fake/iso.iso "$hold" > "$FU/run/run.log" 2>&1; rc=$?
    echo "$rc"
}
fu_log() { tr '\n' '|' < "$FU/run/run.log" | tail -c 600; }
FU_A='sendevent /dev/input/event7 1 304 1'; FU_B='sendevent /dev/input/event7 1 305 1'

rc=$(fu_soak 7 ours ours hang hang hang)
why=""
[ "$rc" = 0 ] || why="$why rc=$rc"
! grep -q '^ROUTE ABORTED\|^not-foreground' "$FU/run/run.log" || why="$why ABORTED"
for n in 1 2 3; do
    grep -qxF "FOREGROUND: foreground-unreadable: ee317437 adb hung (no answer in 1s) ($n/5)" "$FU/run/run.log" || why="$why no-($n/5)-line"
done
grep -q "$FU_B" "$FU/calls" || why="$why B-not-pressed"
[ -z "$why" ] && ok "(c) unreadable x3 then in front: counted 1/5..3/5, the route plays on, nothing aborted" \
    || bad "(c) unreadable x3:$why | $(fu_log)"

rc=$(fu_soak 7 ours ours nofield nofield)
why=""
[ "$rc" = 5 ] || why="$why rc=$rc"
grep -qxF "ROUTE ABORTED: not foreground (unknown)" "$FU/run/run.log" || why="$why no-ABORTED-line"
grep -q '^not-foreground: unknown (ee317437 answered no FocusedDisplayId)' "$FU/run/run.log" || why="$why no-not-foreground-line"
! grep -q "$FU_B" "$FU/calls" || why="$why B-PRESSED"
[ -z "$why" ] && ok "(d) unknown x2: aborted before the second press, as before" || bad "(d) unknown x2:$why | $(fu_log)"

rc=$(FU_MAX=3 fu_soak 7 ours ours hang hang hang)
why=""
[ "$rc" = 5 ] || why="$why rc=$rc"
grep -qxF "ROUTE ABORTED: not foreground (unreadable)" "$FU/run/run.log" || why="$why no-ABORTED-line"
grep -q '^not-foreground: unreadable (ee317437 adb hung' "$FU/run/run.log" || why="$why no-not-foreground-line"
grep -qxF "FOREGROUND: foreground-unreadable: ee317437 adb hung (no answer in 1s) (3/3)" "$FU/run/run.log" || why="$why no-(3/3)-line"
[ -z "$why" ] && ok "(d) unreadable x FG_UNREADABLE_MAX (3): aborted as not-foreground: unreadable" \
    || bad "(d) unreadable bound:$why | $(fu_log)"

rc=$(fu_soak 7 ours ours lime)
why=""
[ "$rc" = 5 ] || why="$why rc=$rc"
grep -qxF "ROUTE ABORTED: not foreground (io.github.lime3ds.android)" "$FU/run/run.log" || why="$why no-ABORTED-line"
! grep -q "$FU_B" "$FU/calls" || why="$why B-PRESSED"
[ -z "$why" ] && ok "(e) not-foreground x1: aborted at once" || bad "(e) Lime3DS once:$why | $(fu_log)"

rc=$(fu_soak 5 hang)
why=""
[ "$rc" = 5 ] || why="$why rc=$rc"
grep -qxF "ROUTE ABORTED: not foreground (unreadable)" "$FU/run/run.log" || why="$why no-ABORTED-line"
grep -q '^soak aborted: not-foreground before' "$FU/run/run.log" || why="$why no-soak-aborted"
[ "$(grep -c 'am start --display 0' "$FU/calls")" = 1 ] || why="$why remedy-count=$(grep -c 'am start --display 0' "$FU/calls")"
! grep -q sendevent "$FU/calls" || why="$why INPUT-SENT"
[ -z "$why" ] && ok "(f) unreadable before the first input: one am start remedy, no input, exit 5 not-foreground: unreadable" \
    || bad "(f) unreadable wait:$why | $(fu_log)"
