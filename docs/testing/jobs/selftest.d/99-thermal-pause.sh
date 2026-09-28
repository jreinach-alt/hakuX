# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The thermal pause (#507): thermal_state.py's pause episodes and window test,
# soak_title.sh's thermal.jsonl, and title_verdict.py's `thermal-pause` void.
# Fixture samples are thermal.jsonl lines as thermal_state.py writes them; the
# soak legs run against a fake adb that answers the one-call sample script.
#
# THE LEGS, and the world in which each one fails:
#   onset      clean at +220 s, paused at +250 s, window +90..+240 s: flagged.
#              Fails if the onset is taken as the first paused sample (250 >
#              240, so nothing is flagged): the first-seen mutant below.
#   later      clean at +270 s, paused at +300 s, same window: not flagged.
#              Fails if any pause anywhere in the run voids the window.
#   none       a device with no cooling device at all: not flagged, and read
#              (exit 1, not 2). Fails if an empty device list reads as a
#              pause, or as unread (every Nova run would void or go unjudged).
#   unread     the one clean sample before the pause is an adb failure: the
#              bound widens to the clean sample before it, and a window ending
#              at +215 s is flagged. Fails if a failed read counts as clean.
#   all-fail   every sample failed: exit 2 `unread`, never `no pause`.
#   tail-gap   clean at +0, every later sample failed, window +60..+240 s:
#              exit 2 `unread: no reading at or after the window's end`.
#              Fails if a window no readable sample reaches reads as clean
#              (the #508 pass-1 M1 scenario: adb dies after a pause begins).
#   mid-gap    clean at +0 and +300 s, nine failures between: exit 2 `unread:
#              no reading from +0 s to +300 s`. Fails if only the tail is
#              tested. One failed sample (a 60 s gap, `unread` leg) is still
#              covered, so a lone adb blip does not void a run.
#   bad-pause  a `cd` line for thermal-pause-F8 with no cur_state makes the
#              sample an error. Fails if the device is dropped and the rest
#              of the sample reads clean.
#   per-core   `pause-cpu7` 1/1 alone is a pause. Fails if only the mask
#              devices (`thermal-pause-*`) are read.
#   not-pause  kgsl devfreq 5/8 alone is not a pause, and --diff names it.
#   soak       soak_title.sh writes thermal.jsonl: a `start` line before `am
#              start`, `hold` lines from the hold loop, an `end` line, and a
#              `THERMAL: pause thermal-pause-F8 1/1 began after` line in
#              run.log. Fails if the loop does not ride the hold (no hold
#              line) or the end sample is missing.
#   verdict    a played 60 fps run whose thermal.jsonl pauses inside the
#              scored window is void `thermal-pause:` with every fps field
#              null; the same run paused only after `soak end` is judged at
#              60 fps with the pause reported; with no thermal.jsonl it is
#              judged and `thermal.measured` is false; with the samples
#              after the mark all failed it is void `thermal-unread:` and
#              `thermal.window_covered` is false.

echo "== thermal pause: thermal_state.py bounds a sampled pause and tests a window (#507)"
TP="$T/thermalpause"; rm -rf "$TP"; mkdir -p "$TP/bin" "$TP/t"
# <file> <spec>...: each spec is <second>:<state>, state c (clean), p (thermal-
# pause-F8 1/1), k (clean, kgsl devfreq 5/8), u (per-core pause-cpu7 1/1),
# e (adb failed), n (a device with no cooling devices).
tp_fix() {
    python3 - "$@" <<'PY'
import json, sys, datetime as dt
path, specs = sys.argv[1], sys.argv[2:]
base = dt.datetime(2000, 9, 27, 13, 0, 0)
out = []
for spec in specs:
    sec, st = spec.split(":")
    rec = {"t": 1790000000 + int(sec), "label": "hold",
           "dev_time": (base + dt.timedelta(seconds=int(sec))).strftime("%m-%d %H:%M:%S"),
           "up": 100.0 + int(sec), "tz": [[90, "xo-therm", 77000]]}
    cool = [[10, "thermal-pause-F8", 1 if st == "p" else 0, 1],
            [15, "pause-cpu7", 1 if st == "u" else 0, 1],
            [34, "devfreq-3d00000.qcom,kgsl-3d0", 5 if st == "k" else 0, 8]]
    rec["cool"] = [] if st in "en" else cool
    if st == "e":
        rec["error"] = "adb: exit 1, ['error: closed']"
        rec["dev_time"] = None
    rec["pause"] = None if st == "e" else (st in "pu")
    out.append(json.dumps(rec))
open(path, "w").write("\n".join(out) + "\n")
PY
}
tp_win() {   # <thermal_state.py> <file> <lo> <hi> -> "rc|first line"
    local out rc
    out=$(python3 "$1" --window "$2" "$3" "$4" 2>&1); rc=$?
    printf '%s|%s\n' "$rc" "$(printf '%s\n' "$out" | head -1)"
}
tp_fix "$TP/onset.jsonl" 0:c 30:c 60:c 90:c 120:c 150:c 180:c 210:c 220:c 250:p 280:p 310:c
tp_fix "$TP/later.jsonl" 0:c 30:c 60:c 90:c 120:c 150:c 180:c 210:c 240:c 270:c 300:p 330:p
tp_fix "$TP/none.jsonl"  0:n 30:n 60:n 90:n 120:n 150:n 180:n 210:n 240:n 270:n
tp_fix "$TP/unread.jsonl" 0:c 30:c 60:c 90:c 120:c 150:c 180:c 210:c 220:e 250:p 280:c
tp_fix "$TP/allfail.jsonl" 0:e 30:e 60:e
tp_fix "$TP/tailgap.jsonl" 0:c 30:e 60:e 90:e 120:e 150:e 180:e 210:e 240:e 270:e 300:e
tp_fix "$TP/midgap.jsonl" 0:c 30:e 60:e 90:e 120:e 150:e 180:e 210:e 240:e 270:e 300:c
tp_fix "$TP/percore.jsonl" 0:c 30:c 60:c 90:c 120:u 150:c
tp_fix "$TP/kgsl.jsonl"  0:c 30:c 60:c 90:c 120:k 150:k
tp_legs() {    # <thermal_state.py> -> one "FAIL <why>" per unmet leg
    local s="$1" r
    r=$(tp_win "$s" "$TP/onset.jsonl" 90 240)
    case "$r" in "0|thermal-pause: thermal-pause-F8 1/1 began after +220 s and by +250 s (device 09-27 13:04:10); cleared by +310 s") ;;
        *) echo "FAIL onset: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/later.jsonl" 90 240)
    case "$r" in "1|no pause may overlap +90..+240 s") ;; *) echo "FAIL later: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/none.jsonl" 90 240)
    case "$r" in "1|no pause may overlap"*) ;; *) echo "FAIL none: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/unread.jsonl" 90 215)
    case "$r" in "0|thermal-pause: thermal-pause-F8 1/1 began after +210 s and by +250 s"*) ;;
        *) echo "FAIL unread: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/allfail.jsonl" 0 60)
    case "$r" in "2|unread: no sample with a reading") ;; *) echo "FAIL all-fail: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/tailgap.jsonl" 60 240)
    case "$r" in "2|unread: no reading at or after the window's end +240 s (last +0 s)") ;;
        *) echo "FAIL tail-gap: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/midgap.jsonl" 60 240)
    case "$r" in "2|unread: no reading from +0 s to +300 s (300 s > 90 s)") ;;
        *) echo "FAIL mid-gap: [$r]" ;; esac
    r=$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import thermal_state as t
s = t.parse_sample("now 09-27 13:00:00 up 5.0\ncd 10  1 thermal-pause-F8\ncd 34 0 8 devfreq\nend\n")
print(s.get("bad_pause") or "-", t.paused(dict(s, error="x") if s.get("bad_pause") else s))' "$(dirname "$s")" 2>&1)
    case "$r" in "cd 10  1 thermal-pause-F8 None") ;; *) echo "FAIL bad-pause: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/percore.jsonl" 100 110)
    case "$r" in "0|thermal-pause: pause-cpu7 1/1 began after +90 s and by +120 s"*) ;;
        *) echo "FAIL per-core: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/kgsl.jsonl" 0 150)
    case "$r" in "1|"*) ;; *) echo "FAIL not-pause: [$r]" ;; esac
    r=$(python3 "$s" --diff "$(sed -n 4p "$TP/kgsl.jsonl")" "$(sed -n 5p "$TP/kgsl.jsonl")" 2>&1)
    case "$r" in "devfreq-3d00000.qcom,kgsl-3d0(cd34) 0->5/8") ;; *) echo "FAIL diff: [$r]" ;; esac
}
out=$(tp_legs "$TESTING/thermal_state.py")
[ -z "$out" ] && ok "thermal_state: onset, later, none, unread, all-fail, tail-gap, mid-gap, bad-pause, per-core, not-pause and --diff each read as they should" \
    || bad "thermal_state: $(printf '%s; ' "$out")"

echo "== thermal pause mutant: take the onset as the first paused sample"
if python3 - "$TESTING/thermal_state.py" "$TP/t/thermal_state.py" <<'PY'
import sys
s = open(sys.argv[1]).read()
old = 'a = ep["after"] if ep["after"] is not None else float("-inf")'
if old not in s:
    sys.exit(3)
open(sys.argv[2], "w").write(s.replace(old, 'a = ep["first"]', 1))
PY
then
    out=$(tp_legs "$TP/t/thermal_state.py")
    case "$out" in *"FAIL onset: [1|"*) ok "first-seen mutant: a pause first seen at +250 s no longer voids a window ending at +240 s, and the onset leg turns red" ;;
        *) bad "first-seen mutant: the legs did not catch it: [$out]" ;; esac
else
    bad "first-seen mutant: its anchor is gone from thermal_state.py -- update the mutant"
fi

echo "== thermal pause: soak_title.sh samples at start, from the hold loop, and at end"
cat > "$TP/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$TP_FAKE/calls"
case "$*" in
    *thermal_zone*)
        # The Nth sample pauses cpu3-7 from the TP_PAUSE_FROM'th (3rd) on;
        # xo-therm reads TP_XO_START + TP_XO_STEP * (n-1) millidegrees.
        n=$(( $(cat "$TP_FAKE/thn" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$TP_FAKE/thn"
        echo "thermal" >> "$TP_FAKE/order"
        printf 'now %s up %s\r\n' "$(date +'%m-%d %H:%M:%S')" "$((1000 + n))"
        printf 'cd 10 %d 1 thermal-pause-F8\r\ncd 34 0 8 devfreq-3d00000.qcom,kgsl-3d0\r\n' "$([ "$n" -ge "${TP_PAUSE_FROM:-3}" ] && echo 1 || echo 0)"
        printf 'tz 90 %d xo-therm\r\nend\r\n' "$(( ${TP_XO_START:-71000} + ${TP_XO_STEP:-1000} * (n - 1) ))" ;;
    *"settings put"*) echo "perf" >> "$TP_FAKE/order"; exit 0 ;;
    *"am start"*) echo "am" >> "$TP_FAKE/order"; exit 0 ;;
    *"ps -A -o NAME"*) printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *"settings get system performance_mode"*) echo "0 4" ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$TP/bin/adb"
tp_soak() {   # <env...>: one fake soak into a fresh $TP/run; env such as THERMAL_COOL_C=off
    rm -rf "$TP/run" "$TP/thn" "$TP/order" "$TP/calls"; mkdir -p "$TP/run"; : > "$TP/run/logcat.txt"
    env PATH="$TP/bin:$PATH" TP_FAKE="$TP" SERIAL=ee317437 DISPLAY_WAKE_S=0 ADB_RETRY_SLEEP=0 \
        HAKUX_DEVICE_LEASE="$TP/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 THERMAL_EVERY_S=1 \
        THERMAL_COOL_EVERY_S=1 PERF_RESULT="$TP/run/perf_regimen.json" \
        THERMAL_OUT="$TP/run/thermal.jsonl" "$@" \
        timeout 60 bash "$TESTING/soak_title.sh" /fake/iso.iso 3 > "$TP/run/run.log" 2>&1
    labels=$(python3 -c 'import json,sys
print(" ".join(json.loads(l)["label"] for l in open(sys.argv[1]) if l.strip()))' "$TP/run/thermal.jsonl" 2>/dev/null)
    order=$(tr '\n' ' ' < "$TP/order" 2>/dev/null)
}
tp_soak THERMAL_COOL_C=off
case "$labels" in "start hold"*" end") lab_ok=1 ;; *) lab_ok=0 ;; esac
if [ "$lab_ok" = 1 ] && case "$order" in "perf thermal am "*) true ;; *) false ;; esac \
        && grep -q '^THERMAL: pause thermal-pause-F8 1/1 began after +' "$TP/run/run.log"; then
    ok "soak: thermal.jsonl reads [$labels], the first sample before am start, and run.log names the pause"
else
    bad "soak: labels [$labels] order [$order] run.log: $(tr '\n' '|' < "$TP/run/run.log" | tail -c 400)"
fi

echo "== thermal pause: the cool-down gate holds a hot device before MAX and am start"
# THE LEGS, and the world in which each one fails:
#   cool       a cool sample (xo-therm 64 C, limit 65 C) exits 0, a hot one
#              (65 C) 1. Fails if the limit is not inclusive or the zone's
#              millidegrees are compared with degrees.
#   paused     xo-therm 60 C with thermal-pause-F8 1/1 exits 1. Fails in a
#              world where the pause is bound to another zone (socd on a
#              low-battery Nova): the gate would start a run already paused.
#   no-zone    no xo-therm zone, or an adb failure, exits 2 (not gated).
#              Fails if a device without the zone is held for the whole cap.
#   waits      xo-therm 70 -> 67 -> 64 C, one sample a second: three `cool`
#              lines before the first perf write and am start, then `start`,
#              and `waited 2 s` in run.log. Fails if the gate runs after MAX is
#              set (the title's own heat is then waited out) or not at all.
#   cap        xo-therm stuck at 80 C, THERMAL_COOL_MAX_S=2: `gave up after
#              2 s ... starting hot`, and the title still starts. Fails if the
#              gate can hold a run past the cap or refuses it.
tp_cool() {   # <tz 90 temp> <pause 0|1> [error] -> "rc|phrase"
    local f="$TP/cool.jsonl" out rc
    python3 -c 'import json,sys
t, p, e = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
r = {"t": 1, "label": "cool", "dev_time": "09-27 13:00:00", "up": 1.0,
     "cool": [[10, "thermal-pause-F8", p, 1]], "tz": [[90, "xo-therm", t]] if t else []}
if e:
    r.update(error=e, cool=[], tz=[], dev_time=None)
print(json.dumps(r))' "$1" "$2" "${3:-}" > "$f"
    out=$(python3 "$TESTING/thermal_state.py" --cool "$f" xo-therm 65 2>&1); rc=$?
    printf '%s|%s\n' "$rc" "$out"
}
r="$(tp_cool 64000 0);$(tp_cool 65000 0);$(tp_cool 60000 1);$(tp_cool 0 0);$(tp_cool 64000 0 'adb: exit 1')"
[ "$r" = "0|xo-therm 64.0 C < 65 C;1|xo-therm 65.0 C >= 65 C;1|xo-therm 60.0 C, paused (thermal-pause-F8 1/1);2|no xo-therm zone;2|unread: adb: exit 1" ] \
    && ok "--cool: cool, hot at the limit, paused below it, no zone and unread each read as they should" \
    || bad "--cool legs: [$r]"
tp_soak TP_XO_START=70000 TP_XO_STEP=-3000 TP_PAUSE_FROM=99
case "$order" in "thermal thermal thermal perf"*"am"*) ord_ok=1 ;; *) ord_ok=0 ;; esac
if [ "$ord_ok" = 1 ] && case "$labels" in "cool cool cool start hold"*" end") true ;; *) false ;; esac \
        && grep -qF 'THERMAL: cool-down: waited 2 s, from [xo-therm 70.0 C >= 65 C] to [xo-therm 64.0 C < 65 C]' "$TP/run/run.log"; then
    ok "gate waits: [$labels], three cool samples before MAX and am start, run.log names the wait"
else
    bad "gate waits: labels [$labels] order [$order] run.log: $(tr '\n' '|' < "$TP/run/run.log" | tail -c 400)"
fi
tp_soak TP_XO_START=80000 TP_XO_STEP=0 TP_PAUSE_FROM=99 THERMAL_COOL_MAX_S=2
if case "$order" in *"am"*) true ;; *) false ;; esac \
        && grep -qF 'THERMAL: cool-down: gave up after 2 s, from [xo-therm 80.0 C >= 65 C] to [xo-therm 80.0 C >= 65 C]; starting hot' "$TP/run/run.log"; then
    ok "gate cap: gave up after 2 s at 80 C and started the title hot"
else
    bad "gate cap: labels [$labels] order [$order] run.log: $(tr '\n' '|' < "$TP/run/run.log" | tail -c 400)"
fi

echo "== thermal pause: title_verdict.py voids a scored window a pause overlaps"
tp_verdict() {   # <rdir> -> "void|fps_ok_share|fps_window_median|fps_windows|pass|failing|thermal"
    python3 "$TESTING/title_verdict.py" "$1" --targets /dev/null >/dev/null 2>&1 || { echo "exit $?"; return; }
    python3 -c 'import json,sys; v=json.load(open(sys.argv[1]+"/verdict.json"))
th = v.get("thermal") or {}
print("|".join(str(v.get(k)) for k in ("void","fps_ok_share","fps_window_median","fps_windows","pass","failing"))
      + "|%s,%s,%d" % (th.get("measured"), th.get("in_window"), len(th.get("pauses") or [])))' "$1"
}
# 40 perf lines at 60 flips per second from 13:00:06, mark at 13:00:05, soak end 13:00:50.
PV="$TP/played"; rm -rf "$PV"; mkdir -p "$PV"
python3 - "$PV/logcat.txt" <<'PY'
import sys
out = ["09-27 13:00:00.000 I/hakuX-route( 100): soak start",
       "09-27 13:00:05.000 I/hakuX-route( 100): mark gameplay"]
for i in range(40):
    out.append("09-27 13:00:%02d.000 I/hakuX-perf( 200): gfps=60 G:16.7(16.0-17.0)" % (6 + i))
out.append("09-27 13:00:50.000 I/hakuX-route( 100): soak end")
open(sys.argv[1], "w").write("\n".join(out) + "\n")
PY
printf 'held iso.iso for 45s\nadb_failures=0\n' > "$PV/run.log"
echo '{"title": "iso.iso"}' > "$PV/request.json"
tp_fix "$PV/thermal.jsonl" 0:c 10:c 20:c 30:p 40:p 52:c
r=$(tp_verdict "$PV")
case "$r" in "thermal-pause: thermal-pause-F8 1/1 began after +15 s and by +25 s"*"relative to the mark|None|None|0|False|void: thermal-pause: "*"|True,True,1")
        ok "paused in the window: void, no frame rate, first failure names thermal-pause" ;;
    *) bad "paused-in-window verdict: [$r]" ;; esac
tp_fix "$PV/thermal.jsonl" 0:c 10:c 20:c 30:c 40:c 51:c 60:p
r=$(tp_verdict "$PV")
case "$r" in "None|1.0|60.0|39|"*"|True,False,1") ok "paused after soak end: judged at 60 fps over 39 windows, the pause reported, not in the window" ;;
    *) bad "paused-after verdict: [$r]" ;; esac
rm -f "$PV/thermal.jsonl"
r=$(tp_verdict "$PV")
case "$r" in "None|1.0|60.0|39|"*"|False,False,0") ok "no thermal.jsonl: judged as before, thermal.measured false" ;;
    *) bad "no-thermal verdict: [$r]" ;; esac
tp_fix "$PV/thermal.jsonl" 0:c 10:e 20:e 30:e 40:e 51:e
r=$(tp_verdict "$PV")
case "$r" in "thermal-unread: no reading at or after the window's end +45 s (last -5 s), relative to the mark|None|None|0|False|void: thermal-unread: "*"|True,False,0")
        ok "no reading after the mark: void thermal-unread, no frame rate" ;;
    *) bad "unread-window verdict: [$r]" ;; esac
wc=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]+"/verdict.json"))["thermal"]["window_covered"])' "$PV")
[ "$wc" = False ] && ok "unread window: thermal.window_covered is false" || bad "unread window: window_covered [$wc]"
