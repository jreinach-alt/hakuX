#!/usr/bin/env bash
# Each mutant is one edit to a COPY of board.sh in a scratch jobs dir; the
# fragment must go red on every one. Prints one line per mutant.
set -u
LANE="$(cd "$(dirname "$0")" && pwd)"; JOBS="$(cd "$LANE/../../testing/jobs" && pwd)"
S=$(mktemp -d "${TMPDIR:-/tmp}/boardprio-mut.XXXXXX")
mutate() {   # <name> <old> <new>
    mkdir -p "$S/$1/testing/jobs"
    cp "$JOBS/board.sh" "$JOBS/localtime.sh" "$JOBS/window.sh" "$S/$1/testing/jobs/"
    cp "$JOBS/../board_files.py" "$S/$1/testing/"
    python3 -c 'import sys
p, old, new = sys.argv[1:]
s = open(p).read()
assert s.count(old) == 1, "mutant anchor not found exactly once: %r" % old
open(p, "w").write(s.replace(old, new))' "$S/$1/testing/jobs/board.sh" "$2" "$3" || { echo "$1: MUTANT DID NOT APPLY"; return; }
    if out=$(bash "$LANE/run-fragment.sh" "$S/$1/testing/jobs" 2>&1); then
        echo "$1: GREEN (the fragment cannot see this mutant)"
    else
        echo "$1: red -- $(grep -c '  FAIL' <<< "$out") failed: $(grep '  FAIL' <<< "$out" | head -1 | sed 's/^ *FAIL //')"
    fi
}
mutate ascending   'key=lambda t: t[0])' 'key=lambda t: (t[0][0], -t[0][1], t[0][2]))'
mutate no-game     'if row.get("game_visible") is True:' 'if False:'
mutate onestep-1to1 'score = px + one // 4' 'score = px + one'
mutate no-join     'ranked = sorted((rank(r) + (r, text) for r, text in out), key=lambda t: t[0])' 'ranked = [rank(r) + (r, text) for r, text in out]'
# The tie-breaks: drop the number (stable sort keeps gh's order inside a tie),
# and newest first. The fixture puts each tie's right answer in the middle.
mutate tie-gh-order 'key=lambda t: t[0])' 'key=lambda t: t[0][:2])'
mutate tie-newest   'key=lambda t: t[0])' 'key=lambda t: (t[0][0], t[0][1], -t[0][2]))'
rm -rf "$S"
