# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# A perflog build (pathfind.py --perflog, lane.pathtele1013) carries ~1.2 ms/frame
# of render-thread telemetry overhead and must never be read as a Playable
# candidate (#433 Part C, lane.pathrules1013). hold_verdict (the FINAL judge,
# pathfind.py) and hold_check's provisional folder (the judge DURING a hold,
# before result.json exists) both write "build" into request.json for exactly
# this reason -- title_verdict.py's judge() must void on either file's "build".
#
# Modeled on 89-title-verdict.sh (read, not edited): fixtures + a mutant per
# check, so a check that is green because it looks at nothing is caught.

echo "== title verdict: perflog build voids"
PV="$T/verdictperflog"; rm -rf "$PV"; mkdir -p "$PV"

python3 - "$PV" <<'PY'
import json, os, sys
root = sys.argv[1]


def make(name, *, result_build=None, request_build=None, env=None):
    d = os.path.join(root, name)
    os.makedirs(d)
    open(os.path.join(d, "logcat.txt"), "w").close()
    open(os.path.join(d, "run.log"), "w").write("ROUTE 13:00:00.000 start r.route serial=x\n")
    req = {"id": "fx-" + name, "title": "Sim", "title_id": "00000000", "route_name": "r", "ref": "abc"}
    if request_build is not None:
        req["build"] = request_build
        req["env"] = env
    json.dump(req, open(os.path.join(d, "request.json"), "w"))
    if result_build is not None:
        res = {"kind": "soak", "device_label": "nova", "apk_sha": "0" * 12, "ref": "abc", "build": result_build}
        if env is not None:
            res["env"] = env
        json.dump(res, open(os.path.join(d, "result.json"), "w"))


# the final judge, after finish() has written result.json's "build": "perflog"
make("result", result_build="perflog", env=["HAKUX_GPUXFR=1"])
# the provisional (mid-hold) judge: result.json does not exist yet, only hold_verdict's /
# hold_check's own request.json has "build" -- this is the case pathtele1013's author could
# not fix (outside their territory): title_verdict read only res.get("build"), always None here
make("request", request_build="perflog", env=["HAKUX_GPUXFR=1"])
# a plain (non-perflog) run: neither file names a build; must not void
make("plain")
PY

verdict_void() {   # <title_verdict.py> -> one line per fixture: "<name> <void or '-'>"
    local vpy="$1" f
    for f in result request plain; do
        rm -f "$PV/$f/verdict.json"
        # PYTHONPATH: a mutant copy lives outside docs/testing/, so its own
        # `HERE = dirname(__file__)` misses thermal_state.py/hitch_report.py
        # unless the real docs/testing/ is still on the search path.
        PYTHONPATH="$TESTING${PYTHONPATH:+:$PYTHONPATH}" python3 "$vpy" "$PV/$f" --targets "$TESTING/titles/targets.toml" >/dev/null 2>&1 \
            || { echo "$f: title_verdict exited non-zero"; continue; }
        python3 -c "
import json, sys
v = json.load(open(sys.argv[1]))
print(sys.argv[2], v.get('void') or '-', v.get('build') or '-')
" "$PV/$f/verdict.json" "$f"
    done
}

out=$(verdict_void "$TESTING/title_verdict.py")
case "$out" in
    *"result build: perflog"*) ok "result.json's perflog build voids the final judge" ;;
    *) bad "result.json's perflog build should void: $(printf '%s\n' "$out" | grep '^result ')" ;;
esac
case "$out" in
    *"request build: perflog"*) ok "request.json's perflog build voids a provisional (mid-hold) judge with no result.json yet" ;;
    *) bad "request.json's perflog build should void: $(printf '%s\n' "$out" | grep '^request ')" ;;
esac
case "$out" in
    *"plain -"*) ok "a plain folder (no build field anywhere) does not void" ;;
    *) bad "a plain folder should not void: $(printf '%s\n' "$out" | grep '^plain ')" ;;
esac

echo "== title verdict: perflog mutants of title_verdict.py"
tv_mutant() {   # <name> <fixture line that must change> <python: old> <python: new>
    local name="$1" want="$2" m="$T/tv-perflog-mutant.py"
    python3 - "$TESTING/title_verdict.py" "$m" "$3" "$4" <<'PY'
import sys
src, dst, old, new = sys.argv[1:5]
s = open(src).read()
if s.count(old) != 1:
    sys.exit("anchor not found once: %r" % old)
open(dst, "w").write(s.replace(old, new))
PY
    [ $? = 0 ] || { bad "mutant '$name': its anchor is gone from title_verdict.py -- update the mutant"; return; }
    local after
    after=$(verdict_void "$m")
    case "$after" in
        *"$want"*) ok "mutant caught: $name" ;;
        *) bad "mutant SURVIVED: $name ($after)" ;;
    esac
    rm -f "$m"
}
tv_mutant "drop the perflog void check entirely" "result -" \
    'elif res.get("build") == "perflog" or req.get("build") == "perflog":' \
    'elif False:'
tv_mutant "read only result.json's build (not request.json's, pre-finish())" "request -" \
    'res.get("build") == "perflog" or req.get("build") == "perflog"' \
    'res.get("build") == "perflog"'
tv_mutant "void every run regardless of build" "plain build: perflog" \
    'elif res.get("build") == "perflog" or req.get("build") == "perflog":' \
    'elif True:'
