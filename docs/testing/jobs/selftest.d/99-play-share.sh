# Sourced by ../selftest.sh: $T, $TESTING, ok/bad. No shebang, no exit.
#
# The play timeline (owner, 2026-10-01, #433: "we're getting bad FPS data if
# half the time is spent in a menu"). title_verdict.py reads drive.py's
# `hakuX-route: state=<s> t=<n>` lines, reports play_share over the scored
# window, FAILS a confirmation under 90% as "menu time", and judges fps over
# `play` seconds only. Every leg is a 600 s confirmation (mark at t=100, soak
# end at t=700) at 30 fps with clean audio, except where it says otherwise.
#
# THE LEGS, and the world in which each one fails:
#   none      no state line at all (a blind route): PASS, timeline "none".
#             Fails if a run with no timeline is failed or relabelled.
#   allplay   state=play from before the mark to the end: PASS, play_share
#             1.0. Fails if the state in force AT the mark is not carried
#             into the window (it was set 5 s before it).
#   menu      play, then main_menu from t=300 to t=500, then play: FAIL
#             "menu time: 66.7% ...". Fails if the share is not judged, or
#             the menu span is counted as play.
#   excluded  play, then paused from t=640 (play_share 0.9 exactly, at the
#             bar) with the frame rate at 10 fps while paused: PASS, and the
#             paused windows are left out (fps_excluded_s ~60, slowest
#             counted window 30 fps). Fails if non-play windows are scored.

echo "== play timeline: title_verdict.py play_share and play-only fps (#433)"
PS="$T/playshare"; rm -rf "$PS"

# ps_fix <rdir> <spec>: spec is a list "t:state,t:state" of state lines.
# perf lines every 2 s (30 fps) while the state in force is play or the run
# has no timeline, every 6 s (10 fps) otherwise.
ps_fix() {
    local d="$1" spec="$2"
    rm -rf "$d"; mkdir -p "$d"
    python3 - "$d" "$spec" <<'PY'
import json, os, sys
d, spec = sys.argv[1], sys.argv[2]
T0 = 13 * 3600

def stamp(t):
    t = T0 + t
    return "09-25 %02d:%02d:%06.3f" % (t // 3600, (t % 3600) // 60, t % 60)

ch = [(float(x.split(":")[0]), x.split(":")[1]) for x in spec.split(",") if x]
end = 700.0
L = [(1.0, "I", "hakuX", "surface_scale=1"), (2.0, "I", "hakuX-route", "soak start"),
     (100.0, "I", "hakuX-route", "mark gameplay")]
for t, s in ch:
    L.append((t, "I", "hakuX-route", "state=%s t=%d" % (s, int(t))))

def state_at(t):
    cur = None
    for a, s in ch:
        if a <= t:
            cur = s
    return cur

t = 100.5
while t < end - 0.5:
    L.append((t, "I", "hakuX-perf", "gfps=30 G:33.3(32.3-34.3) D:16.7"))
    st = state_at(t)
    t += 2.0 if (not ch or st == "play") else 6.0
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
json.dump({"id": "fx-" + os.path.basename(d), "title": "playshare-nomatch.iso", "route_name": "r",
           "route": "drive x 600 mark\n"}, open(os.path.join(d, "request.json"), "w"))
json.dump({"kind": "soak", "device_label": "nova", "apk_sha": "0" * 12, "ref": "abc"},
          open(os.path.join(d, "result.json"), "w"))
# Post-mark route-frames, as the window's liveness and position tests read
# them (every 30 s, noise: the scene changes every sample, as live play does).
# Only with PIL: the verdict reads pixels, and a window it cannot read fails.
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

# Judged on the timeline, not the window. On a runner with no PIL the window
# cannot be read, so `window unmeasured` is the one failure a leg may carry
# there, and the leg reads as the verdict's pass. With PIL the frames exist
# and the verdict must pass on its own.
ps_verdict() {   # <verdict.py> <rdir> -> "pass|failing|play_share|excluded_s|min_fps"
    python3 "$1" "$2" --require confirmation --targets "$TESTING/titles/targets.toml" >/dev/null 2>&1 \
        || { echo "exit $?"; return; }
    python3 -c '
import importlib.util, json, sys
v = json.load(open(sys.argv[1] + "/verdict.json"))
tl = v.get("timeline")
no_pil = not all(importlib.util.find_spec(m) is not None for m in ("PIL", "numpy"))
if no_pil and v.get("failures") and all(f.startswith("window unmeasured") for f in v["failures"]):
    v["pass"], v["failing"] = True, None
if tl == "none":
    print("%s|%s|none|-|%s" % (v["pass"], v["failing"], v.get("fps_window_min")))
else:
    print("%s|%s|%s|%s|%s" % (v["pass"], v["failing"], tl["play_share"], tl["fps_excluded_s"], v.get("fps_window_min")))
' "$2"
}

ps_legs() {   # <verdict.py> -> one "FAIL <leg>: [...]" per unmet leg
    local vpy="$1" r
    ps_fix "$PS/none" ""
    r=$(ps_verdict "$vpy" "$PS/none")
    case "$r" in "True|None|none|-|"*) ;; *) echo "FAIL none: [$r]" ;; esac
    ps_fix "$PS/allplay" "95:play"
    r=$(ps_verdict "$vpy" "$PS/allplay")
    case "$r" in "True|None|1.0|0.0|"*) ;; *) echo "FAIL allplay: [$r]" ;; esac
    ps_fix "$PS/menu" "95:play,300:main_menu,500:play"
    r=$(ps_verdict "$vpy" "$PS/menu")
    case "$r" in "False|menu time: 66.7% of the scored window in \`play\`"*) ;; *) echo "FAIL menu: [$r]" ;; esac
    ps_fix "$PS/excluded" "95:play,640:paused"
    r=$(ps_verdict "$vpy" "$PS/excluded")
    case "$r" in "True|None|0.9|"*) ;; *) echo "FAIL excluded: [$r]" ;; esac
    python3 -c '
import sys
p = sys.argv[1].split("|")
ok = len(p) == 5 and p[3] not in ("-", "None") and float(p[3]) >= 50 and float(p[4]) >= 29.5
sys.exit(0 if ok else 1)' "$r" || echo "FAIL excluded: [$r] wants >= 50 s excluded and the slowest counted window at 30 fps"
}

out=$(ps_legs "$TESTING/title_verdict.py")
for f in none allplay menu excluded; do
    case "$out" in
        *"FAIL $f:"*) bad "play timeline, '$f' fixture: $(printf '%s\n' "$out" | grep "FAIL $f:" | head -1)" ;;
        *) ok "play timeline, '$f' fixture reads as it should" ;;
    esac
done

echo "== play timeline: mutants of title_verdict.py"
ps_mutant() {   # <name> <fixture that must catch it> <old> <new>
    local name="$1" want="$2" m="$T/ps-mutant.py"
    python3 - "$TESTING/title_verdict.py" "$m" "$3" "$4" <<'PY'
import sys
src, dst, old, new = sys.argv[1:5]
s = open(src).read()
if s.count(old) != 1:
    sys.exit("anchor not found once: %r" % old)
open(dst, "w").write(s.replace(old, new))
PY
    [ $? = 0 ] || { bad "mutant '$name': its anchor is gone from title_verdict.py -- update the mutant"; return; }
    case "$(ps_legs "$m")" in
        *"FAIL $want:"*) ok "mutant caught by the '$want' fixture: $name" ;;
        *) bad "mutant SURVIVED the '$want' fixture: $name" ;;
    esac
    rm -f "$m"
}
ps_mutant "score every window, play or not" excluded \
    'kept = [w for w in windows if in_spans((w[4] + w[5]) / 2.0, tl["play_spans"])]' \
    'kept = list(windows)'
ps_mutant "never fail on menu time" menu \
    'and (tl["play_share"] is None or tl["play_share"] < play_share_min):' \
    'and False:'
ps_mutant "drop the state in force at the mark" allplay \
    '        if t <= mark_t:
            cur = s' \
    '        pass'
unset PS
