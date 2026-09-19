# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# fold.sh: a fold that stops must reach the PR, not only the host's log.
# Landed on master as an insert into selftest.sh (#127, lane/foldci); carried
# here unchanged when that fold met this split.
#
# 85 because on master this block sat between the labels block and the
# fold-notes block, and the numbering keeps that position. Self-contained:
# its own gh shim under $T/foldci and its own HAKUX_WORK, so it depends on
# no other fragment -- the number is for the record, not for a fixture.

echo "== fold.sh: a fold that stops must reach the PR, not only the host's log"
# Until 2026-09-18 only RED commented. A head with no CI run at all mapped to
# NONE and then waited forever in silence -- #102 sat a full day that way, its
# only record a line in $WORK/logs/fold/tick.log that no lane can read. These
# run the REAL fold.sh against a gh shim of their own (the shared shim above
# answers every `pr view` GREEN, which is the one state that must not stop) and
# read back what it posted. `rm -rf "$FC/work"` between scenarios is what makes
# each one a fresh head's worth of history.
FC="$T/foldci"; mkdir -p "$FC/bin"
cat > "$FC/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
# A candidate row is number, branch, head, isDraft, labels, title -- title
# last, because it is the only free-text field.
case "$1 $2" in
    "pr list")    printf '102\tlane/foldci\t%s\tfalse\tfold-ready\tfold: a lane\n' "${FC_HEAD:?}" ;;
    "pr view")    echo "${FC_CI:?}" ;;
    "pr comment") { echo "--- comment on $3"; cat "${args##*--body-file }"; } >> "${FC_LOG:?}" ;;
esac
exit 0
EOF
chmod +x "$FC/bin/gh"
fold_tick() {   # <state> [head]: one tick of the real fold.sh against that shim
    FC_CI=$1 FC_HEAD="${2:-headaaaaaaaa1111}" FC_LOG="$FC/comments.log" \
    PENDING_STUCK_SECS="${FC_STUCK:-7200}" PATH="$FC/bin:$PATH" HAKUX_WORK="$FC/work" \
        bash "$HERE/fold.sh" >/dev/null 2>&1
}
ncomments() { grep -c '^--- comment on 102' "$FC/comments.log" 2>/dev/null || echo 0; }
# A negative runs as a function, not `bash -c '! grep ... "$FC/..."'`: $FC is not
# exported, so in a child shell that path is "/comments.log", grep fails, the
# negation succeeds and the check can never fail. One of these was written that
# way and a deliberate mutant caught it.
unsaid() { ! grep -q "$1" "$FC/comments.log"; }

rm -rf "$FC/work"; : > "$FC/comments.log"
fold_tick NONE; fold_tick NONE
check "a head with NO CI run at all is reported on the PR" grep -q 'no CI run exists' "$FC/comments.log"
check "  the comment names [skip ci] in the head commit as the cause" grep -q 'skip ci' "$FC/comments.log"
check "  it warns not to quote the marker in the unblocking commit" grep -q 'not quote the marker' "$FC/comments.log"
check "  it rules out the path-filter theory instead of leaving it open" grep -q 'path-filter' "$FC/comments.log"
check "  and it is said exactly once, however many ticks pass" [ "$(ncomments)" = 1 ]
check "NONE still does not fold: no merge worktree is ever created" [ ! -e "$FC/work/fold-wt" ]

rm -rf "$FC/work"; : > "$FC/comments.log"
fold_tick RED; fold_tick RED
check "RED is unchanged: one comment per head, same words" [ "$(grep -c 'CI is red' "$FC/comments.log")" = 1 ]

rm -rf "$FC/work"; : > "$FC/comments.log"
fold_tick NONE; fold_tick RED
# The marker is a ledger, not a boolean. Reusing it as a boolean would have
# moved the silence one state over: the NONE comment would eat the RED one.
check "a RED that follows a NONE on the same head is still reported" grep -q 'CI is red' "$FC/comments.log"

rm -rf "$FC/work"; : > "$FC/comments.log"
mkdir -p "$FC/work/fold/failed"; : > "$FC/work/fold/failed/102-headaaaaaaaa1111-ci"
fold_tick RED
check "an EMPTY marker, all the pre-09-18 job ever wrote, still means RED was said" unsaid 'CI is red'

rm -rf "$FC/work"; : > "$FC/comments.log"
fold_tick PENDING; fold_tick PENDING
check "a run still in flight is not commented on (ticks are 30m; the build is long)" [ ! -s "$FC/comments.log" ]
FC_STUCK=0 fold_tick PENDING
check "a pending older than PENDING_STUCK_SECS is reported as stuck" grep -q 'has been \*\*pending\*\*' "$FC/comments.log"
FC_STUCK=0 fold_tick PENDING
check "  and that too is said exactly once" [ "$(ncomments)" = 1 ]
