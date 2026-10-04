# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The 10-minute confirmation (owner, 2026-09-30, #433): targets.toml's
# `[defaults] confirmation_s` moved from 1200 to 600, and title_verdict.py
# honours a title's own `confirmation_s` (Forza, Kabuki Warriors: 1200) and
# bumps a sub-1200 s figure back to 1200 when the scored window was still
# heating at the end. Fixtures read the REAL targets.toml (Forza's own
# confirmation_s is what is tested), so an edit to either file is caught
# here, not just in production. Every leg calls title_verdict.py with
# `--require confirmation`, as lane.verdict433's judge_copy.py does for a
# real confirmation check (title_verdict.py's own auto-detect, used when
# `--require` is omitted, picks "screening" for a run short of its
# confirmation bar -- a different question from the one this rule answers).
#
# THE LEGS, and the world in which each one fails:
#   flat     a 600 s confirmation run on a title with no targets.toml entry,
#             thermal flat throughout (xo-therm 45 C, battery 30 C every
#             30 s): PASS. Fails if the default did not move to 600 s (still
#             demands 1200), or a flat window reads as heating.
#   heating  the same run, its last 180 s reading xo-therm climbing 1.5
#             C/min (battery flat): FAIL "confirmation: 1200 s needed -- the
#             device was still heating at the end". Fails if the rate is not
#             read, the 1.0 C/min bar is missed, or the wording differs.
#   forza    a 600 s confirmation run on Forza Motorsport (targets.toml's own
#             confirmation_s = 1200), thermal flat: FAIL on duration, needing
#             1200 s -- the generic "duration:" message, NOT the heating
#             one (the flag is why, not the heat). Fails if a per-title
#             confirmation_s is not read, or the heating wording leaks into
#             a flag-driven failure.
#   full     a 1200 s confirmation run, unflagged title, thermal flat: PASS.
#             Fails if a run already long enough for the old 1200 s bar is
#             broken by the new 600 s default.

echo "== 10-minute confirmation: title_verdict.py honours confirmation_s (#433)"
VC="$T/verdict10min"; rm -rf "$VC"

# vc_fix <rdir> <title-iso-basename> <gameplay_s> <flat|heat>: a route-marked
# soak at a steady 30 fps and clean audio, mark gameplay at t=100, soak end at
# t=100+gameplay_s. thermal.jsonl samples every 30 s: flat holds xo-therm/
# battery constant; heat ramps xo-therm 1.5 C/min over the window's last 180 s
# (battery stays flat, so only one zone need cross the 1.0 C/min bar).
vc_fix() {
    local d="$1" iso="$2" gp="$3" spec="$4"
    rm -rf "$d"; mkdir -p "$d"
    python3 - "$d" "$iso" "$gp" "$spec" <<'PY'
import json, os, sys, datetime as dt
d, iso, gp, spec = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
T0 = 13 * 3600

def stamp(t):
    t = T0 + t
    return "09-25 %02d:%02d:%06.3f" % (t // 3600, (t % 3600) // 60, t % 60)

end = 100.0 + gp
L = [(1.0, "I", "hakuX", "surface_scale=1"), (2.0, "I", "hakuX-route", "soak start"),
     (100.0, "I", "hakuX-route", "mark gameplay")]
t = 100.5
while t < end - 0.5:
    L.append((t, "I", "hakuX-perf", "gfps=30 G:33.3(32.3-34.3) D:16.7"))
    t += 2.0
a = 0.0
while a < end - 0.5:
    L.append((a, "I", "hakuX-audiocap", "starve: 0/9375 callbacks short (0 empty), 0/1 bytes zero-filled"))
    a += 30.0
L.append((end, "I", "hakuX-route", "soak end"))
L.sort(key=lambda x: x[0])
with open(os.path.join(d, "logcat.txt"), "w") as f:
    for x in L:
        f.write("%s %s/%s( 4242): %s\n" % (stamp(x[0]), x[1], x[2], x[3]))
with open(os.path.join(d, "run.log"), "w") as f:
    f.write("ROUTE 13:00:00.000 start r.route serial=x\nheld iso.iso for %ds\nadb_failures=0\n" % int(end + 5))
json.dump({"id": "fx-" + os.path.basename(d), "title": iso, "route_name": "generic", "route": "wait 1\n"},
          open(os.path.join(d, "request.json"), "w"))
json.dump({"kind": "soak", "device_label": "nova", "apk_sha": "0" * 12, "ref": "abc"},
          open(os.path.join(d, "result.json"), "w"))

base = dt.datetime(2000, 9, 25, 13, 0, 0)
tail0 = end - 180.0
# Every 30 s from 0, PLUS a sample at exactly `end`: thermal_state.coverage()
# needs a reading at or after the window's end (less END_SLACK_S), which a
# plain 30 s grid does not land on for every `end`.
secs = [i * 30.0 for i in range(int(end // 30.0) + 1)] + [end]
therm = []
for sec in secs:
    if spec == "heat" and sec >= tail0:
        xo = 45000 + int(1500 * (sec - tail0) / 60.0)   # 1.5 C/min
    else:
        xo = 45000
    therm.append(json.dumps({
        "t": 1790000000 + sec, "label": "start" if sec == 0 else "hold",
        "dev_time": (base + dt.timedelta(seconds=sec)).strftime("%m-%d %H:%M:%S"),
        "up": 100.0 + sec, "cool": [[10, "thermal-pause-F8", 0, 1]],
        "tz": [[90, "xo-therm", xo], [91, "battery", 30000]]}))
open(os.path.join(d, "thermal.jsonl"), "w").write("\n".join(therm) + "\n")
# Post-mark route-frames every 30 s, as the window's tests read them. Only
# with PIL (the verdict reads pixels; a window it cannot read fails).
import importlib.util
if all(importlib.util.find_spec(m) is not None for m in ("PIL", "numpy")):
    from PIL import Image
    rf = os.path.join(d, "route-frames"); os.makedirs(rf)
    for i, t in enumerate(range(130, int(end) - 30, 30)):
        h, m, s = (T0 + t) // 3600, ((T0 + t) % 3600) // 60, (T0 + t) % 60
        Image.effect_noise((640, 480), 80).convert("RGB").save(
            os.path.join(rf, "%02d%02d%02d-r%02d.png" % (h, m, s, i)))
PY
}

# Judged on the duration and heating, not the window: on a runner with no PIL
# the window cannot be read, so `window unmeasured` is the one failure a leg
# may carry there and the leg reads as the verdict's pass. With PIL the frames
# exist and the verdict must pass on its own.
vc_verdict() {   # <verdict.py> <rdir> -> "pass|failing"
    python3 "$1" "$2" --require confirmation --targets "$TESTING/titles/targets.toml" >/dev/null 2>&1 \
        || { echo "exit $?"; return; }
    python3 -c '
import importlib.util, json, sys
v = json.load(open(sys.argv[1] + "/verdict.json"))
no_pil = not all(importlib.util.find_spec(m) is not None for m in ("PIL", "numpy"))
if no_pil and v.get("failures") and all(f.startswith("window unmeasured") for f in v["failures"]):
    v["pass"], v["failing"] = True, None
print("%s|%s" % (v["pass"], v["failing"]))
' "$2"
}

vc_legs() {   # <verdict.py> -> one "FAIL <why>" per unmet leg
    local vpy="$1" r
    vc_fix "$VC/flat" "verdict10min-nomatch.iso" 600 flat
    r=$(vc_verdict "$vpy" "$VC/flat")
    case "$r" in "True|None") ;; *) echo "FAIL flat: [$r]" ;; esac
    vc_fix "$VC/heating" "verdict10min-nomatch.iso" 600 heat
    r=$(vc_verdict "$vpy" "$VC/heating")
    case "$r" in "False|confirmation: 1200 s needed -- the device was still heating at the end") ;;
        *) echo "FAIL heating: [$r]" ;; esac
    vc_fix "$VC/forza" "4D53006E-Forza_Motorsport.xiso.iso" 600 flat
    r=$(vc_verdict "$vpy" "$VC/forza")
    case "$r" in "False|duration: 600 s of gameplay < 1200 s confirmation") ;;
        *) echo "FAIL forza: [$r]" ;; esac
    vc_fix "$VC/full" "verdict10min-nomatch.iso" 1200 flat
    r=$(vc_verdict "$vpy" "$VC/full")
    case "$r" in "True|None") ;; *) echo "FAIL full: [$r]" ;; esac
}

out=$(vc_legs "$TESTING/title_verdict.py")
for f in flat heating forza full; do
    case "$out" in
        *"FAIL $f:"*) bad "10-minute confirmation, '$f' fixture: $(printf '%s\n' "$out" | grep "FAIL $f:")" ;;
        *) ok "10-minute confirmation, '$f' fixture reads as it should" ;;
    esac
done

echo "== 10-minute confirmation: mutants of title_verdict.py"
vc_mutant() {   # <name> <fixture that must catch it> <old> <new>
    local name="$1" want="$2" m="$T/vc-mutant.py"
    python3 - "$TESTING/title_verdict.py" "$m" "$3" "$4" <<'PY'
import sys
src, dst, old, new = sys.argv[1:5]
s = open(src).read()
if s.count(old) != 1:
    sys.exit("anchor not found once: %r" % old)
open(dst, "w").write(s.replace(old, new))
PY
    [ $? = 0 ] || { bad "mutant '$name': its anchor is gone from title_verdict.py -- update the mutant"; return; }
    case "$(vc_legs "$m")" in
        *"FAIL $want:"*) ok "mutant caught by the '$want' fixture: $name" ;;
        *) bad "mutant SURVIVED the '$want' fixture: $name" ;;
    esac
    rm -f "$m"
}
vc_mutant "ignore a title's own confirmation_s" forza \
    '"confirmation": float(entry.get("confirmation_s", defaults.get("confirmation_s", 600)))}' \
    '"confirmation": float(defaults.get("confirmation_s", 600))}'
vc_mutant "never bump for a still-heating window" heating \
    'heating_bump = windowed and still_heating and need["confirmation"] < 1200.0' \
    'heating_bump = False'
unset VC
