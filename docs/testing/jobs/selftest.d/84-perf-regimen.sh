# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# ok/bad. Not executable, no shebang, no exit -- `fail` is shared.
#
# The gameplay regimen (soak_title.sh perf_enter/perf_leave, devices.sh
# device_perf_*): a title soak runs at MAX performance and fan and leaves the
# device at REST on every exit path. Driven against a fake adb that keeps the
# two settings in a file, so "the device" here is that file.
#
# THE LEGS, and the world in which each one fails:
#   exit 0     the hold runs out. Fails if REST is restored anywhere but a
#              path every exit takes, or not at all.
#   exit !=0   the script dies right after `am start` (a mutant copy with an
#              `exit 3` there, standing for any fatal error). Fails if REST is
#              restored only at the end of the happy path.
#   TERM       killed mid-hold, as timeout(1) or a preemption does. Fails if
#              TERM is not trapped, and -- the second assertion -- if a
#              trapped TERM returns into the hold loop instead of exiting,
#              which is what `trap release EXIT INT TERM` did.
#   MAX ran    the fake records the modes at the moment of `am start`. Fails
#              if the switch to MAX happens after the title starts, or never.
#   read-back  a fake whose writes are ignored. Fails if perf_restored is
#              computed from what was asked rather than what the device says.
#   pgraph     run_disc.sh never calls device_perf_set. Fails if a disc run
#              starts touching the modes, which the brief rules out.
# And three mutants of soak_title.sh that must each turn a leg red.

echo "== perf regimen: MAX during a title soak, REST on every exit"
PR="$T/perfreg"; rm -rf "$PR"; mkdir -p "$PR/bin"
cat > "$PR/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
S="$PERF_FAKE/state"; [ -f "$S" ] || echo "0 4" > "$S"
case "$*" in
    *"settings put system performance_mode"*)
        [ -f "$PERF_FAKE/ignore_writes" ] && exit 0
        set -- $(printf '%s\n' "$*" | sed -n 's/.*performance_mode \([0-9-]*\).*fan_mode \([0-9-]*\).*/\1 \2/p')
        echo "$1 $2" > "$S" ;;
    *"settings get system performance_mode"*) cat "$S" ;;
    *"am start"*) cp "$S" "$PERF_FAKE/at_start"; touch "$PERF_FAKE/started" ;;
    *"ps -A -o NAME"*)
        printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$PR/bin/adb"
# Every run starts where the Nova was found on 2026-09-26, performance 1 and
# fan 4 -- not REST -- so "left at REST" cannot pass by never writing.
echo "1 4" > "$PR/seed"
# Mutant copies run from a scratch tree beside a link to devices.sh (the
# soak sources it from its own directory), never from the repository's.
mkdir -p "$PR/t"; ln -sf "$TESTING/devices.sh" "$PR/t/devices.sh"

# The legs below run as the Nova (ee317437), whose MAX is 2/5; the Thor leg
# sets PERF_SERIAL=bdc158a5.
perf_soak() {   # <soak_title.sh> <hold seconds> [TERM-after-start] -> rc on stdout
    local s="$1" hold="$2" term="${3:-}" pid rc
    rm -f "$PR/started" "$PR/at_start" "$PR/state" "$PR/perf_regimen.json"
    cp "$PR/seed" "$PR/state"
    : > "$PR/logcat.txt"
    PATH="$PR/bin:$PATH" PERF_FAKE="$PR" SERIAL="${PERF_SERIAL:-ee317437}" \
        HAKUX_DEVICE_LEASE="$PR/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 \
        PERF_RESULT="$PR/perf_regimen.json" \
        timeout 60 bash "$s" /fake/iso.iso "$hold" > "$PR/run.log" 2>&1 &
    pid=$!
    if [ -n "$term" ]; then
        for _ in $(seq 100); do [ -f "$PR/started" ] && break; sleep 0.1; done
        sleep 0.5
        # The soak, not timeout(1): pkill -P names the child by its parent PID.
        pkill -TERM -P "$pid"
    fi
    wait "$pid"; rc=$?
    echo "$rc"
}
perf_json() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2]))' "$PR/perf_regimen.json" "$1" 2>/dev/null; }

# exit 0
rc=$(perf_soak "$TESTING/soak_title.sh" 1)
[ "$rc" = 0 ] && ok "exit 0: the soak ran to its deadline" || bad "exit 0: rc=$rc: $(tail -3 "$PR/run.log")"
[ "$(cat "$PR/at_start" 2>/dev/null)" = "2 5" ] && ok "MAX ran: the title started at performance 2, fan 5" \
    || bad "MAX ran: the title started at [$(cat "$PR/at_start" 2>/dev/null)], not [2 5]"
[ "$(cat "$PR/state")" = "0 4" ] && ok "exit 0: the device is left at REST 0/4" \
    || bad "exit 0: the device is left at [$(cat "$PR/state")]"
[ "$(perf_json perf_restored)/$(perf_json perf_mode)/$(perf_json fan_mode)" = "True/2/5" ] \
    && ok "exit 0: perf_regimen.json says perf_mode 2, fan_mode 5, perf_restored true" \
    || bad "exit 0: perf_regimen.json: $(cat "$PR/perf_regimen.json" 2>/dev/null | tr -d '\n')"
grep -q "^PERF: restored=\[0 4\] perf_restored=true" "$PR/run.log" \
    && ok "exit 0: run.log carries the PERF: restore line" || bad "exit 0: no PERF: restore line in run.log"

# exit != 0: a copy that dies right after `am start`.
sed_anchor='a shell log -t hakuX-route "'"'"'soak start'"'"'" >/dev/null 2>&1'
if grep -qF "$sed_anchor" "$TESTING/soak_title.sh"; then
    python3 - "$TESTING/soak_title.sh" "$PR/soak_die.sh" "$sed_anchor" <<'PY'
import sys
src, dst, anchor = sys.argv[1:4]
s = open(src).read()
open(dst, "w").write(s.replace(anchor, anchor + "\nexit 3", 1))
PY
    cp "$PR/soak_die.sh" "$PR/t/soak_title.sh"
    rc=$(perf_soak "$PR/t/soak_title.sh" 30)
    [ "$rc" = 3 ] && ok "exit 3: the dying copy exited 3" || bad "exit 3: rc=$rc"
    [ "$(cat "$PR/at_start" 2>/dev/null)" = "2 5" ] && [ "$(cat "$PR/state")" = "0 4" ] \
        && ok "exit 3: MAX at start, REST after a non-zero exit" \
        || bad "exit 3: at start [$(cat "$PR/at_start" 2>/dev/null)], after [$(cat "$PR/state")]"
    [ "$(perf_json perf_restored)" = True ] && ok "exit 3: perf_restored true" \
        || bad "exit 3: perf_restored is $(perf_json perf_restored)"
else
    bad "exit 3: the soak-start anchor is gone from soak_title.sh -- update this leg"
fi

# TERM mid-hold: 30 s hold, TERM half a second after `am start`.
t0=$(date +%s)
rc=$(perf_soak "$TESTING/soak_title.sh" 30 term)
dt=$(( $(date +%s) - t0 ))
[ "$rc" = 143 ] && ok "TERM: the soak exited 143" || bad "TERM: rc=$rc"
[ "$dt" -lt 15 ] && ok "TERM: it exited in ${dt}s, not at its 30 s deadline" \
    || bad "TERM: it took ${dt}s -- a trapped TERM went back into the hold loop"
[ "$(cat "$PR/state")" = "0 4" ] && [ "$(perf_json perf_restored)" = True ] \
    && ok "TERM: the device is left at REST, perf_restored true" \
    || bad "TERM: left at [$(cat "$PR/state")], perf_restored $(perf_json perf_restored)"

# PERF_REGIMEN=rest: the pilot's control arm starts at REST, not at MAX.
PERF_REGIMEN=rest perf_soak "$TESTING/soak_title.sh" 1 >/dev/null
[ "$(cat "$PR/at_start" 2>/dev/null)" = "0 4" ] && ok "rest arm: the title started at REST 0/4" \
    || bad "rest arm: the title started at [$(cat "$PR/at_start" 2>/dev/null)]"

# A queued soak's request picks the arm: `request.sh --env PERF_REGIMEN=rest`.
# Laid out as the dispatcher does, results/<id>/logcat.txt beside
# running/<id>.req. Fails if the request is not found from CAPTURE_LOG, or its
# env is not read -- then the REST arm of the Thor pilot runs at MAX.
mkdir -p "$PR/d/results/r1" "$PR/d/running"
echo '{"title":"x","env":["HAKUX_X=1","PERF_REGIMEN=rest"]}' > "$PR/d/running/r1.req"
CAPTURE_LOG="$PR/d/results/r1/logcat.txt" perf_soak "$TESTING/soak_title.sh" 1 >/dev/null
[ "$(cat "$PR/at_start" 2>/dev/null)" = "0 4" ] && [ "$(perf_json regimen)" = rest ] \
    && ok "request env: PERF_REGIMEN=rest in the running request starts the title at REST" \
    || bad "request env: started at [$(cat "$PR/at_start" 2>/dev/null)], regimen $(perf_json regimen)"
echo '{"title":"x","env":["HAKUX_X=1"]}' > "$PR/d/running/r1.req"
CAPTURE_LOG="$PR/d/results/r1/logcat.txt" perf_soak "$TESTING/soak_title.sh" 1 >/dev/null
[ "$(cat "$PR/at_start" 2>/dev/null)" = "2 5" ] && ok "request env: a request without it runs at MAX" \
    || bad "request env: a request without PERF_REGIMEN started at [$(cat "$PR/at_start" 2>/dev/null)]"

# The Thor's fan MAX is not SPORT (5). Hot (66-74 C), SMART (4) ran
# 25000-29000 duty and SPORT a fixed 25000, so 5 cools less than REST under
# gameplay (NOTES 5d, audit M1). Fails if the Thor row goes back to 5, or if
# the soak takes its values from anywhere but the serial's own row.
read -r _ thor_fan_max _ _ <<<"$(bash -c '. "$1"; device_perf_values bdc158a5' _ "$TESTING/devices.sh")"
[ -n "$thor_fan_max" ] && [ "$thor_fan_max" != 5 ] \
    && ok "thor: device_perf_values gives fan MAX $thor_fan_max, not 5 (SPORT)" \
    || bad "thor: device_perf_values gives fan MAX [$thor_fan_max]"
PERF_SERIAL=bdc158a5 perf_soak "$TESTING/soak_title.sh" 1 >/dev/null
[ "$(cat "$PR/at_start" 2>/dev/null)" = "2 $thor_fan_max" ] && [ "$(cat "$PR/state")" = "0 4" ] \
    && ok "thor: the title started at 2/$thor_fan_max and the device is left at REST 0/4" \
    || bad "thor: started at [$(cat "$PR/at_start" 2>/dev/null)], left at [$(cat "$PR/state")]"

# Read-back: writes that do nothing must read as not restored.
touch "$PR/ignore_writes"
perf_soak "$TESTING/soak_title.sh" 1 >/dev/null
rm -f "$PR/ignore_writes"
[ "$(perf_json perf_restored)" = False ] && ok "read-back: ignored writes record perf_restored false" \
    || bad "read-back: ignored writes record perf_restored $(perf_json perf_restored)"

# pgraph/disc runs never touch the modes. On the call, not the prose.
if grep -qE '^[^#]*device_perf_(set|get)' "$TESTING/run_disc.sh"; then
    bad "pgraph: run_disc.sh calls device_perf_* -- disc runs must not switch modes"
else
    ok "pgraph: run_disc.sh does not switch modes"
fi

# Mutants: each must turn a leg red, or the leg is looking at nothing.
perf_mutant() {   # <name> <old> <new> <leg: exit0|term> <assert: rest|prompt>
    local name="$1" old="$2" new="$3" leg="$4" what="$5" m="$PR/t/soak_title.sh" rc t0 dt caught=0
    if ! grep -qF "$old" "$TESTING/soak_title.sh"; then
        bad "perf mutant '$name': its anchor is gone from soak_title.sh -- update the mutant"; return
    fi
    python3 -c 'import sys; s=open(sys.argv[1]).read(); open(sys.argv[2],"w").write(s.replace(sys.argv[3], sys.argv[4], 1))' \
        "$TESTING/soak_title.sh" "$m" "$old" "$new"
    t0=$(date +%s)
    if [ "$leg" = term ]; then rc=$(perf_soak "$m" 8 term); else rc=$(perf_soak "$m" 1); fi
    dt=$(( $(date +%s) - t0 ))
    case "$what" in
        rest)   [ "$(cat "$PR/state")" = "0 4" ] || caught=1 ;;
        prompt) [ "$dt" -lt 6 ] || caught=1 ;;
    esac
    [ "$caught" = 1 ] && ok "perf mutant '$name' is caught" || bad "perf mutant '$name' SURVIVED"
}
perf_mutant "no restore in release()" "    perf_leave
    a shell input keyevent KEYCODE_SLEEP" "    a shell input keyevent KEYCODE_SLEEP" exit0 rest
perf_mutant "TERM returns into the hold loop" "
trap 'exit 143' TERM
" "
trap release TERM
" term prompt
perf_mutant "no EXIT trap: a TERM exits without restoring" \
    "
trap release EXIT
" "
trap - EXIT
" term rest
