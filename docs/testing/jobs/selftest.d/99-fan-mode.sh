# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The per-request fan mode (#507 D.3; soak_title.sh THE FAN MODE, devices.sh
# DEVICE_FAN_OPTIONS): FAN_MODE=<name> puts the fan setting the handheld's
# own menu writes for <name> on the device before `am start` -- fan_mode,
# and fan_speed for the Customize slider -- refuses anything the menu does
# not show at the performance mode the title runs at, never writes the
# fan's PWM node, and puts the prior fan_mode and fan_speed back on every
# exit. Driven against a fake adb that keeps performance_mode, fan_mode and
# fan_speed in files, answers thermal_state.py's sample with the fan mode it
# holds, and logs every command it is given, so the assertions are on the
# adb command words.
#
# THE LEGS, and the world in which each one fails:
#   set        the Nova at MAX (performance_mode 2), FAN_MODE=customize:100:
#              `settings put system fan_mode 6; settings put system fan_speed
#              100` reaches adb after MAX and before `am start`, the title
#              starts at 6/100, and perf_regimen.json fan_request says what
#              was asked, shown, run and prior. Fails if the setting lands
#              after the title starts, or never, or the regimen's fan (5) is
#              what the title runs at.
#   sampled    thermal.jsonl: every sample from `start` on reads fan.mode 6,
#              and the THERMAL summary says so. Fails if the sampler does not
#              read the mode.
#   rest       PERF_REGIMEN=rest (performance_mode 0), FAN_MODE=quiet: starts
#              at 1, and writes no fan_speed. Fails if the options are not
#              read per performance mode, or a mode without a slider moves it.
#   settle     a fake SystemUI tile that puts fan_mode 4 back once, just
#              after the write: run.log names it `written again` and the
#              title still starts at 6/100. Fails if the read-back is taken
#              before the tile can act, or a moved write is not redone.
#   moved      a fake charger trigger that puts fan_mode 4 on once the title
#              runs: run.log names `FAN: fan_mode read [4]` and
#              perf_regimen.json counts moved >= 1. Fails if a hold sample's
#              mode is not checked against the one asked for.
#   noduty     no adb command in any leg writes to the PWM node. Fails if the
#              knob reaches for a fan speed no menu offers (#563's way).
#   end        PERF_REGIMEN=off on a device at performance_mode 2 whose prior
#              fan is 3 / fan_speed 7 (neither REST nor asked), so nothing but
#              the fan restore can put them back: the hold runs out, the last
#              fan_mode write is `fan_mode 3; ... fan_speed 7`, after `am
#              start`, the device reads 3/7, run.log says `FAN: restored=[3 7]
#              to=[3 7] fan_restored=true`, perf_regimen.json agrees. Fails if
#              release() does not restore, or restores REST or the asked mode.
#   killed     the same, TERM half a second after `am start`. Fails if the
#              restore is not reached from the EXIT trap.
#   nullspeed  a prior fan_speed never written (`null`) is put back by
#              `settings delete system fan_speed`. Fails if the restore leaves
#              the slider at 100 on a device whose menu never moved it.
#   refused    exit 6, a `fan-mode-refused:` line, no `am start`, no settings
#              write, fan_request.refused set, for: a name no menu has
#              (`turbo`), a bare mode number (`6`), an option hidden at the
#              title's performance mode (`quiet` and `off` at MAX,
#              `customize:50` at REST, `off` at STANDARD under
#              PERF_REGIMEN=off), and slider positions the control cannot
#              take (`customize:101`, `customize`, `customize:x`, `smart:5`).
#              Fails if a run at a fan the player cannot pick goes ahead.
#   none       no FAN_MODE: no fan write but the regimen's, fan_request null.
#              Fails if a run that asked for nothing has its fan moved.
#   request    `"fan_mode": "CUSTOMIZE:100"` in the running request, then
#              `FAN_MODE=customize:100` in its env: each starts the title at
#              6/100. Fails if the dispatcher's request is not read, or a
#              name's case refuses it.
# And one mutant: release() without fan_leave must turn `end` and `killed` red.

echo "== fan mode: a menu-selectable fan setting during a soak, refused otherwise, prior setting after (#507)"
FM="$T/fanmode"; rm -rf "$FM"; mkdir -p "$FM/bin" "$FM/t"
cat > "$FM/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
F="$FAN_FAKE"
[ -f "$F/perf" ] || cat "$F/perf0" > "$F/perf"
[ -f "$F/mode" ] || cat "$F/mode0" > "$F/mode"
[ -f "$F/speed" ] || cat "$F/speed0" > "$F/speed"
[ "$1" = shell ] && printf '%s\n' "$*" >> "$F/adb.log"
case "$*" in
    *"settings put system performance_mode"*)
        set -- $(printf '%s\n' "$*" | sed -n 's/.*performance_mode \([0-9-]*\).*fan_mode \([0-9-]*\).*/\1 \2/p')
        echo "$1" > "$F/perf"; echo "$2" > "$F/mode" ;;
    *"settings get system performance_mode"*) echo "$(cat "$F/perf") $(cat "$F/mode")" ;;
    *"settings get system fan_speed"*)
        # SystemUI's tile, once: fan_mode back to 4 just after the soak's write.
        [ -f "$F/tile_once" ] && [ -f "$F/fan_written" ] && { echo 4 > "$F/mode"; rm -f "$F/tile_once"; }
        echo "fan $(cat "$F/mode") $(cat "$F/speed")" ;;
    *"settings put system fan_mode "*)
        printf '%s\n' "$*" | sed -n 's/.*fan_mode \([0-9-]*\).*/\1/p' > "$F/mode"
        case "$*" in
            *"settings put system fan_speed "*) printf '%s\n' "$*" | sed -n 's/.*fan_speed \([0-9-]*\).*/\1/p' > "$F/speed" ;;
            *"settings delete system fan_speed"*) echo null > "$F/speed" ;;
        esac
        touch "$F/fan_written" ;;
    *"cooling_device"*)
        # The charger trigger: Smart on, once the title runs.
        [ -f "$F/charger" ] && [ -f "$F/started" ] && echo 4 > "$F/mode"
        # thermal_state.py's sample: a clock, the fan, and the mode it runs at.
        printf 'now 09-28 12:00:00 up 100.0\ntz 0 40000 xo-therm\nfan duty 25000\nfan period 50000\nfan mode %s\nend\n' "$(cat "$F/mode")" ;;
    *"am start"*) echo "$(cat "$F/mode") $(cat "$F/speed")" > "$F/at_start"; touch "$F/started" ;;
    *"ps -A -o NAME"*)
        printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$FM/bin/adb"
ln -sf "$TESTING/devices.sh" "$FM/t/devices.sh"
ln -sf "$TESTING/thermal_state.py" "$FM/t/thermal_state.py"

NOVA=ee317437
# fm_soak <soak_title.sh> <perf0> <mode0> <speed0> <hold seconds> [term] -> rc
fm_soak() {
    local s="$1" hold="$5" term="${6:-}" pid rc
    rm -f "$FM/started" "$FM/at_start" "$FM/perf" "$FM/mode" "$FM/speed" \
          "$FM/fan_written" "$FM/adb.log" "$FM/perf_regimen.json" "$FM/thermal.jsonl"
    echo "$2" > "$FM/perf0"; echo "$3" > "$FM/mode0"; echo "$4" > "$FM/speed0"
    PATH="$FM/bin:$PATH" FAN_FAKE="$FM" SERIAL="$NOVA" \
        HAKUX_DEVICE_LEASE="$FM/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 FAN_SETTLE_S=0.1 \
        THERMAL_EVERY_S=1 THERMAL_COOL_C=off THERMAL_OUT="$FM/thermal.jsonl" \
        PERF_RESULT="$FM/perf_regimen.json" \
        timeout 60 bash "$s" /fake/iso.iso "$hold" > "$FM/run.log" 2>&1 &
    pid=$!
    if [ -n "$term" ]; then
        for _ in $(seq 100); do [ -f "$FM/started" ] && break; sleep 0.1; done
        sleep 0.5
        pkill -TERM -P "$pid"
    fi
    wait "$pid"; rc=$?
    echo "$rc"
}
fm_json() {   # <python expr over d> -> its value, or ERR
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' \
        "$FM/perf_regimen.json" "$1" 2>/dev/null || echo ERR
}
# adb.log line numbers. A lone fan write starts `shell settings put system
# fan_mode`; the regimen's starts `... performance_mode`.
fm_last() { grep -nF -- "$1" "$FM/adb.log" 2>/dev/null | tail -1 | cut -d: -f1; }
fm_first() { grep -nF -- "$1" "$FM/adb.log" 2>/dev/null | head -1 | cut -d: -f1; }
FM_DUTY_WRITES=0
fm_noduty() { grep -q '> */sys/' "$FM/adb.log" 2>/dev/null && FM_DUTY_WRITES=$((FM_DUTY_WRITES + 1)); }
read -r _ NOVA_FAN_MAX _ NOVA_FAN_REST <<<"$(bash -c '. "$1"; device_perf_values "$2"' _ "$TESTING/devices.sh" "$NOVA")"

# The restore legs, as a function so the mutant runs the same assertions.
fm_restore_legs() {   # <soak_title.sh>
    local s="$1" rc lr lm
    for leg in end killed; do
        if [ "$leg" = end ]; then
            rc=$(PERF_REGIMEN=off FAN_MODE=customize:100 fm_soak "$s" 2 3 7 1)
        else
            rc=$(PERF_REGIMEN=off FAN_MODE=customize:100 fm_soak "$s" 2 3 7 30 term)
        fi
        fm_noduty
        [ "$leg" = end ] && [ "$rc" != 0 ] && { echo "$leg: red rc=$rc"; continue; }
        [ "$leg" = killed ] && [ "$rc" != 143 ] && { echo "$leg: red rc=$rc"; continue; }
        [ "$(cat "$FM/at_start" 2>/dev/null)" = "6 100" ] || echo "$leg: red the title started at [$(cat "$FM/at_start" 2>/dev/null)]"
        lr=$(fm_last "shell settings put system fan_mode 3; settings put system fan_speed 7")
        lm=$(fm_last "shell settings put system fan_mode")
        if [ -n "$lr" ] && [ "$lr" = "$lm" ] && [ "$lr" -gt "$(fm_first "am start")" ]; then
            echo "$leg: ok adb log: \`settings put system fan_mode 3; settings put system fan_speed 7\` is the last fan write, after \`am start\`"
        else
            echo "$leg: red adb log: last restore line ${lr:-none}, last fan write line ${lm:-none}"
        fi
        [ "$(cat "$FM/mode" 2>/dev/null) $(cat "$FM/speed" 2>/dev/null)" = "3 7" ] && echo "$leg: ok the device reads the prior 3/7" \
            || echo "$leg: red the device reads [$(cat "$FM/mode" 2>/dev/null) $(cat "$FM/speed" 2>/dev/null)]"
        grep -q '^FAN: restored=\[3 7\] to=\[3 7\] fan_restored=true' "$FM/run.log" \
            && echo "$leg: ok run.log: FAN: restored=[3 7] to=[3 7] fan_restored=true" \
            || echo "$leg: red run.log has no FAN: restored=[3 7] true line: $(grep '^FAN:' "$FM/run.log" | tail -1)"
        [ "$(fm_json 'd["fan_request"]["fan_restored"], d["fan_request"]["prior"], d["fan_request"]["restored"]')" \
              = "(True, {'fan_mode': 3, 'fan_speed': 7}, {'fan_mode': 3, 'fan_speed': 7})" ] \
            && echo "$leg: ok perf_regimen.json fan_request restored 3/7 of prior 3/7" \
            || echo "$leg: red perf_regimen.json fan_request $(fm_json 'd["fan_request"]')"
    done
}

# set + sampled: the Nova at MAX, prior REST with the slider never moved.
rc=$(FAN_MODE=customize:100 fm_soak "$TESTING/soak_title.sh" 0 "$NOVA_FAN_REST" null 3); fm_noduty
[ "$rc" = 0 ] && ok "set: the soak ran to its deadline" || bad "set: rc=$rc: $(tail -3 "$FM/run.log")"
[ "$(cat "$FM/at_start" 2>/dev/null)" = "6 100" ] && ok "set: FAN_MODE=customize:100 started the title at fan_mode 6, fan_speed 100" \
    || bad "set: the title started at [$(cat "$FM/at_start" 2>/dev/null)], not [6 100]"
lset=$(fm_first "shell settings put system fan_mode 6; settings put system fan_speed 100")
lmax=$(fm_last "settings put system performance_mode 2; settings put system fan_mode $NOVA_FAN_MAX")
lam=$(fm_first "am start")
[ -n "$lset" ] && [ -n "$lam" ] && [ -n "$lmax" ] && [ "$lmax" -lt "$lset" ] && [ "$lset" -lt "$lam" ] \
    && ok "set: adb got MAX (line $lmax), then \`fan_mode 6; fan_speed 100\` (line $lset), then \`am start\` (line $lam)" \
    || bad "set: MAX line ${lmax:-none}, fan line ${lset:-none}, am start line ${lam:-none}"
[ "$(fm_json 'd["fan_request"]["requested"], d["fan_request"]["want"], d["fan_request"]["ran"], d["fan_request"]["prior"], d["fan_request"]["perf_mode"], d["fan_request"]["offered"], d["fan_mode"]')" \
      = "('customize:100', {'fan_mode': 6, 'fan_speed': 100}, {'fan_mode': 6, 'fan_speed': 100}, {'fan_mode': $NOVA_FAN_REST, 'fan_speed': None}, 2, ['smart', 'sport', 'customize:<0-100>'], 6)" ] \
    && ok "set: perf_regimen.json requested customize:100 -> 6/100 at performance_mode 2 (shown: smart, sport, customize), ran 6/100, prior $NOVA_FAN_REST/null" \
    || bad "set: perf_regimen.json: $(tr -d '\n ' < "$FM/perf_regimen.json" 2>/dev/null | head -c 900)"
smodes=$(python3 -c 'import json,sys
rs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
print(" ".join("%s:%s" % (r.get("label"), (r.get("fan") or {}).get("mode")) for r in rs))' "$FM/thermal.jsonl" 2>/dev/null)
nh=$(printf '%s\n' $smodes | grep -c '^hold:')
if [ -n "$smodes" ] && [ "$nh" -ge 2 ] && ! printf '%s\n' $smodes | grep -qv ':6$'; then
    ok "sampled: every thermal.jsonl sample reads fan.mode 6 [$smodes]"
else
    bad "sampled: thermal.jsonl samples [$smodes] ($nh hold)"
fi
grep -q '^THERMAL: .*at fan_mode 6$' "$FM/run.log" && ok "sampled: the THERMAL summary names fan_mode 6" \
    || bad "sampled: THERMAL line [$(grep '^THERMAL:' "$FM/run.log")]"
[ "$(cat "$FM/mode") $(cat "$FM/speed")" = "$NOVA_FAN_REST null" ] \
    && [ "$(fm_last "shell settings put system fan_mode $NOVA_FAN_REST; settings delete system fan_speed")" != "" ] \
    && ok "nullspeed: the slider never moved before the soak is deleted again; the device reads $NOVA_FAN_REST/null" \
    || bad "nullspeed: the device reads [$(cat "$FM/mode") $(cat "$FM/speed")]; $(grep '^FAN: restored' "$FM/run.log")"

# rest: performance_mode 0 shows quiet; no slider, so no fan_speed write.
rc=$(PERF_REGIMEN=rest FAN_MODE=quiet fm_soak "$TESTING/soak_title.sh" 0 "$NOVA_FAN_REST" null 1); fm_noduty
[ "$rc" = 0 ] && [ "$(cat "$FM/at_start" 2>/dev/null)" = "1 null" ] && ! grep -q 'fan_speed [0-9]' "$FM/adb.log" \
    && [ "$(fm_json 'd["fan_request"]["perf_mode"], d["fan_request"]["offered"]')" = "(0, ['off', 'quiet', 'smart', 'sport'])" ] \
    && ok "rest: FAN_MODE=quiet at REST starts at fan_mode 1, writes no fan_speed; shown at 0: off, quiet, smart, sport" \
    || bad "rest: rc=$rc at_start [$(cat "$FM/at_start" 2>/dev/null)]; $(fm_json 'd["fan_request"]'); $(grep -m1 '^fan-mode\|^FAN:' "$FM/run.log")"

# settle: SystemUI's tile puts fan_mode 4 back once, just after the write.
touch "$FM/tile_once"
rc=$(FAN_MODE=customize:100 fm_soak "$TESTING/soak_title.sh" 0 "$NOVA_FAN_REST" null 1); fm_noduty
rm -f "$FM/tile_once"
grep -q '^FAN: read \[4 100\] 0.1s after the write, not \[6 100\]; written again' "$FM/run.log" \
    && [ "$(cat "$FM/at_start" 2>/dev/null)" = "6 100" ] \
    && ok "settle: a tile that moves fan_mode after the write is named, written again, and the title starts at 6/100" \
    || bad "settle: rc=$rc at_start [$(cat "$FM/at_start" 2>/dev/null)]; $(grep '^FAN:' "$FM/run.log" | head -2 | tr '\n' ';')"

# moved: the charger trigger puts Smart on under the title.
touch "$FM/charger"
rc=$(FAN_MODE=customize:100 fm_soak "$TESTING/soak_title.sh" 0 "$NOVA_FAN_REST" null 3); fm_noduty
rm -f "$FM/charger"
grep -q '^FAN: fan_mode read \[4\] at [0-9]*s, not 6$' "$FM/run.log" && [ "$(fm_json 'd["fan_request"]["moved"] >= 1')" = True ] \
    && ok "moved: a hold sample at fan_mode 4 is named in run.log and counted moved $(fm_json 'd["fan_request"]["moved"]')" \
    || bad "moved: $(grep '^FAN: fan_mode read' "$FM/run.log" | head -1); moved $(fm_json 'd["fan_request"]["moved"]')"

# end + killed, against the real soak.
while IFS= read -r line; do
    case "$line" in
        *": ok "*) ok "${line/: ok /: }" ;;
        *) bad "$line" ;;
    esac
done < <(fm_restore_legs "$TESTING/soak_title.sh")

# refused: <regimen> <perf0> <FAN_MODE> <why fragment>
while read -r reg perf0 want why; do
    rc=$(PERF_REGIMEN="$reg" FAN_MODE="$want" fm_soak "$TESTING/soak_title.sh" "$perf0" "$NOVA_FAN_REST" null 1); fm_noduty
    if [ "$rc" = 6 ] && grep -q "^fan-mode-refused: fan_mode '$want' is $why" "$FM/run.log" \
        && [ ! -f "$FM/started" ] && ! grep -q 'settings put\|settings delete' "$FM/adb.log" \
        && [ "$(fm_json 'd["fan_request"]["refused"] is not None, d["fan_request"]["ran"]')" = "(True, None)" ]; then
        ok "refused: $reg, FAN_MODE=$want exits 6: \`$(grep '^fan-mode-refused:' "$FM/run.log" | cut -c19-120)...\`; no am start, no settings write"
    else
        bad "refused: $reg, FAN_MODE=$want rc=$rc; $(grep -m1 'fan-mode' "$FM/run.log"); started=$([ -f "$FM/started" ] && echo yes || echo no)"
    fi
done <<'LEGS'
max 0 turbo not a fan setting this device offers
max 0 6 not a fan setting this device offers
max 0 quiet not shown at performance_mode 2
max 0 off not shown at performance_mode 2
rest 0 customize:50 not shown at performance_mode 0
off 1 off not shown at performance_mode 1
max 0 customize:101 not a position
max 0 customize not a position
max 0 customize:x not a position
max 0 smart:5 not a position
LEGS

# none: no FAN_MODE, the fan is the regimen's.
fm_soak "$TESTING/soak_title.sh" 0 "$NOVA_FAN_REST" null 2 >/dev/null; fm_noduty
if [ -z "$(fm_first "shell settings put system fan_mode")" ] && [ "$(cat "$FM/at_start")" = "$NOVA_FAN_MAX null" ] \
    && [ "$(fm_json 'd["fan_request"]')" = None ] && ! grep -q '^FAN:' "$FM/run.log"; then
    ok "none: no FAN_MODE writes no fan setting but the regimen's; the title started at MAX's fan $NOVA_FAN_MAX"
else
    bad "none: started at [$(cat "$FM/at_start")]; $(grep -c 'shell settings put system fan_mode' "$FM/adb.log") lone fan writes"
fi

# request: the field (in upper case), then the env entry, from running/<id>.req.
mkdir -p "$FM/d/results/r1" "$FM/d/running"
for body in '{"title":"x","fan_mode":"CUSTOMIZE:100","env":["HAKUX_X=1"]}' '{"title":"x","env":["HAKUX_X=1","FAN_MODE=customize:100"]}'; do
    echo "$body" > "$FM/d/running/r1.req"
    CAPTURE_LOG="$FM/d/results/r1/logcat.txt" fm_soak "$TESTING/soak_title.sh" 0 "$NOVA_FAN_REST" null 1 >/dev/null; fm_noduty
    [ "$(cat "$FM/at_start" 2>/dev/null)" = "6 100" ] && ok "request: $body starts the title at 6/100" \
        || bad "request: $body started at [$(cat "$FM/at_start" 2>/dev/null)]; $(grep -m1 '^fan-mode\|^FAN:' "$FM/run.log")"
done

[ "$FM_DUTY_WRITES" = 0 ] && ok "noduty: no soak in this fragment wrote to a /sys node" \
    || bad "noduty: $FM_DUTY_WRITES soaks wrote to a /sys node"

# The mutant: release() without fan_leave. `end` and `killed` must both go red.
anchor="    fan_leave
    perf_leave"
# python, not grep -F: grep takes a two-line pattern as two patterns, and
# `perf_leave` alone would match a release() that has lost fan_leave.
if python3 -c 'import sys; s=open(sys.argv[1]).read(); a=sys.argv[3]
if a not in s: sys.exit(1)
open(sys.argv[2],"w").write(s.replace(a, "    perf_leave", 1))' \
        "$TESTING/soak_title.sh" "$FM/t/soak_title.sh" "$anchor"; then
    mres=$(fm_restore_legs "$FM/t/soak_title.sh")
    printf '%s\n' "$mres" | grep -q '^end: red' && printf '%s\n' "$mres" | grep -q '^killed: red' \
        && ok "mutant 'no fan_leave in release()' is caught by end and killed ($(printf '%s\n' "$mres" | grep -c ': red') red)" \
        || bad "mutant 'no fan_leave in release()' SURVIVED: $(printf '%s\n' "$mres" | tr '\n' ';')"
else
    bad "mutant: the fan_leave/perf_leave anchor is gone from release() -- update the mutant"
fi
