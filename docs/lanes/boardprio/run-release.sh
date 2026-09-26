#!/usr/bin/env bash
# Run selftest.d/97-board-release.sh alone, against the testing dir given
# (default: this tree's). The fragment reads board.sh from $HERE and the
# Python tools from $TESTING, so a mutant or the old master copy is a whole
# scratch testing/ tree. Used for the mutants and the falsification run in
# NOTES.md; the gate of record is still docs/testing/jobs/selftest.sh.
#
#   run-release.sh [testing-dir]
set -u
LANE="$(cd "$(dirname "$0")" && pwd)"
FRAG="$LANE/../../testing/jobs/selftest.d/97-board-release.sh"
TESTING="$(cd "${1:-$LANE/../../testing}" && pwd)"; export TESTING
export HERE="$TESTING/jobs"
T=$(mktemp -d "${TMPDIR:-/tmp}/boardrelease.XXXXXX")
export HAKUX_WORK="$T/work"; mkdir -p "$HAKUX_WORK"
export DISPATCH_DIR="$T/dispatch"; mkdir -p "$DISPATCH_DIR/fleet"
pass=0; fail=0
ok()   { echo "  ok   $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL $*"; fail=$((fail+1)); }
check() { local msg=$1; shift; if "$@" >/dev/null 2>&1; then ok "$msg"; else bad "$msg"; fi; }
. "$FRAG"
echo "fragment: $pass passed, $fail failed"
rm -rf "$T"
[ "$fail" = 0 ]
