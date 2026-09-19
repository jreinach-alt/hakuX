# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# fold.sh: a board-level gate failure must not be recorded as a property of
# the PR's head.
#
# `$F/failed/$pr-$head` is permanent -- that head is never tried again. On
# 2026-09-19 the board opened a `decision-needed` issue, preflight's coverage
# gate went red for every fold, and #123, #124 and #130 were each written off
# on a head that was complete, green and innocent. The board repaired its own
# row one tick later; only the marker outlived it, and the three PRs folded
# when a person deleted the markers by hand.
#
# 91 sits after the fold-notes block and before the arms ones. SELF-CONTAINED:
# its own gh shim, its own git repository and its own $HAKUX_WORK, so it
# depends on no other fragment and on nothing of this host's -- the number is
# for the record, not for a fixture.

echo "== fold.sh: a board gate's failure is not the head's property"
FT="$T/foldtr"; mkdir -p "$FT/bin"

# ----------------------------------------------------------- the fake host
cat > "$FT/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
case "$1 $2" in
    "pr list")    [[ "$args" == *"--label fold-ready"* ]] \
                      && printf '150\t%s\t%s\tfalse\tfoldtr: a lane\n' "${FT_BRANCH:?}" "${FT_HEAD:?}" ;;
    "pr view")    echo GREEN ;;
    "pr comment") { echo "--- comment on $3"; cat "${args##*--body-file }"; } >> "${FT_LOG:?}" ;;
esac
exit 0
EOF
chmod +x "$FT/bin/gh"

# A repository for the fold to actually merge in: the real fold.sh creates a
# worktree, fetches, merges and then runs `docs/testing/preflight.sh` INSIDE
# the merged tree. So the tree carries a stand-in for preflight -- one whose
# failing gates this fragment chooses, printed in preflight.sh's own layout
# (`step()` pads the gate name to 28 columns, `bad()` prints FAILED and
# nothing else). Reading a real preflight here would mean building psh_differ
# and reaching `origin/board`; the column is the whole interface, and the
# checks at the bottom of this file are what keep the stand-in honest about it.
rm -rf "$FT/origin.git" "$FT/repo" "$FT/work"
git -c init.defaultBranch=master init -q --bare "$FT/origin.git"
git -c init.defaultBranch=master init -q "$FT/repo"
git -C "$FT/repo" config user.name selftest        # shared by its worktrees,
git -C "$FT/repo" config user.email selftest@example   # so the fold can commit
git -C "$FT/repo" remote add origin "$FT/origin.git"
git -C "$FT/repo" checkout -q -b master
mkdir -p "$FT/repo/docs/testing"
cat > "$FT/repo/docs/testing/preflight.sh" <<'EOF'
#!/usr/bin/env bash
# stand-in for preflight.sh: the same one-line-per-gate column, failing
# exactly the gates named one per line in $FOLDTR_GATES.
fail=0
for g in "psh_differ build" aci_vmstate "nv2a index" territory coverage "board files"; do
    if grep -qxF -- "$g" "${FOLDTR_GATES:-/dev/null}" 2>/dev/null; then
        printf '%-28sFAILED\n' "$g"; echo "  a gate's own output, which says FAILED"; fail=1
    else
        printf '%-28sok\n' "$g"
    fi
done
echo
[ $fail -eq 0 ] && echo "preflight passed - safe to push" \
                || echo "preflight FAILED - fix before pushing, do not spend a CI run finding out"
exit $fail
EOF
cat > "$FT/repo/docs/testing/nv2a_index.py" <<'EOF'
import sys; sys.exit(0)   # the index gate is not what this fragment measures
EOF
printf 'wave = 5\n' > "$FT/repo/docs/testing/territory.toml"
git -C "$FT/repo" add -A && git -C "$FT/repo" commit -qm "the tree a fold merges into"
git -C "$FT/repo" push -q origin master
# The lane: one innocent branch, and one that edits a board file.
git -C "$FT/repo" checkout -q -b lane/foldtr
printf 'a lane change\n' > "$FT/repo/docs/lanes-file"
git -C "$FT/repo" add -A && git -C "$FT/repo" commit -qm "foldtr: a lane change"
git -C "$FT/repo" push -q origin lane/foldtr
git -C "$FT/repo" checkout -q -b lane/foldtr-board master
printf 'wave = 4\n' > "$FT/repo/docs/testing/territory.toml"
git -C "$FT/repo" add -A && git -C "$FT/repo" commit -qm "foldtr: a lane that edits the board"
git -C "$FT/repo" push -q origin lane/foldtr-board
git -C "$FT/repo" checkout -q master

ft_reset() { rm -rf "$FT/work"; git -C "$FT/repo" worktree prune 2>/dev/null; : > "$FT/comments.log"; : > "$FT/tick.log"; }
ft_tick() {   # <branch> [failing gate]... : one tick of the REAL fold.sh
    local br=$1; shift
    if [ $# -gt 0 ]; then printf '%s\n' "$@" > "$FT/gates"; else : > "$FT/gates"; fi
    FT_BRANCH="$br" FT_HEAD="$(git -C "$FT/repo" rev-parse "$br")" FT_LOG="$FT/comments.log" \
    FOLDTR_GATES="$FT/gates" TESTS="$FT/tests" SUPPORT="$FT/support" \
    BOARD_GATE_STUCK_SECS="${FT_STUCK:-7200}" \
    PATH="$FT/bin:$PATH" HAKUX_WORK="$FT/work" HAKUX_REPO_DIR="$FT/repo" \
        bash "$HERE/fold.sh" >>"$FT/tick.log" 2>&1
}
ft_marked() {   # <branch> -> 0 when this head has been written off permanently
    [ -f "$FT/work/fold/failed/150-$(git -C "$FT/repo" rev-parse "$1")" ]
}
# A negative runs as a function, never `bash -c '! grep ... "$FT/..."'`: $FT is
# not exported, so in a child shell the path would be "/comments.log", grep
# would fail, the negation would succeed and the check could never fail.
ft_unmarked() { ! ft_marked "$1"; }
ft_unsaid()   { ! grep -q "$1" "$FT/comments.log"; }

# ------------------------------------------------- the failure being fixed
ft_reset; ft_tick lane/foldtr coverage
check "a coverage-only preflight failure does NOT write off the head" ft_unmarked lane/foldtr
check "  and the tick log says why it is being retried instead" grep -q "only the board's own gates failed" "$FT/tick.log"
ft_tick lane/foldtr coverage
check "  the head is retried on the next tick, not skipped" \
    [ "$(grep -c "only the board's own gates failed" "$FT/tick.log")" = 2 ]
check "  a transient board gate is not commented on straight away" [ ! -s "$FT/comments.log" ]
check "  and nothing is folded on it either" [ -z "$(git -C "$FT/origin.git" log --oneline -1 --grep 'fold: PR' master)" ]

# The positive control: this whole path is only reachable if the fold really
# merged and really ran preflight, so a real failure must still be recorded.
ft_reset; ft_tick lane/foldtr "nv2a index"
check "a failure in a gate the merged TREE causes still writes the marker" ft_marked lane/foldtr
check "  and still tells the lane its preflight fails" grep -q 'preflight fails on the merged tree' "$FT/comments.log"
check "  the marker names the gate, so \`fold.sh list\` can say more than 'failed'" \
    grep -q 'nv2a index' "$FT/work/fold/failed/150-$(git -C "$FT/repo" rev-parse lane/foldtr)"

ft_reset; ft_tick lane/foldtr coverage "nv2a index"
check "a MIXED failure is a real one: the board gate does not excuse the other" ft_marked lane/foldtr

# board_files prefers origin/board but falls back to the worktree copy, so for
# as long as that transition lasts a PR that edits the board files CAN fail
# these gates by itself -- and --allow-tracker has stopped asking by then.
ft_reset; ft_tick lane/foldtr-board territory
check "a PR that edits the board files is not excused by a board gate" ft_marked lane/foldtr-board

# Parking a PR in silence is the #102 failure over again, so a board gate that
# outlives the board's own repair time is said on the PR -- once.
ft_reset; ft_tick lane/foldtr coverage
FT_STUCK=0 ft_tick lane/foldtr coverage
check "a board gate red for longer than BOARD_GATE_STUCK_SECS is reported" \
    grep -q 'this is not your PR' "$FT/comments.log"
check "  the comment tells the lane its head is NOT marked failed" grep -q 'not marked failed' "$FT/comments.log"
FT_STUCK=0 ft_tick lane/foldtr coverage
check "  and it is said exactly once, however many ticks pass" \
    [ "$(grep -c '^--- comment on 150' "$FT/comments.log")" = 1 ]
check "  a head that was never marked stays unmarked through all of it" ft_unmarked lane/foldtr
check "  and a stuck board gate never says the lane must push something" ft_unsaid 'push a fix'

# --------------------------------------------- the verdict on its own merits
# `fold.sh preflight-verdict <log>` is the decision without the merge, the way
# `resolve-notes` is the resolution without the gh. Cases a fixture would
# make expensive, and one -- `board files` -- whose name invites the wrong
# answer: it is a gate about what this checkout edited, which is the lane's.
pf() {   # <failing gate>... -> board|tree, from a log in preflight's layout
    local g
    { for g in "psh_differ build" aci_vmstate "nv2a index" territory coverage "board files"; do
          if printf '%s\n' "$@" | grep -qxF -- "$g"; then printf '%-28sFAILED\n' "$g"
          else printf '%-28sok\n' "$g"; fi
      done
      echo "  an indented line of a gate's own output that says FAILED"
      echo "preflight FAILED - fix before pushing, do not spend a CI run finding out"
    } > "$FT/pf.log"
    bash "$HERE/fold.sh" preflight-verdict "$FT/pf.log"
}
check "coverage alone is the board's"                  [ "$(pf coverage)" = board ]
check "territory alone is the board's"                 [ "$(pf territory)" = board ]
check "both board gates together are still the board's" [ "$(pf coverage territory)" = board ]
check "a board gate beside a tree gate is the tree's"  [ "$(pf coverage 'nv2a index')" = tree ]
check "\`board files\` is the LANE's gate, whatever its name" [ "$(pf 'board files')" = tree ]
check "psh_differ alone is the tree's"                 [ "$(pf 'psh_differ build')" = tree ]
: > "$FT/pf.log"
check "an empty log names no gate, so it is not called transient" \
    [ "$(bash "$HERE/fold.sh" preflight-verdict "$FT/pf.log")" = tree ]
echo "preflight FAILED - fix before pushing, do not spend a CI run finding out" > "$FT/pf.log"
check "a log with only the closing prose is not a gate report either" \
    [ "$(bash "$HERE/fold.sh" preflight-verdict "$FT/pf.log")" = tree ]
check "a missing log is the tree's too, not a free pass" \
    [ "$(bash "$HERE/fold.sh" preflight-verdict "$FT/nonexistent.log")" = tree ]

# --------------------------------------- the interface the above depends on
# All of it keys on preflight.sh's gate column and on two gate NAMES. Both are
# in a file this lane does not own, so a rename there would silently turn a
# board gate into a tree gate and start writing off innocent heads again.
PF="$HERE/../preflight.sh"
check "preflight.sh still prints FAILED as the whole rest of a gate's line" \
    grep -qE 'bad\(\)[[:space:]]*\{[[:space:]]*echo "FAILED"' "$PF"
check "preflight.sh still pads the gate name into a column before it" \
    grep -qF "step() { printf '%-28s'" "$PF"
for g in coverage territory; do
    check "  preflight.sh still has a gate named '$g'" grep -qF "step \"$g\"" "$PF"
done
check "  and still has 'board files', which must NOT be treated as the board's" \
    grep -qF 'step "board files"' "$PF"
