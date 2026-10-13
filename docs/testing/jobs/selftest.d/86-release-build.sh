# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check, and the live prediction's
# fixtures. Not executable, no shebang, no exit -- `fail` is shared and is
# the run's verdict.
#
# release_build.sh: a versioned release builds only from a clean tagged
# commit, and is refused unless the APK is signed, says exactly that version,
# and defaults Debug Capture off (#433). Its own fixtures live in
# release_build_selftest.sh (stub gradlew and aapt2, no SDK needed).

echo "== release_build.sh: refusals and the one success path"
RB_OUT=$(TMPDIR="$T" bash "$TESTING/release_build_selftest.sh" 2>&1); RB_RC=$?
check "  release_build_selftest.sh passes every check" [ "$RB_RC" -eq 0 ]
[ "$RB_RC" -eq 0 ] || grep -v '^ok - ' <<<"$RB_OUT" | sed 's/^/    /' | head -20
