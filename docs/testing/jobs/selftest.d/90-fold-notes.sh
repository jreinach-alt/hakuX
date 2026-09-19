# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# fold.sh: a root NOTES.md is the one conflict it may resolve.
#
# Builds its own git fixtures under $T/foldnotes. No shared state.

echo "== fold.sh: a root NOTES.md is the one conflict it may resolve"
# roles/lane.md used to ask every lane for NOTES.md in the branch ROOT. master
# had none, so the first fold landed one and every fold after it conflicted on
# that exact path -- for good, since master then held lane A's notes and lane
# B's were a conflicting rewrite of them. Four lanes were queued behind that.
# The instruction is now docs/lanes/<lane>/NOTES.md, but the lanes already
# running never saw it, so fold.sh moves an incoming root copy to the lane's
# own path. What this pins is the BOUNDARY: that move happens only when root
# NOTES.md is the whole conflict, and any source file in the list still sends
# the PR back untouched.
FD="$T/foldnotes"
fixture() {   # <dir> [extra file both sides change] -> a repo mid-merge, conflicted
    local d="$1" also="${2:-}"; rm -rf "$d"; mkdir -p "$d"
    git -c init.defaultBranch=master init -q "$d"
    git -C "$d" config user.email s@t; git -C "$d" config user.name s
    echo base > "$d/src.c"; git -C "$d" add -A; git -C "$d" commit -q -m base
    git -C "$d" checkout -q -b lane/fixture
    echo "lane B measured the thing" > "$d/NOTES.md"
    [ -n "$also" ] && echo "lane B code" > "$d/$also"
    git -C "$d" add -A; git -C "$d" commit -q -m lane
    git -C "$d" checkout -q master
    echo "lane A measured the other thing" > "$d/NOTES.md"
    [ -n "$also" ] && echo "master code" > "$d/$also"
    git -C "$d" add -A; git -C "$d" commit -q -m master
    git -C "$d" merge --no-ff --no-edit -m "fold: PR #1 lane/fixture -- t" lane/fixture >/dev/null 2>&1
}
unmerged() { git -C "$1" diff --name-only --diff-filter=U | tr '\n' ' '; }

fixture "$FD/only"
check "the fixture really conflicts, and only in NOTES.md" [ "$(unmerged "$FD/only")" = "NOTES.md " ]
bash "$HERE/fold.sh" resolve-notes "$FD/only" lane/fixture >"$FD/only.log" 2>&1; rc=$?
check "resolve-notes accepts a NOTES.md-only conflict" [ "$rc" = 0 ]
check "nothing is left unmerged" [ -z "$(unmerged "$FD/only")" ]
check "the lane's notes are kept, at the lane's own path" \
    bash -c 'grep -q "lane B measured" "$1/docs/lanes/fixture/NOTES.md"' _ "$FD/only"
check "master's root copy is untouched" \
    bash -c 'grep -q "lane A measured" "$1/NOTES.md"' _ "$FD/only"
check "the move is staged, not left dirty" \
    bash -c '[ -z "$(git -C "$1" diff --name-only)" ]' _ "$FD/only"
git -C "$FD/only" commit -q -m "fold: PR #1 lane/fixture -- t" >/dev/null 2>&1
check "the result is still a merge commit (both parents)" git -C "$FD/only" rev-parse -q --verify HEAD^2

fixture "$FD/code" src.c
check "the second fixture conflicts in a source file too" bash -c '[ "$(git -C "$1" diff --name-only --diff-filter=U | tr "\n" " ")" = "NOTES.md src.c " ]' _ "$FD/code"
bash "$HERE/fold.sh" resolve-notes "$FD/code" lane/fixture >"$FD/code.log" 2>&1; rc=$?
check "resolve-notes REFUSES when a source file conflicts as well" [ "$rc" != 0 ]
check "  and leaves the conflict exactly as it found it" [ "$(unmerged "$FD/code")" = "NOTES.md src.c " ]
check "  and writes no per-lane notes file" [ ! -e "$FD/code/docs/lanes/fixture/NOTES.md" ]

fixture "$FD/taken"
mkdir -p "$FD/taken/docs/lanes/fixture"; echo "an earlier record" > "$FD/taken/docs/lanes/fixture/NOTES.md"
bash "$HERE/fold.sh" resolve-notes "$FD/taken" lane/fixture >"$FD/taken.log" 2>&1; rc=$?
check "resolve-notes REFUSES when the destination is occupied (that would be a content decision)" [ "$rc" != 0 ]
check "  and does not overwrite what is there" grep -q "an earlier record" "$FD/taken/docs/lanes/fixture/NOTES.md"

check "roles/lane.md asks for the per-lane path, not the branch root" \
    grep -q 'docs/lanes/<your lane name>/NOTES.md' "$HERE/roles/lane.md"
check "roles/cloud.md asks for the same" grep -q 'docs/lanes/cloud-<short>/NOTES.md' "$HERE/roles/cloud.md"
check "no role file still asks for NOTES.md in the branch root" \
    bash -c '! grep -rn "NOTES.md\` in the branch root\|NOTES.md in the branch root" "$HERE/roles/"'
