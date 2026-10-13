# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# lane.profilegate1011 (#433): THE PROFILE GATE. A title run is refused only
# when it would redo work already kept -- R1 (a first-run route remaking a
# kept profile), R2 (a first-run route that keeps nothing), R3 (finding a
# route blind for a title that already has a PROVEN one) -- with three
# overrides (--remake-profile/--path-broken) and a grandfather
# (profile-transition.toml). Addendum 2: R3's "known path" test is narrower
# at queue time (a proven route only) than inside pathfind.py (also a bare
# pathknow success), because a route's own first proof soak still needs
# --find-route even after pathknow already reached gameplay once.
#
# A. request.sh, queue time (the public CLI) -- including A8-A10, Addendum 4's
# bare-TitleID defect fix (--title 5454000F passed queue-time checks and
# failed mid-claim; request.sh now refuses it and names the real file).
# B. dispatcher.sh's profile_gate_check(), claim time -- called directly,
# proving nothing is grandfathered there: a request dropped straight into
# dispatch/queue (no request.sh step) is gated the same way. C. the canonical
# mutants M1-M7 (titlestate.py: admit()/compose()/live_transition(),
# sed-copy-and-compare, same technique as 83-blank-rule.sh), D. M8
# (dispatcher.sh's claim-time call site itself), and F. M9 (request.sh's
# bare-TitleID check itself). E. pathfind.py's own dry-mode R3 check (real
# code only; M4 is titlestate.py's admit(), not pathfind.py -- see C).

echo "== profile gate: R1/R2/R3, overrides, Addendum 2, nothing grandfathered at claim"
PG="$T/profilegate"; rm -rf "$PG"; mkdir -p "$PG"
pg_has()   { printf '%s\n' "$2" | grep -qE -- "$1"; }
pg_hasnt() { ! printf '%s\n' "$2" | grep -qE -- "$1"; }

# ------------------------------------------------------- A. request.sh (queue time)
mkdir -p "$PG/a-routes"
cat > "$PG/a-targets.toml" <<'TOML'
[titles.AAAA1003]
route = "a3-route"
iso = { nova = "A3 Title (USA).xiso.iso" }
TOML
cat > "$PG/a-routes/a3-route.route" <<'ROUTE'
mark gameplay
step 1
ROUTE

pg_rq() {  # <dir> <who> <title.iso> [extra request.sh args...]
    local d="$1" who="$2" title="$3"; shift 3
    DISPATCH_DIR="$d" TITLESTATE_DIR="$d/titlestate" TITLE_TARGETS="$PG/a-targets.toml" \
        TITLE_ROUTES="$PG/a-routes" MAKE_XBOX_HDD="$REPO/tools/make_xbox_hdd.py" \
        bash "$TESTING/request.sh" --who "$who" --purpose "profile gate selftest" --no-expect selftest \
        --title "$title" --seconds 60 "$@" 2>&1
}
pg_dir() { local d="$PG/$1"; rm -rf "$d"; mkdir -p "$d"/{queue,running,results,pilots}; echo "$d"; }
pg_n()   { ls "$1"/queue/*.req 2>/dev/null | wc -l; }
pg_ok()  { grep -qE "^queued [0-9]+-$1-[0-9]+$" <<< "$2"; }
pg_field() {  # <dir> <json key> -> value from the one queued request
    python3 -c 'import glob, json, sys
p = glob.glob(sys.argv[1] + "/queue/*.req")
print(json.load(open(p[0])).get(sys.argv[2], "") if p else "<no request queued>")' "$1" "$2"
}

# A1/A2: a title with no golden and no known route.
D=$(pg_dir a12)
out=$(pg_rq "$D" pga1 "AAAA1001-A1.iso"); rc=$?
if [ "$rc" = 2 ] && pg_has 'no profile \(no golden\) and no route-finding' "$out"; then
    ok "A1: no golden, no --find-route -- refused, names the way forward"
else bad "A1: exit $rc, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "A1: and nothing was queued" [ "$(pg_n "$D")" -eq 0 ]

out=$(pg_rq "$D" pga2 "AAAA1001-A1.iso" --find-route "selftest finding AAAA1001's first route")
if pg_ok pga2 "$out"; then ok "A2: --find-route (12+ chars) admits the same title"
else bad "A2: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "A2: the request records find_route and profile_clause find-route" \
      bash -c '[ "$(python3 -c "import glob,json,sys; p=glob.glob(sys.argv[1]+\"/queue/*.req\")[-1]; r=json.load(open(p)); print(r[\"find_route\"] and r[\"profile_clause\"]==\"find-route\")" "$1")" = True ]' _ "$D"

# A3/A4: a title with a PROVEN route.
D=$(pg_dir a34)
mkdir -p "$D/results/1-1700000000-a3-1"
python3 -c 'import json,sys
json.dump({"title": "AAAA1003-A3.iso", "route_name": "a3-route", "requester": "pg"}, open(sys.argv[1]+"/request.json", "w"))
json.dump({"reached_gameplay": True}, open(sys.argv[1]+"/verdict.json", "w"))' "$D/results/1-1700000000-a3-1"
out=$(pg_rq "$D" pga3 "AAAA1003-A3.iso" --find-route "finding AAAA1003's route again, blind"); rc=$?
if [ "$rc" = 2 ] && pg_has 'already has a proven route' "$out"; then
    ok "A3: --find-route is refused once the route is proven"
else bad "A3: exit $rc, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi

out=$(pg_rq "$D" pga4 "AAAA1003-A3.iso" --find-route "is it actually broken" --path-broken "1-1700000000-a3-1")
if pg_ok pga4 "$out"; then ok "A4: --path-broken naming a run of the proven route overrides it"
else bad "A4: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "A4: the request's profile_clause is path-broken" \
      [ "$(pg_field "$D" profile_clause)" = path-broken ]

# A5/A6/A7: --save.
D=$(pg_dir a567)
SAVEID=$(python3 - "$D" "$TESTING" <<'PY'
import hashlib, json, os, sys
root, testing = sys.argv[1], sys.argv[2]
tid = "AAAA1002"
rel = "UDATA/%s/TitleMeta.xbx" % tid
data = b"a save for A5/A6"
p = os.path.join(root, "import-src", tid, *rel.split("/"))
os.makedirs(os.path.dirname(p), exist_ok=True)
open(p, "wb").write(data)
m = {"title_id": tid, "entries": [{"path": rel, "dir": False, "bytes": len(data),
     "sha256": hashlib.sha256(data).hexdigest(), "times": [1, 2, 3, 4, 5, 6]}], "source": {}}
sys.path.insert(0, os.path.join(testing, "titles"))
import saves
m["save_id"] = saves.save_id(m)
json.dump(m, open(os.path.join(root, "import-src", tid, "save.json"), "w"))
print(m["save_id"])
PY
)
TITLESTATE_DIR="$D/titlestate" python3 "$TESTING/titles/titlestate.py" import-save --dir "$D/import-src/AAAA1002" >/dev/null
TITLESTATE_DIR="$D/titlestate" python3 "$TESTING/titles/titlestate.py" promote --title-id AAAA1002 --save "$SAVEID" --by pg >/dev/null

out=$(pg_rq "$D" pga5 "AAAA1002-A5.iso" --save "$SAVEID")
if pg_ok pga5 "$out"; then ok "A5: --save <in-store id> admits (the title now has a golden too)"
else bad "A5: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "A5: the request's save field is the stored id" \
      [ "$(pg_field "$D" save)" = "$SAVEID" ]

out=$(pg_rq "$D" pga6 "AAAA1002-A5.iso" --save "not-a-real-save-id"); rc=$?
if [ "$rc" = 2 ] && pg_has 'is not in the store' "$out"; then
    ok "A6: --save naming a save not in the store is refused before any device is touched"
else bad "A6: exit $rc, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi

# request.sh's own "need --title or --suites" gate (line 212) fires before
# --save's own "needs a title the gate can identify" line ever could -- so a
# titleless --save is refused on the public CLI either way; the later line is
# defence-in-depth for a path (--suites, no --title) this selftest does not
# drive, since it would need the pgraph/vsh disc-build machinery for real.
out=$(DISPATCH_DIR="$D" TITLESTATE_DIR="$D/titlestate" bash "$TESTING/request.sh" --who pga7 \
      --purpose "profile gate selftest" --no-expect selftest --save "$SAVEID" --seconds 60 2>&1); rc=$?
if [ "$rc" = 2 ] && pg_has 'need --suites, or --title for a soak' "$out"; then
    ok "A7: --save with neither --title nor --suites is refused before the gate even runs"
else bad "A7: exit $rc, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi

# A8/A9/A10: a bare 8-hex TitleID is not a file name (Addendum 4). tid_for_iso()
# takes the 8-hex HEAD of any name it is given, so a bare TitleID typed as
# --title is its own head and would otherwise pass straight through to the
# dispatcher's literal ISO-root file lookup, which then fails mid-claim.
D=$(pg_dir a8910)
out=$(pg_rq "$D" pga8 "AAAA1003"); rc=$?
if [ "$rc" = 2 ] && pg_has 'bare TitleID' "$out" && pg_has 'A3 Title \(USA\)\.xiso\.iso' "$out"; then
    ok "A8: a bare TitleID with a targets.toml iso entry -- refused, names the file"
else bad "A8: exit $rc, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "A8: nothing was queued" [ "$(pg_n "$D")" -eq 0 ]

out=$(pg_rq "$D" pga9 "FFFF9999"); rc=$?
if [ "$rc" = 2 ] && pg_has 'bare TitleID' "$out" && pg_has 'devices\.sh' "$out"; then
    ok "A9: a bare TitleID with no known on-device name -- refused, names devices.sh"
else bad "A9: exit $rc, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi

out=$(pg_rq "$D" pga10 "AAAA1003-A3.iso" --find-route "selftest: a real file name still queues (Addendum 4)")
if pg_ok pga10 "$out"; then ok "A10: a full file name (not a bare TitleID) still queues normally"
else bad "A10: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi

unset -f pg_rq pg_dir pg_n pg_ok pg_field

# ----------------------------------------------- B. dispatcher.sh (claim time)
echo "[titles]" > "$PG/b-targets.toml"
mkdir -p "$PG/b-routes"
cat > "$PG/b-routes/b6-route.route" <<'ROUTE'
mark gameplay
step 1
ROUTE
cat > "$PG/b-targets.toml" <<'TOML'
[titles.BBBB0006]
route = "b6-route"
TOML

pg_src() {  # <dispatcher.sh path> <shell expr>
    ( export DISPATCH_DIR="$PG/bdd" TITLESTATE_DIR="$PG/bdd/titlestate" DISPATCH_TREE="$REPO" \
             DISPATCH_REPO="$REPO" TITLE_TARGETS="$PG/b-targets.toml" TITLE_ROUTES="$PG/b-routes"
      . "$1" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$2" )
}
pg_req() {  # <path> <title_id> [key=val ...]
    local path="$1" tid="$2"; shift 2
    python3 -c 'import json, sys
path, tid = sys.argv[1], sys.argv[2]
d = {"title_id": tid, "route_name": "", "route": "", "find_route": "", "remake_profile": "", "path_broken": ""}
for kv in sys.argv[3:]:
    k, v = kv.split("=", 1)
    d[k] = v
json.dump(d, open(path, "w"))' "$path" "$tid" "$@"
}
rm -rf "$PG/bdd"; mkdir -p "$PG/bdd"

# B1: nothing is grandfathered at claim -- the same refusal as A1, with no request.sh step.
mkdir -p "$PG/bdd/r1"
pg_req "$PG/bdd/req1.json" BBBB0001
out=$(pg_src "$TESTING/dispatcher.sh" "profile_gate_check '$PG/bdd/req1.json' '$PG/bdd/r1'"); rc=$?
if [ "$rc" = 3 ] && pg_has 'no profile \(no golden\) and no route-finding' "$(cat "$PG/bdd/r1/profile.refused")"; then
    ok "B1: a request dropped straight into the queue is gated identically to A1"
else bad "B1: rc=$rc, $(cat "$PG/bdd/r1/profile.refused" 2>/dev/null)"; fi

# B2/B3: R1, and its override.
mkdir -p "$PG/bdd/r2" "$PG/bdd/r3" "$PG/bdd/titlestate"
SAVEID2=$(python3 - "$PG/bdd" "$TESTING" <<'PY'
import hashlib, json, os, sys
root, testing = sys.argv[1], sys.argv[2]
tid = "BBBB0002"
rel = "UDATA/%s/TitleMeta.xbx" % tid
data = b"B2's kept profile"
p = os.path.join(root, "import-src", tid, *rel.split("/"))
os.makedirs(os.path.dirname(p), exist_ok=True)
open(p, "wb").write(data)
m = {"title_id": tid, "entries": [{"path": rel, "dir": False, "bytes": len(data),
     "sha256": hashlib.sha256(data).hexdigest(), "times": [1, 2, 3, 4, 5, 6]}], "source": {}}
sys.path.insert(0, os.path.join(testing, "titles"))
import saves
m["save_id"] = saves.save_id(m)
json.dump(m, open(os.path.join(root, "import-src", tid, "save.json"), "w"))
print(m["save_id"])
PY
)
TITLESTATE_DIR="$PG/bdd/titlestate" python3 "$TESTING/titles/titlestate.py" import-save --dir "$PG/bdd/import-src/BBBB0002" >/dev/null
TITLESTATE_DIR="$PG/bdd/titlestate" python3 "$TESTING/titles/titlestate.py" promote --title-id BBBB0002 --save "$SAVEID2" --by pg >/dev/null

pg_req "$PG/bdd/req2.json" BBBB0002 'route=# state: first-run
step 1'
out=$(pg_src "$TESTING/dispatcher.sh" "profile_gate_check '$PG/bdd/req2.json' '$PG/bdd/r2'"); rc=$?
if [ "$rc" = 3 ] && pg_has 'kept profile' "$(cat "$PG/bdd/r2/profile.refused")"; then
    ok "B2: R1 -- a first-run route is refused on a title with a kept profile"
else bad "B2: rc=$rc, $(cat "$PG/bdd/r2/profile.refused" 2>/dev/null)"; fi

pg_req "$PG/bdd/req3.json" BBBB0002 'route=# state: first-run
step 1' 'remake_profile=the kept profile was lost, selftest'
out=$(pg_src "$TESTING/dispatcher.sh" "profile_gate_check '$PG/bdd/req3.json' '$PG/bdd/r3'"); rc=$?
check "B3: --remake-profile overrides R1" [ "$rc" = 0 ]

# B4/B5: R2, and `mark profile-saved`.
mkdir -p "$PG/bdd/r4" "$PG/bdd/r5"
pg_req "$PG/bdd/req4.json" BBBB0004 'route=# state: first-run
step 1'
out=$(pg_src "$TESTING/dispatcher.sh" "profile_gate_check '$PG/bdd/req4.json' '$PG/bdd/r4'"); rc=$?
if [ "$rc" = 3 ] && pg_has 'make the profile first' "$(cat "$PG/bdd/r4/profile.refused")"; then
    ok "B4: R2 -- a first-run route with no \`mark profile-saved\` is refused on a title with no golden"
else bad "B4: rc=$rc, $(cat "$PG/bdd/r4/profile.refused" 2>/dev/null)"; fi

pg_req "$PG/bdd/req5.json" BBBB0004 'route=# state: first-run
mark profile-saved
step 1'
out=$(pg_src "$TESTING/dispatcher.sh" "profile_gate_check '$PG/bdd/req5.json' '$PG/bdd/r5'"); rc=$?
check "B5: \`mark profile-saved\` admits the same title (clause make-profile)" [ "$rc" = 0 ]

# B6: Addendum 2's full sequence, at this layer: pathknow-only admits a queued
# find-route; proving the route then blocks it; --path-broken overrides again.
mkdir -p "$PG/bdd/pathknow/paths" "$PG/bdd/r6a" "$PG/bdd/r6b" "$PG/bdd/r6c"
echo '{"complete": true, "result": "gameplay"}' > "$PG/bdd/pathknow/paths/BBBB0006.json"
pg_req "$PG/bdd/req6.json" BBBB0006 'find_route=proving b6-route for the first time, Addendum 2'
out=$(pg_src "$TESTING/dispatcher.sh" "PATHFIND_KNOW='$PG/bdd/pathknow' profile_gate_check '$PG/bdd/req6.json' '$PG/bdd/r6a'"); rc=$?
check "B6a: a pathknow-only title still admits a queued find-route (Addendum 2)" [ "$rc" = 0 ]

mkdir -p "$PG/bdd/results/1-1700000002-b6-1"
python3 -c 'import json,sys
json.dump({"title": "BBBB0006-B6.iso", "route_name": "b6-route", "requester": "pg"}, open(sys.argv[1]+"/request.json", "w"))
json.dump({"reached_gameplay": True}, open(sys.argv[1]+"/verdict.json", "w"))' "$PG/bdd/results/1-1700000002-b6-1"
out=$(pg_src "$TESTING/dispatcher.sh" "PATHFIND_KNOW='$PG/bdd/pathknow' profile_gate_check '$PG/bdd/req6.json' '$PG/bdd/r6b'"); rc=$?
if [ "$rc" = 3 ] && pg_has 'already has a proven route' "$(cat "$PG/bdd/r6b/profile.refused")"; then
    ok "B6b: once that same route is proven, the queued find-route is refused"
else bad "B6b: rc=$rc, $(cat "$PG/bdd/r6b/profile.refused" 2>/dev/null)"; fi

pg_req "$PG/bdd/req6c.json" BBBB0006 'find_route=is it actually broken now' 'path_broken=1-1700000002-b6-1'
out=$(pg_src "$TESTING/dispatcher.sh" "PATHFIND_KNOW='$PG/bdd/pathknow' profile_gate_check '$PG/bdd/req6c.json' '$PG/bdd/r6c'"); rc=$?
check "B6c: --path-broken naming that proof overrides it again" [ "$rc" = 0 ]

# B7: the profile-transition.toml grandfather admits past R1.
mkdir -p "$PG/bdd/r7"
cat > "$PG/bdd/transitions.toml" <<'TOML'
[[entry]]
route = "b7-route"
until = "2100-01-01T00:00:00Z"
why = "selftest"
approved = "selftest"
TOML
pg_req "$PG/bdd/req7.json" BBBB0007 'route_name=b7-route' 'route=# state: first-run
step 1'
out=$(pg_src "$TESTING/dispatcher.sh" "PROFILE_TRANSITION_PATH='$PG/bdd/transitions.toml' profile_gate_check '$PG/bdd/req7.json' '$PG/bdd/r7'"); rc=$?
check "B7: a live profile-transition.toml entry admits past R1 too (today's existing fallback)" [ "$rc" = 0 ]

unset -f pg_src pg_req

# -------------------------------------- C. mutants M1-M7 (titlestate.py): sed-copy,
# confirm the sed changed something, run the real-vs-mutant harness, assert each
# mutant gets its one case wrong (83-blank-rule.sh's technique).
PGSRC="$REPO/docs/testing/titles/titlestate.py"
SAVES_SRC="$REPO/docs/testing/titles/saves.py"
cp "$REPO/docs/testing/extract_results.py" "$PG/extract_results.py"
mkdir -p "$PG/real"; cp "$PGSRC" "$PG/real/titlestate.py"; cp "$SAVES_SRC" "$PG/real/saves.py"

declare -A PGMUT=(
  [m1]='s/^        if gg:  # R1: a golden of EITHER kind already exists -- do not remake it$/        if False and gg:  # M1 mutant: R1 off/'
  [m2]='s/^        if "mark profile-saved" in (route_text or ""):$/        if True:  # M2 mutant: R2 off/'
  [m3]='s/^            if kp\["known"\]:$/            if False:  # M3 mutant: R3 off for queued runs/'
  [m4]='s/kp = known_path(title_id, broad=False)  # R3, the narrower (proven-only) test/kp = known_path(title_id, broad=True)  # M4 mutant: broad applied to queued runs/'
  [m5]='s/^    if tid_for_iso(req.get("title") or "") != title_id:$/    if False:  # M5 mutant: title check off/'
  [m6]='s/^        if save not in store_saves(dt):$/        if False:  # M6 mutant: store check off/'
  [m7]='s/^        if e\["route"\] == route_name and now_s < e\["until"\]:$/        if e["route"] == route_name:  # M7 mutant: until check dropped/'
)
for name in m1 m2 m3 m4 m5 m6 m7; do
    mkdir -p "$PG/$name"
    sed "${PGMUT[$name]}" "$PGSRC" > "$PG/$name/titlestate.py"
    cp "$SAVES_SRC" "$PG/$name/saves.py"
    check "$name: the sed mutation actually changed titlestate.py" \
          bash -c "! cmp -s '$PGSRC' '$PG/$name/titlestate.py'"
done

cat > "$PG/pgcases.py" <<'PY'
import hashlib, importlib, json, os, sys, tempfile

# saves.py's own mkhdd loader defaults to ../../../tools/make_xbox_hdd.py,
# which is right for the real tree but not for this isolated mutant copy.
os.environ["MAKE_XBOX_HDD"] = os.path.join(sys.argv[2], "tools", "make_xbox_hdd.py")
sys.path.insert(0, sys.argv[1])
import titlestate as ts
importlib.reload(ts)

cases = []


def case(name, want, got, detail=""):
    cases.append((name, want, got, detail))


def make_save(root, tid, files):
    d = os.path.join(root, tid)
    entries = []
    for rel, data in files.items():
        p = os.path.join(d, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(data)
        entries.append({"path": rel, "dir": False, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(), "times": [1, 2, 3, 4, 5, 6]})
    m = {"title_id": tid, "entries": entries, "source": {}}
    m["save_id"] = ts.saves.save_id(m)
    json.dump(m, open(os.path.join(d, "save.json"), "w"))
    return d, m


with tempfile.TemporaryDirectory() as tmp:
    os.environ["TITLESTATE_DIR"] = os.path.join(tmp, "ts")
    os.environ["DISPATCH_DIR"] = os.path.join(tmp, "dispatch")
    os.environ["TITLE_ROUTES"] = os.path.join(tmp, "routes")
    os.environ["TITLE_TARGETS"] = os.path.join(tmp, "targets.toml")
    os.environ["PATHFIND_KNOW"] = os.path.join(tmp, "pathknow")
    os.environ.pop("PROFILE_TRANSITION_PATH", None)
    os.makedirs(os.environ["DISPATCH_DIR"])
    os.makedirs(os.environ["TITLE_ROUTES"])
    os.makedirs(os.path.join(os.environ["PATHFIND_KNOW"], "paths"))

    R1T, R2T, R3T, OTHT, PKT = "AAAA0001", "AAAA0002", "AAAA0003", "AAAA0005", "AAAA0004"
    with open(os.environ["TITLE_TARGETS"], "w") as fh:
        fh.write('[titles.AAAA0003]\nroute = "m-route"\n\n[titles.AAAA0004]\nroute = "pk-route"\n')
    for rn in ("m-route", "pk-route"):
        with open(os.path.join(os.environ["TITLE_ROUTES"], rn + ".route"), "w") as fh:
            fh.write("mark gameplay\nstep 1\n")

    fix = os.path.join(tmp, "fix")
    d1, m1 = make_save(os.path.join(fix, "r1"), R1T, {f"UDATA/{R1T}/TitleMeta.xbx": b"x"})
    ts.import_save(d1)
    ts.set_golden(R1T, m1["save_id"], by="pg-mutant", how="seed")

    # M1: R1 -- a first-run route on a title with a kept profile. `mark
    # profile-saved` is included so a disabled R1 falls through to an
    # ADMIT via R2's clause, not a refusal that only looks like R1 held.
    r = ts.admit(R1T, route_text="# state: first-run\nmark profile-saved\nstep 1\n")
    case("M1: R1 refuses a first-run route on a title with a kept profile", False, r["admit"], str(r))

    # M2: R2 -- a first-run route with no `mark profile-saved`, no golden.
    r = ts.admit(R2T, route_text="# state: first-run\nstep 1\n")
    case("M2: R2 refuses a first-run route with no `mark profile-saved`", False, r["admit"], str(r))

    # M3/M4/M5: R3T has a proven route.
    rdir = os.path.join(os.environ["DISPATCH_DIR"], "results", "1-1700000000-m-1")
    os.makedirs(rdir)
    json.dump({"title": f"{R3T}-M3.iso", "route_name": "m-route", "requester": "pg"},
              open(os.path.join(rdir, "request.json"), "w"))
    json.dump({"reached_gameplay": True}, open(os.path.join(rdir, "verdict.json"), "w"))

    # M3: R3 off for queued runs.
    r = ts.admit(R3T, find_route="finding it again, blind, for M3")
    case("M3: R3 refuses a queued find-route once the route is proven", False, r["admit"], str(r))

    # M5: --path-broken naming a run of a DIFFERENT title must still be refused.
    other_rdir = os.path.join(os.environ["DISPATCH_DIR"], "results", "1-1700000001-oth-1")
    os.makedirs(other_rdir)
    json.dump({"title": f"{OTHT}-Other.iso", "route_name": "m-route", "requester": "pg"},
              open(os.path.join(other_rdir, "request.json"), "w"))
    r = ts.admit(R3T, find_route="is this actually broken, for M5", path_broken="1-1700000001-oth-1")
    case("M5: --path-broken is refused when it names a run of a DIFFERENT title", False, r["admit"], str(r))

    # M4 (Addendum 2): pathfind's broader (pathknow-aware) test must NOT gate a queued find-route.
    json.dump({"complete": True, "result": "gameplay"},
              open(os.path.join(os.environ["PATHFIND_KNOW"], "paths", f"{PKT}.json"), "w"))
    r = ts.admit(PKT, find_route="proving pk-route for the first time, for M4")
    case("M4 (Addendum 2): a queued find-route is admitted on a pathknow-only title", True, r["admit"], str(r))

    # M6: compose() must refuse a --save that is not in the store.
    try:
        ts.compose("nova", title_id=OTHT, state="any", save="not-a-real-save-id")
        got6 = True
    except ts.NoGolden:
        got6 = False
    case("M6: compose() refuses a --save that is not in the store", False, got6, "")

    # M7: an EXPIRED profile-transition.toml entry must not admit a first-run route.
    tr_path = os.path.join(tmp, "profile-transition.toml")
    with open(tr_path, "w") as fh:
        fh.write('[[entry]]\nroute = "expired-route"\nuntil = "2000-01-01T00:00:00Z"\n'
                 'why = "selftest"\napproved = "selftest"\n')
    os.environ["PROFILE_TRANSITION_PATH"] = tr_path
    r = ts.admit(R2T, route_name="expired-route", route_text="# state: first-run\nstep 1\n")
    case("M7: an EXPIRED transition entry does not admit a first-run route", False, r["admit"], str(r))

for name, want, got, detail in cases:
    print("case %-70s want %-5s got %-5s %s" % (name, want, got,
          "ok" if got == want else ("MISMATCH " + detail if detail else "MISMATCH")))
PY

REALOUT=$(python3 "$PG/pgcases.py" "$PG/real" "$REPO" 2>&1)
check "pgcases ran all 7 cases against the real code (positive control)" \
      [ "$(grep -c '^case ' <<< "$REALOUT")" -eq 7 ]
check "and the real code gets every one right (no MISMATCH, no Traceback)" \
      pg_hasnt 'MISMATCH|Traceback' "$REALOUT"

M1OUT=$(python3 "$PG/pgcases.py" "$PG/m1" "$REPO" 2>&1)
check "M1 mutant (R1 off): wrongly ADMITS a first-run route on a kept profile" \
      pg_has '^case M1:.*want False +got True +MISMATCH' "$M1OUT"

M2OUT=$(python3 "$PG/pgcases.py" "$PG/m2" "$REPO" 2>&1)
check "M2 mutant (R2 off): wrongly ADMITS a first-run route with no mark profile-saved" \
      pg_has '^case M2:.*want False +got True +MISMATCH' "$M2OUT"

M3OUT=$(python3 "$PG/pgcases.py" "$PG/m3" "$REPO" 2>&1)
check "M3 mutant (R3 off for queued runs): wrongly ADMITS a find-route on a proven title" \
      pg_has '^case M3:.*want False +got True +MISMATCH' "$M3OUT"

M4OUT=$(python3 "$PG/pgcases.py" "$PG/m4" "$REPO" 2>&1)
check "M4 mutant (broad applied to queued runs): wrongly REFUSES Addendum 2's pathknow-only find-route" \
      pg_has '^case M4 .*want True +got False +MISMATCH' "$M4OUT"

M5OUT=$(python3 "$PG/pgcases.py" "$PG/m5" "$REPO" 2>&1)
check "M5 mutant (path-broken title check off): wrongly ADMITS a result of a DIFFERENT title" \
      pg_has '^case M5:.*want False +got True +MISMATCH' "$M5OUT"

M6OUT=$(python3 "$PG/pgcases.py" "$PG/m6" "$REPO" 2>&1)
check "M6 mutant (save store check off): compose\(\) wrongly ADMITS a save not in the store" \
      pg_has '^case M6:.*want False +got True +MISMATCH' "$M6OUT"

M7OUT=$(python3 "$PG/pgcases.py" "$PG/m7" "$REPO" 2>&1)
check "M7 mutant (transition until check dropped): wrongly ADMITS past an EXPIRED entry" \
      pg_has '^case M7:.*want False +got True +MISMATCH' "$M7OUT"

# ----------------------------- D. M8: dispatcher.sh's claim-time call site itself.
DSPSRC="$TESTING/dispatcher.sh"
mkdir -p "$PG/m8/titles"
sed '/if ! profile_gate_check "\$req" "\$rdir" "\$ttid"; then/,/^        fi$/d' "$DSPSRC" > "$PG/m8/dispatcher.sh"
check "M8: the sed mutation actually changed dispatcher.sh" \
      bash -c "! cmp -s '$DSPSRC' '$PG/m8/dispatcher.sh'"
cp "$REPO/docs/testing/titles/titlestate.py" "$PG/m8/titles/titlestate.py"
cp "$REPO/docs/testing/titles/saves.py" "$PG/m8/titles/saves.py"
cp "$REPO/docs/testing/extract_results.py" "$PG/m8/extract_results.py"
cp "$REPO/docs/testing/devices.sh" "$PG/m8/devices.sh"  # dispatcher.sh sources this at HERE/devices.sh on load

pg_src8() {  # <dispatcher.sh path> <shell expr>
    ( export DISPATCH_DIR="$PG/m8dd" TITLESTATE_DIR="$PG/m8dd/titlestate" DISPATCH_TREE="$REPO" \
             DISPATCH_REPO="$REPO" TITLE_TARGETS="$PG/b-targets.toml" TITLE_ROUTES="$PG/b-routes"
      . "$1" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$2" )
}
mkdir -p "$PG/m8dd/r8"
REALBODY=$(pg_src8 "$TESTING/dispatcher.sh" 'declare -f serve_one')
MUTBODY=$(pg_src8 "$PG/m8/dispatcher.sh" 'declare -f serve_one')
check "the real dispatcher.sh's serve_one calls profile_gate_check" \
      pg_has 'profile_gate_check' "$REALBODY"
check "M8 mutant: its serve_one no longer calls profile_gate_check at all" \
      pg_hasnt 'profile_gate_check' "$MUTBODY"

python3 -c 'import json,sys
json.dump({"title_id": "AAAA9001", "route_name": "", "route": "", "find_route": "",
           "remake_profile": "", "path_broken": ""}, open(sys.argv[1], "w"))' "$PG/m8dd/req8.json"
out=$(pg_src8 "$PG/m8/dispatcher.sh" "profile_gate_check '$PG/m8dd/req8.json' '$PG/m8dd/r8'"); rc8=$?
if [ "$rc8" = 3 ] && pg_has 'no profile \(no golden\) and no route-finding' "$(cat "$PG/m8dd/r8/profile.refused")"; then
    ok "M8: profile_gate_check itself (untouched by the sed) still refuses this fixture when called directly"
else bad "M8: rc=$rc8, $(cat "$PG/m8dd/r8/profile.refused" 2>/dev/null)"; fi
echo "  (so M8's defect is specifically the missing call in serve_one, not a broken profile_gate_check)"
unset -f pg_src8

# ----------------------------- F. M9: request.sh's bare-TitleID check (Addendum 4)
# itself, sed-deleted -- proves A8's refusal actually depends on the check
# added for the "--title 5454000F passes queue-time checks and fails at serve
# time" defect, not some other refusal firing for an unrelated reason.
#
# request.sh resolves sibling scripts AND its queue-time --ref via
# $(dirname "$0") (titles/titlestate.py, devices.sh, and `git -C
# $(dirname "$0")/../.. rev-parse`), so the mutated copy cannot simply live
# in a scratch directory: it needs real siblings (symlinked -- the mutation
# is to request.sh alone) and SOME git repo two levels up for the ref check,
# which a fresh throwaway `git init` satisfies without touching this lane's
# own tree.
RQSRC="$TESTING/request.sh"
mkdir -p "$PG/m9root/docs/testing"
for f in "$TESTING"/*; do
    b="$(basename "$f")"; [ "$b" = "request.sh" ] || ln -s "$f" "$PG/m9root/docs/testing/$b"
done
git -C "$PG/m9root" init -q
git -C "$PG/m9root" -c user.email=pg@selftest -c user.name=pg commit -q --allow-empty -m seed
sed '/# A BARE TITLEID IS NOT A FILE NAME/,/^fi$/d' "$RQSRC" > "$PG/m9root/docs/testing/request.sh"
check "M9: the sed mutation actually changed request.sh" \
      bash -c "! cmp -s '$RQSRC' '$PG/m9root/docs/testing/request.sh'"

mkdir -p "$PG/m9dd"/{queue,running,results,pilots}
out=$(DISPATCH_DIR="$PG/m9dd" TITLESTATE_DIR="$PG/m9dd/titlestate" TITLE_TARGETS="$PG/a-targets.toml" \
      TITLE_ROUTES="$PG/a-routes" MAKE_XBOX_HDD="$REPO/tools/make_xbox_hdd.py" \
      bash "$PG/m9root/docs/testing/request.sh" --who pgm9 --purpose "profile gate selftest" --no-expect selftest \
      --title "AAAA1003" --seconds 60 \
      --find-route "selftest: proving the bare-TitleID check itself matters, M9" 2>&1); rc9=$?
if [ "$rc9" = 0 ] && pg_hasnt 'bare TitleID' "$out"; then
    ok "M9 mutant: dropping the check wrongly queues A8's bare TitleID (no refusal at all)"
else bad "M9: exit $rc9, $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "and the bare TitleID was actually written to the queue, wrongly, under M9" \
      [ "$(ls "$PG/m9dd"/queue/*.req 2>/dev/null | wc -l)" -eq 1 ]
unset RQSRC out rc9

# ------------------------- E. pathfind.py's own dry-mode R3 check (real code only).
# M4 is titlestate.py's admit() (section C); pathfind.py's own gate uses the
# correct broad=True unconditionally, so there is nothing to mutate here --
# this is a behavioural positive control that the wiring reaches pathfind.py
# too, using the dry-run harness documented in pathfind.py's own docstring:
# PATHFIND_DRY=1 + --sim + --budget-min 0 never shells to a real `claude -p`
# (Model.ask()'s sim branch) and exits via the R3 check before any Agent is
# built, so this is as safe and bounded as the Python-level cases above.
PF="$PG/pf"; mkdir -p "$PF/fixdir" "$PF/dispatch" "$PF/know/paths" "$PF/out" "$PF/sim"
PFPY="$TESTING/titles/pathfind.py"

# --budget-min 0 always ends in "gave-up" (exit 1, no budget to attempt
# anything) regardless of the gate, so the discriminator here is the gate's
# OWN message, not the exit code -- which is exactly what case (b) below adds.
OUT_NONE=$(PATHFIND_DRY=1 HAKUX_WORK="$PF/fixdir" DISPATCH_DIR="$PF/dispatch" PATHFIND_KNOW="$PF/know" \
    timeout 15 python3 "$PFPY" 00000000 --device nova --out "$PF/out" --sim "$PF/sim" --budget-min 0 2>&1)
check "pathfind.py: nothing known yet -- a dry session is NOT blocked by R3" \
      pg_hasnt 'already has a known path' "$OUT_NONE"

echo '{"complete": true, "result": "gameplay"}' > "$PF/know/paths/00000000.json"
OUT_PK=$(PATHFIND_DRY=1 HAKUX_WORK="$PF/fixdir" DISPATCH_DIR="$PF/dispatch" PATHFIND_KNOW="$PF/know" \
    timeout 15 python3 "$PFPY" 00000000 --device nova --out "$PF/out" --sim "$PF/sim" --budget-min 0 2>&1); rc_pk=$?
if [ "$rc_pk" != 0 ] && pg_has 'already has a known path \(pathknow\)' "$OUT_PK"; then
    ok "pathfind.py: a pathknow success blocks a dry session (R3, the broader test)"
else bad "pathfind.py: pathknow block: exit $rc_pk, $(tail -3 <<< "$OUT_PK" | tr '\n' ' ')"; fi

OUT_PB=$(PATHFIND_DRY=1 HAKUX_WORK="$PF/fixdir" DISPATCH_DIR="$PF/dispatch" PATHFIND_KNOW="$PF/know" \
    timeout 15 python3 "$PFPY" 00000000 --device nova --out "$PF/out" --sim "$PF/sim" --budget-min 0 \
    --path-broken nonexistent-result 2>&1); rc_pb=$?
if [ "$rc_pb" != 0 ] && pg_has 'does not name a run on record' "$OUT_PB"; then
    ok "pathfind.py: --path-broken naming no real run still refuses"
else bad "pathfind.py: --path-broken check: exit $rc_pb, $(tail -3 <<< "$OUT_PB" | tr '\n' ' ')"; fi

rm -rf "$PG"
unset -f pg_has pg_hasnt
unset PG PGSRC SAVES_SRC DSPSRC PFPY PF D SAVEID SAVEID2 out rc REALOUT M1OUT M2OUT M3OUT M4OUT M5OUT M6OUT M7OUT \
       REALBODY MUTBODY OUT_NONE OUT_PK OUT_PB rc_pk rc_pb rc8
unset PGMUT
