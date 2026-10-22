# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# $REPO, the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# A dispatched run can play a `drive` route (#433, lane.snapdrive).
#
# A worker plays the scripts in $DISPATCH_DIR/bin, which snapshot_scripts
# copies from a fixed list. route.sh was on it; drive.py, classify.py,
# waitfor_match.py (classify's import) and drive-profiles/ were not, so on the
# live snapshot `route.sh --check routes/sonic-heroes.drive.route` failed with
# "drive 'sonic-heroes': no profile" and no dispatched run could use `drive`
# (routedriver2 NOTES section 4). 97-dispatch-deploy checks the lists are
# closed; this builds a real snapshot and plays the check against it.
#
# THE LEGS, and the world in which each one fails:
#   check     every routes/*.drive.route passes `route.sh --check` with the
#             SNAPSHOT's route.sh, from a result dir as the dispatcher writes
#             it (route.txt). Fails if a profile is not copied.
#   nodir     the same snapshot with bin/titles/drive-profiles removed fails
#             with "no profile": the leg above can fail.
#   import    drive.py's and classify.py's imports resolve inside the
#             snapshot's titles/ and nowhere else. Fails if classify.py or
#             waitfor_match.py is not copied.
#   newprof   a profile added to the source after a snapshot moves src_hash
#             (so it IS a re-exec) and is in the next snapshot, with
#             dispatcher.sh untouched. Fails if profiles are named, not
#             globbed, or the hash does not cover them.
#   startup   a worker whose bin/ was refreshed by an OLDER dispatcher -- it
#             copied the new dispatcher.sh but not the files the new lists
#             add -- has those files in bin/ once it has started. Fails
#             without the worker's startup snapshot_scripts (the mutant).
#   classifier  a profile with `classifier = "pathclass"` (drive-profiles/
#             generic.toml, #433) makes classify.py import titles/pathclass.py
#             and load titles/pathknow/classifier/head.npz at runtime. Neither
#             was in SCRIPT_DEPS/SNAPSHOT_GLOBS, so a dispatched `drive
#             generic` step failed closed with `pathclass unavailable` for a
#             reason that was purely a snapshot omission (lane.pathclass
#             restart, Addendum 1 6b). Fails if either drops out of the list
#             (the two mutants).
#   targets   titlestate.py's `admit` (profile_gate_check's only subcommand)
#             opens titles/targets.toml, titles/routes/<name>.route and
#             titles/profile-transition.toml beside itself. None were shipped,
#             so any --find-route claim on a title with no golden crashed
#             outright on targets.toml (snaptargets1018, #433: a first-run or
#             find-route title never short-circuits admit() before targets()
#             the way a title with a golden does). The other two fail closed
#             and silent instead -- both opens are try/excepted -- which
#             drops the "already has a proven route" R3 check and the
#             transition grandfather with nothing in the log to say why.
#             Fails (this leg's admit call) without targets.toml in the
#             snapshot (the mutant); the presence checks fail without
#             routes/ or profile-transition.toml.

echo "== dispatch snapshot: a dispatched run can play a drive route"
SD="$T/snapdrive"; rm -rf "$SD"; mkdir -p "$SD"
sd_env() {   # <dispatch dir> <src dir> <shell>: run shell inside a sourced dispatcher.sh
    ( export DISPATCH_DIR="$1" DISPATCH_SRC="$2" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$3" )
}
sd_env "$SD/d" "$TESTING" snapshot_scripts
BIN="$SD/d/bin"

# check: from a result dir, as dispatcher.sh writes the route (route.txt).
nroutes=0
for r in "$TESTING"/titles/routes/*.drive.route; do
    [ -f "$r" ] || continue
    nroutes=$((nroutes+1))
    rd="$SD/d/results/$(basename "$r" .drive.route)"; mkdir -p "$rd"; cp "$r" "$rd/route.txt"
    out=$(bash "$BIN/titles/route.sh" --check "$rd/route.txt" 2>&1)
    case "$out" in
        "route ok: "*) ok "the snapshot's route.sh passes $(basename "$r") from a result dir" ;;
        *) bad "the snapshot's route.sh refuses $(basename "$r"): $out" ;;
    esac
done
check "there is a drive route to check (found $nroutes)" test "$nroutes" -gt 0

# nodir: the leg above can fail.
rd="$SD/d/results/sonic-heroes"
mv "$BIN/titles/drive-profiles" "$SD/profiles.away"
case "$(bash "$BIN/titles/route.sh" --check "$rd/route.txt" 2>&1)" in
    *"drive 'sonic-heroes': no profile"*) ok "  and fails with 'no profile' when the snapshot has no drive-profiles/" ;;
    *) bad "  route.sh --check did not fail without drive-profiles/ -- the leg above checks nothing" ;;
esac
mv "$SD/profiles.away" "$BIN/titles/drive-profiles"

# import: resolved against the snapshot's titles/ ONLY, so a module found on
# the selftest's own path or beside the tree does not count. find_spec needs
# no PIL or numpy (the CI runner has neither); the full import runs where
# they are installed.
for m in drive classify waitfor_match; do
    check "the snapshot's titles/ holds $m for drive.py's imports" \
        python3 -c 'import importlib.machinery as im, sys; s = im.PathFinder.find_spec(sys.argv[1], [sys.argv[2]]); assert s and s.origin.startswith(sys.argv[2])' \
        "$m" "$BIN/titles"
done
if python3 -c 'import PIL, numpy' 2>/dev/null; then
    check "drive.py imports from the snapshot (classify, waitfor_match, the profile loader)" \
        python3 -c 'import sys; sys.path[:0] = [sys.argv[1]]; import drive, classify; assert drive.__file__.startswith(sys.argv[1]) and classify.__file__.startswith(sys.argv[1]); classify.load_profile(sys.argv[1] + "/drive-profiles/sonic-heroes.toml")' \
        "$BIN/titles"
else
    echo "  --   no PIL/numpy here: the full import of drive.py from the snapshot is not run (find_spec above is)"
fi

# classifier: SCRIPT_DEPS carries titles/pathclass.py, SNAPSHOT_GLOBS carries
# its trained head -- both named in BIN by the sd_env snapshot_scripts call above.
check "the snapshot's titles/ holds pathclass.py (SCRIPT_DEPS)" test -f "$BIN/titles/pathclass.py"
check "the snapshot carries pathclass's trained head (SNAPSHOT_GLOBS)" \
    test -f "$BIN/titles/pathknow/classifier/head.npz"

# The mutants: a dispatcher.sh that drops one entry from its own list. Each
# gets its own dispatch dir so the two checks cannot mask each other.
mutant_drop() {   # <key: SCRIPT_DEPS|SNAPSHOT_GLOBS> <word to drop> <dst>
    python3 - "$TESTING/dispatcher.sh" "$1" "$2" "$3" <<'PY'
import sys
src, key, word, dst = sys.argv[1:]
s = open(src).read()
anchor = key + '="'
start = s.index(anchor) + len(anchor)
end = s.index('"', start)
# A line-continued list has a literal backslash+newline in the file (bash
# splices it away at parse time; this script reads the file's own bytes, so
# it must splice too, or a word right after a continuation -- titles/targets.toml,
# snaptargets1018 -- never matches " "+word).
block = s[start:end].replace("\\\n", " ")
assert (" " + word) in block or block.startswith(word + " "), \
    "mutant word %r not found in %s block" % (word, key)
new = block.replace(" " + word, "", 1) if (" " + word) in block else block.replace(word + " ", "", 1)
open(dst, "w").write(s[:start] + new + s[end:])
PY
}
mutant_drop "SCRIPT_DEPS" "titles/pathclass.py" "$SD/no-pathclass.sh"
if [ -f "$SD/no-pathclass.sh" ]; then
    sd_env_at() { ( export DISPATCH_DIR="$2" DISPATCH_SRC="$3" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
                     . "$1" selftest-not-a-subcommand >/dev/null 2>&1; eval "$4" ); }
    sd_env_at "$SD/no-pathclass.sh" "$SD/dnp" "$TESTING" snapshot_scripts
    if [ -f "$SD/dnp/bin/titles/pathclass.py" ]; then
        bad "  mutant 'drop titles/pathclass.py from SCRIPT_DEPS' still shipped it -- the leg above checks nothing"
    else
        ok "  mutant 'drop titles/pathclass.py from SCRIPT_DEPS' leaves it out (red, as it must be)"
    fi
else
    bad "  mutant anchor for SCRIPT_DEPS no longer matches dispatcher.sh"
fi
mutant_drop "SNAPSHOT_GLOBS" "titles/pathknow/classifier/head.npz" "$SD/no-head.sh"
if [ -f "$SD/no-head.sh" ]; then
    sd_env_at "$SD/no-head.sh" "$SD/dnh" "$TESTING" snapshot_scripts
    if [ -f "$SD/dnh/bin/titles/pathknow/classifier/head.npz" ]; then
        bad "  mutant 'drop head.npz from SNAPSHOT_GLOBS' still shipped it -- the leg above checks nothing"
    else
        ok "  mutant 'drop head.npz from SNAPSHOT_GLOBS' leaves it out (red, as it must be)"
    fi
else
    bad "  mutant anchor for SNAPSHOT_GLOBS no longer matches dispatcher.sh"
fi

# book (routebuild1021): drive.py imports pathbook.py (SCRIPT_DEPS) and replays a title's
# pathfind path from titles/pathknow/paths/ beside it (SNAPSHOT_GLOBS). 41430003 is a
# complete path in the repo; with the glob dropped (the mutant) the snapshot has none.
check "the snapshot's titles/ holds pathbook.py (SCRIPT_DEPS)" test -f "$BIN/titles/pathbook.py"
sd_book() {   # <bin dir> -> the file pathbook.load() replays for 41430003, or "none"
    HAKUX_PATHS_DIR= python3 -c 'import sys; sys.path[:0] = [sys.argv[1]]; import pathbook
p, f = pathbook.load("41430003"); print(f if p and p.get("complete") else "none")' "$1/titles" 2>&1
}
if python3 -c 'import PIL, numpy' 2>/dev/null; then
    out=$(sd_book "$BIN")
    check "pathbook.py (snapshot) loads a complete repo path from the snapshot's own pathknow/paths/: $out" \
        bash -c 'case "$1" in "$2"/titles/pathknow/paths/41430003.json) ;; *) exit 1 ;; esac' _ "$out" "$BIN"
    # devices.sh beside the mutant, or its snapshot never runs at all (see the targets
    # mutant below) and sd_book fails on a missing pathbook.py, not on a missing path.
    cp "$TESTING/devices.sh" "$SD/devices.sh"
    mutant_drop "SNAPSHOT_GLOBS" "titles/pathknow/paths/*.json" "$SD/no-paths.sh"
    if [ -f "$SD/no-paths.sh" ]; then
        sd_env_at "$SD/no-paths.sh" "$SD/dnb" "$TESTING" snapshot_scripts
        mout=$(sd_book "$SD/dnb/bin")
        case "$mout" in
            none) ok "  mutant 'drop pathknow/paths from SNAPSHOT_GLOBS' leaves no path to replay (red, as it must be)" ;;
            *) bad "  mutant 'drop pathknow/paths from SNAPSHOT_GLOBS' still loaded one -- the leg above checks nothing: $mout" ;;
        esac
    else
        bad "  mutant anchor for SNAPSHOT_GLOBS no longer matches dispatcher.sh"
    fi
else
    check "the snapshot carries pathfind's recorded paths (SNAPSHOT_GLOBS)" \
        test -f "$BIN/titles/pathknow/paths/41430003.json"
fi

# targets: titlestate.py's admit() opens titles/targets.toml, titles/routes/<name>.route
# and titles/profile-transition.toml beside itself (snaptargets1018, #433). targets.toml
# ships now (SNAPSHOT_GLOBS); check the other two landed too.
check "the snapshot's titles/ holds targets.toml (SNAPSHOT_GLOBS)" test -f "$BIN/titles/targets.toml"
check "the snapshot's titles/ holds profile-transition.toml (SNAPSHOT_GLOBS)" \
    test -f "$BIN/titles/profile-transition.toml"
check "the snapshot's titles/routes/ holds at least one *.route file (SNAPSHOT_GLOBS)" \
    bash -c 'ls "$1"/titles/routes/*.route >/dev/null 2>&1' _ "$BIN"

# admit, exactly as profile_gate_check (dispatcher.sh) runs it, for a title with no
# targets.toml entry and no known path: FFFFFFFF is not an 8-hex id any real title uses.
# On master (targets.toml not shipped) this is the brief's own traceback,
# admit -> known_path -> proven_route -> title_routes -> targets() -> FileNotFoundError;
# with the fix it must come back admit=true, clause=find-route.
sd_admit() {   # <bin dir> <dispatch dir> -> titlestate.py admit's stdout+stderr
    MAKE_XBOX_HDD="$REPO/tools/make_xbox_hdd.py" TITLESTATE_DIR="$2/titlestate" DISPATCH_DIR="$2" \
        python3 "$1/titles/titlestate.py" admit --title-id FFFFFFFF --route-text-file /dev/null \
        --find-route "selftest: snaptargets1018, titlestate.py admit from the snapshot" 2>&1
}
out=$(sd_admit "$BIN" "$SD/d")
check "titlestate.py admit (snapshot, --find-route, no golden) returns admit=true, not a traceback" \
    python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d.get("admit") is True and d.get("clause") == "find-route", d' "$out"

# auto (routebuild1021): from the snapshot, a title with no route of its own is given
# routes/auto.route, and the gate admits it with no golden -- the claim-time half of
# "the dispatcher must not reject a request with no known path".
out=$(MAKE_XBOX_HDD="$REPO/tools/make_xbox_hdd.py" TITLESTATE_DIR="$SD/d/titlestate" DISPATCH_DIR="$SD/d" \
      python3 "$BIN/titles/titlestate.py" suggest-route --title-id FFFFFFFF 2>&1)
check "titlestate.py suggest-route (snapshot, no route) names the shipped auto route: $out" \
    python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d.get("name") == "auto" and d.get("source") == "auto", d' "$out"
out=$(MAKE_XBOX_HDD="$REPO/tools/make_xbox_hdd.py" TITLESTATE_DIR="$SD/d/titlestate" DISPATCH_DIR="$SD/d" \
      python3 "$BIN/titles/titlestate.py" admit --title-id FFFFFFFF --route auto \
      --route-text-file "$BIN/titles/routes/auto.route" 2>&1)
check "titlestate.py admit (snapshot, auto route, no golden) returns admit=true, clause auto-route" \
    python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d.get("admit") is True and d.get("clause") == "auto-route", d' "$out"

# The mutant: drop titles/targets.toml from SNAPSHOT_GLOBS. Must crash the admit call
# above the same way master does -- the stop rule the brief sets for this fragment.
# sd_env_at sources a standalone file whose HERE is its own directory; dispatcher.sh's
# first two lines source HERE/devices.sh and call device_env, so without a copy beside
# the mutant that source dies before snapshot_scripts is even defined (checked by hand:
# with no devices.sh, "$SD/dnt/bin" never appears at all, not just without targets.toml).
cp "$TESTING/devices.sh" "$SD/devices.sh"
mutant_drop "SNAPSHOT_GLOBS" "titles/targets.toml" "$SD/no-targets.sh"
if [ -f "$SD/no-targets.sh" ]; then
    sd_env_at "$SD/no-targets.sh" "$SD/dnt" "$TESTING" snapshot_scripts
    mout=$(sd_admit "$SD/dnt/bin" "$SD/dnt")
    case "$mout" in
        *FileNotFoundError*targets.toml*) ok "  mutant 'drop titles/targets.toml from SNAPSHOT_GLOBS' crashes admit (red, as it must be)" ;;
        *) bad "  mutant 'drop titles/targets.toml from SNAPSHOT_GLOBS' did not crash admit -- the leg above checks nothing: $mout" ;;
    esac
else
    bad "  mutant anchor for SNAPSHOT_GLOBS no longer matches dispatcher.sh"
fi

# newprof: a scratch source tree holding what the snapshot ships.
SRC2="$SD/src"; mkdir -p "$SRC2"
( cd "$TESTING" && for f in $(sd_env "$SD/x" "$TESTING" 'printf "%s\n" $SCRIPT_DEPS; snapshot_globbed'); do
      mkdir -p "$SRC2/$(dirname "$f")"; cp "$f" "$SRC2/$f"; done )
h1=$(sd_env "$SD/d2" "$SRC2" 'snapshot_scripts; src_hash')
mkdir -p "$SRC2/titles/drive-profiles/probe-title"
printf 'name = "probe-title"\n' > "$SRC2/titles/drive-profiles/probe-title.toml"
cp "$TESTING/titles/drive-profiles/sonic-heroes/hud.png" "$SRC2/titles/drive-profiles/probe-title/hud.png"
h2=$(sd_env "$SD/d2" "$SRC2" 'src_hash')
check "a new profile moves src_hash (adding one is a re-exec): $h1 -> $h2" \
    bash -c '[ -n "$1" ] && [ -n "$2" ] && [ "$1" != "$2" ]' _ "$h1" "$h2"
h3=$(sd_env "$SD/d2" "$SRC2" 'snapshot_scripts; src_hash')
check "  and is in the next snapshot, toml and crop, with dispatcher.sh untouched" \
    test -f "$SD/d2/bin/titles/drive-profiles/probe-title.toml" -a -f "$SD/d2/bin/titles/drive-profiles/probe-title/hud.png"
printf 'x' >> "$SRC2/titles/drive-profiles/probe-title/hud.png"
h4=$(sd_env "$SD/d2" "$SRC2" 'src_hash')
check "  and an edit to one of its crops moves the hash too" bash -c '[ "$1" = "$2" ] && [ "$2" != "$3" ]' _ "$h2" "$h3" "$h4"

# startup: bin/ as an older dispatcher's re-exec leaves it -- the new
# dispatcher.sh (and devices.sh, which it sources) and none of the files the
# new lists add. The worker runs held, so it claims nothing; it is stopped
# by PID once the files appear or after 15 s.
sd_worker() {   # <dispatcher.sh to start> -> "yes" if bin/ got drive.py and a profile
    local d="$SD/w" pid i
    rm -rf "$d"; mkdir -p "$d/bin" "$d/hold"
    cp "$1" "$d/bin/dispatcher.sh"; cp "$TESTING/devices.sh" "$d/bin/devices.sh"
    local label; label=$(sd_env "$d" "$TESTING" 'printf %s "$DEVICE_LABEL"')
    : > "$d/hold/${label:-nova}"
    ( export DISPATCH_DIR="$d" DISPATCH_SRC="$TESTING" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      exec bash "$d/bin/dispatcher.sh" worker ee317437 ) > "$d/worker.out" 2>&1 &
    pid=$!
    for i in $(seq 1 30); do
        [ -f "$d/bin/titles/drive.py" ] && [ -f "$d/bin/titles/drive-profiles/sonic-heroes.toml" ] && break
        sleep 0.5
    done
    kill "$pid" 2>/dev/null; sleep 0.2; kill -9 "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
    [ -f "$d/bin/titles/drive.py" ] && [ -f "$d/bin/titles/drive-profiles/sonic-heroes.toml" ] && echo yes || echo no
}
check "a worker started by an older re-exec snapshots the files the new lists add" \
    test "$(sd_worker "$TESTING/dispatcher.sh")" = yes
# The mutant: no snapshot_scripts at worker startup.
python3 - "$TESTING/dispatcher.sh" "$SD/mutant.sh" <<'PY'
import sys
src, dst = sys.argv[1:]
s = open(src).read()
anchor = "    export DISPATCH_SRC_HASH\n"
i = s.index(anchor) + len(anchor)
j = s.index("    snapshot_scripts\n", i)
assert s[i:j].strip() == "" or all(l.strip().startswith("#") for l in s[i:j].splitlines() if l.strip()), "mutant anchor no longer matches dispatcher.sh"
open(dst, "w").write(s[:j] + s[j + len("    snapshot_scripts\n"):])
PY
if [ -f "$SD/mutant.sh" ]; then
    case "$(sd_worker "$SD/mutant.sh")" in
        no) ok "  mutant 'no startup snapshot' leaves them out (red, as it must be)" ;;
        *) bad "  mutant 'no startup snapshot' still had them -- the leg above checks nothing" ;;
    esac
else
    bad "  mutant anchor no longer matches dispatcher.sh"
fi

echo "== request.sh --route: a route is checked as the run will see it"
# THE LEGS (each in a private dispatch dir, so nothing reaches the harness's
# queue; DISPATCH_TREE named, so the host's serving tree is never read):
#   drive     a .drive.route against a snapshot holding its profile: queued.
#   crops     a route with `waitfor` crops: queued. The crop travels with the
#             request (route_refs, Addendum 3 #433 lane.soakvideo1011) and
#             request.sh stages it into the check-copy's refs/route.txt/
#             before this same check, so the crop no longer has to sit where
#             this tree's route.sh would find it on its own. Before that fix
#             this leg was refused (the run plays <result dir>/route.txt,
#             and nothing wrote its refs/); 62-routerefs-soakvideo1011.sh
#             carries the refusal-reproducing mutant now.
#   noprof    a .drive.route against a snapshot with no drive-profiles/ and
#             no serving tree: refused, "no profile".
#   server    the same snapshot, but a serving tree whose dispatcher ships
#             profiles: queued (a worker re-snapshots before it claims).
rq_sd() {   # <dispatch dir> <serving tree> <route> -> request.sh's output
    mkdir -p "$1"/queue "$1"/running "$1"/results "$1"/expect
    # --find-route: "Sonic Heroes.iso" matches no targets.toml iso entry and
    # no 8-hex prefix, so the profile gate (lane.profilegate1011, #433)
    # refuses it outright unless the run is finding a route -- this test is
    # about drive-profile/snapshot resolution, not profile state.
    env DISPATCH_DIR="$1" DISPATCH_TREE="$2" bash "$TESTING/request.sh" --who sd --purpose "snapdrive selftest" \
        --no-expect "selftest" --title "Sonic Heroes.iso" --seconds 600 --route "$3" \
        --find-route "selftest: drive/snapshot resolution, not a profile check" 2>&1
}
cp -r "$SD/d/bin" "$SD/q1-bin"
mkdir -p "$SD/q1"; mv "$SD/q1-bin" "$SD/q1/bin"
out=$(rq_sd "$SD/q1" "$SD/no-tree" sonic-heroes.drive)
if ls "$SD/q1/queue/"*.req >/dev/null 2>&1; then ok "a drive route is queued against a snapshot holding its profile"
else bad "a drive route was refused against a snapshot holding its profile: $out"; fi
crop=$(cd "$TESTING/titles/routes" && grep -l '^[[:space:]]*\(waitfor\|press-until\)' *.route | head -1)
if [ -n "$crop" ]; then
    out=$(rq_sd "$SD/q2" "$SD/no-tree" "${crop%.route}")
    if ls "$SD/q2/queue/"*.req >/dev/null 2>&1; then
        ok "a route with waitfor crops is queued: the crop travels in route_refs (${crop%.route}, Addendum 3 #433)"
    else
        bad "a route with waitfor crops was refused even though the crop travels (${crop%.route}): $out"
    fi
else
    bad "no route under titles/routes/ has a waitfor or press-until step to check this with"
fi
mkdir -p "$SD/q3/bin"; cp -r "$SD/d/bin/." "$SD/q3/bin/"; rm -rf "$SD/q3/bin/titles/drive-profiles"
out=$(rq_sd "$SD/q3" "$SD/no-tree" sonic-heroes.drive)
case "$out" in
    *"would not run in the dispatched soak"*"no profile"*) ok "a drive route is refused against a snapshot without its profile" ;;
    *) bad "a drive route was not refused against a snapshot without its profile: $out" ;;
esac
out=$(rq_sd "$SD/q3" "$REPO" sonic-heroes.drive)
if ls "$SD/q3/queue/"*.req >/dev/null 2>&1; then ok "  and queued when the serving tree ships profiles at its next re-exec"
else bad "  and refused even with a serving tree that ships profiles: $out"; fi
rm -rf "$SD"
unset SD BIN SRC2 nroutes rd out h1 h2 h3 h4 crop
