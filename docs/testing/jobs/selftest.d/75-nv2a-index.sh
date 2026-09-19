# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# nv2a_index.py: the fold job regenerates the index, so the DIRECTION of the
# difference between the index's provenance and the tests tree matters.
#
# Builds its own throwaway repos under $T/gate. No shared state.

echo "== nv2a_index.py: the fold job regenerates the index, so the tree it reads matters"
# The fold job runs `nv2a_index.py check` after a merge and, if it fails,
# `build` -- from whatever nxdk_pgraph_tests checkout the host holds. On
# 2026-09-19 that checkout was five commits behind the one the committed index
# came from, so the regeneration would have DELETED a suite (Surface as vertex
# array) and pushed the deletion to master. The gate checks the DIRECTION of
# the difference. Two throwaway repos are enough to test that; no suite parsing
# is involved.
GT="$T/gate"; mkdir -p "$GT/tests"
git -C "$GT/tests" init -q 2>/dev/null
git -C "$GT/tests" -c user.email=s@t -c user.name=s commit -q --allow-empty -m one
c1=$(git -C "$GT/tests" rev-parse HEAD)
git -C "$GT/tests" -c user.email=s@t -c user.name=s commit -q --allow-empty -m two
c2=$(git -C "$GT/tests" rev-parse HEAD)
printf '{"provenance": {"tests_commit": "%s"}}\n' "$c2" > "$GT/index.json"
gate() {   # <checkout-at> <allow_older> -> the gate's return code
    git -C "$GT/tests" checkout -q "$1"
    python3 - "$REPO/docs/testing/nv2a_index.py" "$GT/index.json" "$GT/tests" "$2" 2>"$GT/gate.err" <<'PYGATE'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("nv2a_index", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.INDEX_PATH = sys.argv[2]
print(m.tests_provenance_gate(sys.argv[3], sys.argv[4] == "1"))
PYGATE
}
check "a tests tree OLDER than the index refuses the rebuild" [ "$(gate "$c1" 0)" = 3 ]
check "the same tree with --allow-older-tests proceeds" [ "$(gate "$c1" 1)" = 0 ]
check "a tests tree AT the index's commit builds" [ "$(gate "$c2" 0)" = 0 ]
git -C "$GT/tests" -c user.email=s@t -c user.name=s commit -q --allow-empty -m three
check "a tests tree NEWER than the index builds" [ "$(gate HEAD 0)" = 0 ]
printf '{"provenance": {"tests_commit": "%s"}}\n' "0123456789012345678901234567890123456789" > "$GT/index.json"
check "a provenance commit this checkout has never seen refuses" [ "$(gate HEAD 0)" = 3 ]

echo "== nv2a_index.py: a suite disagreement has a DIRECTION, and only one of them may regenerate"
# The gate above asks GIT whether the checkout is behind, and it is blind
# whenever git cannot answer: a tests tree that is not a checkout at all, an
# index with no tests_commit, a different fork. MEASURED 2026-09-19 (#157): a
# copy of the host's tests tree with one suite's source deleted and no .git in
# it passed the provenance gate with rc 0, and `build` wrote a 102-suite index
# over the committed 103-suite one in silence. Provenance ranks the TREE; this
# ranks the RESULT, which is the thing being lost, so it catches the event
# however the tree got that way. Synthetic suite tables, so no index is built.
IDX="$GT/suites-index.json"
drift() {   # <committed csv> <fresh csv> <allow 0|1> [tests_root] -> "rc=N" then the text
    # tests_root defaults to a path and is passed EMPTY for the no---tests
    # build, because that is what build_index records in provenance when
    # --tests was not given -- the gate branches on it to name that cause.
    python3 - "$REPO/docs/testing/nv2a_index.py" "$IDX" "$1" "$2" "$3" "${4-/tmp/tree}" <<'PYSD'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("nv2a_index", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.INDEX_PATH = sys.argv[2]
def table(csv):
    return {n: {"sources": ["src/tests/%s.cpp" % n], "symbols": []}
            for n in csv.split(",") if n}
committed, fresh = table(sys.argv[3]), table(sys.argv[4])
json.dump({"suites": committed}, open(m.INDEX_PATH, "w"))
tests_root = sys.argv[6] or None
missing, extra, changed = m.suite_drift(committed, fresh)
print("rc=%d" % m.suite_removal_gate(
    {"suites": fresh, "provenance": {"tests_root": tests_root}},
    sys.argv[5] == "1"))
print(m.stale_headline(bool(missing)))
print("\n".join(m.describe_suite_drift(missing, extra, changed, tests_root)))
PYSD
}
has()  { printf '%s\n' "$2" | grep -qF -- "$1"; }
hasnt() { ! printf '%s\n' "$2" | grep -qF -- "$1"; }

short=$(drift "Alpha func,Fog,Surface as vertex array" "Alpha func,Fog" 0 2>&1)
check "a tests tree short of the index NAMES the missing suite" \
      has "MISSING 1 suite(s) the index has: Surface as vertex array" "$short"
check "  and says to fix the tree rather than the index" \
      has "Fix the TREE, not the" "$short"
# THE BUG ITSELF, as an absence: the old headline told every failure to
# regenerate, and regenerating is what deletes the suite. A wording change
# that reintroduces the word `build` on this path fails here.
check "  and its headline does NOT tell the reader to regenerate" \
      hasnt "regenerate with: nv2a_index.py build" "$short"
check "  and the build refuses to write the smaller index" has "rc=4" "$short"
check "  naming what would be deleted" \
      has "would be deleted: Surface as vertex array" "$short"

allowed=$(drift "Alpha func,Fog,Surface as vertex array" "Alpha func,Fog" 1 2>&1)
check "the same build with --allow-suite-removal proceeds" has "rc=0" "$allowed"
check "  and still says which suite it dropped" \
      has "would be deleted: Surface as vertex array" "$allowed"

ahead=$(drift "Alpha func,Fog" "Alpha func,Fog,Surface as vertex array" 0 2>&1)
check "a tests tree AHEAD of the index names the suite the index lacks" \
      has "the tests tree has 1 suite(s) the index does NOT: Surface as vertex array" "$ahead"
check "  and THIS direction is told to regenerate" \
      has "regenerate with: nv2a_index.py build" "$ahead"
check "  and the build is allowed: adding suites loses nothing" has "rc=0" "$ahead"

same=$(drift "Alpha func,Fog" "Alpha func,Fog" 0 2>&1)
check "an agreeing tree reports no drift at all" hasnt "suite(s)" "$same"
check "  and builds" has "rc=0" "$same"

# The 2026-09-13 accident: `build` with no --tests parses no suites, writes an
# empty suite half, and a `check` with no --tests then passes it because both
# sides agree there are none. An empty fresh table is the extreme of the same
# removal, so the same gate catches it.
none=$(drift "Alpha func,Fog" "" 0 "" 2>&1)
check "a build that parsed NO suites is refused as a removal of all of them" \
      has "rc=4" "$none"
check "  and names the missing --tests as the cause" has "WITHOUT --tests" "$none"
