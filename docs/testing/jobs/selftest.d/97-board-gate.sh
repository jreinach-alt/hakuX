# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# board.sh's positive gate: the tick wakes on capacity-and-work and on a ready
# PR with no state label, not only on fleet.py / check_coverage.py FAIL lines.
# Written as an append to selftest.sh (#124, lane/boardgate); carried here
# unchanged when that PR met the split in #136.
#
# 97 because it was appended after the fleet-registry block on that branch.
# Every check greps the OUTPUT, never the exit status alone: half the cases
# expect "no trigger", and the pre-#124 board.sh (no `gate` argument) also
# exits non-zero, so an exit-code check is green against the file replaced.
#
# Builds its own gh shim ($BG) and limits.env; depends on no other fragment.
# It truncates $HAKUX_WORK/limits.env on the way out.

echo "== board.sh: the positive gate, because both of the old gates were error reports"
# board.sh's gate read fleet.py's FAIL lines and check_coverage.py's rows, and
# NEITHER can say "there is capacity and there is work". So six consecutive
# ticks on 2026-09-20 (03:25 to 05:10Z) logged `nothing actionable` with 29
# issues open, 0 labelled dispatchable, 0 lanes running against LANE_MAX=4 and
# both handhelds idle -- and this job is the only actor that may label an issue
# dispatchable or call lane.sh start, so nothing else could break the loop.
#
# `board.sh gate` runs the positive half alone and shares its predicate
# (nothing_actionable) with the tick, so what is checked here is what the tick
# decides. The shared gh/systemctl shims cannot drive it -- this needs issues
# and PRs with chosen labels, and a chosen lane count -- so this block brings
# its own two shims on PATH ahead of them and leaves the shared ones alone.
#
# EVERY CHECK BELOW ASSERTS ON THE OUTPUT, not only on the exit status. Half of
# these cases expect "no trigger", and a board.sh that cannot answer at all
# also exits non-zero: an exit-code-only check would pass against the very file
# this replaces.
BG="$T/boardgate"; mkdir -p "$BG/bin"
cat > "$BG/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$1 $2" in
    "auth status") [ -n "${BG_NO_GH:-}" ] && exit 1; exit 0 ;;
    "issue list")  cat "${BG_ISSUES:-/dev/null}" ;;
    "pr list")     cat "${BG_PRS:-/dev/null}" ;;
esac
exit 0
EOF
cat > "$BG/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *list-units*hakux-lane*)
        n=${BG_LANES:-0}
        for ((i=0; i<n; i++)); do echo "hakux-lane-$i.service loaded active running lane $i"; done ;;
esac
exit 0
EOF
chmod +x "$BG/bin/"*
# One open issue a lane may be started on (#120), one already held by a lane
# (#121), and one carrying only labels that bar nothing (#122) -- an over-broad
# skip list starves the fleet just as thoroughly as no trigger at all.
cat > "$BG/issues.json" <<'EOF'
[{"number":120,"title":"nv2a: blend surface diverges","labels":[]},
 {"number":121,"title":"already held","labels":[{"name":"lane:foo"}]},
 {"number":122,"title":"free and labelled","labels":[{"name":"harness"},{"name":"dispatchable"},{"name":"verified"}]}]
EOF
# Every reason an open issue is NOT startable, one row each. If any single one
# leaks through, the gate wakes a model tick every twenty minutes forever --
# which is this defect with its sign flipped.
cat > "$BG/barred.json" <<'EOF'
[{"number":1,"title":"a","labels":[{"name":"lane:x"}]},
 {"number":2,"title":"b","labels":[{"name":"claimed:cloud"}]},
 {"number":3,"title":"c","labels":[{"name":"blocked:needs-owner"}]},
 {"number":4,"title":"d","labels":[{"name":"decision-needed"}]},
 {"number":5,"title":"e","labels":[{"name":"upstream"}]},
 {"number":6,"title":"f","labels":[{"name":"unmodellable"}]},
 {"number":7,"title":"g","labels":[{"name":"xbox-hardware"}]},
 {"number":8,"title":"h","labels":[{"name":"harness-status"}]}]
EOF
# #101 and #102 are the two that went ready at 04:36Z and 04:38Z and were
# missed; #102 also shows that an arms verdict is not a state. #103 is still
# working, #104 already has its state, #105 is waiting on its own lane.
cat > "$BG/prs.json" <<'EOF'
[{"number":101,"title":"lane/one","isDraft":false,"labels":[]},
 {"number":102,"title":"lane/two","isDraft":false,"labels":[{"name":"verified"}]},
 {"number":103,"title":"lane/three","isDraft":true,"labels":[]},
 {"number":104,"title":"lane/four","isDraft":false,"labels":[{"name":"needs-audit-1"}]},
 {"number":105,"title":"lane/five","isDraft":false,"labels":[{"name":"needs-rebase"}]}]
EOF
echo '[]' > "$BG/none.json"
# HAKUX_REPO_DIR is pinned to a directory that does not exist, which pins the
# claim that the gate needs no tree: it must answer from gh and arithmetic
# alone, before board.sh reaches the board worktree. It also makes the
# replace-with-origin/master falsification run safe -- the old board.sh, which
# has no `gate` argument at all, falls through to that worktree setup, cannot
# fetch, and dies with "cannot create" instead of running a real board tick and
# spending a model session.
bgate() {   # <issues.json> <prs.json> <lanes> [limits.env contents]
    printf '%s' "${4:-}" > "$HAKUX_WORK/limits.env"
    BG_ISSUES="$BG/$1" BG_PRS="$BG/$2" BG_LANES="$3" BG_NO_GH="${BG_NO_GH:-}" \
        HAKUX_REPO_DIR="$BG/no-such-repo" PATH="$BG/bin:$PATH" \
        bash "$HERE/board.sh" gate 2>&1
}
gate_says()  { local w=$1 p=$2; shift 2; local o; o=$(bgate "$@"); local r=$?; [ "$r" = "$w" ] && grep -q -- "$p" <<< "$o"; }
gate_omits() { local w=$1 p=$2; shift 2; local o; o=$(bgate "$@"); local r=$?; [ "$r" = "$w" ] && ! grep -q -- "$p" <<< "$o"; }

check "capacity and startable work wake the tick, naming the issue" \
    gate_says 0 '#120' issues.json none.json 0
check "the gate says how much room there is under the cap" \
    gate_says 0 '0/2 lanes running' issues.json none.json 0
check "an issue already held by a lane is not startable" \
    gate_omits 0 '#121' issues.json none.json 0
check "labels that bar nothing leave an issue startable" \
    gate_says 0 '#122' issues.json none.json 0

check "every barred issue is excluded, so the gate stays quiet" \
    gate_says 1 'no positive trigger' barred.json none.json 0
check "startable work at LANE_MAX does NOT wake the tick" \
    gate_says 1 'no positive trigger' issues.json none.json 2

# LANE_MAX is read, not hardcoded: raise it in limits.env and the same two
# running lanes now leave room. It is 4 on the host, not 2.
check "LANE_MAX is read from \$WORK/limits.env, not hardcoded" \
    gate_says 0 '2/3 lanes running' issues.json none.json 2 'LANE_MAX=3'
check "and the gate is quiet again once that raised cap is full" \
    gate_says 1 'no positive trigger' issues.json none.json 3 'LANE_MAX=3'

check "a ready PR with no state label wakes the tick even at the lane cap" \
    gate_says 0 '#101' none.json prs.json 9
check "an arms verdict is not a state label, so #102 is still the board's" \
    gate_says 0 '#102' none.json prs.json 9
check "a draft PR is not the board's to label" \
    gate_omits 0 '#103' none.json prs.json 9
check "a PR that already has its state label is not re-reported" \
    gate_omits 0 '#104' none.json prs.json 9
check "needs-rebase is a state, so a PR waiting on its lane stays quiet" \
    gate_omits 0 '#105' none.json prs.json 9

# Blind, not loud. A gh outage that woke a model tick every twenty minutes
# would cost more than the idleness this gate was written to end -- but it must
# not read as health either, or the next six quiet ticks are unexplained again.
export BG_NO_GH=1
out=$(bgate issues.json prs.json 0); rc=$?
unset BG_NO_GH
check "no usable gh fails QUIET, and says it went blind rather than healthy" \
    bash -c '[ "$2" -eq 1 ] && grep -q "no positive trigger" <<< "$1" && grep -q "no usable gh" <<< "$1"' _ "$out" "$rc"
: > "$HAKUX_WORK/limits.env"

