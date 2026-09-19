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
