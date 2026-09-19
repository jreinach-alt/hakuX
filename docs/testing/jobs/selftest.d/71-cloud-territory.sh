# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# cloud.sh writes its own territory row, so the board does not spend a model
# session doing it.
#
# 71 because it belongs beside 70-cloud-audit.sh (the same script) and must
# run before 98-audit-outlet.sh, which drives the same PR number; it cleans up
# the attempt counter and the worktree it creates, so 98 sees what it did
# before. Depends on no other fragment: it builds its own git remote, its own
# repo and its own gh shim, and it never touches this repository or the shared
# gh shim.
#
# REAL GIT, NOT A SHIM. The property under test is that a row reaches the
# `board` BRANCH and survives a concurrent writer, and no shim can stand in
# for git's own refusal of a non-fast-forward push -- which is the entire
# lost-update guard. So `origin` here is a real bare repository with a real
# orphan board branch, and the concurrent board tick is a real pre-receive
# hook that moves the branch under the claim.

echo "== cloud.sh: the audit outlet writes the territory row it used to leave to a board tick"
# MEASURED 2026-09-19, $WORK/logs/board/tick.log: seven "FAIL: 1 lane(s) are
# RUNNING with no territory row", five naming a unit cloud.sh started. Each
# woke a board tick -- a model session against the shared window -- to write a
# row the claim already had in hand; and until that tick ran, check_territory
# could not see the session at all.
CT="$T/cloudterr"; mkdir -p "$CT/bin"

# A gh that answers as GitHub does for ONE open PR: #102, head lane/blitsafe,
# needs-remediation. Its body carries the lane contract's `Issue: #88` header
# and, further down, a #999 in prose -- a number mentioned is not an issue
# claimed, and the difference is coverage that does not exist.
cat > "$CT/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        [[ "$args" == *"--label ${CT_LABEL:-needs-remediation}"* ]] || exit 0
        printf '102\tlane/blitsafe\tblit: clamp the destination rect\n'; exit 0 ;;
    "pr view")
        cat <<'JSON'
{"body": "Lane: blitsafe            Issue: #88\nBase: master @ deadbeef\nIt also revisits the #999 measurement in passing, which is prose and not a claim.",
 "closingIssuesReferences": [{"number": 88}],
 "files": [{"path": "hw/xbox/nv2a/pgraph/vk/blit.c"},
           {"path": "hw/xbox/nv2a/pgraph/gl/surface.c"},
           {"path": "docs/lanes/blitsafe/NOTES.md"}]}
JSON
        exit 0 ;;
    "api "*)
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${CT_LABELS:-}; exit 0; }
        exit 0 ;;
esac
exit 0
EOF
chmod +x "$CT/bin/gh"; CTPATH="$CT/bin:$PATH"

# The fixture board: a wave, a lane holding one of the PR's files, and a
# [free] list holding another. Both are paths check_territory.py would FAIL
# on if a second row claimed them -- and that FAIL makes preflight red for
# every lane on the repository, so a bookkeeping write must not be able to
# cause it.
ct_fixture() {   # <dir> -> <dir>/origin.git (bare) + <dir>/repo (a clone with a worktree)
    local d=$1
    rm -rf "$d"; mkdir -p "$d"
    git init -q --bare "$d/origin.git"
    git init -q "$d/repo"
    git -C "$d/repo" remote add origin "$d/origin.git"
    git -C "$d/repo" config user.email t@example.invalid
    git -C "$d/repo" config user.name t
    git -C "$d/repo" checkout -q -b master
    echo "the trunk" > "$d/repo/README.md"
    git -C "$d/repo" add -A && git -C "$d/repo" commit -qm "fixture: master"
    git -C "$d/repo" push -q origin master
    git -C "$d/repo" checkout -q -b lane/blitsafe
    echo "a lane's work" > "$d/repo/blit.txt"
    git -C "$d/repo" add -A && git -C "$d/repo" commit -qm "fixture: the PR's branch"
    git -C "$d/repo" push -q origin lane/blitsafe
    git -C "$d/repo" checkout -q master
    # The board branch, orphan, exactly as bootstrap-board-branch.sh makes it.
    git -C "$d/repo" checkout -q --orphan board
    git -C "$d/repo" rm -rq --cached . >/dev/null 2>&1
    rm -f "$d/repo/README.md" "$d/repo/blit.txt"
    cat > "$d/repo/territory.toml" <<'TOML'
# WHO HOLDS WHICH FILES. A fixture, with the comments that a tomllib
# round-trip would delete -- which is why the edit is textual and the
# VALIDATION is what parses.
wave = 7
updated_utc = "2026-09-19T00:00:00Z"

[lane.blitsafe]
issues = ["88"]
files = ["hw/xbox/nv2a/pgraph/vk/blit.c"]
standing = false
note = "the local lane that opened PR #102; it still holds its file"

[free]
files = ["hw/xbox/nv2a/pgraph/gl/surface.c"]
TOML
    git -C "$d/repo" add -A && git -C "$d/repo" commit -qm "fixture: the board"
    git -C "$d/repo" push -q origin board
    git -C "$d/repo" checkout -q master
}
ct_claim() {     # <dir> [extra env] -- run a real claim against the fixture
    local d=$1; shift
    rm -f "$HAKUX_WORK/attempts/cloud-remediate-102"
    env "$@" HAKUX_REPO_DIR="$d/repo" PATH="$CTPATH" bash "$HERE/cloud.sh" 2>&1
}
ct_cleanup() {   # the worktree cloud.sh made, and the counter 98- reads
    git -C "$1/repo" worktree remove --force "$HAKUX_WORK/wt/cloud-remediate-102" 2>/dev/null
    rm -rf "$HAKUX_WORK/wt/cloud-remediate-102"
    rm -f "$HAKUX_WORK/attempts/cloud-remediate-102"
}
ct_row() {       # <dir> <lane> -> that lane's row as JSON, or {} if it is absent
    git -C "$1/origin.git" show "board:territory.toml" > "$CT/after.toml" 2>/dev/null
    python3 - "$CT/after.toml" "$2" <<'PY'
import json, sys, tomllib
try:
    d = tomllib.load(open(sys.argv[1], "rb"))
except Exception as e:
    print(json.dumps({"UNPARSEABLE": str(e)})); raise SystemExit(0)
print(json.dumps(d.get("lane", {}).get(sys.argv[2], {}), sort_keys=True))
PY
}

# ---------------------------------------------------------------- the claim
ct_fixture "$CT/a"
: > "$SELFTEST_GH_LOG"
cout=$(ct_claim "$CT/a")
ROW=$(ct_row "$CT/a" cloud-remediate-102)
has() { grep -q -- "$1" <<< "$ROW"; }

check "the claim writes the row itself, on the board branch, with no board tick" \
    bash -c '[ "$1" != "{}" ]' _ "$ROW"
check "and the row is the lane the unit is named after (hakux-lane-cloud-remediate-102)" \
    grep -q "territory: lane.cloud-remediate-102 row written" <<< "$cout"
check "it claims the PR's issue, from the closing reference and the body header" \
    has '"issues": \["88"\]'
check "a number mentioned in the PR's prose is NOT claimed as an issue" \
    bash -c '! grep -q 999 <<< "$1"' _ "$ROW"
# A remediation edits the PR's own files, so it says so -- but only for the
# paths no other row already names. Claiming a path twice, or claiming one
# [free] lists, is a check_territory.py FAIL, and that gate is red for EVERY
# lane at once: the collision is already visible through the row that holds
# the path, a fleet-wide red gate would be new damage.
check "a remediation claims the PR's files" \
    has 'docs/lanes/blitsafe/NOTES.md'
check "except a path another lane already holds" \
    bash -c '! grep -q "vk/blit.c\"" <<< "$1"' _ "$ROW"
check "and except a path [free] lists, which is the same FAIL by another name" \
    bash -c '! grep -q "gl/surface.c\"" <<< "$1"' _ "$ROW"
check "the omission is written into the note, naming who holds each path" \
    bash -c 'grep -q "NOT CLAIMED" <<< "$1" && grep -q "lane.blitsafe" <<< "$1" && grep -q "free" <<< "$1"' _ "$ROW"
check "the note says the row was written at claim by the outlet, not by the board" \
    has 'WRITTEN AT CLAIM by jobs/cloud.sh'

check "the session starts, and starts claimed" \
    grep -q "^systemd-run" "$SELFTEST_GH_LOG"
# THE ROW EXISTS BEFORE THE SESSION DOES. fleet.py's own account of this
# defect lists "a row written and validated but COMMITTED AFTER DISPATCH" as
# one of its three variants: the lane then ran its whole life against a table
# where its files sat in [free]. The dispatch and the push are in two
# different logs, so the ORDER is pinned in the script, anchored on the calls
# rather than on any wording near them.
check "the row is written BEFORE systemd-run, not after the session exists" bash -c '
    r=$(grep -n "^territory_row add " "$1" | head -1 | cut -d: -f1)
    s=$(grep -n "^systemd-run --user" "$1" | head -1 | cut -d: -f1)
    [ -n "$r" ] && [ -n "$s" ] && [ "$r" -lt "$s" ]' _ "$HERE/cloud.sh"

# NOTHING ELSE MOVED. The file is 90% comments earned one incident at a time,
# so the edit is textual and the parse is the check: three board-file
# breakages in one session came from writing a structured file by slicing.
OTHER=$(ct_row "$CT/a" blitsafe)
check "the other lane's row is untouched, field for field" bash -c '[ "$1" = "$2" ]' _ "$OTHER" \
    '{"files": ["hw/xbox/nv2a/pgraph/vk/blit.c"], "issues": ["88"], "note": "the local lane that opened PR #102; it still holds its file", "standing": false}'
check "the wave, the [free] list and the file's comments all survive the edit" bash -c '
    grep -q "^wave = 7$" "$1" && grep -q "gl/surface.c" "$1" && grep -q "^# WHO HOLDS WHICH FILES" "$1"' _ "$CT/after.toml"
check "master is not touched: the row goes to the board branch only" bash -c '
    [ "$(git -C "$1/origin.git" rev-parse master)" = "$(git -C "$1/repo" rev-parse master)" ]' _ "$CT/a"

# ---------------------------------------------------------------- the unclaim
# `finish` already drops the claim label on exit; a row that outlived its unit
# is a claim with no agent, and fleet.py prints that as `ghost` and sets no rc,
# so nothing would ever fail on one accumulating per audit.
PATH="$CTPATH" HAKUX_REPO_DIR="$CT/a/repo" CT_LABELS="needs-remediation claimed:cloud" \
    bash "$HERE/cloud.sh" finish remediate 102 >/dev/null 2>&1
GONE=$(ct_row "$CT/a" cloud-remediate-102)
check "finish removes the row it claimed under" bash -c '[ "$1" = "{}" ]' _ "$GONE"
check "and removes nothing else with it" bash -c '
    grep -q "^\[lane.blitsafe\]" "$1" && grep -q "^wave = 7$" "$1"' _ "$CT/after.toml"
twice=$(PATH="$CTPATH" HAKUX_REPO_DIR="$CT/a/repo" bash "$HERE/cloud.sh" finish remediate 102 2>&1)
check "a second finish for the same unit is a no-op, not an error" \
    grep -q "no row to remove" <<< "$twice"
ct_cleanup "$CT/a"

# ------------------------------------------------- a board file that does not parse
# REFUSE, do not repair and do not overwrite. The board branch is the only
# copy the checkers read; a claim that cannot read it must not be the actor
# that replaces it.
ct_fixture "$CT/b"
git -C "$CT/b/repo" checkout -q board
printf 'wave = 7\n[lane.broken\nfiles = [\n' > "$CT/b/repo/territory.toml"
git -C "$CT/b/repo" commit -qam "fixture: a board file that does not parse"
git -C "$CT/b/repo" push -q origin board
git -C "$CT/b/repo" checkout -q master
btip=$(git -C "$CT/b/origin.git" rev-parse board)
: > "$SELFTEST_GH_LOG"
bout=$(ct_claim "$CT/b")
check "a territory.toml that does not parse is REFUSED, not written over" \
    grep -q "territory: REFUSED" <<< "$bout"
check "and the board branch does not move" bash -c '
    [ "$(git -C "$1/origin.git" rev-parse board)" = "$2" ]' _ "$CT/b" "$btip"
check "the session still starts -- a bookkeeping failure is not a dispatch failure" \
    grep -q "^systemd-run" "$SELFTEST_GH_LOG"
check "and the PR is told, so the board tick is not the silent fallback" \
    grep -q "could not write the .territory.toml. row" "$SELFTEST_GH_LOG"
ct_cleanup "$CT/b"

# ------------------------------------------------- the race with a board tick
# TWO JOBS WRITE THIS FILE NOW. The board regenerates it on a tick; this claims
# on another. There is no lock: the push is not a fast-forward if the branch
# moved, git refuses it, and the loop re-reads the branch and re-applies the
# row to the tip that actually exists. A lost update here is a lane nothing can
# see -- the defect being closed, reintroduced by the fix.
#
# The concurrent tick is a real pre-receive hook: on the FIRST push it moves
# the branch to a commit adding [lane.boardtick] and then rejects, which is
# exactly the interleaving (fetch, board tick, push) that loses an update.
ct_fixture "$CT/c"
git -C "$CT/c/repo" checkout -q board
printf '\n\n[lane.boardtick]\nissues = []\nfiles = []\nstanding = false\nnote = "written by a board tick during the claim"\n' >> "$CT/c/repo/territory.toml"
git -C "$CT/c/repo" commit -qam "board: a tick, mid-claim"
concurrent=$(git -C "$CT/c/repo" rev-parse HEAD)
git -C "$CT/c/repo" push -q origin "$concurrent:refs/heads/board-tick"
git -C "$CT/c/repo" checkout -q master
git -C "$CT/c/repo" branch -qD board
echo "$concurrent" > "$CT/c/origin.git/concurrent.sha"
cat > "$CT/c/origin.git/hooks/pre-receive" <<'EOF'
#!/usr/bin/env bash
# The board tick, landing between this claim's fetch and its push -- once.
#
# `env -u GIT_QUARANTINE_PATH` because a receive hook runs with the incoming
# objects quarantined and git then refuses EVERY ref update from inside it
# ("ref updates forbidden inside quarantine environment"): without this the
# hook rejects the push, the branch does not move, and the retry re-pushes
# the same commit successfully -- a green test of nothing at all.
d="$(git rev-parse --git-dir)"
[ -e "$d/raced" ] && exit 0
touch "$d/raced"
env -u GIT_QUARANTINE_PATH -u GIT_OBJECT_DIRECTORY -u GIT_ALTERNATE_OBJECT_DIRECTORIES \
    git update-ref refs/heads/board "$(cat "$d/concurrent.sha")" >&2
echo "pre-receive: the board branch moved under you" >&2
exit 1
EOF
chmod +x "$CT/c/origin.git/hooks/pre-receive"
: > "$SELFTEST_GH_LOG"
rout=$(ct_claim "$CT/c")
RROW=$(ct_row "$CT/c" cloud-remediate-102)
check "a push that lost the race is retried, not forced" \
    grep -q "territory: push rejected (try 1 of 3)" <<< "$rout"
# A credential, a protected branch and a failed unpack all print "[remote
# rejected]" too, so the log must carry what git actually said rather than
# only this script's guess at why.
check "and the log carries git's own message, not just 'the board moved'" \
    grep -q "git said:.*rejected" <<< "$rout"
check "the row lands anyway, on the tip the board tick left" \
    bash -c '[ "$1" != "{}" ]' _ "$RROW"
check "and the board tick's own row is still there: no lost update" \
    grep -q "^\[lane.boardtick\]" "$CT/after.toml"
check "the retry re-reads the branch rather than re-pushing the stale commit" bash -c '
    [ "$(git -C "$1/origin.git" rev-parse board^)" = "$2" ]' _ "$CT/c" "$concurrent"
ct_cleanup "$CT/c"
unset ROW RROW
