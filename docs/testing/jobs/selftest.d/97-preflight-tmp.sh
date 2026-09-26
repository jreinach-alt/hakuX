# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# $REPO, ok/bad/check. Not executable, no shebang, no exit.
#
# Two preflights running at once must each read their own logs
# (dispatch-hardening defect 26).
#
# preflight.sh wrote its logs to fixed /tmp/preflight-* paths, and the fold job
# and every lane run it, often in the same minute. The fold refused PR #367
# twice with "psh_differ report ... produced no report" on a sha that passes
# when run alone: a second run's `>/tmp/preflight-differ.log` truncated the
# report the first had just written, before the first read it.
#
# The fixture is exact, not a race. Each tree is a stub repository around the
# REAL preflight.sh, with every gate stubbed to pass. A's psh-differ prints
# `TOTAL A`, and B's preflight starts only then; A's waits until B's has
# started, and B's waits until A's preflight has finished before printing
# `TOTAL B`. So B's redirect opens its report after A wrote its own and
# before A reads it. The mutant is the same preflight.sh with
# the per-run directory replaced by one fixed directory, which is the old code
# with /tmp/preflight- renamed; it must fail A with "produced no report".

echo "== preflight: two concurrent runs each read their own report"

PT="$T/pftmp"; rm -rf "$PT"; mkdir -p "$PT/sync" "$PT/tmp" "$PT/tests/.git" "$PT/shared"
pf_tree() {   # <dir> <preflight.sh> <psh-differ body>: a stub repository around a preflight.sh
    local d=$1
    mkdir -p "$d/docs/testing/psh_differ/build" "$d/docs/testing/aci_vmstate"
    cp "$2" "$d/docs/testing/preflight.sh"
    printf 'all:\n\t@true\n' > "$d/docs/testing/psh_differ/Makefile"
    printf 'run:\n\t@echo "guest state reproduced"\n' > "$d/docs/testing/aci_vmstate/Makefile"
    printf '#!/usr/bin/env bash\n%s\n' "$3" > "$d/docs/testing/psh_differ/build/psh-differ"
    chmod +x "$d/docs/testing/psh_differ/build/psh-differ"
    printf 'SCAN_ROOTS = ["hw/xbox"]\n' > "$d/docs/testing/nv2a_index.py"
    : > "$d/docs/testing/check_territory.py"
    printf 'print("coverage ok: stub")\n' > "$d/docs/testing/check_coverage.py"
}
WAIT='for i in $(seq 100); do [ -e "$1" ] && break; sleep 0.1; done'
pf_pair() {   # <preflight.sh> -> A's and B's output in $PT/a.out, $PT/b.out
    rm -rf "$PT/a" "$PT/b" "$PT/sync"/* "$PT/tmp"/* "$PT/shared"/*
    pf_tree "$PT/a" "$1" "echo 'TOTAL A'; touch '$PT/sync/a-wrote'; set -- '$PT/sync/b-started'; $WAIT"
    pf_tree "$PT/b" "$1" "touch '$PT/sync/b-started'; set -- '$PT/sync/a-finished'; $WAIT; echo 'TOTAL B'"
    ( export TMPDIR="$PT/tmp" TESTS="$PT/tests" SUPPORT=""
      bash "$PT/a/docs/testing/preflight.sh" > "$PT/a.out" 2>&1 & a=$!
      set -- "$PT/sync/a-wrote"; eval "$WAIT"
      bash "$PT/b/docs/testing/preflight.sh" > "$PT/b.out" 2>&1 & b=$!
      wait "$a"; touch "$PT/sync/a-finished"
      wait "$b" )
}

pf_pair "$TESTING/preflight.sh"
check "run A reads its own report (TOTAL A)" grep -q '^  TOTAL A$' "$PT/a.out"
check "  and passes" grep -q '^preflight passed' "$PT/a.out"
check "run B reads its own report (TOTAL B)" grep -q '^  TOTAL B$' "$PT/b.out"
check "  and passes" grep -q '^preflight passed' "$PT/b.out"
check "  and neither reads the other's" bash -c '! grep -q "TOTAL B" "$1" && ! grep -q "TOTAL A" "$2"' -- "$PT/a.out" "$PT/b.out"
check "a passing run removes its log directory" bash -c '[ -z "$(ls -A "$1")" ]' -- "$PT/tmp"

# A failing run keeps its directory and names it, so the path it prints exists.
rm -rf "$PT/f" "$PT/tmp"/*
pf_tree "$PT/f" "$TESTING/preflight.sh" "echo 'no report here'"
( export TMPDIR="$PT/tmp" TESTS="$PT/tests" SUPPORT=""; bash "$PT/f/docs/testing/preflight.sh" > "$PT/f.out" 2>&1 )
fdir=$(sed -n "s/^  this run's logs: //p" "$PT/f.out")
check "a failing run says 'produced no report'" grep -q '^  produced no report' "$PT/f.out"
check "  and names its log directory" test -n "$fdir"
check "  which still holds the report it read" grep -q 'no report here' "$fdir/differ.log"

# The mutant: one fixed directory for every run, the old /tmp/preflight-*.
python3 - "$TESTING/preflight.sh" "$PT/mut-preflight.sh" "$PT/shared" <<'PY'
import sys
s = open(sys.argv[1]).read()
old = 'PF_TMP=$(mktemp -d "${TMPDIR:-/tmp}/preflight.XXXXXX")'
assert s.count(old) == 1, "preflight.sh no longer makes PF_TMP with mktemp"
open(sys.argv[2], "w").write(s.replace(old, 'PF_TMP="%s"' % sys.argv[3]).replace('rm -rf "$PF_TMP"', 'true'))
PY
pf_pair "$PT/mut-preflight.sh"
check "MUTANT (one shared log directory): run A loses its report" grep -q '^  produced no report' "$PT/a.out"
check "  and fails" grep -q '^preflight FAILED' "$PT/a.out"

# #367's refusal read `baseline basic/gl does not generate` out of the shared
# differ.err. A run that passes alone must not fail on ANOTHER tree's stderr:
# B's psh-differ prints that line, and A must stay green. A opens its files
# first and B truncates after, so B's line lands at the start of a shared file.
pf_errpair() {   # <preflight.sh>
    rm -rf "$PT/a" "$PT/b" "$PT/sync"/* "$PT/tmp"/* "$PT/shared"/*
    pf_tree "$PT/a" "$1" "echo 'TOTAL A'; touch '$PT/sync/a-wrote'; set -- '$PT/sync/b-wrote'; $WAIT"
    pf_tree "$PT/b" "$1" "echo 'psh-differ: baseline basic/gl does not generate.' >&2; touch '$PT/sync/b-wrote'; set -- '$PT/sync/a-finished'; $WAIT"
    ( export TMPDIR="$PT/tmp" TESTS="$PT/tests" SUPPORT=""
      bash "$PT/a/docs/testing/preflight.sh" > "$PT/a.out" 2>&1 & a=$!
      set -- "$PT/sync/a-wrote"; eval "$WAIT"
      bash "$PT/b/docs/testing/preflight.sh" > "$PT/b.out" 2>&1 & b=$!
      wait "$a"; touch "$PT/sync/a-finished"
      wait "$b" )
}
pf_errpair "$TESTING/preflight.sh"
check "another tree's 'does not generate' does not fail run A" grep -q '^preflight passed' "$PT/a.out"
check "  and run B, whose line it is, fails on it" grep -q 'basic/gl does not generate' "$PT/b.out"
pf_errpair "$PT/mut-preflight.sh"
check "MUTANT: run A fails on B's stderr, as #367 did" grep -q 'basic/gl does not generate' "$PT/a.out"
