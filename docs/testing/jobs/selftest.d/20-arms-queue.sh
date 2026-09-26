# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# arms.sh run: the live prediction is queued, once, as two well-formed requests.
#
# Runs after 10-arms-list (nothing is queued yet when it starts) and leaves the
# pair and the two .req files that 30-arms-error reads.

echo "== arms.sh run: queue"
bash "$HERE/arms.sh" >/dev/null 2>&1
pairs=$(ls "$HAKUX_WORK"/arms/pairs/*.json 2>/dev/null | wc -l)
reqs=$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)
check "one pair recorded" [ "$pairs" -eq 1 ]
check "two requests in the dispatcher queue" [ "$reqs" -eq 2 ]
if [ "$reqs" -eq 2 ]; then
    for r in "$DISPATCH_DIR"/queue/*.req; do
        python3 - "$r" "$EXP" <<'PY' && ok "request $(basename "$r") parses, runs is an int, expect_sha bound" || bad "request $(basename "$r") malformed"
import json, sys, hashlib
d = json.load(open(sys.argv[1]))
assert isinstance(d["runs"], int) and d["runs"] >= 1, d["runs"]
assert d["expect_sha"] == hashlib.sha256(open(sys.argv[2], "rb").read()).hexdigest(), "expect_sha"
assert d["suites"] == ["Blend surface", "Color mask blend"], d["suites"]
PY
    done
fi
check "nothing was skipped for the live prediction" bash -c '! ls "$HAKUX_WORK"/arms/skipped/* 2>/dev/null | xargs -r grep -l selftest-live'
check "a second run does not queue it again" bash -c 'bash "$HERE/arms.sh" >/dev/null 2>&1; [ "$(ls "$DISPATCH_DIR"/queue/*.req | wc -l)" -eq 2 ]'
