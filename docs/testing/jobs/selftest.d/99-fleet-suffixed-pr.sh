# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# fleet.py files a `lane/<name>-<suffix>` PR under <name>, not under a lane
# called `<name>-<suffix>` that has no row and no unit. On 2026-09-28 job.board
# retired lane.sustain507 as having "no open PR" while #547
# (`lane/sustain507-levers`) was open. Builds its own fixtures; stubs gh the
# way 96-fleet-registry.sh does.

echo "== fleet.py: a lane's suffixed PR is filed under the lane"
export SX="$T/suffixpr"; mkdir -p "$SX/bin" "$SX/work/wt"
cat > "$SX/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *"/pulls?"*) cat "${SELFTEST_FLEET_PRS:?}" ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$SX/bin/gh"
# IN REST'S SHAPE (head.ref, draft), as /pulls sends it.
cat > "$SX/prs.json" <<'EOF'
[{"number":9601,"head":{"ref":"lane/sustain507-levers"},"draft":true,"labels":[],"title":"part C"},
 {"number":9602,"head":{"ref":"lane/flip474-ts"},"draft":false,"labels":[],"title":"ts"},
 {"number":9603,"head":{"ref":"lane/foo-bar"},"draft":true,"labels":[],"title":"exact wins"},
 {"number":9604,"head":{"ref":"lane/zzz-1"},"draft":true,"labels":[],"title":"no row"},
 {"number":9605,"head":{"ref":"lane/foo-bar-2"},"draft":true,"labels":[],"title":"longest prefix"},
 {"number":9606,"head":{"ref":"lane/qux-x"},"draft":true,"labels":[],"title":"worktree"},
 {"number":9607,"head":{"ref":"lane/cloud-abc"},"draft":true,"labels":[],"title":"cloud"},
 {"number":9608,"head":{"ref":"lane/sustain507"},"draft":false,"labels":[],"title":"part A"}]
EOF
# The third resolver: no row matches `qux-x`, but wt/quxlane has it checked out.
git init -q -b lane/qux-x "$SX/work/wt/quxlane"
cat > "$SX/map.py" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import fleet
rows = {k: {} for k in ("sustain507", "flip474", "foo", "foo-bar", "cloud")}
for p in fleet.lane_prs({}, rows, {}):
    print("MAP %s -> %s" % (p["headRefName"], p["lane"]))
EOF
( export PATH="$SX/bin:$PATH" SELFTEST_FLEET_PRS="$SX/prs.json" \
         HAKUX_REPO="example/hakux" HAKUX_WORK="$SX/work"
  python3 "$SX/map.py" "$TESTING" ) > "$SX/out.txt" 2>&1
check "lane/sustain507-levers is filed under sustain507, its row" \
    grep -qx 'MAP lane/sustain507-levers -> sustain507' "$SX/out.txt"
check "lane/flip474-ts is filed under flip474" \
    grep -qx 'MAP lane/flip474-ts -> flip474' "$SX/out.txt"
check "lane/foo-bar with rows foo and foo-bar is foo-bar: exact wins" \
    grep -qx 'MAP lane/foo-bar -> foo-bar' "$SX/out.txt"
check "lane/foo-bar-2 goes to the LONGEST prefix row, foo-bar" \
    grep -qx 'MAP lane/foo-bar-2 -> foo-bar' "$SX/out.txt"
check "lane/zzz-1 with no matching row keeps zzz-1" \
    grep -qx 'MAP lane/zzz-1 -> zzz-1' "$SX/out.txt"
check "lane/qux-x, no row, goes to the worktree that has it checked out" \
    grep -qx 'MAP lane/qux-x -> quxlane' "$SX/out.txt"
check "lane/cloud-abc is left as is, even with a row called cloud" \
    grep -qx 'MAP lane/cloud-abc -> cloud-abc' "$SX/out.txt"
check "the lane's own-name PR is still its own" \
    grep -qx 'MAP lane/sustain507 -> sustain507' "$SX/out.txt"
check "every PR in the fixture was mapped, none dropped" \
    bash -c '[ "$(grep -c "^MAP " "$SX/out.txt")" = 8 ]'
