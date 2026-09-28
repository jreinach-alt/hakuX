# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# Power and energy per frame (#507): thermal_state.py's `pw` reading and its
# time-weighted average, and title_verdict.py's `power` block. Fixture samples
# are thermal.jsonl lines as thermal_state.py writes them, with a known current
# and voltage, so every expected number below is arithmetic on the fixture.
#
# THE SIGN: battery W is + while the battery DISCHARGES and - while it CHARGES.
# The kernel's current_now is the other way round (below zero while draining).
#
# THE LEGS, and the world in which each one fails:
#   parse      the device's `ps` and `ths` lines become `pw`: -2 A at 4 V is
#              +8.0 W, 0.45 A at 4.8 V of USB is 2.16 W, usb_type keeps its
#              spaces, thermal status 1. Fails if the value is split on
#              spaces or microamps are read as milliamps (8e-6 W).
#   unread     a current_now line with no value gives no power reading. Fails
#              if an unread field is 0 (a 0 W run, and 0 J per frame).
#   sample     thermal_state.py <serial> against a fake adb carries `pw` into
#              the JSON line. Fails if the one-call script loses the block.
#   weighted   4 W at +0 s and 8 W at +100 s, window +50..+100 s: 7.0 W.
#              Fails if the samples inside the window are averaged (8.0) or
#              all samples are (6.0).
#   summary    the run.log line ends `battery +8.00 W (+ is discharging), usb
#              in 2.50 W, net 10.50 W`. Fails if the line drops the sign's
#              meaning, the one place a reader of run.log would learn it.
#   drain      a 60 fps run, battery -2 A at 4 V, USB 0.5 A at 5 V: battery
#              +8.0 W, net 10.5 W, 2340 flips in 39.0 s, 0.175 J per frame
#              (0.1333 from the battery alone). Fails if the sign is flipped
#              (the mutant below), or J per frame divides by the windows (39)
#              and not the flips.
#   charge     battery +1 A at 4 V, USB 2 A at 9 V: battery -4.0 W, net 14.0 W,
#              0.2333 J per frame. Fails if the magnitude is taken: a charging
#              run would then read 22 W, more than the input.
#   old        samples with no `pw` (every thermal.jsonl before this change):
#              power.measured false and no J per frame, fps judged as before.
#              Fails if a missing reading is 0 W.
#   void       a pause inside the window: void, watts reported, no J per
#              frame, and first_pause_s after 20 by 30 s from the start.
#              Fails if a paused window's flips price the title's frames, or
#              the time to pause is counted from the mark (15 and 25).
#   suspect    USB offline and the battery "charging" at 4 W: sign_suspect 4
#              and no J per frame. Fails on a kernel with the other sign, where
#              every reading would otherwise be negated without a word.
#   bound      only input_current_limit read (0.5 A): usb_w 2.5 W, named an
#              upper bound. Fails if a limit is reported as a measurement.

echo "== power per frame: thermal_state.py reads power, title_verdict.py prices a frame (#507)"
PW="$T/powerframe"; rm -rf "$PW"; mkdir -p "$PW/bin" "$PW/t" "$PW/run"
# <file> <spec>...: each spec is <second>:<state>:<battery uA>:<battery uV>:<usb>
# state c (clean) or p (thermal-pause-F8 1/1); battery uA `-` writes no `pw`;
# usb is <uA>,<uV> (measured), off (online 0), lim (only the limit), or none.
pw_fix() {
    python3 - "$@" <<'PY'
import json, sys, datetime as dt
path, specs = sys.argv[1], sys.argv[2:]
base = dt.datetime(2000, 9, 27, 13, 0, 0)
out = []
for n, spec in enumerate(specs):
    sec, st, ua, uv, usb = spec.split(":")
    rec = {"t": 1790000000 + int(sec), "label": "start" if n == 0 else "hold",
           "dev_time": (base + dt.timedelta(seconds=int(sec))).strftime("%m-%d %H:%M:%S"),
           "up": 100.0 + int(sec), "tz": [[90, "xo-therm", 70000]],
           "cool": [[10, "thermal-pause-F8", 1 if st == "p" else 0, 1]], "pause": st == "p"}
    if ua != "-":
        pw = {"battery": {"current_now": int(ua), "voltage_now": int(uv), "capacity": 80,
                          "status": "Charging"}, "thermal_status": 0}
        if usb == "off":
            pw["usb"] = {"online": 0}
        elif usb == "lim":
            pw["usb"] = {"online": 1, "input_current_limit": 500000}
        elif usb != "none":
            i, v = usb.split(",")
            pw["usb"] = {"online": 1, "current_now": int(i), "voltage_now": int(v),
                         "input_current_limit": 500000}
        rec["pw"] = pw
    out.append(json.dumps(rec))
open(path, "w").write("\n".join(out) + "\n")
PY
}
pw_verdict() {   # <testing dir> <rdir> -> "void|fps_window_median|measured|battery_w|usb_w|net_w|flips|scored_s|j|j_battery|suspect|first_pause"
    python3 "$1/title_verdict.py" "$2" --targets /dev/null >/dev/null 2>&1 || { echo "exit $?"; return; }
    python3 -c 'import json,sys; v=json.load(open(sys.argv[1]+"/verdict.json"))
p = v.get("power") or {}
fp = (v.get("thermal") or {}).get("first_pause_s")
print("|".join(str(x) for x in [(v.get("void") or "None")[:13], v.get("fps_window_median")]
      + [p.get(k) for k in ("measured","battery_w","usb_w","net_w","flips","scored_s","j_per_frame","j_per_frame_battery","sign_suspect")]
      + [("%s,%s" % (fp["after"], fp["by"])) if fp else None]))' "$2"
}

r=$(python3 -c 'import sys, json; sys.path.insert(0, sys.argv[1]); import thermal_state as t
s = t.parse_sample("""now 09-27 13:00:00 up 5.0
cd 10 0 1 thermal-pause-F8
tz 90 70000 xo-therm
ps battery status Charging
ps battery current_now -2000000
ps battery voltage_now 4000000
ps usb usb_type Unknown [SDP] DCP CDP
ps usb current_now 450000
ps usb voltage_now 4800000
ths Thermal Status: 1
end
""")
p = t.power(s)
print("%.2f|%.2f|%s|%s|%s" % (p["battery_w"], p["usb_w"], s["pw"]["usb"]["usb_type"], s["pw"]["thermal_status"], p["suspect"]))
u = t.parse_sample("now 09-27 13:00:00 up 5.0\nps battery current_now \nps battery voltage_now 4000000\nend\n")
print(u.get("pw"), t.power(u))' "$TESTING" 2>&1 | tr '\n' ';')
[ "$r" = "8.00|2.16|Unknown [SDP] DCP CDP|1|False;{'battery': {'voltage_now': 4000000}} None;" ] \
    && ok "parse and unread: -2 A at 4 V is +8.00 W discharging, usb 2.16 W, and a current that did not read is no reading" \
    || bad "parse legs: [$r]"

cat > "$PW/bin/adb" <<'EOF'
#!/usr/bin/env bash
printf 'now 09-27 13:00:00 up 5.0\r\ncd 10 0 1 thermal-pause-F8\r\ntz 90 70000 xo-therm\r\n'
printf 'ps battery current_now -2000000\r\nps battery voltage_now 4000000\r\n'
printf 'ps usb online 1\r\nps usb current_now 500000\r\nps usb voltage_now 5000000\r\n'
printf 'ths Thermal Status: 0\r\nend\r\n'
EOF
chmod +x "$PW/bin/adb"
r=$(PATH="$PW/bin:$PATH" python3 "$TESTING/thermal_state.py" FAKE --label start 2>&1 | python3 -c 'import json,sys
r = json.loads(sys.stdin.read()); p = r.get("pw") or {}
print(r.get("label"), r.get("pause"), p.get("battery"), p.get("usb"), p.get("thermal_status"))' 2>&1)
[ "$r" = "start False {'current_now': -2000000, 'voltage_now': 4000000} {'online': 1, 'current_now': 500000, 'voltage_now': 5000000} 0" ] \
    && ok "sample: one adb call carries the battery, the USB input and the thermal status into the JSON line" \
    || bad "sample leg: [$r]"

pw_fix "$PW/w.jsonl" 0:c:-1000000:4000000:none 100:c:-2000000:4000000:none
r=$(python3 "$TESTING/thermal_state.py" --power "$PW/w.jsonl" 50 100 2>&1 | python3 -c 'import json,sys
p = json.loads(sys.stdin.read()); print(p["battery_w"], p["samples"], p["net_w"], p["sign"])' 2>&1)
[ "$r" = "7.0 1 None battery_w: + discharging, - charging; net_w = battery_w + usb_w" ] \
    && ok "weighted: 4 W at +0 s and 8 W at +100 s average 7.0 W over +50..+100 s, and the output names its sign" \
    || bad "weighted leg: [$r]"

# The 60 fps run of 99-thermal-pause.sh: mark 13:00:05, 40 perf lines a second
# apart from 13:00:06, soak end 13:00:50. 39 windows, 2340 flips, 39.0 s.
PWV="$PW/played"; mkdir -p "$PWV"
python3 - "$PWV/logcat.txt" <<'PY'
import sys
out = ["09-27 13:00:00.000 I/hakuX-route( 100): soak start",
       "09-27 13:00:05.000 I/hakuX-route( 100): mark gameplay"]
for i in range(40):
    out.append("09-27 13:00:%02d.000 I/hakuX-perf( 200): gfps=60 G:16.7(16.0-17.0)" % (6 + i))
out.append("09-27 13:00:50.000 I/hakuX-route( 100): soak end")
open(sys.argv[1], "w").write("\n".join(out) + "\n")
PY
printf 'held iso.iso for 45s\nadb_failures=0\n' > "$PWV/run.log"
echo '{"title": "iso.iso"}' > "$PWV/request.json"
pw_drain() { pw_fix "$PWV/thermal.jsonl" 0:c:-2000000:4000000:500000,5000000 10:c:-2000000:4000000:500000,5000000 \
    20:c:-2000000:4000000:500000,5000000 30:c:-2000000:4000000:500000,5000000 \
    40:c:-2000000:4000000:500000,5000000 51:c:-2000000:4000000:500000,5000000; }
PW_DRAIN="None|60.0|True|8.0|2.5|10.5|2340|39.0|0.175|0.1333|0|None"

pw_drain
r=$(python3 "$TESTING/thermal_state.py" --summary "$PWV/thermal.jsonl" 2>&1)
case "$r" in "THERMAL: no thermal-pause device above 0; 6 samples, 0 unread, hottest zone 70.0 C; battery +8.00 W (+ is discharging), usb in 2.50 W, net 10.50 W")
        ok "summary: run.log's line carries the watts and says which way the sign runs" ;;
    *) bad "summary leg: [$r]" ;; esac
r=$(pw_verdict "$TESTING" "$PWV")
[ "$r" = "$PW_DRAIN" ] && ok "drain: battery +8.0 W, net 10.5 W, 2340 flips in 39.0 s, 0.175 J per frame" \
    || bad "drain verdict: [$r]"

pw_fix "$PWV/thermal.jsonl" 0:c:1000000:4000000:2000000,9000000 10:c:1000000:4000000:2000000,9000000 \
    20:c:1000000:4000000:2000000,9000000 30:c:1000000:4000000:2000000,9000000 \
    40:c:1000000:4000000:2000000,9000000 51:c:1000000:4000000:2000000,9000000
r=$(pw_verdict "$TESTING" "$PWV")
[ "$r" = "None|60.0|True|-4.0|18.0|14.0|2340|39.0|0.2333|-0.0667|0|None" ] \
    && ok "charge: battery -4.0 W while charging, net 14.0 W, 0.2333 J per frame" \
    || bad "charge verdict: [$r]"

pw_fix "$PWV/thermal.jsonl" 0:c:-:-:none 10:c:-:-:none 20:c:-:-:none 30:c:-:-:none 40:c:-:-:none 51:c:-:-:none
r=$(pw_verdict "$TESTING" "$PWV")
[ "$r" = "None|60.0|False|None|None|None|2340|39.0|None|None|0|None" ] \
    && ok "old samples: no pw block is power unmeasured and no J per frame, with the run judged at 60 fps as before" \
    || bad "old-samples verdict: [$r]"

pw_fix "$PWV/thermal.jsonl" 0:c:-2000000:4000000:500000,5000000 10:c:-2000000:4000000:500000,5000000 \
    20:c:-2000000:4000000:500000,5000000 30:p:-2000000:4000000:500000,5000000 \
    40:p:-2000000:4000000:500000,5000000 52:c:-2000000:4000000:500000,5000000
r=$(pw_verdict "$TESTING" "$PWV")
[ "$r" = "thermal-pause|None|True|8.0|2.5|10.5|0|0.0|None|None|0|20.0,30.0" ] \
    && ok "void: a paused window reports its watts and no J per frame; the first pause came after 20 s and by 30 s from the start" \
    || bad "void verdict: [$r]"

pw_fix "$PWV/thermal.jsonl" 0:c:1000000:4000000:off 10:c:1000000:4000000:off 20:c:1000000:4000000:off \
    30:c:1000000:4000000:off 40:c:1000000:4000000:off 51:c:1000000:4000000:off
r=$(pw_verdict "$TESTING" "$PWV")
[ "$r" = "None|60.0|True|-4.0|0.0|-4.0|2340|39.0|None|None|4|None" ] \
    && ok "suspect: charging at 4 W with the USB offline is counted 4 times in the window and prices no frame" \
    || bad "suspect verdict: [$r]"

pw_fix "$PWV/thermal.jsonl" 0:c:-2000000:4000000:lim 10:c:-2000000:4000000:lim 20:c:-2000000:4000000:lim \
    30:c:-2000000:4000000:lim 40:c:-2000000:4000000:lim 51:c:-2000000:4000000:lim
r=$(pw_verdict "$TESTING" "$PWV")
uf=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]+"/verdict.json"))["power"]["usb_from"])' "$PWV" 2>&1)
[ "$r" = "$PW_DRAIN" ] && [ "$uf" = "upper bound: input_current_limit x 5 V" ] \
    && ok "bound: with only the input limit read, usb_w is 2.5 W and usb_from calls it an upper bound" \
    || bad "bound verdict: [$r] usb_from [$uf]"

echo "== power per frame mutant: battery power without the sign flip"
cp "$TESTING/title_verdict.py" "$PW/t/title_verdict.py"
if python3 - "$TESTING/thermal_state.py" "$PW/t/thermal_state.py" <<'PY'
import sys
s = open(sys.argv[1]).read()
old = '"battery_w": -(i * v) / 1e12'
if old not in s:
    sys.exit(3)
open(sys.argv[2], "w").write(s.replace(old, '"battery_w": (i * v) / 1e12', 1))
PY
then
    pw_drain
    r=$(pw_verdict "$PW/t" "$PWV")
    case "$r" in "None|60.0|True|-8.0|2.5|-5.5|2340|39.0|"*) ok "sign mutant: a draining battery reads -8.0 W and the drain leg turns red" ;;
        *) bad "sign mutant: the drain leg did not catch it: [$r]" ;; esac
else
    bad "sign mutant: its anchor is gone from thermal_state.py -- update the mutant"
fi
