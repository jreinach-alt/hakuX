# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# fold.sh regen_index: `check --exact` on the first check, only when the
# merged tree's nv2a_index.py takes it.
#
# After #360, `check` passes an index whose only drift is line numbers, and
# only `check --exact` fails on it. regen_index rebuilds when the first check
# fails, so without --exact master's line numbers would never be refreshed.
# Before #360 the script rejects --exact, so passing it unconditionally would
# fail every fold's check, rebuild, and hand back. Both trees are driven here
# through `fold.sh regen-index`, with a stand-in for each script.
#
# Builds everything under $T/foldexact. Depends on no other fragment.

echo "== fold.sh: regen_index passes --exact to the first check only where the tree's script takes it"
FE="$T/foldexact"; rm -rf "$FE"; mkdir -p "$FE"
IX=docs/testing/nv2a_index.json

fe_repo() {   # <dir> -> one commit; prints its sha
    git -c init.defaultBranch=master init -q "$1"
    git -C "$1" config user.email s@t; git -C "$1" config user.name s
    echo 1 > "$1/tree.txt"; git -C "$1" add -A; git -C "$1" commit -q -m c1; git -C "$1" rev-parse HEAD
}
FE_TC=$(fe_repo "$FE/tests"); FE_PB=$(fe_repo "$FE/support")

# Two stand-ins. Each logs its argv to $FE_CALLS. The index carries "drift":
# true (sites moved, anchors intact) until a build clears it.
#   old: argparse without --exact -- rejects it (exit 2), and `check` fails
#        on drift, as master's script does today.
#   new: --exact accepted -- plain `check` passes drift, `check --exact`
#        fails on it, as #360's script does.
cat > "$FE/common.py" <<'EOF'
import json, os, sys
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nv2a_index.json")
open(os.environ["FE_CALLS"], "a").write(" ".join(sys.argv[1:]) + "\n")
def main(has_exact):
    if "--help" in sys.argv:
        print("usage: nv2a_index.py check [-h] [--tests TESTS] [--support SUPPORT]" + (" [--exact]" if has_exact else ""))
        sys.exit(0)
    exact = "--exact" in sys.argv
    if exact and not has_exact:
        sys.stderr.write("nv2a_index.py: error: unrecognized arguments: --exact\n"); sys.exit(2)
    d = json.load(open(P))
    if sys.argv[1] == "check":
        sys.exit(1 if d["provenance"].get("drift") and (exact or not has_exact) else 0)
    d["provenance"]["drift"] = False
    json.dump(d, open(P, "w"), indent=1)
EOF
fe_tree() {   # <dir> <old|new> -> a tree whose index has drifted, at one commit
    local d=$1; rm -rf "$d"; mkdir -p "$d/docs/testing" "$d/.github/workflows"
    git -c init.defaultBranch=master init -q "$d"
    git -C "$d" config user.email s@t; git -C "$d" config user.name s
    cp "$FE/common.py" "$d/docs/testing/fe_common.py"
    { echo 'import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))'
      echo "import fe_common; fe_common.main($([ "$2" = new ] && echo True || echo False))"; } > "$d/docs/testing/nv2a_index.py"
    printf 'jobs:\n  check:\n    steps:\n      - env:\n          PBKIT_SHA: %s\n' "$FE_PB" > "$d/.github/workflows/nv2a-index.yml"
    printf '{"provenance": {"tests_commit": "%s", "drift": true},\n "suites": {"s0": 1}}\n' "$FE_TC" > "$d/$IX"
    git -C "$d" add -A; git -C "$d" commit -q -m base
}
fe_regen() {   # <fold.sh> <dir> -> fold.sh regen-index's code; calls in $FE/calls
    : > "$FE/calls"
    TESTS="$FE/tests" SUPPORT="$FE/support" HAKUX_WORK="$FE/work" HAKUX_REPO_DIR="$FE/nohost" \
        FE_CALLS="$FE/calls" bash "$1" regen-index "$2" 5 >"$FE/regen.log" 2>&1
}
first_check() { grep -v -- '--help' "$FE/calls" | grep -m1 '^check'; }
rebuilt() { [ "$(git -C "$1" log -1 --format=%s)" = "nv2a index: regenerate after folding #5" ]; }

case_old() {   # master today: no --exact anywhere; drift still triggers the rebuild
    local d="$FE/old"; fe_tree "$d" old
    fe_regen "$1" "$d" || return 1
    ! grep -q -- '--exact' "$FE/calls" && rebuilt "$d"
}
case_new() {   # after #360: the FIRST check is --exact and catches the drift; the post-build one is plain
    local d="$FE/new"; fe_tree "$d" new
    fe_regen "$1" "$d" || return 1
    first_check | grep -q -- '--exact' && rebuilt "$d" \
        && [ "$(grep -v -- '--help' "$FE/calls" | grep '^check' | tail -1 | grep -c -- '--exact')" = 0 ] \
        && [ "$(grep -v -- '--help' "$FE/calls" | grep -c '^check')" = 2 ]
}
check "pre-#360 tree: --exact is never passed, and the drifted index is rebuilt" case_old "$HERE/fold.sh"
check "post-#360 tree: the first check is --exact, so line drift is rebuilt" case_new "$HERE/fold.sh"

fe_not() { ! "$@"; }   # in this shell: the case functions are not exported
fe_mutant() {   # <name> <sed expr> -> a mutated fold.sh
    local m="$FE/mut-$1"; mkdir -p "$m"; cp -a "$HERE/." "$m/"; sed -i "$2" "$m/fold.sh"; echo "$m/fold.sh"
}
m=$(fe_mutant always 's/&& exact=--exact$/; exact=--exact/')
check "mutant always: the sed applied" bash -c '! cmp -s "$1" "$2"' _ "$m" "$HERE/fold.sh"
check "  mutant always: the pre-#360 script is handed --exact, which it rejects (so case_old tests the gate)" fe_not case_old "$m"
m=$(fe_mutant never 's/&& exact=--exact$/\&\& exact=/')
check "mutant never: the sed applied" bash -c '! cmp -s "$1" "$2"' _ "$m" "$HERE/fold.sh"
check "  mutant never: the post-#360 drift is NOT rebuilt (so case_new tests the flag)" fe_not case_new "$m"
