# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The per-request fan duty (#507 D.3; soak_title.sh THE FAN DUTY, devices.sh
# device_fan_*): FAN_DUTY puts fan_mode 6 (CUSTOM) and the duty on the fan
# before `am start`, writes the duty again after every hold-loop thermal
# sample, and puts the device's REST fan mode back on every exit. Driven
# against a fake adb that keeps fan_mode, duty and period in files and logs
# every command it is given, so the assertions are on the adb command words.
#
# THE LEGS, and the world in which each one fails:
#   set        FAN_DUTY=50000 on the Nova at MAX: `fan_mode 6` then `echo
#              50000 > .../duty` reach adb before `am start`, and the title
#              starts at 6/50000. Fails if the duty is written after the
#              title starts, or never, or the mode write comes after it.
#   rewrite    a 3 s hold at THERMAL_EVERY_S=1 logs at least two `was ...;
#              echo 50000 > duty` re-writes. Fails if the re-write is not in
#              the hold loop, or runs once.
#   firmware   a fake that puts 25000 back between samples: run.log names
#              `FAN: duty read [25000]` and perf_regimen.json counts it
#              `moved`. Fails if the re-write reads after it writes (it would
#              always read 50000), or a moved duty is not recorded.
#   end        PERF_REGIMEN=off, so nothing but the fan restore can write
#              fan_mode 4: the hold runs out, the last fan_mode written is 4
#              and it comes after the last duty write, no duty is written
#              after it, the device reads 4, and run.log says `FAN:
#              restored=[4 ...] fan_restored=true`. Fails if release() does
#              not restore, or restores only on the happy path's end.
#   killed     the same, TERM half a second after `am start`. Fails if the
#              restore is not reached from the EXIT trap.
#   refused    FAN_DUTY=60000 (above the period) and `fast`: exit 6, a
#              `fan-duty-refused:` line, no `am start`, no fan write. Fails if
#              a run the fan cannot hold goes ahead at another fan.
#   none       no FAN_DUTY: no duty write, no re-write. Fails if a run that
#              asked for nothing has its fan moved.
#   request    `"fan_duty": 50000` in the running request, then `FAN_DUTY=
#              30000` in its env: each is the duty the title starts at.
#              Fails if the dispatcher's request is not read.
#   path       devices.sh DEVICE_FAN_PWM_DIR is thermal_state.py FAN_DIR.
#              Fails if the node written and the node sampled part.
# And one mutant: release() without fan_leave must turn `end` and `killed` red.

echo "== fan duty: CUSTOM + duty during a soak, re-written per sample, REST fan after (#507)"
FD="$T/fanduty"; rm -rf "$FD"; mkdir -p "$FD/bin" "$FD/t"
cat > "$FD/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
F="$FAN_FAKE"
[ -f "$F/perf" ] || echo 1 > "$F/perf"
[ -f "$F/mode" ] || echo 4 > "$F/mode"
[ -f "$F/duty" ] || echo 12000 > "$F/duty"
[ "$1" = shell ] && printf '%s\n' "$*" >> "$F/adb.log"
# The firmware: every mode but CUSTOM owns the duty (SMART idles at 12000).
fw() { [ "$(cat "$F/mode")" = 6 ] || echo 12000 > "$F/duty"; }
case "$*" in
    *"settings put system performance_mode"*)
        set -- $(printf '%s\n' "$*" | sed -n 's/.*performance_mode \([0-9-]*\).*fan_mode \([0-9-]*\).*/\1 \2/p')
        echo "$1" > "$F/perf"; echo "$2" > "$F/mode"; fw ;;
    *"settings get system performance_mode"*) echo "$(cat "$F/perf") $(cat "$F/mode")" ;;
    *"echo \"was "*)
        # The firmware putting its own duty back since the last write.
        [ -f "$F/firmware_resets" ] && echo 25000 > "$F/duty"
        echo "was $(cat "$F/duty")"
        printf '%s\n' "$*" | sed -n 's/.*echo \([0-9]*\) > .*duty.*/\1/p' > "$F/duty" ;;
    *"settings put system fan_mode 6; sleep 1; echo "*)
        echo 6 > "$F/mode"
        printf '%s\n' "$*" | sed -n 's/.*echo \([0-9]*\) > .*duty.*/\1/p' > "$F/duty" ;;
    *"settings put system fan_mode "*)
        printf '%s\n' "$*" | sed -n 's/.*fan_mode \([0-9-]*\).*/\1/p' > "$F/mode"; fw ;;
    *"gpio5_pwm2/period"*) echo "fan $(cat "$F/mode") $(cat "$F/duty") 50000" ;;
    *"am start"*) echo "$(cat "$F/mode") $(cat "$F/duty")" > "$F/at_start"; touch "$F/started" ;;
    *"ps -A -o NAME"*)
        printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$FD/bin/adb"
ln -sf "$TESTING/devices.sh" "$FD/t/devices.sh"

fan_soak() {   # <soak_title.sh> <hold seconds> [term] -> rc on stdout
    local s="$1" hold="$2" term="${3:-}" pid rc
    rm -f "$FD/started" "$FD/at_start" "$FD/perf" "$FD/mode" "$FD/duty" \
          "$FD/adb.log" "$FD/perf_regimen.json"
    PATH="$FD/bin:$PATH" FAN_FAKE="$FD" SERIAL=ee317437 \
        HAKUX_DEVICE_LEASE="$FD/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 \
        THERMAL_EVERY_S=1 PERF_RESULT="$FD/perf_regimen.json" \
        timeout 60 bash "$s" /fake/iso.iso "$hold" > "$FD/run.log" 2>&1 &
    pid=$!
    if [ -n "$term" ]; then
        for _ in $(seq 100); do [ -f "$FD/started" ] && break; sleep 0.1; done
        sleep 0.5
        pkill -TERM -P "$pid"
    fi
    wait "$pid"; rc=$?
    echo "$rc"
}
fan_json() {   # <python expr over d> -> its value, or ERR
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' \
        "$FD/perf_regimen.json" "$1" 2>/dev/null || echo ERR
}
# The line numbers in adb.log of the last command matching each pattern.
fan_last() { grep -nF -- "$1" "$FD/adb.log" 2>/dev/null | tail -1 | cut -d: -f1; }
fan_first() { grep -nF -- "$1" "$FD/adb.log" 2>/dev/null | head -1 | cut -d: -f1; }

# The restore legs, as a function so the mutant runs the same assertions.
# Prints one `leg: ok|red <why>` line per assertion.
fan_restore_legs() {   # <soak_title.sh>
    local s="$1" rc lw lr lm
    for leg in end killed; do
        if [ "$leg" = end ]; then
            rc=$(PERF_REGIMEN=off FAN_DUTY=50000 fan_soak "$s" 1)
        else
            rc=$(PERF_REGIMEN=off FAN_DUTY=50000 fan_soak "$s" 30 term)
        fi
        [ "$leg" = end ] && [ "$rc" != 0 ] && { echo "$leg: red rc=$rc"; continue; }
        [ "$leg" = killed ] && [ "$rc" != 143 ] && { echo "$leg: red rc=$rc"; continue; }
        lw=$(fan_last "> /sys/class/gpio5_pwm2/duty")
        lr=$(fan_last "settings put system fan_mode 4")
        lm=$(fan_last "settings put system fan_mode")
        if [ -n "$lr" ] && [ -n "$lw" ] && [ "$lr" -gt "$lw" ] && [ "$lr" = "$lm" ]; then
            echo "$leg: ok adb log: \`settings put system fan_mode 4\` is the last fan_mode write and follows the last duty write"
        else
            echo "$leg: red adb log: last duty write line ${lw:-none}, last fan_mode 4 line ${lr:-none}, last fan_mode line ${lm:-none}"
        fi
        [ "$(cat "$FD/mode" 2>/dev/null)" = 4 ] && echo "$leg: ok the device reads fan_mode 4" \
            || echo "$leg: red the device reads fan_mode [$(cat "$FD/mode" 2>/dev/null)]"
        grep -q '^FAN: restored=\[4 12000 50000\] fan_restored=true' "$FD/run.log" \
            && echo "$leg: ok run.log: FAN: restored=[4 12000 50000] fan_restored=true" \
            || echo "$leg: red run.log has no FAN: restored=[4 ...] true line: $(grep '^FAN:' "$FD/run.log" | tail -1)"
        [ "$(fan_json 'd["fan_duty"]["fan_restored"]')" = True ] \
            && echo "$leg: ok perf_regimen.json fan_duty.fan_restored true" \
            || echo "$leg: red perf_regimen.json fan_duty.fan_restored $(fan_json 'd["fan_duty"]["fan_restored"]')"
    done
}

# set + rewrite: the Nova at MAX (2/5), a 3 s hold.
rc=$(FAN_DUTY=50000 fan_soak "$TESTING/soak_title.sh" 3)
[ "$rc" = 0 ] && ok "set: the soak ran to its deadline" || bad "set: rc=$rc: $(tail -3 "$FD/run.log")"
[ "$(cat "$FD/at_start" 2>/dev/null)" = "6 50000" ] && ok "set: the title started at fan_mode 6, duty 50000" \
    || bad "set: the title started at [$(cat "$FD/at_start" 2>/dev/null)], not [6 50000]"
lset=$(fan_first "settings put system fan_mode 6; sleep 1; echo 50000 > /sys/class/gpio5_pwm2/duty")
lmax=$(fan_last "settings put system performance_mode 2; settings put system fan_mode 5")
lam=$(fan_first "am start")
[ -n "$lset" ] && [ -n "$lam" ] && [ -n "$lmax" ] && [ "$lmax" -lt "$lset" ] && [ "$lset" -lt "$lam" ] \
    && ok "set: adb got MAX (line $lmax), then \`fan_mode 6; sleep 1; echo 50000 > duty\` (line $lset), then \`am start\` (line $lam)" \
    || bad "set: MAX line ${lmax:-none}, duty set line ${lset:-none}, am start line ${lam:-none}"
nre=$(grep -c 'echo "was .*echo 50000 > /sys/class/gpio5_pwm2/duty' "$FD/adb.log" 2>/dev/null)
[ "${nre:-0}" -ge 2 ] && ok "rewrite: $nre re-writes of 50000 in a 3 s hold at one per second" \
    || bad "rewrite: ${nre:-0} re-writes of 50000 in the adb log"
lre=$(fan_first 'echo "was')
[ -n "$lre" ] && [ "$lre" -gt "$lam" ] && ok "rewrite: the first re-write follows \`am start\`" \
    || bad "rewrite: first re-write line ${lre:-none}, am start line $lam"
[ "$(fan_json 'd["fan_duty"]["requested"], d["fan_duty"]["ran"]["fan_mode"], d["fan_duty"]["ran"]["duty"], d["fan_duty"]["period"], d["fan_mode"], d["fan_duty"]["moved"], d["fan_duty"]["rewrites"] >= 2')" \
      = "(50000, 6, 50000, 50000, 6, 0, True)" ] \
    && ok "set: perf_regimen.json requested 50000, ran 6/50000 of 50000, fan_mode 6, moved 0, rewrites >= 2" \
    || bad "set: perf_regimen.json: $(tr -d '\n ' < "$FD/perf_regimen.json" 2>/dev/null | head -c 600)"
# At MAX the regimen's own restore also writes fan 4; the duty restore still says so.
[ "$(cat "$FD/mode")" = 4 ] && grep -q '^FAN: restored=\[4 ' "$FD/run.log" \
    && ok "set: left at fan_mode 4, and run.log says FAN: restored=[4 ...]" \
    || bad "set: left at fan_mode [$(cat "$FD/mode")]; $(grep '^FAN:' "$FD/run.log" | tail -1)"

# firmware: the duty is found at 25000 before every re-write.
touch "$FD/firmware_resets"
FAN_DUTY=50000 fan_soak "$TESTING/soak_title.sh" 3 >/dev/null
rm -f "$FD/firmware_resets"
grep -q '^FAN: duty read \[25000\] at [0-9]*s, not 50000; written again' "$FD/run.log" \
    && [ "$(fan_json 'd["fan_duty"]["moved"] >= 2')" = True ] \
    && ok "firmware: run.log names the duty read at 25000, and perf_regimen.json counts moved >= 2" \
    || bad "firmware: $(grep '^FAN: duty read' "$FD/run.log" | head -1); moved $(fan_json 'd["fan_duty"]["moved"]')"

# end + killed, against the real soak.
while IFS= read -r line; do
    case "$line" in
        *": ok "*) ok "${line/: ok /: }" ;;
        *) bad "$line" ;;
    esac
done < <(fan_restore_legs "$TESTING/soak_title.sh")
# After the restore, no duty is written: the firmware owns it again.
lr=$(fan_last "settings put system fan_mode 4"); lw=$(fan_last "> /sys/class/gpio5_pwm2/duty")
[ -n "$lr" ] && [ "$lw" -lt "$lr" ] && [ "$(cat "$FD/duty")" = 12000 ] \
    && ok "killed: no duty write after the restore; the firmware's 12000 is on the node" \
    || bad "killed: duty write line $lw after restore line $lr; node reads $(cat "$FD/duty")"

# refused: above the period, then not a number.
for want in 60000 fast; do
    rc=$(FAN_DUTY="$want" fan_soak "$TESTING/soak_title.sh" 1)
    if [ "$rc" = 6 ] && grep -q '^fan-duty-refused: ' "$FD/run.log" && [ ! -f "$FD/started" ] \
        && ! grep -q 'fan_mode 6\|> /sys/class/gpio5_pwm2/duty\|performance_mode 2' "$FD/adb.log"; then
        ok "refused: FAN_DUTY=$want exits 6 with \`$(grep '^fan-duty-refused:' "$FD/run.log" | cut -c1-70)...\`, no am start, no mode or duty write"
    else
        bad "refused: FAN_DUTY=$want rc=$rc; $(grep -m1 'fan-duty' "$FD/run.log"); started=$([ -f "$FD/started" ] && echo yes || echo no)"
    fi
done

# none: no FAN_DUTY, the fan is the regimen's.
fan_soak "$TESTING/soak_title.sh" 2 >/dev/null
if ! grep -q 'fan_mode 6\|> /sys/class/gpio5_pwm2/duty' "$FD/adb.log" && [ "$(cat "$FD/at_start")" = "5 12000" ] \
    && [ "$(fan_json 'd["fan_duty"]')" = None ] && ! grep -q '^FAN:' "$FD/run.log"; then
    ok "none: no FAN_DUTY writes no duty and no mode 6; the title started at the regimen's fan 5"
else
    bad "none: started at [$(cat "$FD/at_start")]; $(grep -c 'gpio5_pwm2/duty' "$FD/adb.log") duty writes"
fi

# request: the field, then the env entry, from running/<id>.req.
mkdir -p "$FD/d/results/r1" "$FD/d/running"
for body in '{"title":"x","fan_duty":50000,"env":["HAKUX_X=1"]}' '{"title":"x","env":["HAKUX_X=1","FAN_DUTY=30000"]}'; do
    echo "$body" > "$FD/d/running/r1.req"
    want=$(printf '%s' "$body" | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r.get("fan_duty") or [e.split("=")[1] for e in r["env"] if e.startswith("FAN_DUTY=")][0])')
    CAPTURE_LOG="$FD/d/results/r1/logcat.txt" THERMAL_COOL_C=off fan_soak "$TESTING/soak_title.sh" 1 >/dev/null
    [ "$(cat "$FD/at_start" 2>/dev/null)" = "6 $want" ] && ok "request: $body starts the title at 6/$want" \
        || bad "request: $body started at [$(cat "$FD/at_start" 2>/dev/null)]"
done

# path: one node, two readers.
dpath=$(bash -c '. "$1"; echo "$DEVICE_FAN_PWM_DIR"' _ "$TESTING/devices.sh")
tpath=$(cd "$TESTING" && python3 -c 'import thermal_state; print(thermal_state.FAN_DIR)')
[ -n "$dpath" ] && [ "$dpath" = "$tpath" ] && ok "path: devices.sh writes $dpath, thermal_state.py samples $tpath" \
    || bad "path: devices.sh [$dpath], thermal_state.py [$tpath]"

# The mutant: release() without fan_leave. `end` and `killed` must both go red.
anchor="    fan_leave
    perf_leave"
# python, not grep -F: grep takes a two-line pattern as two patterns, and
# `perf_leave` alone would match a release() that has lost fan_leave.
if python3 -c 'import sys; s=open(sys.argv[1]).read(); a=sys.argv[3]
if a not in s: sys.exit(1)
open(sys.argv[2],"w").write(s.replace(a, "    perf_leave", 1))' \
        "$TESTING/soak_title.sh" "$FD/t/soak_title.sh" "$anchor"; then
    mres=$(fan_restore_legs "$FD/t/soak_title.sh")
    printf '%s\n' "$mres" | grep -q '^end: red' && printf '%s\n' "$mres" | grep -q '^killed: red' \
        && ok "mutant 'no fan_leave in release()' is caught by end and killed ($(printf '%s\n' "$mres" | grep -c ': red') red)" \
        || bad "mutant 'no fan_leave in release()' SURVIVED: $(printf '%s\n' "$mres" | tr '\n' ';')"
else
    bad "mutant: the fan_leave/perf_leave anchor is gone from release() -- update the mutant"
fi
