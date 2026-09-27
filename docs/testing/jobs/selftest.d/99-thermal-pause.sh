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
#              judged and `thermal.measured` is false.

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
    r=$(tp_win "$s" "$TP/percore.jsonl" 100 110)
    case "$r" in "0|thermal-pause: pause-cpu7 1/1 began after +90 s and by +120 s"*) ;;
        *) echo "FAIL per-core: [$r]" ;; esac
    r=$(tp_win "$s" "$TP/kgsl.jsonl" 0 150)
    case "$r" in "1|"*) ;; *) echo "FAIL not-pause: [$r]" ;; esac
    r=$(python3 "$s" --diff "$(sed -n 4p "$TP/kgsl.jsonl")" "$(sed -n 5p "$TP/kgsl.jsonl")" 2>&1)
    case "$r" in "devfreq-3d00000.qcom,kgsl-3d0(cd34) 0->5/8") ;; *) echo "FAIL diff: [$r]" ;; esac
}
out=$(tp_legs "$TESTING/thermal_state.py")
[ -z "$out" ] && ok "thermal_state: onset, later, none, unread, all-fail, per-core, not-pause and --diff each read as they should" \
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
        # The Nth sample pauses cpu3-7 from the 3rd on.
        n=$(( $(cat "$TP_FAKE/thn" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$TP_FAKE/thn"
        echo "start" >> "$TP_FAKE/order"
        printf 'now %s up %s\r\n' "$(date +'%m-%d %H:%M:%S')" "$((1000 + n))"
        printf 'cd 10 %d 1 thermal-pause-F8\r\ncd 34 0 8 devfreq-3d00000.qcom,kgsl-3d0\r\n' "$([ "$n" -ge 3 ] && echo 1 || echo 0)"
        printf 'tz 90 %d xo-therm\r\nend\r\n' "$((70000 + 1000 * n))" ;;
    *"am start"*) echo "am" >> "$TP_FAKE/order"; exit 0 ;;
    *"ps -A -o NAME"*) printf 'NAME                       \r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *"settings get system performance_mode"*) echo "0 4" ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$TP/bin/adb"
rm -rf "$TP/run"; mkdir -p "$TP/run"; : > "$TP/run/logcat.txt"
PATH="$TP/bin:$PATH" TP_FAKE="$TP" SERIAL=ee317437 DISPLAY_WAKE_S=0 ADB_RETRY_SLEEP=0 \
    HAKUX_DEVICE_LEASE="$TP/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 THERMAL_EVERY_S=1 \
    PERF_RESULT="$TP/run/perf_regimen.json" THERMAL_OUT="$TP/run/thermal.jsonl" \
    timeout 60 bash "$TESTING/soak_title.sh" /fake/iso.iso 3 > "$TP/run/run.log" 2>&1
labels=$(python3 -c 'import json,sys
print(" ".join(json.loads(l)["label"] for l in open(sys.argv[1]) if l.strip()))' "$TP/run/thermal.jsonl" 2>/dev/null)
case "$labels" in "start hold"*" end") lab_ok=1 ;; *) lab_ok=0 ;; esac
if [ "$lab_ok" = 1 ] && [ "$(head -1 "$TP/order")" = start ] \
        && grep -q '^THERMAL: pause thermal-pause-F8 1/1 began after +' "$TP/run/run.log"; then
    ok "soak: thermal.jsonl reads [$labels], the first sample before am start, and run.log names the pause"
else
    bad "soak: labels [$labels] order [$(tr '\n' ' ' < "$TP/order" 2>/dev/null)] run.log: $(tr '\n' '|' < "$TP/run/run.log" | tail -c 400)"
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
