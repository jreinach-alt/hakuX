# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# cloud.sh: the audit path cannot hold a branch a lane worktree already holds.
#
# Reads cloud.sh's own text -- a shim cannot reproduce git's refusal against
# the real lane worktrees. No shared state.

echo "== cloud.sh: the audit path cannot hold a branch a lane worktree already holds"
# Every local lane keeps its branch checked out under $WORK/wt, and git refuses
# one branch in two worktrees, so `worktree add -B "$branch"` failed for every
# PR a local lane had opened -- exit 5, before the first say(): no tick log, no
# comment, no label. A shim cannot reproduce git's refusal against the real
# lane worktrees, so this pins the mechanism.
check "the audit worktree is detached, not -B <branch>" \
    grep -q 'worktree add --quiet --detach "$wt" "origin/$branch"' "$HERE/cloud.sh"
check "the audit brief tells the session to push HEAD:<branch>" \
    grep -q 'git push origin HEAD:\$branch' "$HERE/cloud.sh"
check "no claim path exits without saying why" bash -c '! grep -nE "\|\| exit [0-9]" "$HERE/cloud.sh"'
