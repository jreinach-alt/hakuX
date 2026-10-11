# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit.
#
# route_refs (request.sh --route / dispatcher.sh write_route_refs, Addendum 3
# #433 lane.soakvideo1011): a `waitfor`/`press-until` step's reference crop
# now travels WITH the request, instead of being assumed to sit next to the
# route file -- the worker never had that: it plays <result dir>/route.txt,
# a text copy with no refs/ beside it, so route.sh's ref_path() found
# nothing and the first waitfor/press-until line failed with the soak
# running on (castlevania-cod.first-run and every route with a crop, before
# this). request.sh's own "as the run will see it" check caught the same gap
# a step earlier and refused to queue ANY such route at all.
#
# titlestate.py resolve-route has no --routes-dir, so a route request.sh can
# actually resolve by name has to live under titles/routes/ -- this builds
# one there (a throwaway name, never committed) and removes it whether or
# not a check below fails.

echo "== route_refs: a waitfor crop travels with the request and lands where route.sh --check expects it"
RR_NAME="zzz-routerefs-selftest"
RR_ROUTE="$TESTING/titles/routes/$RR_NAME.route"
RR_REFDIR="$TESTING/titles/routes/refs/$RR_NAME"
rr_clean() { rm -f "$RR_ROUTE"; rm -rf "$RR_REFDIR"; rm -f "$TESTING/request-routerefs-mutant.sh"; }
rr_clean   # a previous aborted run may have left these behind

mkdir -p "$RR_REFDIR"
printf '# state: first-run\nwaitfor probe-crop 5 10,10,20,20 10\n' > "$RR_ROUTE"
# Distinguishable bytes, not a real PNG -- route.sh --check and
# write_route_refs only move and compare bytes; neither decodes an image.
head -c 256 /dev/urandom > "$RR_REFDIR/probe-crop.png"
RR_SHA=$(sha256sum "$RR_REFDIR/probe-crop.png" | cut -d' ' -f1)

check "route.sh --check passes the route as committed, crop included" \
    bash "$TESTING/titles/route.sh" --check "$RR_ROUTE"

echo "== route_refs: the queued request carries the crop's exact bytes"
RR_D="$T/routerefs"; rm -rf "$RR_D"
rr_rq() {   # <request.sh path> <dispatch dir> -> request.sh's output on the fd
    mkdir -p "$2"/queue "$2"/running "$2"/results "$2"/expect
    env DISPATCH_DIR="$2" bash "$1" --who rr --purpose "routerefs selftest" \
        --no-expect "selftest" --title "RouteRefs Selftest.iso" --seconds 600 --route "$RR_NAME" 2>&1
}
out=$(rr_rq "$TESTING/request.sh" "$RR_D")
if ls "$RR_D/queue/"*.req >/dev/null 2>&1; then
    ok "a route naming a waitfor crop is queued (not refused)"
    RR_REQ=$(ls "$RR_D/queue/"*.req | head -1)
    rr_b64=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["route_refs"]["probe-crop.png"])' "$RR_REQ" 2>/dev/null)
    rr_got=$(printf '%s' "$rr_b64" | python3 -c 'import base64,hashlib,sys; print(hashlib.sha256(base64.b64decode(sys.stdin.read())).hexdigest())' 2>/dev/null)
    case "$rr_got" in
        "$RR_SHA") ok "  and route_refs['probe-crop.png'] decodes to the crop's exact bytes (sha256 matches)" ;;
        *) bad "  route_refs bytes do not match the crop file: got sha256 $rr_got, want $RR_SHA" ;;
    esac
else
    bad "a route naming a waitfor crop was refused: $out"
fi

echo "== route_refs: dispatcher.sh's write_route_refs writes the crop byte-identical at refs/route.txt/"
rr_wrr() {   # <rdir> <req> -> write_route_refs's stdout; $? is its exit code
    ( export SERIAL=ee317437 DISPATCH_DIR="$RR_D/d" DISPATCH_SRC="$TESTING" DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      write_route_refs "$1" "$2" )
}
RR_RDIR="$RR_D/rdir"; mkdir -p "$RR_RDIR"
wmsg=$(rr_wrr "$RR_RDIR" "$RR_REQ"); wrc=$?
case "$wrc" in
    0) ok "write_route_refs accepts the route_refs entry (a valid [A-Za-z0-9._-]+.png name)" ;;
    *) bad "write_route_refs refused a valid entry (rc=$wrc): $wmsg" ;;
esac
check "  and writes it at refs/route.txt/probe-crop.png" test -f "$RR_RDIR/refs/route.txt/probe-crop.png"
check "  byte-identical to the committed crop" \
    bash -c 'cmp -s "$1" "$2"' _ "$RR_REFDIR/probe-crop.png" "$RR_RDIR/refs/route.txt/probe-crop.png"

echo "== route_refs: route.sh --check on the played route.txt passes with the materialized crop"
cp "$RR_ROUTE" "$RR_RDIR/route.txt"
check "route.sh --check <result dir>/route.txt passes (the crop is where ref_path() looks for it)" \
    bash "$TESTING/titles/route.sh" --check "$RR_RDIR/route.txt"

echo "== route_refs: write_route_refs refuses a name outside [A-Za-z0-9._-]+.png before writing anything"
RR_BADREQ="$RR_D/bad.req"
python3 -c 'import json,sys; json.dump({"route_refs": {"../escape.png": "aGk="}}, open(sys.argv[1], "w"))' "$RR_BADREQ"
RR_BADDIR="$RR_D/baddir"; mkdir -p "$RR_BADDIR"
bmsg=$(rr_wrr "$RR_BADDIR" "$RR_BADREQ"); brc=$?
case "$brc:$bmsg" in
    1:*"refused name"*) ok "write_route_refs refuses a '../' name, exit 1, before writing anything" ;;
    *) bad "write_route_refs did not refuse the escaping name (rc=$brc): $bmsg" ;;
esac
check "  and nothing was written under baddir/" bash -c '[ ! -e "$1/refs" ]' _ "$RR_BADDIR"

echo "== route_refs MUTANT: disable request.sh's check-copy staging -- today's refusal comes back"
# Deletes the mkdir+python3 block that materializes route_refs into
# $RCHK/refs/route.txt/ before the "as the run will see it" route.sh --check
# a few lines later. Without it this is exactly the bug Addendum 3 fixes: the
# crop never travels, so the copy's check fails with "no reference crop",
# and request.sh refuses to queue -- what it did to every crop route before
# this lane's fix (today's refusal, reproduced on a copy of the script).
# Placed IN $TESTING, not under $T: request.sh resolves its own repo root,
# titles/route.sh and drive-profiles/ relative to its own $(dirname "$0"), so
# a copy run from anywhere else fails earlier and for the wrong reason
# (no repo at ../.. to resolve --ref HEAD against) before ever reaching the
# route_refs logic this mutant targets.
RR_MUT="$TESTING/request-routerefs-mutant.sh"
python3 - "$TESTING/request.sh" "$RR_MUT" <<'PY'
import sys
src, dst = sys.argv[1:]
s = open(src).read()
anchor = '    mkdir -p "$RCHK/refs/route.txt"\n'
i = s.index(anchor)
tail = '\' "$ROUTE_REFS_FILE" "$RCHK/refs/route.txt"\n'
j = s.index(tail, i) + len(tail)
assert i < j, "mutant anchor no longer matches request.sh's check-copy staging block"
open(dst, "w").write(s[:i] + s[j:])
PY
if [ -f "$RR_MUT" ]; then
    out=$(rr_rq "$RR_MUT" "$RR_D/mutrq")
    case "$out" in
        *"no reference crop"*) ok "  with staging disabled, request.sh refuses again -- the crop does not travel, reproducing today's bug" ;;
        *) bad "  MUTANT: staging disabled still queued the route (or failed some other way) -- the legs above check nothing: $out" ;;
    esac
else
    bad "  mutant anchor no longer matches request.sh"
fi

rr_clean
rm -f "$RR_MUT"
rm -rf "$RR_D"
unset RR_NAME RR_ROUTE RR_REFDIR RR_SHA RR_D out RR_REQ rr_b64 rr_got RR_RDIR wmsg wrc RR_BADREQ RR_BADDIR bmsg brc RR_MUT
