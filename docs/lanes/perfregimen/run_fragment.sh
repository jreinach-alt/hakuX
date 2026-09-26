#!/usr/bin/env bash
# Source one selftest.d fragment on its own, with ok/bad and $T/$TESTING, the
# way ../../testing/jobs/selftest.sh does. run_fragment.sh <fragment>
HERE="$(cd "$(dirname "$0")/../../testing/jobs" && pwd)"
TESTING="$(dirname "$HERE")"
T="$(mktemp -d "${TMPDIR:-/tmp}/perfreg-frag.XXXXXX")"
pass=0; fail=0
ok()   { echo "  ok   $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL $*"; fail=$((fail+1)); }
. "$1"
echo "fragment: $pass passed, $fail failed ($T)"
[ "$fail" -eq 0 ]
