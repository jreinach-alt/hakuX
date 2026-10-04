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
#   crops     a route with `waitfor` crops: refused. The run plays
#             <result dir>/route.txt and nothing writes its refs/, so it
#             would die at line 1 with the soak running on. Fails if the
#             check reads the route where it sits in this tree.
#   noprof    a .drive.route against a snapshot with no drive-profiles/ and
#             no serving tree: refused, "no profile".
#   server    the same snapshot, but a serving tree whose dispatcher ships
#             profiles: queued (a worker re-snapshots before it claims).
rq_sd() {   # <dispatch dir> <serving tree> <route> -> request.sh's output
    mkdir -p "$1"/queue "$1"/running "$1"/results "$1"/expect
    env DISPATCH_DIR="$1" DISPATCH_TREE="$2" bash "$TESTING/request.sh" --who sd --purpose "snapdrive selftest" \
        --no-expect "selftest" --title "Sonic Heroes.iso" --seconds 600 --route "$3" 2>&1
}
cp -r "$SD/d/bin" "$SD/q1-bin"
mkdir -p "$SD/q1"; mv "$SD/q1-bin" "$SD/q1/bin"
out=$(rq_sd "$SD/q1" "$SD/no-tree" sonic-heroes.drive)
if ls "$SD/q1/queue/"*.req >/dev/null 2>&1; then ok "a drive route is queued against a snapshot holding its profile"
else bad "a drive route was refused against a snapshot holding its profile: $out"; fi
crop=$(cd "$TESTING/titles/routes" && grep -l '^[[:space:]]*\(waitfor\|press-until\)' *.route | head -1)
if [ -n "$crop" ]; then
    out=$(rq_sd "$SD/q2" "$SD/no-tree" "${crop%.route}")
    case "$out" in
        *"would not run in the dispatched soak"*"no reference crop"*) ok "a route with waitfor crops is refused: they do not travel (${crop%.route})" ;;
        *) bad "a route with waitfor crops was not refused (${crop%.route}): $out" ;;
    esac
else
    bad "no route under titles/routes/ has a waitfor or press-until step to check the refusal with"
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
