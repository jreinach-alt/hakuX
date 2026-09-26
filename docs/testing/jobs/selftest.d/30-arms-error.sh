# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# arms.sh run: an arm whose result is an ERROR is judged ARM ERROR, and the
# verdict is posted somewhere.
#
# Consumes the pair 20-arms-queue left; must run after it.

echo "== arms.sh run: judge the ERROR path"
pair=$(ls "$HAKUX_WORK"/arms/pairs/*.json | head -1)
idb=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['id_b'])" "$pair")
sha=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['sha'])" "$pair")
mkdir -p "$DISPATCH_DIR/results/$idb"; echo "simulated device failure" > "$DISPATCH_DIR/results/$idb/ERROR"
bash "$HERE/arms.sh" >/dev/null 2>&1
check "an ERROR arm is judged as ARM ERROR" grep -q ERROR "$HAKUX_WORK/arms/judged/$sha"
check "the ARM ERROR was posted somewhere" grep -qE '^(pr|issue) comment' "$SELFTEST_GH_LOG"
