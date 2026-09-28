# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The screen across the cool-down gate (#507). soak_title.sh used to wake the
# device, then run the gate, which can wait minutes, then `am start`. On the
# Thor on 2026-09-28, with a 60 s screen timeout, a 77 s and a 78 s cool-down
# left the display OFF at `am start`, and both routes aborted "not foreground
# (unknown)". Now the gate runs with the screen asleep, and the wake and the
# display check come after it.
#
# The fake adb models the screen: KEYCODE_WAKEUP turns it on and starts its
# timeout clock (WG_TIMEOUT, 1.5 s here), KEYCODE_SLEEP turns it off, and
# `dumpsys power` reads Awake only while it is on and inside the timeout.
# xo-therm reads 70 C for the first three samples, then 50 C, one sample a
# second, so the gate waits about 3 s: twice the timeout.
#
# THE LEGS, and the world in which each one fails:
#   on         the gate waits longer than the timeout, and the display still
#              reads ON at `am start`. Fails if the wake comes before the gate
#              (the old order; the mutant below).
#   order      adb saw: wake, then sleep before the first `cool` sample, then
#              wake after the last one and before the `start` sample and
#              `am start`. Fails if the
#              gate runs with the screen lit, or the wake is not the last
#              screen event before the title starts.
#   recheck    a window that covers display 0 once the gate is done is
#              refused: exit 4, `display-covered:` in run.log, no `am start`.
#              Fails if the display is checked only before the gate.
#   covered    a display covered from the start is refused with no
#              KEYCODE_SLEEP at all (the owner's screen is not put out).
#              Fails if the sleep comes before the first check.
# And one mutant: the old order (no sleep, no wake or check after the gate)
# must turn `on` red.

echo "== wake after the gate: the display is on at am start after a long cool-down (#507)"
WG="$T/wakegate"; rm -rf "$WG"; mkdir -p "$WG/bin" "$WG/t"
cat > "$WG/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
F="$WG_FAKE"
screen() {   # ON or OFF, now
    [ "$(cat "$F/state" 2>/dev/null)" = on ] || { echo OFF; return; }
    awk -v a="$(cat "$F/wake_at")" -v n="$(date +%s.%N)" -v t="$WG_TIMEOUT" \
        'BEGIN { print (n - a < t) ? "ON" : "OFF" }'
}
case "$*" in
    *"keyevent KEYCODE_WAKEUP"*) echo on > "$F/state"; date +%s.%N > "$F/wake_at"; echo wake >> "$F/order" ;;
    *"keyevent KEYCODE_SLEEP"*)  echo off > "$F/state"; echo sleep >> "$F/order"; touch "$F/slept" ;;
    *"dumpsys power"*)
        if [ "$(screen)" = ON ]; then printf '  mWakefulness=Awake\r\n'; else printf '  mWakefulness=Asleep\r\n'; fi ;;
    *"dumpsys window windows"*)
        printf '  Window #0 Window{1a2b3c u0 com.jreinach.hakux.debug/x.E}:\r\n'
        printf '    mDisplayId=0 rootTaskId=1\r\n    package=com.jreinach.hakux.debug appop=NONE\r\n'
        printf '    mAttrs={(0,0)(fillxfill) ty=BASE_APPLICATION fmt=TRANSLUCENT\r\n'
        printf '    mViewVisibility=0x0 mHaveFrame=true\r\n    mHasSurface=true isReadyForDisplay()=true\r\n'
        # A cover that appears once the device has been put to sleep: `late`;
        # a cover there from the start: `early`.
        if [ -f "$F/early" ] || { [ -f "$F/late" ] && [ -f "$F/slept" ]; }; then
            printf '  Window #1 Window{1a2b3d u0 primaryScreenTopLayout}:\r\n'
            printf '    mDisplayId=0 rootTaskId=1\r\n    package=com.odin.dualscreen.assistant appop=SYSTEM_ALERT_WINDOW\r\n'
            printf '    mAttrs={(0,0)(fillxfill) ty=BOOT_PROGRESS fmt=TRANSLUCENT\r\n'
            printf '    mViewVisibility=0x0 mHaveFrame=true\r\n    mHasSurface=true isReadyForDisplay()=true\r\n'
        fi ;;
    *thermal_zone*)
        n=$(( $(cat "$F/thn" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$F/thn"
        echo cool >> "$F/order"
        printf 'now %s up %s\r\n' "$(date +'%m-%d %H:%M:%S')" "$((1000 + n))"
        printf 'tz 90 %d xo-therm\r\nend\r\n' "$([ "$n" -le 3 ] && echo 70000 || echo 50000)" ;;
    *"am start"*) screen > "$F/at_start"; echo am >> "$F/order" ;;
    *"settings get system performance_mode"*) echo "0 4" ;;
    *"ps -A -o NAME"*) printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$WG/bin/adb"

wg_soak() {   # <soak_title.sh> [early|late] -> rc; run.log, order, at_start in $WG
    local rc
    rm -f "$WG/state" "$WG/wake_at" "$WG/order" "$WG/thn" "$WG/at_start" "$WG/slept" \
          "$WG/early" "$WG/late" "$WG/run.log" "$WG/thermal.jsonl"
    [ -n "${2:-}" ] && touch "$WG/$2"
    env PATH="$WG/bin:$PATH" WG_FAKE="$WG" WG_TIMEOUT=1.5 SERIAL=ee317437 \
        DISPLAY_WAKE_S=0 ADB_RETRY_SLEEP=0 HAKUX_DEVICE_LEASE="$WG/lease" \
        SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 THERMAL_EVERY_S=1 THERMAL_COOL_EVERY_S=1 \
        THERMAL_OUT="$WG/thermal.jsonl" PERF_RESULT="$WG/perf_regimen.json" PERF_REGIMEN=off \
        timeout 60 bash "$1" /fake/iso.iso 1 > "$WG/run.log" 2>&1; rc=$?
    echo "$rc"
}
wg_on() {     # <soak_title.sh> -> "" or the reasons `on` failed
    local rc why=""
    rc=$(wg_soak "$1")
    [ "$rc" = 0 ] || why="$why rc=$rc"
    grep -qxE 'COOLDOWN: waited [2-9] s, xo 70\.0 -> 50\.0 C \[xo-therm 50\.0 C < 65 C\]' "$WG/run.log" \
        || why="$why no-long-COOLDOWN-line"
    [ "$(cat "$WG/at_start" 2>/dev/null)" = ON ] || why="$why display-$(cat "$WG/at_start" 2>/dev/null || echo unread)-at-am-start"
    echo "$why"
}

why=$(wg_on "$TESTING/soak_title.sh")
[ -z "$why" ] && ok "on: the gate waited $(sed -n 's/^COOLDOWN: waited \([0-9]*\) s.*/\1/p' "$WG/run.log") s against a 1.5 s screen timeout, and the display read ON at am start" \
    || bad "on:$why | $(tr '\n' '|' < "$WG/run.log" | tail -c 400)"

order=$(tr '\n' ' ' < "$WG/order" 2>/dev/null)
case "$order" in
    "wake sleep cool cool cool cool wake cool am "*) ok "order: adb saw [$order]" ;;
    *) bad "order: adb saw [$order], not wake, sleep, four cool samples, wake, the start sample, am start" ;;
esac

rc=$(wg_soak "$TESTING/soak_title.sh" late)
if [ "$rc" = 4 ] && grep -q '^display-covered: .*primaryScreenTopLayout' "$WG/run.log" \
        && [ ! -f "$WG/at_start" ] && grep -q '^COOLDOWN: waited' "$WG/run.log"; then
    ok "recheck: a cover that appears during the gate is refused after it: exit 4, display-covered, no am start"
else
    bad "recheck: rc=$rc at_start=$(cat "$WG/at_start" 2>/dev/null || echo none) | $(tr '\n' '|' < "$WG/run.log" | tail -c 400)"
fi

rc=$(wg_soak "$TESTING/soak_title.sh" early)
order=$(tr '\n' ' ' < "$WG/order" 2>/dev/null)
if [ "$rc" = 4 ] && [ ! -f "$WG/at_start" ] && [ "$order" = "wake " ]; then
    ok "covered: a display covered from the start is refused before any sleep; adb saw [$order]"
else
    bad "covered: rc=$rc adb saw [$order] | $(tr '\n' '|' < "$WG/run.log" | tail -c 400)"
fi

echo "== wake after the gate mutant: the old order (wake, gate, am start)"
if python3 - "$TESTING" "$WG/t" <<'PY'
import os, shutil, sys
src, dst = sys.argv[1], sys.argv[2]
for d in ("titles", "perf"):
    shutil.rmtree(os.path.join(dst, d), ignore_errors=True)
    shutil.copytree(os.path.join(src, d), os.path.join(dst, d))
for f in ("devices.sh", "thermal_state.py"):
    shutil.copy(os.path.join(src, f), os.path.join(dst, f))
s = open(os.path.join(src, "soak_title.sh")).read()
olds = ["display_gate\n\n# Dark through the cool-down gate",
        "a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1\n\n# THE THERMAL RECORD",
        "a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1\ndisplay_gate\n\narm_audio"]
news = ["display_gate\n\n# Dark through the cool-down gate",
        "\n# THE THERMAL RECORD",
        "arm_audio"]
if any(s.count(o) != 1 for o in olds):
    sys.exit(3)
for o, n in zip(olds, news):
    s = s.replace(o, n, 1)
open(os.path.join(dst, "soak_title.sh"), "w").write(s)
PY
then
    why=$(wg_on "$WG/t/soak_title.sh")
    case "$why" in *display-OFF-at-am-start*) ok "old-order mutant: the display is OFF at am start, and the on leg turns red" ;;
        *) bad "old-order mutant: the on leg did not catch it: [$why]" ;; esac
else
    bad "old-order mutant: its anchors are gone from soak_title.sh -- update the mutant"
fi
