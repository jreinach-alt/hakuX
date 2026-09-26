#!/usr/bin/env bash
# Run selftest.d/97-board-priority.sh alone, against the jobs dir given
# (default: this tree's). Used for the mutants and the falsification run in
# NOTES.md; the gate of record is still docs/testing/jobs/selftest.sh.
#
#   run-fragment.sh [jobs-dir] [fragment]
set -u
LANE="$(cd "$(dirname "$0")" && pwd)"
export HERE="${1:-$LANE/../../testing/jobs}"
HERE="$(cd "$HERE" && pwd)"; TESTING="$(dirname "$HERE")"
FRAG="${2:-$LANE/../../testing/jobs/selftest.d/97-board-priority.sh}"
T=$(mktemp -d "${TMPDIR:-/tmp}/boardprio.XXXXXX")
export HAKUX_WORK="$T/work"; mkdir -p "$HAKUX_WORK"
pass=0; fail=0
ok()   { echo "  ok   $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL $*"; fail=$((fail+1)); }
check() { local msg=$1; shift; if "$@" >/dev/null 2>&1; then ok "$msg"; else bad "$msg"; fi; }
. "$FRAG"
echo "fragment: $pass passed, $fail failed"
rm -rf "$T"
[ "$fail" = 0 ]
