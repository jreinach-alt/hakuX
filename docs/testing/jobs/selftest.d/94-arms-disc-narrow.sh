# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $A/$B (the live refs), $GOLDENS, the shims on PATH, ok/bad/check. Not
# executable, no shebang, no exit.
#
# arms.sh queues a prediction's whole disc composition (dispatch-hardening
# defect 27).
#
# suites_for() read `disc.suites` only and both request.sh calls passed
# --suites only, so a prediction registered with `disc.skip_tests` was queued
# on a disc WITH the skipped test, and ab_compare, which checks all three
# composition axes, refused the pair it was built for: tiecode282-binade.json
# on #379, whose disc skips `Texture render target::RenderTextureLoop`.
#
# Three predictions, the narrowed ones either side of a plain one: a skip list
# (a JSON list), a plain disc (no flag may appear), an allow-list (a comma
# string). Its own work and dispatch dirs; the mutant runs from a copy.

echo "== arms.sh: a prediction's skip_tests / only_tests reach both arms"

DN="$T/discnarrow"
dn_setup() {
    rm -rf "$DN"; mkdir -p "$DN/work/arms" "$DN/work/logs/arms" "$DN/d"/{queue,running,results,expect,bin}
    date -u -d '1 minute ago' '+%FT%TZ' > "$DN/work/arms/since"
    # request.sh checks the SERVING dispatcher for each narrowing flag: the
    # tree for --skip-tests, the snapshot for --only-tests. This tree is both.
    cp "$TESTING/dispatcher.sh" "$TESTING/make_test_iso.py" "$DN/d/bin/"
    python3 - "$DN/d/expect" "$A" "$B" <<'PY'
import json, os, sys, datetime
d, a, b = sys.argv[1:]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def reg(name, disc):
    json.dump({"registered_utc": now, "who": "lane." + name, "issue": "1",
               "prediction": name, "a_ref": a, "b_ref": b,
               "expect": {"Blend_surface/TestA": 0}, "must_not_move": [],
               "must_not_regress": [], "expect_counts": {},
               "disc": disc}, open(os.path.join(d, name + ".json"), "w"), indent=2)
reg("dnskip", {"suites": ["Blend surface", "Color mask blend"],
               "skip_tests": ["Color mask blend::Other"], "only_tests": [],
               "source": "stated on the --register command line"})
reg("dnplain", {"suites": ["Blend surface", "Color mask blend"],
                "skip_tests": [], "only_tests": []})
reg("dnonly", {"suites": "Blend surface", "only_tests": "Blend surface::TestA"})
PY
}
dn_tick() {   # <arms.sh>  -> the tick log
    ( export HAKUX_WORK="$DN/work" DISPATCH_DIR="$DN/d" DISPATCH_TREE="$REPO" \
             ARMS_QUEUE_MAX=10 ARMS_MAX_PAIRS_PER_TICK=3
      bash "$1" ) >/dev/null 2>&1
    cat "$DN/work/logs/arms/tick.log" 2>/dev/null
}
dn_req() { ls "$DN/d/queue/"*"-arms-$1-$2"*.req 2>/dev/null | head -1; }   # <name> base|fix
# <name> -> "skip|only" per arm, then whether ab_compare's composition check
# accepts that pair against its prediction (it dies on a mismatch, because
# every prediction here carries an `expect` absolute).
dn_read() {
    local a b; a=$(dn_req "$1" base); b=$(dn_req "$1" fix)
    [ -n "$a" ] && [ -n "$b" ] || { echo "UNQUEUED"; return; }
    python3 - "$TESTING" "$DN/d/expect/$1.json" "$a" "$b" <<'PY'
import json, sys, types
sys.path.insert(0, sys.argv[1]); import ab_compare
exp = json.load(open(sys.argv[2]))
arms = []
for n, p in (("a", sys.argv[3]), ("b", sys.argv[4])):
    r = json.load(open(p))
    print("%s skip=%s only=%s" % (n, ",".join(r.get("skip_tests") or []), ",".join(r.get("only_tests") or [])))
    arms.append(types.SimpleNamespace(name=n, label=n, request=r))
if isinstance(exp["disc"].get("suites"), str) or isinstance(exp["disc"].get("only_tests"), str):
    # ab_compare reads a registered axis as a list (--register writes one);
    # a hand-written comma string is normalised as arms.sh reads it.
    for k in ab_compare.COMPOSITION_AXES:
        v = exp["disc"].get(k)
        if isinstance(v, str):
            exp["disc"][k] = [x.strip() for x in v.split(",") if x.strip()]
try:
    ab_compare.composition_notes(exp, *arms)
    print("composition ok")
except SystemExit:
    print("composition REFUSED")
PY
}

dn_setup; log=$(dn_tick "$HERE/arms.sh")
out=$(dn_read dnskip)
check "skip_tests: both arms' requests carry the skip" \
    grep -qz 'a skip=Color mask blend::Other only=.b skip=Color mask blend::Other only=' <<< "$out"
check "  and ab_compare's composition check passes on the pair" grep -qx 'composition ok' <<< "$out"
check "  and the tick log names the skip" grep -q 'queue .*dnskip.*skip=\[Color mask blend::Other\]' <<< "$log"
out=$(dn_read dnplain)
check "a plain disc: neither arm gains a skip or an allow-list" \
    grep -qz 'a skip= only=.b skip= only=' <<< "$out"
check "  and its composition check passes" grep -qx 'composition ok' <<< "$out"
check "  and the tick log names no narrowing" bash -c '! grep "queue .*dnplain" <<< "$1" | grep -q "skip=\|only="' _ "$log"
out=$(dn_read dnonly)
check "only_tests (a comma string): both arms carry the allow-list" \
    grep -qz 'a skip= only=Blend surface::TestA.b skip= only=Blend surface::TestA' <<< "$out"
check "  and its composition check passes" grep -qx 'composition ok' <<< "$out"

# The mutant: both calls pass --suites alone, which is the old arms.sh. It
# queues through request.sh, which arms.sh finds at jobs/.., so it runs inside
# a symlink tree of docs/testing with only jobs/arms.sh a real, edited file.
# request.sh resolves --ref with `git -C $0/../..`, so the tree sits at
# docs/testing under a directory whose .git is this repository's.
mr="$DN-mut"; mt="$mr/docs/testing"; md="$mt/jobs"; rm -rf "$mr"; mkdir -p "$md"
ln -s "$REPO/.git" "$mr/.git"
for f in "$TESTING"/*; do [ "${f##*/}" = jobs ] || ln -s "$f" "$mt/"; done
for f in "$HERE"/*; do [ "${f##*/}" = arms.sh ] || ln -s "$f" "$md/"; done
python3 - "$HERE/arms.sh" "$md/arms.sh" <<'PY'
import sys
src, dst = sys.argv[1:]
s = open(src).read()
old = ' ${narrow[@]+"${narrow[@]}"}'
assert s.count(old) == 2, "mutant anchor matches %d times" % s.count(old)
open(dst, "w").write(s.replace(old, ""))
PY
if [ -f "$md/arms.sh" ]; then
    dn_setup; dn_tick "$md/arms.sh" >/dev/null
    s=$(dn_read dnskip); o=$(dn_read dnonly); p=$(dn_read dnplain)
    if grep -qx 'composition REFUSED' <<< "$s" && grep -qx 'composition REFUSED' <<< "$o" \
       && grep -qx 'composition ok' <<< "$p"; then
        ok "mutant '--suites only' queues discs ab_compare refuses for skip and only, the plain one still ok (red, as it must be)"
    else
        bad "mutant '--suites only' was not refused: the fragment cannot see it ($(echo $s / $o / $p))"
    fi
else
    bad "mutant anchor no longer matches arms.sh"
fi
rm -rf "$DN" "$mr"
