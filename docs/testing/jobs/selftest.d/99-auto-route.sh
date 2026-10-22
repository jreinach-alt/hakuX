# Sourced by ../selftest.sh: $T, $TESTING, ok/bad/check. No shebang, no exit.
#
# routebuild1021 (#433, owner 2026-10-21): "This doesn't resolve the gap where the
# dispatcher would reject these requests if it doesn't have a known path." A title
# with no route of its own is given the shared routes/auto.route (drive.py finds the
# way in, replaying the title's book when one is recorded), and the profile gate
# admits it with no golden as it admits --find-route.
#
# THE CASES (titlestate.py, real code and two mutants):
#   no-auto    no auto.route in the routes tree: suggest_route names nothing, and an
#              `any` route on a title with no golden is still refused (A1's rule,
#              unchanged). Fails if the fallback invents a route that is not there.
#   suggest    with auto.route: suggest_route gives ("auto", "auto").
#   admit      admit() of the auto route, no golden: admitted, clause auto-route.
#              The mutant with that branch removed refuses it (the old gap).
#   other-any  an `any` route that is not auto, no golden: still refused.
#   proven     a title with a PROVEN route: suggest_route gives that route, and the
#              auto route is refused for it (R3, as for --find-route). The mutant
#              with the R3 check dropped admits it.

echo "== auto route: a title with no known path is admitted, not refused (routebuild1021)"
AR="$T/autoroute"; rm -rf "$AR"; mkdir -p "$AR/m-admit" "$AR/m-r3"
TSSRC="$TESTING/titles/titlestate.py"
# saves.py (imported by titlestate.py) imports extract_results from its parent directory,
# and loads make_xbox_hdd.py from MAKE_XBOX_HDD (99-profile-gate's mutants do the same)
cp "$TESTING/titles/saves.py" "$AR/m-admit/"; cp "$TESTING/titles/saves.py" "$AR/m-r3/"
cp "$TESTING/extract_results.py" "$AR/extract_results.py"
python3 - "$TSSRC" "$AR" <<'PY'
import sys
src, d = sys.argv[1:]
s = open(src).read()
a = '''        return dict(out, admit=True, clause="auto-route")\n'''
assert s.count(a) == 1, "auto-route admit anchor"
open(d + "/m-admit/titlestate.py", "w").write(s.replace(a, ""))
b = '''        if kp["known"] and kp["route_name"] != AUTO_ROUTE:\n'''
assert s.count(b) == 1, "auto-route R3 anchor"
open(d + "/m-r3/titlestate.py", "w").write(s.replace(b, "        if False:\n"))
PY
check "both mutants were written (their anchors still match titlestate.py)" \
    test -f "$AR/m-admit/titlestate.py" -a -f "$AR/m-r3/titlestate.py"

cat > "$AR/arcases.py" <<'PY'
import json, os, sys, tempfile
os.environ["MAKE_XBOX_HDD"] = os.path.join(sys.argv[3], "tools", "make_xbox_hdd.py")
sys.path.insert(0, sys.argv[1])
auto_text = open(sys.argv[2]).read()
import titlestate as ts

cases = []
def case(name, want, got, detail=""):
    cases.append((name, want, got, detail))

with tempfile.TemporaryDirectory() as tmp:
    for k, v in (("TITLESTATE_DIR", "ts"), ("DISPATCH_DIR", "dispatch"), ("TITLE_ROUTES", "routes"),
                 ("PATHFIND_KNOW", "pathknow")):
        os.environ[k] = os.path.join(tmp, v)
    os.environ["TITLE_TARGETS"] = os.path.join(tmp, "targets.toml")
    os.environ.pop("PROFILE_TRANSITION_PATH", None)
    for k in ("DISPATCH_DIR", "TITLE_ROUTES"):
        os.makedirs(os.environ[k])
    os.makedirs(os.path.join(os.environ["PATHFIND_KNOW"], "paths"))
    NEW, PROVEN = "AAAA0101", "AAAA0102"
    with open(os.environ["TITLE_TARGETS"], "w") as fh:
        fh.write('[titles.AAAA0102]\nroute = "p-route"\n')
    with open(os.path.join(os.environ["TITLE_ROUTES"], "p-route.route"), "w") as fh:
        fh.write("# state: first-run\nmark gameplay\nstep 1\n")
    any_text = "# state: any\nstep 1\n"

    name, note = ts.suggest_route(NEW)
    case("no-auto: suggest_route names nothing without auto.route", None, name, note)
    r = ts.admit(NEW, route_name="other", route_text=any_text)
    case("no-auto: an `any` route with no golden is still refused", False, r["admit"], str(r))

    with open(os.path.join(os.environ["TITLE_ROUTES"], "auto.route"), "w") as fh:
        fh.write(auto_text)
    got = ts.suggest_route(NEW)
    case("suggest: suggest_route falls back to the auto route", ("auto", "auto"), got)
    r = ts.admit(NEW, route_name="auto", route_text=auto_text)
    case("admit: the auto route is admitted with no golden", True, r["admit"], str(r))
    case("admit: under clause auto-route", "auto-route", r["clause"], str(r))
    r = ts.admit(NEW, route_name="other", route_text=any_text)
    case("other-any: an `any` route that is not auto is still refused", False, r["admit"], str(r))

    rdir = os.path.join(os.environ["DISPATCH_DIR"], "results", "1-1700000000-p-1")
    os.makedirs(rdir)
    json.dump({"title": PROVEN + "-P.iso", "route_name": "p-route", "requester": "ar"},
              open(os.path.join(rdir, "request.json"), "w"))
    json.dump({"reached_gameplay": True}, open(os.path.join(rdir, "verdict.json"), "w"))
    got = ts.suggest_route(PROVEN)
    case("proven: suggest_route gives the proven route, not auto", ("p-route", "proven"), got)
    r = ts.admit(PROVEN, route_name="auto", route_text=auto_text)
    case("proven: the auto route is refused on a title with a proven route", False, r["admit"], str(r))

for name, want, got, detail in cases:
    print("case %-66s want %-16s got %-16s %s" % (name, want, got,
          "ok" if got == want else ("MISMATCH " + detail if detail else "MISMATCH")))
PY

AUTO="$TESTING/titles/routes/auto.route"
REALOUT=$(python3 "$AR/arcases.py" "$TESTING/titles" "$AUTO" "$REPO" 2>&1)
check "arcases ran all 8 cases against the real code" [ "$(grep -c '^case ' <<< "$REALOUT")" -eq 8 ]
if grep -qE 'MISMATCH|Traceback' <<< "$REALOUT"; then
    bad "the real code gets a case wrong: $(grep -E 'MISMATCH|Traceback' <<< "$REALOUT" | head -3)"
else
    ok "and the real code gets every one right"
fi
MOUT=$(python3 "$AR/arcases.py" "$AR/m-admit" "$AUTO" "$REPO" 2>&1)
check "mutant (no auto-route admit): the auto route is refused again, as before this lane" \
    grep -qE '^case admit: the auto route is admitted.*want True +got False +MISMATCH' <<< "$MOUT"
MOUT=$(python3 "$AR/arcases.py" "$AR/m-r3" "$AUTO" "$REPO" 2>&1)
check "mutant (R3 dropped for auto): the auto route is admitted over a proven route" \
    grep -qE '^case proven: the auto route is refused.*want False +got True +MISMATCH' <<< "$MOUT"
check "routes/auto.route passes route.sh --check" bash "$TESTING/titles/route.sh" --check "$AUTO"
