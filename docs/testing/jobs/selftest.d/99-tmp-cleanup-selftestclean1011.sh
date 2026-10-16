# Sourced by ../selftest.sh with the harness already built: $T, $HERE,
# $REPO, ok/bad/check. Not executable, no shebang, no exit.
#
# #433: selftest.sh made its own fake host with mktemp and never removed it.
# Every run -- lane, fold, CI shard -- left one behind: 256 of them in /tmp
# since the 10-09 boot, 1.58M files, 27.7 GB, about 50 new a day. This proves
# the fix (selftest.sh's T_OWNED block, just above the final echo): a passing
# run that made its own dir removes it; a failing run, or one given
# SELFTEST_DIR, keeps it.
#
# THE GUARD. This fragment runs a REAL nested selftest.sh (not a stub) with
# SELFTEST_ONLY narrowed to one fragment, to keep it to seconds. The one
# fragment it narrows to is ITSELF: inside the nested run, SELFTEST_ONLY
# selects this very file, and SELFTEST_TMPCLEANUP_PROBE (set only by the
# nested_run helper below, never by a real run) tells it to act as a tiny
# controllable pass/fail probe instead of recursing into this meta-test. A
# real fragment's content can't be flipped pass/fail from outside without
# touching production scripts; this one owns itself, so it can.
if [ -n "${SELFTEST_TMPCLEANUP_PROBE:-}" ]; then
    if [ "$SELFTEST_TMPCLEANUP_PROBE" = fail ]; then
        bad "tmp-cleanup probe: forced fail (nested run)"
    else
        ok "tmp-cleanup probe: forced pass (nested run)"
    fi
else

echo "== tmp-cleanup: a passing selftest run removes its own fake host (#433)"
TC="$T/tmpcleanup"; rm -rf "$TC"; mkdir -p "$TC"

tc_run() {   # <selftest.sh to run> <TMPDIR> <pass|fail> [SELFTEST_DIR] -> output in $TC/out, $? on stdout
    local sut=$1 tmp=$2 probe=$3 dir=${4:-}
    if [ -n "$dir" ]; then
        env -u SELFTEST_SHARD SELFTEST_TMPCLEANUP_PROBE="$probe" \
            SELFTEST_ONLY=99-tmp-cleanup-selftestclean1011 TMPDIR="$tmp" SELFTEST_DIR="$dir" \
            bash "$sut" > "$TC/out" 2>&1
    else
        env -u SELFTEST_SHARD -u SELFTEST_DIR SELFTEST_TMPCLEANUP_PROBE="$probe" \
            SELFTEST_ONLY=99-tmp-cleanup-selftestclean1011 TMPDIR="$tmp" \
            bash "$sut" > "$TC/out" 2>&1
    fi
    echo $?
}
tc_left() { find "$1" -maxdepth 1 -name 'hakux-selftest.*' 2>/dev/null; }  # <dir> -> its hakux-selftest.* dirs, one per line

# (a) a passing run leaves no hakux-selftest.* under its own TMPDIR.
rm -rf "$TC/a"; mkdir -p "$TC/a"
rc=$(tc_run "$HERE/selftest.sh" "$TC/a" pass)
[ "$rc" = 0 ] && grep -q 'removed' "$TC/out" \
    && ok "(a) passing run exits 0 and says it removed its dir" \
    || bad "(a) passing run: rc=$rc, out: $(tail -n1 "$TC/out")"
left=$(tc_left "$TC/a")
[ -z "$left" ] && ok "(a) passing run leaves no hakux-selftest.* under its TMPDIR" \
    || bad "(a) passing run left: $left"

# (b) a failing run keeps exactly one hakux-selftest.* dir.
rm -rf "$TC/b"; mkdir -p "$TC/b"
rc=$(tc_run "$HERE/selftest.sh" "$TC/b" fail)
[ "$rc" != 0 ] && ok "(b) failing run exits non-zero" || bad "(b) failing run exited 0"
left=$(tc_left "$TC/b")
[ "$(printf '%s\n' "$left" | grep -c .)" = 1 ] && ok "(b) failing run keeps exactly one hakux-selftest.* dir" \
    || bad "(b) failing run left: [$left]"

# (c) a run given SELFTEST_DIR keeps it, pass or fail -- it is the caller's.
rm -rf "$TC/c"; mkdir -p "$TC/c/mine" "$TC/c/tmp"
rc=$(tc_run "$HERE/selftest.sh" "$TC/c/tmp" pass "$TC/c/mine")
[ "$rc" = 0 ] && [ -d "$TC/c/mine" ] && ok "(c) a passing run never removes a caller-given SELFTEST_DIR" \
    || bad "(c) SELFTEST_DIR gone after a passing run (rc=$rc)"
[ -z "$(tc_left "$TC/c/tmp")" ] && ok "  and makes no mktemp dir of its own" \
    || bad "  and also made its own: $(tc_left "$TC/c/tmp")"

# -------------------------------------------------------- the mutant copies
# selftest.sh resolves $HERE/$TESTING/$REPO from its own path (no override),
# so a mutant must keep the same docs/testing/jobs/ depth to resolve the same
# way. Copy the whole jobs/ dir (selftest.sh + selftest.d/, ~3 MB) under a
# scratch root, mutate only the copy's selftest.sh, run the copy.
MR="$TC/mutant/docs/testing/jobs"; rm -rf "$TC/mutant"; mkdir -p "$MR"
cp -a "$HERE/." "$MR/"

tc_mutant_noremove() {   # revert to the pre-#433 ending: never remove $T
    python3 - "$MR/selftest.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = '''if [ "$fail" -eq 0 ] && [ "$T_OWNED" -eq 1 ]; then
    rm -rf "$T"
    echo "selftest: $pass passed, $fail failed, $scope (fake host removed, was $T)"
else
    echo "selftest: $pass passed, $fail failed, $scope (fake host in $T)"
fi'''
new = 'echo "selftest: $pass passed, $fail failed, $scope (fake host in $T)"'
assert s.count(old) == 1, "selftest.sh's ending changed -- update this mutant"
open(p, "w").write(s.replace(old, new, 1))
PY
}
tc_mutant_removefail() {   # drop the fail check: removes on failure too
    python3 - "$MR/selftest.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = 'if [ "$fail" -eq 0 ] && [ "$T_OWNED" -eq 1 ]; then'
new = 'if [ "$T_OWNED" -eq 1 ]; then'
assert s.count(old) == 1, "selftest.sh's ending changed -- update this mutant"
open(p, "w").write(s.replace(old, new, 1))
PY
}

tc_mutant_noremove
rm -rf "$TC/ma"; mkdir -p "$TC/ma"
tc_run "$MR/selftest.sh" "$TC/ma" pass > /dev/null
left=$(tc_left "$TC/ma")
[ -n "$left" ] && ok "MUTANT (never remove, the pre-#433 ending): check (a) catches it -- left $left" \
    || bad "MUTANT (never remove) SURVIVED check (a)"

cp -a "$HERE/." "$MR/"   # reset the copy, then apply the other mutant
tc_mutant_removefail
rm -rf "$TC/mb"; mkdir -p "$TC/mb"
tc_run "$MR/selftest.sh" "$TC/mb" fail > /dev/null
left=$(tc_left "$TC/mb")
[ -z "$left" ] && ok "MUTANT (removes on failure too): check (b) catches it -- nothing left" \
    || bad "MUTANT (removes on failure too) SURVIVED check (b)"

rm -rf "$TC"
fi
