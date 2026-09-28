# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# fleet.py's release-at-ready check never asks a STANDING row to release. A
# standing row (`standing = true`, e.g. [lane.xbox]) is driven by an
# interactive session, so it has no unit and always reads "unit gone". On
# 2026-09-28 lane.xbox's #561 went ready, touching only a file outside its row,
# and fleet.py asked the board to release all 16 files the lane was still
# working in. Drives fold_watch() directly with pr_state stubbed: a normal row
# and a standing row, each with a ready green PR, unreleased files and no unit.

echo "== fleet.py: a standing row is never asked to release at ready"
export SR="$T/standingrel"; mkdir -p "$SR"
cat > "$SR/run.py" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import fleet
fleet.pr_state = lambda n: ("a" * 40, True, "green")
terr = {"lane": {
    "normal": {"files": ["tools/a.py", "tools/b.py"], "released": []},
    "xbox": {"standing": True, "files": ["tools/xbox/x.py", "tools/nv2a_probe/y.py"],
             "released": []},
}}
prs = [{"number": 9701, "lane": "normal", "isDraft": False, "labelset": set()},
       {"number": 9702, "lane": "xbox", "isDraft": False, "labelset": set()}]
release, stuck, unread = fleet.fold_watch(prs, terr, set())
for lane, n, files in release:
    print("RELEASE lane.%s #%d %s" % (lane, n, " ".join(files)))
print("RELEASED %d UNREAD %d" % (len(release), unread))
EOF
( export HAKUX_REPO="example/hakux"; python3 "$SR/run.py" "$TESTING" ) > "$SR/out.txt" 2>&1
check "the normal row, ready green PR and no unit, is asked to release its files" \
    grep -qx 'RELEASE lane.normal #9701 tools/a.py tools/b.py' "$SR/out.txt"
check "the standing row, ready green PR and no unit, is NOT asked to release" \
    bash -c '! grep -q "lane.xbox" "$SR/out.txt"'
check "exactly one release, and fold_watch ran to its end" \
    grep -qx 'RELEASED 1 UNREAD 0' "$SR/out.txt"
