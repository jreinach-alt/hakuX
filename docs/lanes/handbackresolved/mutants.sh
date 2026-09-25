#!/usr/bin/env bash
# Mutant and falsification runs for lane.handbackresolved.
#
#   mutants.sh <ref> <scratch-root>
#
# For each case, a scratch `git worktree` at <ref> (detached), one edit to
# handback.sh IN THAT WORKTREE, and a full `jobs/selftest.sh` there. The real
# tree is never touched. Prints each case's red checks from the
# "a needs-rebase PR whose conflict is already resolved" section.
set -u
ref=$1; root=$2
repo=$(git rev-parse --show-toplevel)
mkdir -p "$root"

mutate() {   # <file> <case>
    python3 - "$1" "$2" <<'PY'
import sys
p, case = sys.argv[1], sys.argv[2]
s = open(p, encoding="utf-8").read()
subs = {
    # drop the merge-tree test: every head reads as not-known-clean
    "no-merge-tree":  ('            merge_state "$branch" "$head"\n', '            MERGE_STATE=UNKNOWN\n'),
    # drop the GREEN condition: any clean head is relabelled
    "no-green":       ('                case "$ci" in\n                GREEN)', '                case GREEN in\n                GREEN)'),
    # treat NONE as GREEN
    "none-is-green":  ('                case "$ci" in\n                GREEN)', '                case "$ci" in\n                GREEN|NONE)'),
}
old, new = subs[case]
assert s.count(old) == 1, (case, s.count(old))
open(p, "w", encoding="utf-8").write(s.replace(old, new))
PY
}

run_case() {   # <case> [old]
    local c=$1 wt="$root/$1"
    git -C "$repo" worktree remove --force "$wt" 2>/dev/null
    git -C "$repo" worktree add -q --detach "$wt" "$ref" || return 1
    if [ "$c" = old-handback ]; then
        # the fragment and its draft-query sibling from <ref>; handback.sh from origin/master
        git -C "$wt" show origin/master:docs/testing/jobs/handback.sh > "$wt/docs/testing/jobs/handback.sh"
    else
        mutate "$wt/docs/testing/jobs/handback.sh" "$c"
    fi
    git -C "$wt" diff --stat
    ( cd "$wt" && bash docs/testing/jobs/selftest.sh > "$root/$c.out" 2>&1; echo "EXIT=$?" >> "$root/$c.out" )
    echo "== $c: $(tail -2 "$root/$c.out" | head -1)"
    echo "   reds in the resolved section:"
    awk '/^== handback.sh: a needs-rebase PR whose conflict/{on=1;next} /^== /{on=0} on' "$root/$c.out" | grep '^  FAIL'
    echo "   reds elsewhere:"
    awk '/^== handback.sh: a needs-rebase PR whose conflict/{on=1;next} /^== /{on=0} !on' "$root/$c.out" | grep '^  FAIL'
    git -C "$repo" worktree remove --force "$wt"
}

for c in "${@:3}"; do run_case "$c"; done
