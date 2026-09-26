#!/usr/bin/env bash
# Two PRs editing glsl/psh.c at different places, before and after this lane.
#
#   demo.sh <tests dir> <pbkitplusplus dir> [base ref, default origin/master]
#
# Builds two commits off the base with plumbing only (a temporary git index;
# no worktree, no branch, nothing pushed): A inserts 4 lines near the top of
# psh.c, B inserts 6 lines near the bottom. Neither touches the index. Then:
#
#   1. each is checked by THIS tree's nv2a_index.py (default mode) -> must pass
#   2. `git merge-tree` of A and B -> must be clean
#   3. the OLD regime, for contrast: each commits its own regenerated index,
#      as CI used to demand, and merge-tree of those two -> index conflict
set -eu
TESTS=$1; SUPPORT=$2; BASE=${3:-origin/master}
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$(git -C "$HERE" rev-parse --show-toplevel)
S=$(mktemp -d "$TOP/.scratch/demo.XXXXXX")
trap 'rm -rf "$S"' EXIT
PSH=hw/xbox/nv2a/pgraph/glsl/psh.c
IX=docs/testing/nv2a_index.json
NEWPY="$TOP/docs/testing/nv2a_index.py"
cd "$TOP"

commit_with() {   # <parent> <message> <path=file>... -> new commit sha
    local parent=$1 msg=$2; shift 2
    export GIT_INDEX_FILE="$S/gitindex"
    git read-tree "$parent"
    local spec
    for spec in "$@"; do
        git update-index --add --cacheinfo "100644,$(git hash-object -w "${spec#*=}"),${spec%%=*}"
    done
    git commit-tree "$(git write-tree)" -p "$parent" -m "$msg"
    unset GIT_INDEX_FILE
}
insert_at() {   # <src> <dst> <after line> <count>
    python3 -c 'import sys
L = open(sys.argv[1]).read().split("\n"); n = int(sys.argv[3]); k = int(sys.argv[4])
L[n:n] = ["/* demo line %d */" % i for i in range(k)]
open(sys.argv[2], "w").write("\n".join(L))' "$@"
}
extract() {   # <commit> <dir>: the scanned roots plus docs/testing, with THIS lane's checker
    mkdir -p "$2"; git archive "$1" hw/xbox docs/testing | tar -x -C "$2"
    cp "$NEWPY" "$2/docs/testing/nv2a_index.py"
}

git show "$BASE:$PSH" > "$S/psh.base"
n=$(wc -l < "$S/psh.base")
insert_at "$S/psh.base" "$S/psh.a" 40 4
insert_at "$S/psh.base" "$S/psh.b" $((n - 40)) 6
base=$(git rev-parse "$BASE")
A=$(commit_with "$base" "demo A: 4 lines near the top of psh.c" "$PSH=$S/psh.a")
B=$(commit_with "$base" "demo B: 6 lines near the bottom of psh.c" "$PSH=$S/psh.b")
echo "base $base"
echo "A    $A  (psh.c +4 after line 40)"
echo "B    $B  (psh.c +6 after line $((n - 40)))"

echo; echo "== 1. each passes check without touching the index"
for side in A B; do
    sha=${!side}; extract "$sha" "$S/$side"
    echo "-- $side:"
    python3 "$S/$side/docs/testing/nv2a_index.py" check --tests "$TESTS" --support "$SUPPORT"
done

echo; echo "== 2. merge-tree A B (the two PRs folded one after the other)"
if out=$(git merge-tree --write-tree --name-only "$A" "$B"); then
    echo "clean: merged tree $(printf '%s\n' "$out" | head -1)"
else
    echo "CONFLICT:"; printf '%s\n' "$out"; exit 1
fi

echo; echo "== 3. contrast, the old regime: each side commits a regenerated index"
for side in A B; do
    python3 "$S/$side/docs/testing/nv2a_index.py" build --tests "$TESTS" --support "$SUPPORT" >/dev/null
    git diff --no-index --stat "$S/$side/$IX" <(git show "$base:$IX") | tail -1 | sed "s/^/   $side's rebuild vs base: /" || true
done
A2=$(commit_with "$A" "demo A: regenerated index" "$IX=$S/A/$IX")
B2=$(commit_with "$B" "demo B: regenerated index" "$IX=$S/B/$IX")
if out=$(git merge-tree --write-tree --name-only "$A2" "$B2"); then
    echo "clean (unexpected)"; exit 1
else
    echo "conflicts, as it did on 2026-09-26:"; printf '%s\n' "$out" | sed -n '2,/^$/p' | sed 's/^/   /'
fi
