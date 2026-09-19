# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# fold.sh: a PR labelled `regressed` is not folded, and only the owner can
# say otherwise.
#
# On 2026-09-19 PR #102 folded as `3d072c6ea6` carrying `regressed` -- its
# failing prediction was `issue88-vk-same-offset-colour-wins.json`,
# `Color_zeta_overlap/Swap 165,447 -> 304,750`, and the label had been set
# twenty minutes earlier precisely to stop the fold. `grep -c regressed
# fold.sh` was 0: the rule lived in `roles/board.md`, which is prose, and the
# job it advises is a script. What these checks pin is that the gate is now in
# the script, that it costs no extra call, that it removes nothing, and that
# the only way past it names an issue.
#
# 86 sits with the other fold-gate fragment (85). SELF-CONTAINED: its own gh
# shim, its own git repository and its own $HAKUX_WORK, so it depends on no
# other fragment and on nothing of this host's.

echo "== fold.sh: a regressed PR is not folded unless the owner accepted it"
FR="$T/foldreg"; mkdir -p "$FR/bin"

# ----------------------------------------------------------- the fake host
# The labels are the variable under test, so they come from the environment
# and ride the candidate `pr list` -- which is the point: the gate must read
# them from the call the job already makes. The `api .../labels` answer is
# what `gh-label.sh`'s label_rm probes before a DELETE, so this shim is also
# what makes "fold-ready was NOT removed" a check with a positive control.
cat > "$FR/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
echo "$args" >> "${FR_GH_LOG:?}"
# A candidate row is number, branch, head, isDraft, labels, title -- title
# last, because it is the only free-text field.
case "$1 $2" in
    "pr list")    [[ "$args" == *"--label fold-ready"* ]] \
                      && printf '160\tlane/foldreg\t%s\tfalse\t%s\tfoldreg: a lane\n' "${FR_HEAD:?}" "${FR_LABELS-}" ;;
    "pr view")    echo GREEN ;;
    "pr comment") { echo "--- comment on $3"; cat "${args##*--body-file }"; } >> "${FR_LOG:?}" ;;
    "api "*)      # one label per line, as `gh api .../labels --jq .[].name` gives
                  # them. The first version of this printed the csv as a single
                  # line: label_rm's `grep -Fxq` then matched nothing, no DELETE
                  # was ever issued for a multi-label PR, and "fold-ready was
                  # kept" was a check that could not fail.
                  [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && printf '%s\n' "${FR_LABELS-}" | tr ',' '\n' ;;
esac
exit 0
EOF
chmod +x "$FR/bin/gh"

# A repository the fold can really merge and really push, so that "it did not
# fold" is measured on the pushed master and not on the absence of a log line.
# preflight and the index are stand-ins: what fails here is chosen by this
# fragment, and neither is what it measures (91 owns the preflight column).
rm -rf "$FR/origin.git" "$FR/repo" "$FR/work"
git -c init.defaultBranch=master init -q --bare "$FR/origin.git"
git -c init.defaultBranch=master init -q "$FR/repo"
git -C "$FR/repo" config user.name selftest
git -C "$FR/repo" config user.email selftest@example
git -C "$FR/repo" remote add origin "$FR/origin.git"
git -C "$FR/repo" checkout -q -b master
mkdir -p "$FR/repo/docs/testing"
printf '#!/usr/bin/env bash\nexit 0\n' > "$FR/repo/docs/testing/preflight.sh"
printf 'import sys; sys.exit(0)\n' > "$FR/repo/docs/testing/nv2a_index.py"
git -C "$FR/repo" add -A && git -C "$FR/repo" commit -qm "the tree a fold merges into"
git -C "$FR/repo" push -q origin master
git -C "$FR/repo" checkout -q -b lane/foldreg
printf 'a lane change\n' > "$FR/repo/docs/lanes-file"
git -C "$FR/repo" add -A && git -C "$FR/repo" commit -qm "foldreg: a lane change"
git -C "$FR/repo" push -q origin lane/foldreg
git -C "$FR/repo" checkout -q master

fr_reset() {   # a fresh host AND a fresh master: a fold pushes, so it must be undone
    rm -rf "$FR/work"; git -C "$FR/repo" worktree prune 2>/dev/null
    git -C "$FR/repo" push -q -f origin master lane/foldreg
    : > "$FR/comments.log"; : > "$FR/gh.log"; : > "$FR/tick.log"
}
fr_tick() {   # <labels csv> [mode] : one tick of the REAL fold.sh
    FR_LABELS="$1" FR_LOG="$FR/comments.log" FR_GH_LOG="$FR/gh.log" \
    FR_HEAD="$(git -C "$FR/repo" rev-parse lane/foldreg)" \
    TESTS="$FR/tests" SUPPORT="$FR/support" \
    PATH="$FR/bin:$PATH" HAKUX_WORK="$FR/work" HAKUX_REPO_DIR="$FR/repo" \
        bash "$HERE/fold.sh" "${2:-run}" >>"$FR/tick.log" 2>&1
}
# Every negative is a function, never `bash -c '! grep ... "$FR/..."'`: $FR is
# not exported, so in a child shell the path would be "/comments.log", grep
# would fail, the negation would succeed and the check could never fail.
fr_folded()   { [ -n "$(git -C "$FR/origin.git" log --oneline --grep 'fold: PR' master)" ]; }
fr_unfolded() { ! fr_folded; }
fr_said()     { grep -q "$1" "$FR/comments.log"; }
fr_unsaid()   { ! grep -q "$1" "$FR/comments.log"; }
fr_ncomments() { grep -c '^--- comment on 160' "$FR/comments.log" 2>/dev/null || echo 0; }
fr_two_states() {   # two comments, and they are the two different ones
    [ "$(fr_ncomments)" = 2 ] \
        && [ "$(grep -c 'labelled .regressed.' "$FR/comments.log")" = 1 ] \
        && [ "$(grep -c 'names no issue' "$FR/comments.log")" = 1 ]
}
fr_dropped_foldready() { grep -q -- '-X DELETE.*labels/fold-ready' "$FR/gh.log"; }
fr_kept_foldready()    { ! fr_dropped_foldready; }
fr_called_pr_view()    { grep -q '^pr view' "$FR/gh.log"; }
fr_no_pr_view()        { ! fr_called_pr_view; }

# ------------------------------------------------- the failure being fixed
fr_reset; fr_tick "fold-ready,regressed"
check "a PR labelled regressed is NOT folded" fr_unfolded
check "  the tick log says why, naming the label" grep -q 'labelled regressed' "$FR/tick.log"
check "  and the PR is told, not just the host's log" fr_said 'labelled .regressed.'
check "  the comment says the fold retries, so nothing needs re-applying" fr_said 'fold-ready. label is kept'
check "  it names the owner's way through, with the issue in the spelling" fr_said 'regression-accepted:<issue>'
check "  it does not tell the lane to remove the label by hand" fr_said 'do not remove it by hand'
check "fold-ready is KEPT: a gate that strips it would need a person to put it back" fr_kept_foldready
check "the head is not written off permanently either" [ ! -f "$FR/work/fold/failed/160-$(git -C "$FR/repo" rev-parse lane/foldreg)" ]
check "the gate costs no extra call: the CI rollup is never fetched for it" fr_no_pr_view
fr_tick "fold-ready,regressed"
check "  and it is said exactly once, however many ticks pass" [ "$(fr_ncomments)" = 1 ]
check "  still not folded on the second tick" fr_unfolded

# The positive control. Every check above is about a fold NOT happening, and
# all of them would pass against a fold.sh that folds nothing at all -- so
# this fixture must be able to fold, and a PR with no verdict at all must
# still go through: most PRs carry no prediction, and `verified` is not a
# requirement to fold.
fr_reset; fr_tick "fold-ready"
check "a PR with no arms verdict at all still folds (verified is NOT required)" fr_folded
check "  and the fold really removed fold-ready, so the DELETE check above can fail" fr_dropped_foldready
check "  a plain fold says nothing about regressions" fr_unsaid 'regression'
fr_reset; fr_tick "fold-ready,verified"
check "a verified PR folds" fr_folded
fr_reset; fr_tick "fold-ready,regression-accepted:91"
check "an override on a PR with no verdict folds it, quietly" fr_folded
check "  and claims no regression the PR has no record of" fr_unsaid 'accepted on #91'

# ------------------------------------------------------------ the override
fr_reset; fr_tick "fold-ready,regressed,regression-accepted:91"
check "an owner-accepted regression folds" fr_folded
check "  and the fold comment names the issue the trade is argued on" fr_said 'accepted on #91'
check "  it says the failing verdict still stands as measured" fr_said 'stands as measured'
check "  the tick log records that it folded on the override" grep -q 'regression-accepted:#91' "$FR/tick.log"
fr_reset; fr_tick "fold-ready,regressed,regression-accepted:#91"
check "the issue may be written with a # too" fr_folded

# An override is an assertion, and the issue is its argument. Without one the
# label says only that somebody wanted this folded.
fr_reset; fr_tick "fold-ready,regressed,regression-accepted"
check "a bare regression-accepted does NOT fold" fr_unfolded
check "  and the comment is about the spelling, not the regression again" fr_said 'names no issue'
check "  it gives the exact label to create" fr_said 'regression-accepted:91'
check "  fold-ready survives that too" fr_kept_foldready
for bad in "regression-accepted:" "regression-accepted:none" "regression-accepted:91x" "regression-accepted-later"; do
    fr_reset; fr_tick "fold-ready,regressed,$bad"
    check "\`$bad\` is not an override" fr_unfolded
done

# The ledger, not a boolean: an owner who adds a malformed override after the
# first comment has ACTED, and a job that has already spoken once about this
# head must still answer them -- or the silence just moves one state over.
fr_reset
fr_tick "fold-ready,regressed"
fr_tick "fold-ready,regressed,regression-accepted"
check "a malformed override added after the first comment is answered" fr_said 'names no issue'
check "  and both comments are on the PR, one per state" fr_two_states
fr_tick "fold-ready,regressed,regression-accepted"
check "  the spelling is said once as well" [ "$(fr_ncomments)" = 2 ]

# The label is matched whole. `unregressed` and `regression-accepted-later`
# are not this state machine's words, and a substring match would make the
# gate fire on a label nobody meant as one.
fr_reset; fr_tick "fold-ready,unregressed,not-regressed-either"
check "a label that merely CONTAINS the word is not the verdict" fr_folded

# ------------------------------------------------------------- list mode
# `fold.sh list` must say why a PR waits -- that is what it is for -- without
# posting anything: the state it would report is on the PR already, as the
# label it is reading.
fr_reset; fr_tick "fold-ready,regressed" list
check "\`fold.sh list\` reports the regression instead of WOULD FOLD" grep -q 'REGRESSED' "$FR/tick.log"
check "  and does not say it would fold it" bash -c '! grep -q "WOULD FOLD" "$1"' _ "$FR/tick.log"
check "  list stays read-only: it folds nothing" fr_unfolded
check "  and comments nothing" [ ! -s "$FR/comments.log" ]
fr_reset; fr_tick "fold-ready,regressed,regression-accepted:91" list
check "an accepted one WOULD fold, and the line says on whose issue" grep -q 'WOULD FOLD (regression accepted on #91)' "$FR/tick.log"
check "  but list folded nothing" fr_unfolded

# ----------------------------------- the interfaces this gate depends on
# The label names are arms.sh's and the owner's; this gate only reads them.
check "arms.sh is still the only writer of the regressed label" \
    grep -q 'label_add "$pr" regressed' "$HERE/arms.sh"
# The jobs' own scripts, not `-r` over $HERE: this very check contains both
# words, and the first draft of it failed against a correct tree by matching
# itself. It also anchors on the CALL -- fold.sh's comment to the owner does
# quote `gh-label.sh add <pr> regression-accepted:91`, which is the owner
# being told how, and is the opposite of a job doing it.
check "no job sets a regression-accepted label (it is the owner's alone)" \
    bash -c '! grep -qE "label_add[[:space:]].*regression-accepted" "$@"' _ "$HERE"/*.sh
check "ensure-labels.sh creates no regression-accepted label to click by mistake" \
    bash -c '! grep -qE "^mk regression-accepted" "$1"' _ "$HERE/ensure-labels.sh"
check "  but it does document who creates one, and how" \
    grep -q 'regression-accepted:91' "$HERE/ensure-labels.sh"
check "roles/board.md says the gate is in the job now, not in the role file" \
    grep -q 'now a gate in `fold.sh`' "$HERE/roles/board.md"
check "  and that the owner alone accepts a regression" \
    grep -q 'never yours' "$HERE/roles/board.md"
