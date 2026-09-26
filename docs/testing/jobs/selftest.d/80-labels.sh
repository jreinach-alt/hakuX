# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# labels: the state machine's only actuator.
#
# Reads the gh shim's log, and truncates it as it goes, so no fragment after
# this one may depend on what $SELFTEST_GH_LOG held before it.

echo "== labels: the state machine's only actuator"
# `gh pr edit --add-label` exits 1 on gh 2.45 (Projects-classic project cards)
# and applies nothing; every job called it with stderr discarded, so for a day
# no PR label the harness set ever took -- fold-ready, folded, needs-rebase,
# verified, regressed, claimed:cloud. The shim cannot reproduce a real gh's
# failure, so this pins the MECHANISM: no job may reach for that call, and the
# helper must go through the REST endpoint that works for issues and PRs alike.
check "no job script labels through 'gh pr edit'" bash -c '! grep -rn "^[^#]*gh pr edit[^|]*--\(add\|remove\)-label" "$HERE"/*.sh'
: > "$SELFTEST_GH_LOG"
( . "$HERE/gh-label.sh"; label_add 102 verified folded ) >/dev/null 2>&1
check "label_add posts to the REST labels endpoint" grep -q 'api -X POST repos/example/hakux/issues/102/labels' "$SELFTEST_GH_LOG"
check "label_add sends every label in one call" grep -q 'labels\[\]=verified.*labels\[\]=folded' "$SELFTEST_GH_LOG"
: > "$SELFTEST_GH_LOG"
( export SELFTEST_LABELS="fold-ready"; . "$HERE/gh-label.sh"; label_rm 102 fold-ready ) >/dev/null 2>&1
check "label_rm deletes a label that is present" grep -q 'api -X DELETE repos/example/hakux/issues/102/labels/fold-ready' "$SELFTEST_GH_LOG"
: > "$SELFTEST_GH_LOG"
( export SELFTEST_LABELS="fold-ready"; . "$HERE/gh-label.sh"; label_rm 102 regressed ) >/dev/null 2>&1
check "label_rm does not DELETE a label that is absent (a 404 is not a failure)" bash -c '! grep -q "DELETE" "$SELFTEST_GH_LOG"'
check "label_rm reports success when there was nothing to remove" bash -c '( export SELFTEST_LABELS="fold-ready"; . "$HERE/gh-label.sh"; label_rm 102 regressed ) >/dev/null 2>&1'
