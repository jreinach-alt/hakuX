# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The device-defaults regimen (#507, owner's ruling 2026-09-27 on #433):
# soak_title.sh PERF_REGIMEN=default runs the title at performance_mode 0 and
# fan SMART (4) and records the display settings in perf_regimen.json; and
# title_verdict.py FAILS a `default` run the thermal pause reached, where at
# MAX the same pause voids.
#
# THE LEGS, and the world in which each one fails:
#   soak       the Nova (MAX 2/5), found at 1/4, runs PERF_REGIMEN=default:
#              the title starts at 0/4 and perf_regimen.json says `default`.
#              Fails if `default` is not a known regimen (it falls to MAX and
#              the title starts at 2/5), or its modes are not written.
#   display    the fake's settings and two displays (0 ON, 4 OFF, as the
#              Thor's second screen) land in `display.start` and
#              `display.end`. Fails if the read is dropped, runs only once,
#              or the display id or state is read from the wrong words.
#   fails      a `default` run paused at +30 s inside the scored window: not
#              void, failed_sustained true, the failure names the pause and
#              its onset from the start (after +20 s, by +30 s), no rating
#              candidate, and the fps windows stand. Fails if a `default` run
#              is voided as at MAX (no fps, a re-queue), or the pause is
#              ignored.
#   max        the same samples with `regimen: max`: void thermal-pause,
#              failed_sustained null. Fails if the `default` branch leaks
#              into MAX runs and a MAX pause is scored as the title's fps.
#   clean      a `default` run with no pause: failed_sustained false and no
#              `thermal:` failure. Fails if every `default` run is failed.
#   cooldown   a `default` run whose only pause is one the cool-down gate
#              waited out before `start`: failed_sustained false. Fails if
#              the previous run's heat is charged to this title.
#   none       no perf_regimen.json (every run before this change): void as
#              before, regimen null. Fails if a missing file reads as
#              `default` and old paused runs gain fps.

echo "== default regimen: the title at the device's defaults, and a pause fails it (#507)"
DR="$T/defregimen"; rm -rf "$DR"; mkdir -p "$DR/bin" "$DR/run"
cat > "$DR/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
S="$PERF_FAKE/state"; [ -f "$S" ] || echo "0 4" > "$S"
case "$*" in
    *"settings put system performance_mode"*)
        set -- $(printf '%s\n' "$*" | sed -n 's/.*performance_mode \([0-9-]*\).*fan_mode \([0-9-]*\).*/\1 \2/p')
        echo "$1 $2" > "$S" ;;
    *"settings get system performance_mode"*) cat "$S" ;;
    *"min_refresh_rate"*)
        printf 'set min_refresh_rate=60.0\r\nset peak_refresh_rate=120.0\r\nset screen_brightness=102\r\n'
        printf 'set screen_brightness_mode=0\r\nset dual_screen_display_mode=0\r\n'
        printf '    mBaseDisplayInfo=DisplayInfo{"Built-in Screen", displayId 0, displayGroupId 0, real 1080 x 1920, state ON, committedState ON}\r\n'
        printf '    mBaseDisplayInfo=DisplayInfo{"HDMI Screen", displayId 4, displayGroupId 0, real 1080 x 1240, state OFF, committedState OFF}\r\n' ;;
    *"am start"*) cp "$S" "$PERF_FAKE/at_start" ;;
    *"ps -A -o NAME"*) printf 'NAME\r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$DR/bin/adb"
echo "1 4" > "$DR/state"
PATH="$DR/bin:$PATH" PERF_FAKE="$DR" SERIAL=ee317437 PERF_REGIMEN=default \
    HAKUX_DEVICE_LEASE="$DR/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 \
    PERF_RESULT="$DR/perf_regimen.json" \
    timeout 60 bash "$TESTING/soak_title.sh" /fake/iso.iso 1 > "$DR/run.log" 2>&1
r=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))
print(d["regimen"], d["perf_mode"], d["fan_mode"], d["default"], d["perf_restored"])' "$DR/perf_regimen.json" 2>&1)
[ "$(cat "$DR/at_start" 2>/dev/null)" = "0 4" ] && [ "$r" = "default 0 4 {'perf_mode': 0, 'fan_mode': 4} True" ] \
    && ok "soak: PERF_REGIMEN=default starts the title at performance 0, fan SMART, and records it" \
    || bad "soak leg: started at [$(cat "$DR/at_start" 2>/dev/null)], perf_regimen [$r]; $(tail -3 "$DR/run.log")"
r=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))["display"]
for k in ("start", "end"):
    x = d[k] or {}
    print(k, x.get("peak_refresh_rate"), x.get("min_refresh_rate"), x.get("screen_brightness"),
          x.get("dual_screen_display_mode"), sorted((x.get("displays") or {}).items()))' "$DR/perf_regimen.json" 2>&1 | tr '\n' ';')
want="120.0 60.0 102 0 [('0', 'ON'), ('4', 'OFF')]"
[ "$r" = "start $want;end $want;" ] \
    && ok "display: refresh rates, brightness, the dual-screen mode and each display's state, at start and at end" \
    || bad "display leg: [$r]"

# The 60 fps run of 99-thermal-pause.sh: mark 13:00:05, 40 perf lines a
# second apart from 13:00:06, soak end 13:00:50. Samples at +0..+52 s.
DRV="$DR/run"
python3 - "$DRV/logcat.txt" <<'PY'
import sys
out = ["09-27 13:00:00.000 I/hakuX-route( 100): soak start",
       "09-27 13:00:05.000 I/hakuX-route( 100): mark gameplay"]
for i in range(40):
    out.append("09-27 13:00:%02d.000 I/hakuX-perf( 200): gfps=60 G:16.7(16.0-17.0)" % (6 + i))
out.append("09-27 13:00:50.000 I/hakuX-route( 100): soak end")
open(sys.argv[1], "w").write("\n".join(out) + "\n")
PY
printf 'held iso.iso for 45s\nadb_failures=0\n' > "$DRV/run.log"
echo '{"title": "iso.iso"}' > "$DRV/request.json"
# <spec>...: <second>:<c|p>[:<label>]; the first unlabelled sample is `start`.
dr_fix() {
    python3 - "$DRV/thermal.jsonl" "$@" <<'PY'
import json, sys, datetime as dt
base = dt.datetime(2000, 9, 27, 13, 0, 0)
out, seen_start = [], False
for spec in sys.argv[2:]:
    f = spec.split(":")
    sec, st = int(f[0]), f[1]
    label = f[2] if len(f) > 2 else ("hold" if seen_start else "start")
    seen_start = seen_start or label == "start"
    out.append(json.dumps({"t": 1790000000 + sec, "label": label,
        "dev_time": (base + dt.timedelta(seconds=sec)).strftime("%m-%d %H:%M:%S"),
        "up": 1000.0 + sec, "tz": [[90, "xo-therm", 70000]],
        "cool": [[10, "thermal-pause-F8", 1 if st == "p" else 0, 1]], "pause": st == "p"}))
open(sys.argv[1], "w").write("\n".join(out) + "\n")
PY
}
dr_regimen() { if [ "$1" = none ]; then rm -f "$DRV/perf_regimen.json"; else echo "{\"regimen\": \"$1\"}" > "$DRV/perf_regimen.json"; fi; }
# -> "void|failed_sustained|regimen|fps_window_median|rating_candidate|the thermal: failure"
dr_verdict() {
    python3 "$TESTING/title_verdict.py" "$DRV" --targets /dev/null >/dev/null 2>&1 || { echo "exit $?"; return; }
    python3 -c 'import json,sys; v=json.load(open(sys.argv[1]+"/verdict.json")); th=v["thermal"]
f = [x for x in v["failures"] if x.startswith("thermal:")]
print("|".join(str(x) for x in [(v["void"] or "None")[:13], th.get("failed_sustained"), th.get("regimen"),
      v.get("fps_window_median"), v["rating_candidate"], f[0] if f else None]))' "$DRV"
}
PAUSED="0:c 10:c 20:c 30:p 40:p 52:c"

dr_fix $PAUSED; dr_regimen default
r=$(dr_verdict)
case "$r" in "None|True|default|60.0|None|thermal: sustained play failed at the device's defaults -- thermal-pause-F8 1/1 began after +20 s and by +30 s"*)
        ok "fails: a pause at the defaults fails the run, names its onset from the start, and keeps its fps" ;;
    *) bad "fails leg: [$r]" ;; esac

dr_regimen max
r=$(dr_verdict)
[ "$r" = "thermal-pause|None|max|None|None|None" ] \
    && ok "max: the same pause at MAX still voids, with no sustained verdict" || bad "max leg: [$r]"

dr_fix 0:c 10:c 20:c 30:c 40:c 52:c; dr_regimen default
r=$(dr_verdict)
[ "$r" = "None|False|default|60.0|None|None" ] \
    && ok "clean: a default run with no pause is not failed on heat" || bad "clean leg: [$r]"

dr_fix -60:p:cool -40:c:cool 0:c 10:c 20:c 30:c 40:c 52:c; dr_regimen default
r=$(dr_verdict)
[ "$r" = "None|False|default|60.0|None|None" ] \
    && ok "cooldown: a pause the gate waited out before the start is not this run's" || bad "cooldown leg: [$r]"

dr_fix $PAUSED; dr_regimen none
r=$(dr_verdict)
[ "$r" = "thermal-pause|None|None|None|None|None" ] \
    && ok "none: a run with no perf_regimen.json voids on a pause as before" || bad "none leg: [$r]"
