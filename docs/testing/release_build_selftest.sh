#!/usr/bin/env bash
#
# Fixtures for release_build.sh's refusal logic (#433). No Gradle, no
# Android SDK, no network: `./gradlew` and aapt2 are both stubs, so this
# runs in well under a second anywhere bash and git exist.
#
# WHY THIS EXISTS. release_build.sh is the one build step allowed to ship a
# versioned release, and its whole job is refusing to run in every situation
# that isn't exactly "a clean checkout at a reviewed tag, verified against
# the APK it actually produced". That is five separate refusals (bad version
# string, dirty tree, no such tag, HEAD not at the tag, and the two
# post-build aapt2 checks) plus the one path where it must NOT refuse. A
# claim like "it refuses on a dirty tree" in a commit message is not a
# check; this file is the check.
#
# Each case is run in its own throwaway git repo (never this worktree) and
# asserts on the words in release_build.sh's own message, not just its exit
# code -- the script exits 1 for three different refusals, so the code alone
# can't tell which one fired.
#
# Usage:
#   docs/testing/release_build_selftest.sh
#
# Environment:
#   SELFTEST_TMP  scratch directory to use instead of `mktemp -d`. Emptied
#                 on entry, so pass a directory you own.
#   SCRIPT        the script under test, for pointing these fixtures at a
#                 mutant copy.
#
# exit 0 all fixtures pass, 1 a fixture failed.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="${SCRIPT:-$HERE/release_build.sh}"
[ -f "$SCRIPT" ] || { echo "selftest: no script at $SCRIPT" >&2; exit 1; }

if [ -n "${SELFTEST_TMP:-}" ]; then
    T="$SELFTEST_TMP"
    rm -rf "$T"; mkdir -p "$T" || exit 1
else
    T=$(mktemp -d) || exit 1
    trap 'rm -rf "$T"' EXIT
fi
T=$(cd "$T" && pwd) || exit 1

FAIL=0
check() {   # <description> <command...>
    local desc=$1; shift
    if "$@"; then
        echo "ok - $desc"
    else
        echo "FAIL - $desc"
        FAIL=1
    fi
}

# A fresh repo whose docs/testing/release_build.sh is the file under test,
# committed -- so an UNcommitted copy of the script itself never reads as
# the "dirty tree" the refusal is about. android/gradlew is a stub that
# records whether it ran and, when $GRADLE_OK is set in its environment,
# writes a fake APK (unsigned when $APK_UNSIGNED is set); aapt2 is a stub that prints canned badging/
# resources output driven by files the test writes into $T/aapt2-answers.
new_repo() {   # -> prints the repo path
    local r="$T/repo-$$-$RANDOM"
    mkdir -p "$r/docs/testing" "$r/android"
    cp "$SCRIPT" "$r/docs/testing/release_build.sh"
    chmod +x "$r/docs/testing/release_build.sh"
    # The gradlew stub below writes its fake APK under android/app/build/,
    # same as the real one -- ignored, so a build the "clean + tagged" case
    # runs does not leave the NEXT case's dirty-tree check seeing it.
    echo "app/build/" > "$r/android/.gitignore"
    cat > "$r/android/gradlew" <<'STUB'
#!/usr/bin/env bash
echo "ran" > "$STUB_RAN"
[ -n "${GRADLE_OK:-}" ] || exit 1
mkdir -p app/build/outputs/apk/release
if [ -n "${APK_UNSIGNED:-}" ]; then : > app/build/outputs/apk/release/app-release-unsigned.apk
else : > app/build/outputs/apk/release/app-release.apk; fi
STUB
    chmod +x "$r/android/gradlew"
    git -C "$r" init -q
    git -C "$r" config user.email selftest@example.com
    git -C "$r" config user.name selftest
    git -C "$r" add -A
    git -C "$r" commit -qm init -q
    printf '%s' "$r"
}

# aapt2 stub: build-tools/36.1.0/aapt2 under a per-case SDK root, so
# ANDROID_SDK_ROOT points this at canned answers instead of a real toolchain.
mk_aapt2() {   # <sdk_root> <version-to-report> <default-to-report>
    local sdk=$1 ver=$2 def=$3 dir="$1/build-tools/36.1.0"
    mkdir -p "$dir"
    cat > "$dir/aapt2" <<STUB
#!/usr/bin/env bash
case "\$2" in
    badging)   echo "package: name='x' versionCode='1' versionName='$ver' platformBuildVersionName='16'" ;;
    resources) printf '    resource 0x7f0a0000 bool/debug_tools_default\n      () $def\n' ;;
esac
STUB
    chmod +x "$dir/aapt2"
}

echo "== release_build.sh: usage and version-format refusals"
out=$(bash "$SCRIPT" 2>&1); rc=$?
check "no argument: exit 2" [ "$rc" -eq 2 ]
check "no argument: usage message" grep -q usage <<<"$out"
out=$(bash "$SCRIPT" not-a-version 2>&1); rc=$?
check "malformed version: exit 2" [ "$rc" -eq 2 ]
check "malformed version: message names it" grep -q "doesn't look like a version" <<<"$out"

echo "== release_build.sh: refuses on a dirty tree"
R=$(new_repo)
echo scratch > "$R/untracked-file"
out=$(STUB_RAN="$T/ran-dirty" GRADLE_OK=1 bash "$R/docs/testing/release_build.sh" 1.2.3 2>&1); rc=$?
check "dirty tree: exit 1" [ "$rc" -eq 1 ]
check "dirty tree: message says uncommitted" grep -q "uncommitted change" <<<"$out"
check "dirty tree: never reached gradlew" bash -c '[ ! -e "$1" ]' _ "$T/ran-dirty"
rm -f "$R/untracked-file"

echo "== release_build.sh: refuses when the tag doesn't exist"
out=$(STUB_RAN="$T/ran-notag" GRADLE_OK=1 bash "$R/docs/testing/release_build.sh" 1.2.3 2>&1); rc=$?
check "no such tag: exit 1" [ "$rc" -eq 1 ]
check "no such tag: message says no tag" grep -q "no tag" <<<"$out"
check "no such tag: never reached gradlew" bash -c '[ ! -e "$1" ]' _ "$T/ran-notag"

echo "== release_build.sh: refuses when HEAD is not the tagged commit"
git -C "$R" tag v1.2.3
git -C "$R" commit -q --allow-empty -m "a commit after the tag"
out=$(STUB_RAN="$T/ran-mismatch" GRADLE_OK=1 bash "$R/docs/testing/release_build.sh" 1.2.3 2>&1); rc=$?
check "tag mismatch: exit 1" [ "$rc" -eq 1 ]
check "tag mismatch: message says HEAD is not the tag" grep -q "is not v1.2.3" <<<"$out"
check "tag mismatch: never reached gradlew" bash -c '[ ! -e "$1" ]' _ "$T/ran-mismatch"

echo "== release_build.sh: a clean checkout at the tag reaches the build"
git -C "$R" checkout -q v1.2.3
SDK="$T/sdk-good"; mk_aapt2 "$SDK" 1.2.3 false
out=$(STUB_RAN="$T/ran-good" GRADLE_OK=1 ANDROID_SDK_ROOT="$SDK" bash "$R/docs/testing/release_build.sh" 1.2.3 2>&1); rc=$?
check "clean + tagged: reached gradlew" [ -e "$T/ran-good" ]
check "clean + tagged: exit 0" [ "$rc" -eq 0 ]
check "clean + tagged: prints the apk path" grep -q "app-release.apk" <<<"$out"

echo "== release_build.sh: refuses when the built APK's versionName disagrees"
SDK="$T/sdk-wrongver"; mk_aapt2 "$SDK" 9.9.9 false
out=$(STUB_RAN="$T/ran-wrongver" GRADLE_OK=1 ANDROID_SDK_ROOT="$SDK" bash "$R/docs/testing/release_build.sh" 1.2.3 2>&1); rc=$?
check "wrong versionName: exit 6" [ "$rc" -eq 6 ]
check "wrong versionName: message names it" grep -q "versionName" <<<"$out"

echo "== release_build.sh: refuses when debug_tools_default is not false"
SDK="$T/sdk-wrongdefault"; mk_aapt2 "$SDK" 1.2.3 true
out=$(STUB_RAN="$T/ran-wrongdefault" GRADLE_OK=1 ANDROID_SDK_ROOT="$SDK" bash "$R/docs/testing/release_build.sh" 1.2.3 2>&1); rc=$?
check "debug_tools_default=true in the APK: exit 7" [ "$rc" -eq 7 ]
check "debug_tools_default=true in the APK: message names it" grep -q "debug_tools_default" <<<"$out"

echo "== release_build.sh: a Gradle failure is reported, not swallowed"
out=$(STUB_RAN="$T/ran-buildfail" bash "$R/docs/testing/release_build.sh" 1.2.3 2>&1); rc=$?
check "gradle failure: exit 3" [ "$rc" -eq 3 ]
check "gradle failure: ran gradlew" [ -e "$T/ran-buildfail" ]
check "gradle failure: message says build failed" grep -q "build failed" <<<"$out"

echo "== release_build.sh: refuses an unsigned APK"
R2=$(new_repo); git -C "$R2" tag v1.2.3
SDK="$T/sdk-unsigned"; mk_aapt2 "$SDK" 1.2.3 false
out=$(STUB_RAN="$T/ran-unsigned" GRADLE_OK=1 APK_UNSIGNED=1 ANDROID_SDK_ROOT="$SDK" bash "$R2/docs/testing/release_build.sh" 1.2.3 2>&1); rc=$?
check "unsigned apk: exit 8" [ "$rc" -eq 8 ]
check "unsigned apk: message says unsigned" grep -q "is unsigned" <<<"$out"

[ "$FAIL" -eq 0 ] && echo "release_build_selftest: all checks passed" || echo "release_build_selftest: FAILURES ABOVE"
exit "$FAIL"
