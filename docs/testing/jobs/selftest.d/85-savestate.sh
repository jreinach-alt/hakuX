# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# Every title run starts from a known profile (lane.savestate433, #433).
#
# THE VOIDS THIS REPRODUCES, each before its guard is checked:
#   1. the titles disk carried whatever the last run harvested, so a title's
#      menus differed run to run (Tron 2.0 New Game vs Auto Load, 10-02);
#      the next prepare KEPT a disk the run had written to;
#   2. a route that assumes a profile was queued and dispatched for a title
#      that had none, and the void was found 20 minutes into the soak;
#   3. a first-run's new profile was nobody's: the next first-run met it.
#
# A fake adb serves one fake device, as in 99-hdd-split.sh. The dispatcher's
# own functions are called, sourced from dispatcher.sh; request.sh runs in a
# private dispatch dir. THE FALSIFIERS: against master, titles_disk_prepare
# takes no title or state (the returning/first-run legs load the same disk),
# plan() keeps the written disk, and request.sh queues crimson-skies with no
# golden. Each of those legs goes red on what the disk or the queue holds.

echo "== savestate: a title run's disk is its golden profile, or none on a first-run"
SS="$T/savestate"; rm -rf "$SS"; mkdir -p "$SS/bin" "$SS/dev/fs" "$SS/dispatch"/{queue,running,results,expect} "$SS/fix"
X=/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box
cat > "$SS/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$SS_DEV/calls"
X=/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box
map() { printf '%s' "${1//$X/$SS_DEV/fs}"; }
case "$1" in
    push) cp "$2" "$(map "$3")" && chmod 644 "$(map "$3")" ;;
    pull) cp "$(map "$2")" "$3" ;;
    shell) shift; c="$*"
        case "$c" in
            "am force-stop"*) ;;
            *"cat > shared_prefs/x1box_prefs.xml"*) cat > "$SS_DEV/prefs.xml" ;;
            *"cat shared_prefs/x1box_prefs.xml"*) cat "$SS_DEV/prefs.xml" ;;
            *) sh -c "$(map "$c")" ;;
        esac ;;
esac
EOF
chmod +x "$SS/bin/adb"
cat > "$SS/dev/prefs.xml" <<EOF
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="hddPath">$X/hdd.img</string>
</map>
EOF

# Crimson Skies (4D530021) with its profile "Nathan" (the golden) and a bare
# state (a run that left only title data); Burnout 3 (4541005B) with none.
python3 - "$TESTING/titles" "$SS/fix" <<'PY'
import hashlib, json, os, sys
sys.path.insert(0, sys.argv[1]); import saves
out = sys.argv[2]
def mk(name, tid, files):
    d = os.path.join(out, name); t = saves.fatx_now(); ents = []; dirs = set()
    for rel, data in files.items():
        parts = rel.split("/")
        for k in range(2, len(parts)):
            dirs.add("/".join(parts[:k]))
        p = os.path.join(d, *parts); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(data)
        ents.append({"path": rel, "dir": False, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "times": t})
    ents += [{"path": x, "dir": True, "times": t} for x in sorted(dirs)]
    m = {"title_id": tid, "entries": ents}; m["save_id"] = saves.save_id(m)
    json.dump(m, open(os.path.join(d, "save.json"), "w"))
    open(os.path.join(out, name + ".id"), "w").write(m["save_id"])
mk("nathan", "4D530021", {"UDATA/4D530021/TitleMeta.xbx": b"Crimson Skies",
                          "UDATA/4D530021/126216BC1B2A/SaveMeta.xbx": b"Nathan" * 40})
mk("bare", "4D530021", {"TDATA/4D530021/prefs.bin": b"\0" * 300})
saves.build(os.path.join(out, "hdd.img"), [os.path.join(out, "nathan")])
saves.build(os.path.join(out, "played.qcow2"), [os.path.join(out, "bare")])
PY
cp "$SS/fix/hdd.img" "$SS/dev/fs/hdd.img"
NATHAN=$(cat "$SS/fix/nathan.id"); BARE=$(cat "$SS/fix/bare.id")
CS_ISO="Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso"

ss_env() {
    ( export DISPATCH_DIR="$SS/dispatch" TITLESTATE_DIR="$SS/dispatch/titlestate" \
             SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO" \
             MAKE_XBOX_HDD="$REPO/tools/make_xbox_hdd.py" SS_DEV="$SS/dev" \
             ADB_RETRY_SLEEP=0 PATH="$SS/bin:$PATH"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$1" )
}
ts() { env TITLESTATE_DIR="$SS/dispatch/titlestate" DISPATCH_DIR="$SS/dispatch" python3 "$TESTING/titles/titlestate.py" "$@"; }
on_disk() { python3 "$TESTING/titles/saves.py" list "$SS/dev/fs/titles.qcow2" 2>/dev/null; }
verifies() { python3 "$TESTING/titles/saves.py" verify "$SS/dev/fs/titles.qcow2" "$SS/dispatch/titlestate/saves/4D530021/$1" >/dev/null 2>&1; }
hj() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2]))' "$1" "$2" 2>/dev/null; }
plans() { python3 -c 'import json,sys; print(" ".join(p["action"] for p in json.load(open(sys.argv[1]))["plans"]))' "$1" 2>/dev/null; }

# ---------------------------------------------------------- seed + returning
mkdir -p "$SS/r1"
ss_env 'titles_disk_prepare req1 "$SS/r1" "[]" 4D530021 returning' > "$SS/r1.log" 2>&1; rc=$?
check "a returning run is prepared from the seeded golden (rc=$rc)" [ "$rc" = 0 ]
check "  ... the seed proposed hdd.img's save as Crimson Skies' golden" \
      eval 'ts golden --title-id 4D530021 | grep -q "proposed $NATHAN"'
check "  ... hdd.json records title, state and the golden loaded (got: $(hj "$SS/r1/hdd.json" loaded) $(hj "$SS/r1/hdd.json" save))" \
      eval '[ "$(hj "$SS/r1/hdd.json" title_id)" = 4D530021 ] && [ "$(hj "$SS/r1/hdd.json" state)" = returning ] &&
            [ "$(hj "$SS/r1/hdd.json" loaded)" = golden ] && [ "$(hj "$SS/r1/hdd.json" save)" = "$NATHAN" ]'
check "  ... and the device's disk carries Nathan" verifies "$NATHAN"

# --------------------------------- void 1: the run leaves another state behind
cp "$SS/fix/played.qcow2" "$SS/dev/fs/titles.qcow2"
ss_env 'titles_disk_after req1 "$SS/r1"' > "$SS/r1.after.log" 2>&1
check "after the run, its save is harvested to latest" \
      eval 'ts golden --title-id 4D530021 | grep -q "latest $BARE"'
check "  ... and the golden is still Nathan" eval 'ts golden --title-id 4D530021 | grep -q "proposed $NATHAN"'
check "VOID REPRODUCED: the device registry names the run's bare save, what the old disk carried next" \
      eval '[ "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[\"titles\"][\"4D530021\"][\"save\"])" "$SS/dispatch/titlestate/devices/nova.json")" = "$BARE" ]'
mkdir -p "$SS/r2"
ss_env 'titles_disk_prepare req2 "$SS/r2" "[]" 4D530021 returning' > "$SS/r2.log" 2>&1; rc=$?
check "GUARD: the next returning run rebuilds (rc=$rc, plans: $(plans "$SS/r2/hdd.json"))" \
      [ "$(plans "$SS/r2/hdd.json")" = "build keep" ]
check "  ... onto Nathan again, not the bare state the last run left" \
      eval 'verifies "$NATHAN" && ! verifies "$BARE"'
ss_env 'titles_disk_after req2 "$SS/r2"' >/dev/null 2>&1

# ------------------------------------------------------------- first-run
mkdir -p "$SS/r3"
ss_env 'titles_disk_prepare req3 "$SS/r3" "[]" 4D530021 first-run' > "$SS/r3.log" 2>&1; rc=$?
check "a first-run of the same title is prepared (rc=$rc)" [ "$rc" = 0 ]
check "  ... its disk carries no Crimson Skies save" eval '! on_disk | grep -q 4D530021'
check "  ... and hdd.json says so (loaded: $(hj "$SS/r3/hdd.json" loaded))" \
      eval '[ "$(hj "$SS/r3/hdd.json" loaded)" = none ] && [ "$(hj "$SS/r3/hdd.json" state)" = first-run ]'
ss_env 'titles_disk_after req3 "$SS/r3"' >/dev/null 2>&1

# -------------------------------------- void 2: returning with no golden
: > "$SS/dev/calls"; mkdir -p "$SS/r4"
ss_env 'titles_disk_prepare req4 "$SS/r4" "[]" 4541005B returning' > "$SS/r4.log" 2>&1; rc=$?
check "a returning run of a title with no golden is refused, rc 3 (got $rc)" [ "$rc" = 3 ]
check "  ... with the reason in hdd.refused" grep -q 'no golden' "$SS/r4/hdd.refused"
check "  ... before any push, and hddPath never moved" \
      eval '! grep -q "^push" "$SS/dev/calls" && grep -q "$X/hdd.img" "$SS/dev/prefs.xml"'

# ----------------------------- void 3: a first-run's profile becomes the golden
mkdir -p "$SS/r5"
ss_env 'titles_disk_prepare req5 "$SS/r5" "[]" 4541005B first-run' > "$SS/r5.log" 2>&1
python3 - "$TESTING/titles" "$SS/fix" <<'PY'
import hashlib, json, os, sys
sys.path.insert(0, sys.argv[1]); import saves
out = sys.argv[2]; tid = "4541005B"; d = os.path.join(out, "b3"); t = saves.fatx_now()
p = os.path.join(d, "UDATA", tid, "57BD267AFF58"); os.makedirs(p)
data = b"Profile 1" * 20; open(os.path.join(p, "SaveMeta.xbx"), "wb").write(data)
m = {"title_id": tid, "entries": [{"path": f"UDATA/{tid}", "dir": True, "times": t},
     {"path": f"UDATA/{tid}/57BD267AFF58", "dir": True, "times": t},
     {"path": f"UDATA/{tid}/57BD267AFF58/SaveMeta.xbx", "dir": False, "bytes": len(data),
      "sha256": hashlib.sha256(data).hexdigest(), "times": t}]}
m["save_id"] = saves.save_id(m); json.dump(m, open(os.path.join(d, "save.json"), "w"))
saves.build(os.path.join(out, "b3.qcow2"), [d, os.path.join(out, "nathan")])
PY
cp "$SS/fix/b3.qcow2" "$SS/dev/fs/titles.qcow2"
echo "ROUTE 12:00:00.000 mark profile-saved" > "$SS/r5/run.log"
ss_env 'titles_disk_after req5 "$SS/r5"' > "$SS/r5.after.log" 2>&1
check "a first-run that reached mark profile-saved makes the title's golden" \
      eval 'ts golden --title-id 4541005B | grep -q "golden .* first-run"'
check "  ... and a returning run of it is now prepared, not refused" \
      eval 'mkdir -p "$SS/r6" && ss_env "titles_disk_prepare req6 \"\$SS/r6\" \"[]\" 4541005B returning" >/dev/null 2>&1'
ss_env 'titles_disk_after req6 "$SS/r6"' >/dev/null 2>&1

# ------------------------------------------------- request.sh, at queue time
echo "== savestate: request.sh refuses a route whose state the disk cannot match"
rq_ss() {   # <dispatch dir> <iso> <route> -> request.sh's output
    mkdir -p "$1"/queue "$1"/running "$1"/results "$1"/expect
    env DISPATCH_DIR="$1" DISPATCH_TREE="$REPO" bash "$TESTING/request.sh" --who ss --purpose "savestate selftest" \
        --no-expect "selftest" --title "$2" --seconds 600 --route "$3" 2>&1
}
out=$(rq_ss "$SS/q1" "$CS_ISO" crimson-skies)
case "$out" in
    *"refusing to queue"*"golden"*) ok "VOID REPRODUCED + GUARD: a returning route with no golden is refused at the prompt" ;;
    *) bad "a returning route with no golden was not refused: $out" ;;
esac
check "  ... and nothing was queued" eval '! ls "$SS/q1/queue/"*.req >/dev/null 2>&1'
cp -r "$SS/dispatch/titlestate" "$SS/q2-ts"; mkdir -p "$SS/q2"; mv "$SS/q2-ts" "$SS/q2/titlestate"
out=$(rq_ss "$SS/q2" "$CS_ISO" crimson-skies)
check "with Crimson Skies' golden it is queued, title_id and state in the request" \
      python3 -c 'import json,glob,sys; r=json.load(open(glob.glob(sys.argv[1]+"/queue/*.req")[0])); assert r["title_id"]=="4D530021" and r["title_state"]=="returning", r' "$SS/q2"
out=$(rq_ss "$SS/q3" "4541005B-Burnout_3_Takedown.xiso.iso" burnout3)
check "a variant family resolves to .first-run for a title with no golden ($(printf '%s' "$out" | grep -m1 'route:'))" \
      python3 -c 'import json,glob,sys; r=json.load(open(glob.glob(sys.argv[1]+"/queue/*.req")[0])); assert r["route_name"]=="burnout3.first-run" and r["title_state"]=="first-run", r' "$SS/q3"
out=$(rq_ss "$SS/q2" "4541005B-Burnout_3_Takedown.xiso.iso" burnout3)
check "  ... and to .returning once it has one" \
      python3 -c 'import json,glob,sys; r=[json.load(open(f)) for f in glob.glob(sys.argv[1]+"/queue/*.req")]; assert any(x["route_name"]=="burnout3.returning" and x["title_state"]=="returning" for x in r), r' "$SS/q2"

# --------------------------------------------------------- the wiring
body=$(ss_env 'declare -f serve_one')
check "serve_one passes the request's title_id and title_state to the prepare" \
      eval 'printf "%s\n" "$body" | grep -q "title_state" && printf "%s\n" "$body" | grep -q "titles_disk_prepare \"\$id\" \"\$rdir\" \"\$req_env\" \"\$ttid\" \"\$tstate\""'
check "  ... and a refusal ends the request before the soak, with its reason" \
      eval 'printf "%s\n" "$body" | grep -q "refused before the soak"'
rm -rf "$SS"
unset SS X NATHAN BARE CS_ISO out body rc
